"""
Componente SEGURANCA PASSIVA (PXS) + CONTENCAO — Defense-in-Depth niveis 3 e 4.

Sistemas passivos do AP1000 modelados como camadas independentes de mitigacao,
atuadas pelo ESFAS (ver protection.py) ou manualmente:

  - CMT (Core Makeup Tanks, 2)   : injecao de agua borada por gravidade.
  - Acumuladores                 : injecao rapida quando o primario despressuriza.
  - PRHR HX                      : remove calor residual do primario para o IRWST.
  - ADS (4 estagios)             : despressuriza o primario de forma controlada.
  - IRWST                        : reservatorio de agua da contencao.
  - Contencao                    : barreira final; pressao/temp/radiacao.

Licao DID: cada sistema e' uma barreira. Vencer o controle (nivel 2) NAO causa
dano se as salvaguardas (nivel 3) atuam. Por isso os playbooks de ataque miram
tambem em BLOQUEAR/enganar as salvaguardas (cmd_block_safety, injecao de sensor).
"""

from .. import config as C


class PassiveSafety:
    def __init__(self):
        self.cmt1 = 100.0
        self.cmt2 = 100.0
        self.accum_press = C.ACCUM_PRESS_NOMINAL
        self.prhr_flow = 0.0
        self.irwst = C.IRWST_LEVEL_NOMINAL
        self.ads_stage = 0
        self.si_flow = 0.0
        # status
        self.cmt_injecting = False
        self.accum_injecting = False
        self.prhr_actuated = False
        self.ads_actuated = False
        # contencao
        self.cont_press = C.CONT_PRESS_NOMINAL
        self.cont_rad = 0.1
        self.cont_temp = 40.0

    def step(self, bus, dt, act, primary):
        """
        act = {s_signal, prhr, ads, si, blocked} (bool). primary = PrimarySystem
        (mutado por ADS/injecao). Escreve bus.Q_prhr, bus.si_flow.
        """
        blocked = act["blocked"]
        s = act["s_signal"] and not blocked
        self.si_flow = 0.0

        # ---- PRHR : remocao passiva de calor residual ----------------------
        want_prhr = (act["prhr"] or s) and not blocked
        self.prhr_actuated = want_prhr
        target = 100.0 if want_prhr else 0.0
        self.prhr_flow += (target - self.prhr_flow) * min(1.0, dt / 8.0)
        self.prhr_flow = max(0.0, min(100.0, self.prhr_flow))
        # remocao proporcional ao superaquecimento -> auto-limitante (equilibrio
        # perto do calor de decaimento; evita resfriamento excessivo)
        overheat = max(0.0, primary.T_coolant - C.PRHR_SINK_TEMP)
        bus.Q_prhr = C.PRHR_K * (self.prhr_flow / 100.0) * overheat

        # ---- CMT : injecao borada por gravidade ----------------------------
        want_cmt = (act["si"] or s) and not blocked
        self.cmt_injecting = want_cmt and (self.cmt1 > 0 or self.cmt2 > 0)
        if self.cmt_injecting:
            self.cmt1 = max(0.0, self.cmt1 - C.CMT_INJECT_RATE * dt)
            self.cmt2 = max(0.0, self.cmt2 - C.CMT_INJECT_RATE * dt)
            self.si_flow += 60.0
            primary.boron = min(C.CMT_BORON, primary.boron + 3.0 * dt)

        # ---- Acumuladores : injecao rapida a baixa pressao -----------------
        self.accum_injecting = (primary.przr_press < C.ACCUM_INJECT_PRESS
                                and self.accum_press > 5.0 and not blocked)
        if self.accum_injecting:
            self.accum_press = max(0.0, self.accum_press - 4.0 * dt)
            self.si_flow += 300.0
            primary.boron = min(C.CMT_BORON, primary.boron + 8.0 * dt)

        # ---- ADS : despressurizacao automatica (4 estagios) ----------------
        want_ads = (act["ads"] or (s and (self.cmt1 < 20.0))) and not blocked
        self.ads_actuated = want_ads
        stage = 0
        if want_ads:
            for i, p_set in enumerate(C.ADS_STAGE_PRESS):
                if primary.przr_press <= p_set:
                    stage = i + 1
            if stage > 0:
                primary.przr_press = max(1.0, primary.przr_press - C.ADS_DEPRESS_RATE * stage * dt)
                self.irwst = max(0.0, self.irwst - 0.05 * stage * dt)
        self.ads_stage = stage

        # inventario reposto reflete no bus (resfria/reenche o primario)
        bus.si_flow = self.si_flow

        # ---- CONTENCAO -----------------------------------------------------
        core_damage = bus.T_fuel > 1200.0
        if core_damage:
            self.cont_press += C.CONT_VOLUME_FACTOR * dt
            self.cont_rad += (bus.T_fuel - 1200.0) * 0.01 * dt
            self.cont_temp += 0.5 * dt
        else:
            self.cont_press += (C.CONT_PRESS_NOMINAL - self.cont_press) * 0.05 * dt
            self.cont_rad += (0.1 - self.cont_rad) * 0.02 * dt
            self.cont_temp += (40.0 - self.cont_temp) * 0.02 * dt
        # descarga de ADS/alivio tambem pressuriza a contencao
        if self.ads_stage > 0:
            self.cont_press += 0.01 * self.ads_stage * dt
        self.cont_press = max(0.5, min(10.0, self.cont_press))
        self.cont_rad = max(0.0, min(2000.0, self.cont_rad))
        self.cont_temp = max(20.0, min(200.0, self.cont_temp))
