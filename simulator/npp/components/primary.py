"""
Componente PRIMARIO — Reactor Coolant System (RCS).

Modela o refrigerante primario como no concentrado (Tavg), as 4 bombas de
refrigerante (RCPs, 2 por loop) com inercia/coastdown, o calculo de Thot/Tcold
a partir da potencia e vazao, e o pressurizador (pressao e nivel).

Bus:
  le   -> Q_core (entra), Q_sg_total + Q_prhr (saem), P_th, si_flow
  escreve -> T_coolant, T_hot, T_cold, core_dt, flow_frac, boron
"""

from .. import config as C


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
        self.inventory = 100.0        # % de inventario do primario (LOCA drena)

    def running_count(self):
        return sum(1 for r in self.rcp_running if r)

    # -------------------------------------------------------------- atuadores
    def apply_pumps(self, running_list, speed_demand):
        self.rcp_running = running_list
        self.rcp_speed = speed_demand

    def apply_boron(self, charge, dilute, dt):
        if charge:
            self.boron += 2.0 * dt
        if dilute:
            self.boron -= 2.0 * dt
        self.boron = max(0.0, min(3500.0, self.boron))

    def apply_pressurizer(self, heater, spray, dt, dTavg):
        dP = C.PRZR_THERMAL_EXP * dTavg
        if heater:
            dP += C.PRZR_HEATER_RATE * dt
        if spray:
            dP -= C.PRZR_SPRAY_RATE * dt
        self.przr_press += dP
        if self.przr_press >= C.PRZR_RELIEF_SETPOINT:
            self.przr_relief_open = True
        elif self.przr_press <= C.PRZR_RELIEF_RESEAT:
            self.przr_relief_open = False
        if self.przr_relief_open:
            self.przr_press -= 2.5 * dt
        self.przr_press = max(1.0, min(250.0, self.przr_press))

    def apply_loca(self, bus, dt, loca_size):
        """Rompimento no primario: drena inventario e despressuriza; a injecao de
        seguranca (bus.si_flow) reenche. Define bus.cooling_factor (descobrimento
        do nucleo)."""
        loca_size = max(0.0, min(1.0, loca_size))
        press_frac = max(0.2, self.przr_press / C.PRZR_PRESS_NOMINAL)
        if loca_size > 0.0:
            self.inventory -= C.LOCA_DRAIN_RATE * loca_size * press_frac * dt
            self.przr_press -= C.LOCA_DEPRESS_RATE * loca_size * press_frac * dt
        # reposicao por injecao de seguranca (CMT/acumuladores/IRWST)
        self.inventory += C.SI_REFILL_GAIN * bus.si_flow * dt
        self.inventory = max(0.0, min(100.0, self.inventory))
        # fator de resfriamento: abaixo do limiar o nucleo descobre; perto de
        # zero de inventario a transferencia quase cessa -> superaquecimento.
        bus.cooling_factor = max(0.02, min(1.0, self.inventory / C.UNCOVERY_THRESHOLD))

    # -------------------------------------------------------------------- step
    def step(self, bus, dt, heater, spray):
        # ---- vazao das 4 RCPs (fracao da nominal, com inercia) -------------
        target = (self.running_count() / C.N_RCP) * self.rcp_speed
        self.flow += (target - self.flow) * min(1.0, dt / C.RCP_COASTDOWN_TAU)
        self.flow = max(0.0, min(110.0, self.flow))
        flow_frac = self.flow / 100.0

        # ---- balanco de energia do refrigerante ----------------------------
        # entra Q_core; saem Q_sg_total (geradores de vapor) e Q_prhr (passivo)
        net = bus.Q_core - bus.Q_sg_total - bus.Q_prhr
        dTavg = net / C.C_COOLANT * dt
        # injecao de seguranca resfria o primario (agua fria borada)
        if bus.si_flow > 0:
            dTavg -= bus.si_flow * 3e-4 * dt
        self.T_coolant += dTavg
        self.T_coolant = max(20.0, self.T_coolant)

        # ---- Thot / Tcold a partir da elevacao no nucleo -------------------
        W = C.RCP_FLOW_NOMINAL * flow_frac                  # kg/s
        core_dt = min(80.0, bus.P_th / max(W * C.CP_COOLANT, 1e-3))
        T_hot = self.T_coolant + core_dt / 2.0
        T_cold = self.T_coolant - core_dt / 2.0

        # ---- pressurizador -------------------------------------------------
        self.apply_pressurizer(heater, spray, dt, dTavg)
        self.przr_level = C.PRZR_LEVEL_NOMINAL + 1.2 * (self.T_coolant - C.COOLANT_TEMP_REF)
        if bus.si_flow > 0:
            self.przr_level += bus.si_flow * 2e-3 * dt      # reposicao de inventario
        self.przr_level = min(self.przr_level, self.inventory)   # LOCA drena o nivel
        self.przr_level = max(0.0, min(100.0, self.przr_level))

        # ---- publica -------------------------------------------------------
        bus.T_coolant = self.T_coolant
        bus.T_hot = T_hot
        bus.T_cold = T_cold
        bus.core_dt = core_dt
        bus.flow_frac = flow_frac
        bus.boron = self.boron
