"""
Componente PRIMARIO — Reactor Coolant System (RCS).

Modela o refrigerante primario como no concentrado (Tavg), as 4 bombas de
refrigerante (RCPs, 2 por loop) com inercia/coastdown, o calculo de Thot/Tcold
a partir da potencia e vazao, e o pressurizador (pressao e nivel).

Balanco de MASSA (kg): o loop fica cheio enquanto o pressurizador tem agua; uma
perda (LOCA, ADS) esvazia primeiro o PZR e so' depois o loop (vazio -> nucleo
descobre). A injecao enche o loop primeiro e depois o PZR. O CVS (carga e
descarga) mantem o nivel do PZR no programa e compensa vazamentos pequenos.

Pressao:
  * Com bolha no PZR: varia com o nivel (compressao/expansao do vapor),
    aquecedores (lentos) e spray (rapido), alivio (PORV).
  * Nunca abaixo da saturacao do ramo quente (a agua ferveria — "flashing").
  * PZR vazio (sistema saturado, LOCA): pressao = saturacao do ramo quente;
    so' cai se a energia sair (ruptura, ADS, geradores de vapor, PRHR).

Bus:
  le   -> Q_core (entra), Q_sg_total + Q_prhr + Q_ads (saem), P_th, si_flow,
          ads_mass_flow
  escreve -> T_coolant, T_hot, T_cold, core_dt, flow_frac, boron, cooling_factor
"""

from math import sqrt

from .. import config as C
from ..water import psat


def level_program(T_avg):
    """Programa de nivel do PZR: 25% sem carga -> 55% a Tavg nominal."""
    f = (T_avg - C.T_NOLOAD) / (C.COOLANT_TEMP_REF - C.T_NOLOAD)
    return C.PRZR_LEVEL_NOLOAD + (C.PRZR_LEVEL_NOMINAL - C.PRZR_LEVEL_NOLOAD) * max(0.0, min(1.0, f))


class PrimarySystem:
    def __init__(self):
        self.T_coolant = C.COOLANT_TEMP_REF
        self.rcp_running = [True, True, True, True]   # 4 RCPs
        self.rcp_speed = 100.0                        # demanda de rotacao comum (%)
        self.flow = 100.0                             # vazao agregada (%)
        self.boron = C.BORON_REF
        # pressurizador
        self.przr_press = C.PRZR_PRESS_NOMINAL
        self.przr_level = C.PRZR_LEVEL_NOMINAL
        self.przr_relief_open = False
        self.inventory = 100.0        # % de massa do loop (LOCA drena)
        self.break_flow = 0.0         # kg/s saindo pela ruptura
        self.cvs_flow = 0.0           # kg/s de carga liquida do CVS (+ carrega, - descarrega)
        self.heater_on = False        # estado REAL dos aquecedores / spray
        self.spray_on = False
        self.cvs_manual = None        # kg/s pedidos pelo operador (None = AUTO)
        self.level_program = C.PRZR_LEVEL_NOMINAL
        self.boiloff = 0.0            # kg/s de vapor gerado no nucleo saindo do RCS aberto
        self.loca_open = False

    def running_count(self):
        return sum(1 for r in self.rcp_running if r)

    @property
    def saturated(self):
        """PZR vazio: o RCS vira um sistema bifasico saturado."""
        return self.przr_level <= 0.5

    # -------------------------------------------------------------- atuadores
    def apply_pumps(self, running_list, speed_demand):
        self.rcp_running = running_list
        self.rcp_speed = speed_demand

    def apply_boron(self, charge, dilute, dt):
        """CVS em "feed & bleed": carrega acido borico (boracao) ou agua
        desmineralizada (diluicao) -> aproximacao exponencial, como na planta."""
        if charge and not dilute:
            self.boron += C.CVS_RATE * (C.BORIC_ACID_PPM - self.boron) * dt
        elif dilute and not charge:
            self.boron -= C.CVS_RATE * self.boron * dt
        self.boron = max(0.0, min(C.BORIC_ACID_PPM, self.boron))

    def apply_loca(self, bus, dt, loca_size, cont_press=C.CONT_PRESS_NOMINAL):
        """Rompimento no primario: vazao pela ruptura ~ area x sqrt(dP). Com o
        RCS ja' na pressao da contencao, so' escoa (por gravidade) a agua acima
        do bocal da ruptura — o vaso retem o resto."""
        loca_size = max(0.0, min(1.0, loca_size))
        dp = max(0.0, self.przr_press - cont_press)
        w = C.LOCA_MAX_FLOW * loca_size * sqrt(dp / C.PRZR_PRESS_NOMINAL)
        if dp < 3.0:
            w *= max(0.0, min(1.0, (self.inventory - C.LOCA_SPILL_LEVEL) / 10.0))
        self.break_flow = w
        self.loca_open = loca_size > 0.0

    # ------------------------------------------------------ balanco de massa
    def _mass_balance(self, bus, dt, dTavg):
        # expansao termica: o loop esta' cheio, o volume extra vai para o PZR
        dlevel = C.PRZR_LEVEL_EXP * dTavg
        # CVS: segura o nivel no programa (capacidade limitada)
        self.level_program = level_program(self.T_coolant)
        if self.cvs_manual is not None:             # operador comanda carga/descarga
            self.cvs_flow = max(-C.CVS_MAX_FLOW, min(C.CVS_MAX_FLOW, self.cvs_manual))
        elif self.inventory >= 99.99:
            want = (self.level_program - self.przr_level) * C.PRZR_KG_PER_PCT / C.CVS_LEVEL_TAU
            self.cvs_flow = max(-C.CVS_MAX_FLOW, min(C.CVS_MAX_FLOW, want))
        else:
            self.cvs_flow = C.CVS_MAX_FLOW          # loop vazio: carga maxima
        net = bus.si_flow + self.cvs_flow - self.break_flow - bus.ads_mass_flow - self.boiloff  # kg/s
        dm = net * dt
        if dm < 0.0:                                # sai do PZR primeiro, depois do loop
            pzr_mass = max(0.0, self.przr_level + dlevel) * C.PRZR_KG_PER_PCT
            take = min(-dm, pzr_mass)
            dlevel -= take / C.PRZR_KG_PER_PCT
            self.inventory -= (-dm - take) / C.RCS_MASS * 100.0
        else:                                       # enche o loop primeiro, depois o PZR
            room = (100.0 - self.inventory) / 100.0 * C.RCS_MASS
            fill = min(dm, room)
            self.inventory += fill / C.RCS_MASS * 100.0
            dlevel += (dm - fill) / C.PRZR_KG_PER_PCT
        self.inventory = max(0.0, min(100.0, self.inventory))
        old = self.przr_level
        self.przr_level = max(0.0, min(100.0, self.przr_level + dlevel))
        return self.przr_level - old

    # -------------------------------------------------------------- pressao
    def _pressurizer(self, bus, dt, heater, spray, dlevel, przr_sp=None, auto=False):
        p_sat = psat(bus.T_hot)
        if self.saturated:
            # sem bolha no PZR: pressao = saturacao (bifasico)
            self.przr_press = max(C.CONT_PRESS_NOMINAL, p_sat)
            self.przr_relief_open = False
            self.heater_on = self.spray_on = False
            return
        dP = C.PRZR_PRESS_PER_LEVEL * dlevel          # compressao/expansao da bolha
        heaters_ok = self.przr_level > C.PRZR_HEATER_CUTOUT
        if auto and przr_sp is not None:
            eff = C.PRZR_CTRL_GAIN * (przr_sp - self.przr_press)
            hmax = C.PRZR_HEATER_RATE if heaters_ok else 0.0
            eff = max(-C.PRZR_SPRAY_RATE, min(hmax, eff))
            dP += eff * dt
            self.heater_on, self.spray_on = eff > 0.005, eff < -0.005
        else:
            self.heater_on = bool(heater) and heaters_ok
            self.spray_on = bool(spray)
            if self.heater_on:
                dP += C.PRZR_HEATER_RATE * dt
            if self.spray_on:
                dP -= C.PRZR_SPRAY_RATE * dt
        self.przr_press += dP
        if self.przr_press >= C.PRZR_RELIEF_SETPOINT:
            self.przr_relief_open = True
        elif self.przr_press <= C.PRZR_RELIEF_RESEAT:
            self.przr_relief_open = False
        if self.przr_relief_open:
            self.przr_press -= 2.5 * dt
        # a agua do ramo quente ferveria abaixo da saturacao ("flashing")
        self.przr_press = max(p_sat, C.CONT_PRESS_NOMINAL, min(250.0, self.przr_press))

    # -------------------------------------------------------------------- step
    def step(self, bus, dt, heater, spray, przr_sp=None, auto=False):
        # ---- vazao das 4 RCPs (fracao da nominal, com inercia) -------------
        target = (self.running_count() / C.N_RCP) * self.rcp_speed
        self.flow += (target - self.flow) * min(1.0, dt / C.RCP_COASTDOWN_TAU)
        self.flow = max(0.0, min(110.0, self.flow))
        flow_frac = self.flow / 100.0

        # ---- balanco de energia do refrigerante ----------------------------
        # entra Q_core + calor das bombas; saem GVs, PRHR, ADS, ruptura e a
        # agua fria das salvaguardas
        Q_pump = self.running_count() * C.PUMP_HEAT_MW * (self.flow / 100.0)
        Q_break = self.break_flow * C.BREAK_ENTHALPY if self.saturated else 0.0
        Q_si = bus.si_flow * C.CP_COOLANT * max(0.0, self.T_coolant - C.SI_WATER_TEMP)
        net = bus.Q_core + Q_pump - bus.Q_sg_total - bus.Q_prhr - bus.Q_ads - Q_break - Q_si
        # RCS saturado e aberto (ruptura/ADS): o excesso de calor FERVE a agua e
        # o vapor sai — a temperatura fica na saturacao e o inventario diminui
        self.boiloff = 0.0
        if self.saturated and (self.loca_open or bus.ads_mass_flow > 0.0) and net > 0.0:
            self.boiloff = net / C.STEAM_LATENT
            Q_break += net
            net = 0.0
        dTavg = net / C.C_COOLANT * dt
        self.T_coolant = max(20.0, self.T_coolant + dTavg)
        bus.Q_break = Q_break

        # ---- Thot / Tcold a partir da elevacao no nucleo -------------------
        W = C.RCP_FLOW_NOMINAL * flow_frac                  # kg/s
        core_dt = min(80.0, bus.P_th / max(W * C.CP_COOLANT, 1e-3))
        T_hot = self.T_coolant + core_dt / 2.0
        T_cold = self.T_coolant - core_dt / 2.0
        bus.T_hot = T_hot

        # ---- massa, nivel e pressao do PZR ---------------------------------
        dlevel = self._mass_balance(bus, dt, dTavg)
        self._pressurizer(bus, dt, heater, spray, dlevel, przr_sp, auto)

        # fator de resfriamento: abaixo do limiar o nucleo descobre; perto de
        # zero de inventario a transferencia quase cessa -> superaquecimento.
        bus.cooling_factor = max(C.UNCOVERED_COOLING, min(1.0, self.inventory / C.UNCOVERY_THRESHOLD))

        # ---- publica -------------------------------------------------------
        bus.T_coolant = self.T_coolant
        bus.T_cold = T_cold
        bus.core_dt = core_dt
        bus.flow_frac = flow_frac
        bus.boron = self.boron
