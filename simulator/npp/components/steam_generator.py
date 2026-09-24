"""
Componente GERADOR DE VAPOR (instanciado 2x — GV1 e GV2).

Cada GV e' independente: tem sua propria temperatura secundaria, pressao, nivel,
vazoes de alimentacao e vapor, e valvula de alivio. Cada um recebe metade do
calor do primario e e' regulado por seu proprio controlador de nivel (ver
controllers/sg_level.py). Isso reproduz a arquitetura real do AP1000 (2 GVs,
2 malhas de nivel independentes).

Bus (compartilhado): le T_coolant, flow_frac, turbine_tripped.
Estado proprio: T_sg, level, pressure, relief. Retorna Q_primario removido.
"""

from .. import config as C


class SteamGenerator:
    def __init__(self, name):
        self.name = name                    # "GV1" / "GV2"
        self.T_sg = C.SG_TEMP_NOMINAL
        self.level = C.SG_LEVEL_NOMINAL
        self.pressure = C.SG_PRESS_NOMINAL
        self.steam_flow = 0.0
        self.feed_flow = 0.0
        self.relief_open = False

    def step(self, bus, dt, feed_valve_pct, turbine_valve_pct, feed_on):
        # ---- pressao secundaria (saturacao linearizada) --------------------
        self.pressure = C.SG_PRESS_NOMINAL + C.SG_SAT_SLOPE * (self.T_sg - C.SG_TEMP_NOMINAL)
        press_factor = max(0.0, min(1.2, self.pressure / C.SG_PRESS_NOMINAL))

        # ---- vazoes de vapor e alimentacao ---------------------------------
        tv = 0.0 if bus.turbine_tripped else max(0.0, min(100.0, turbine_valve_pct)) / 100.0
        self.steam_flow = C.FEED_FLOW_NOMINAL * tv * press_factor
        self.feed_flow = (C.FEED_FLOW_NOMINAL * max(0.0, min(100.0, feed_valve_pct)) / 100.0
                          if feed_on else 0.0)

        # ---- balanco de energia do secundario ------------------------------
        Q_primary = C.H_COOLANT_SG * bus.flow_frac * (bus.T_coolant - self.T_sg)   # MW
        Q_steam = self.steam_flow * C.STEAM_LATENT                                 # MW
        self.T_sg += (Q_primary - Q_steam) / C.C_SG * dt
        self.T_sg = max(20.0, self.T_sg)

        # ---- nivel por balanco de massa ------------------------------------
        self.level += (self.feed_flow - self.steam_flow) * C.SG_LEVEL_GAIN * dt
        self.level = max(0.0, min(100.0, self.level))

        # ---- valvula de alivio ---------------------------------------------
        if self.pressure > C.SG_RELIEF_SETPOINT:
            self.relief_open = True
            self.T_sg -= 2.0 * dt
        elif self.pressure < C.SG_RELIEF_SETPOINT - 3.0:
            self.relief_open = False

        return Q_primary
