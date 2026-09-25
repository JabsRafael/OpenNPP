"""
Componente SEGURANCA PASSIVA (PXS) + CONTENCAO — Defense-in-Depth niveis 3 e 4.

Sistemas passivos do AP1000 modelados como camadas independentes de mitigacao,
atuadas pelo ESFAS (ver protection.py) ou manualmente:

  - CMT (Core Makeup Tanks, 2)   : injecao de agua borada por gravidade.
  - Acumuladores                 : injecao rapida quando o primario despressuriza.
  - PRHR HX                      : remove calor residual do primario para o IRWST.
  - ADS (4 estagios)             : despressuriza o primario de forma controlada
                                   (sequencia AP1000 disparada pelo nivel da CMT).
  - IRWST                        : reservatorio de agua da contencao.
  - Contencao                    : barreira final; pressao/temp/radiacao.

Licao DID: cada sistema e' uma barreira. Vencer o controle (nivel 2) NAO causa
dano se as salvaguardas (nivel 3) atuam. Por isso os playbooks de ataque miram
tambem em BLOQUEAR/enganar as salvaguardas (cmd_block_safety, injecao de sensor).
"""

from .. import config as C
from ..water import tsat


class PassiveSafety:
    def __init__(self):
        self.reset()

    def reset(self):
        self.cmt1 = 100.0                  # % (os 2 tanques drenam juntos)
        self.cmt2 = 100.0
        self.accum_water = 1.0             # fracao de agua restante nos acumuladores
        self.accum_press = C.ACCUM_PRESS_NOMINAL
        self.prhr_flow = 0.0
        self.irwst = C.IRWST_LEVEL_NOMINAL
        self.ads_stage = 0
        self._ads_timer = 0.0
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
        (mutado por ADS/injecao). Escreve bus.Q_prhr, bus.si_flow, bus.Q_ads,
        bus.ads_mass_flow.
        """
        blocked = act["blocked"]
        s = act["s_signal"] and not blocked
        P = primary.przr_press
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
        self.cmt_injecting = want_cmt and self.cmt1 > 0.0
        if self.cmt_injecting:
            dlev = C.CMT_FLOW / C.CMT_MASS * 100.0 * dt
            self.cmt1 = self.cmt2 = max(0.0, self.cmt1 - dlev)
            self.si_flow += C.CMT_FLOW

        # ---- Acumuladores : N2 empurra a agua quando o RCS despressuriza ---
        used = 1.0 - self.accum_water
        self.accum_press = C.ACCUM_PRESS_NOMINAL * C.ACCUM_GAS_FRAC / (
            C.ACCUM_GAS_FRAC + (1.0 - C.ACCUM_GAS_FRAC) * used)
        dp = self.accum_press - P
        acc_flow = 0.0
        if dp > 0.5 and self.accum_water > 0.0 and act.get("accum_armed", True) and not blocked:
            acc_flow = C.ACCUM_MAX_FLOW * min(1.0, dp / 10.0)
            self.accum_water = max(0.0, self.accum_water - acc_flow / C.ACCUM_MASS * dt)
            self.si_flow += acc_flow
        self.accum_injecting = acc_flow > 0.0

        # ---- ADS : despressurizacao automatica (4 estagios em sequencia) ---
        want_ads = (act["ads"] or (s and self.cmt1 < C.ADS_CMT_LOW)) and not blocked
        self.ads_actuated = want_ads
        if want_ads:
            self._ads_timer += dt
            if self.ads_stage < 3:
                nxt = self.ads_stage
                if self._ads_timer >= C.ADS_STAGE_DELAY[nxt]:
                    self.ads_stage += 1
                    self._ads_timer = 0.0
            elif self.ads_stage == 3 and self._ads_timer >= C.ADS_STAGE_DELAY[3] and \
                    (act["ads"] or self.cmt1 < C.ADS_CMT_LOWLOW):
                self.ads_stage = 4
        elif blocked:
            self.ads_stage, self._ads_timer = 0, 0.0
        stage = self.ads_stage
        Q_ads = ads_mass = 0.0
        if stage > 0:
            # vapor ventilado: vazao critica ~ pressao; so' enquanto o RCS
            # estiver acima da saturacao da contencao
            t_floor = tsat(self.cont_press) + 5.0
            if primary.T_coolant > t_floor:
                cap = C.ADS_STAGE_MW[stage - 1] * max(0.15, P / C.PRZR_PRESS_NOMINAL)
                excess = (primary.T_coolant - t_floor) * C.C_COOLANT / 20.0   # nao sub-resfria
                Q_ads = min(cap, excess + bus.P_th)
                ads_mass = Q_ads / C.STEAM_LATENT
            if not primary.saturated:                        # vapor do PZR -> cai direto
                primary.przr_press = max(1.0, P - C.ADS_DEPRESS_RATE * stage * dt)
        bus.Q_ads = Q_ads
        bus.ads_mass_flow = ads_mass

        # ---- IRWST : injecao por gravidade (ADS-4 aberto, RCS despressurizado)
        if stage >= 4 and P < C.IRWST_INJECT_PRESS and self.irwst > 0.0 and not blocked:
            flow = C.IRWST_INJECT_FLOW * (1.0 - P / C.IRWST_INJECT_PRESS * 0.5)
            self.si_flow += flow
            self.irwst = max(0.0, self.irwst - flow / C.IRWST_MASS * 100.0 * dt)

        # agua borada injetada dilui/borifica o RCS (mistura por massa)
        if self.si_flow > 0.0:
            frac = min(1.0, self.si_flow * dt / C.RCS_MASS)
            primary.boron += (C.CMT_BORON - primary.boron) * frac
        bus.si_flow = self.si_flow

        # ---- CONTENCAO -----------------------------------------------------
        steam_mw = bus.Q_break + Q_ads                       # energia liberada na contencao
        self.cont_press += C.CONT_BAR_PER_MJ * steam_mw * dt
        self.cont_press -= C.PCS_RATE * (self.cont_press - C.CONT_PRESS_NOMINAL) * dt
        core_damage = bus.T_fuel > 1200.0
        if core_damage:
            self.cont_press += C.CONT_VOLUME_FACTOR * dt
            self.cont_rad += (bus.T_fuel - 1200.0) * 0.01 * dt
            self.cont_temp += 0.5 * dt
        else:
            self.cont_rad += (0.1 - self.cont_rad) * 0.02 * dt
            t_target = 40.0 + 25.0 * (self.cont_press - C.CONT_PRESS_NOMINAL)
            self.cont_temp += (t_target - self.cont_temp) * 0.02 * dt
        self.cont_press = max(0.5, min(10.0, self.cont_press))
        self.cont_rad = max(0.0, min(2000.0, self.cont_rad))
        self.cont_temp = max(20.0, min(200.0, self.cont_temp))
