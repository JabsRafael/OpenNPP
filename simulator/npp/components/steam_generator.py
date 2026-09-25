"""
Componente GERADOR DE VAPOR (instanciado 2x — GV1 e GV2).

Cada GV e' independente: tem sua propria temperatura secundaria, pressao, nivel,
vazoes de alimentacao e vapor, e valvula de alivio. Cada um recebe metade do
calor do primario e e' regulado por seu proprio controlador de nivel (ver
controllers/sg_level.py). Isso reproduz a arquitetura real do AP1000 (2 GVs,
2 malhas de nivel independentes).

Pressao = saturacao da agua do GV (tabela de vapor). Saidas de vapor:
  turbina (valvula de admissao) + despejo ao condensador (steam dump) + alivio.
Entradas de agua: alimentacao principal (isolavel) + alimentacao de partida
(SFW, automatica quando a principal nao entrega).

Bus (compartilhado): le T_coolant, flow_frac, turbine_tripped, steam_dump_frac,
feed_isolated. Estado proprio: T_sg, level, pressure, relief. Retorna Q removido.
"""

from .. import config as C
from ..water import psat


class SteamGenerator:
    def __init__(self, name):
        self.name = name                    # "GV1" / "GV2"
        self.T_sg = C.SG_TEMP_NOMINAL
        self.level = C.SG_LEVEL_NOMINAL
        self.pressure = C.SG_PRESS_NOMINAL
        self.steam_flow = 0.0               # total que sai do GV
        self.turbine_steam = 0.0
        self.dump_steam = 0.0
        self.feed_flow = 0.0                # total que entra (principal + SFW)
        self.sfw_flow = 0.0
        self.main_feed = 0.0
        self.relief_open = False

    def step(self, bus, dt, feed_valve_pct, turbine_valve_pct, feed_on, sfw_manual_pct=None):
        # ---- pressao secundaria (saturacao) --------------------------------
        self.pressure = psat(self.T_sg)
        pf = max(0.0, min(1.4, self.pressure / C.SG_PRESS_NOMINAL))   # vazao ~ pressao

        # ---- saidas de vapor -----------------------------------------------
        tv = 0.0 if bus.turbine_tripped else max(0.0, min(100.0, turbine_valve_pct)) / 100.0
        self.turbine_steam = C.FEED_FLOW_NOMINAL * tv * pf
        self.dump_steam = C.FEED_FLOW_NOMINAL * C.STEAM_DUMP_CAPACITY * bus.steam_dump_frac * pf
        if self.pressure > C.SG_RELIEF_SETPOINT:
            self.relief_open = True
        elif self.pressure < C.SG_RELIEF_SETPOINT - 3.0:
            self.relief_open = False
        relief = C.SG_RELIEF_FLOW * pf if self.relief_open else 0.0
        self.steam_flow = self.turbine_steam + self.dump_steam + relief

        # ---- agua de alimentacao ------------------------------------------
        main = 0.0
        if feed_on and not bus.feed_isolated:
            main = C.FEED_FLOW_NOMINAL * max(0.0, min(100.0, feed_valve_pct)) / 100.0
        # SFW: em AUTO segura o nivel quando a alimentacao principal nao entrega;
        # em MANUAL o operador define a vazao (% da capacidade)
        if sfw_manual_pct is not None:
            self.sfw_flow = C.SFW_MAX_FLOW * max(0.0, min(100.0, sfw_manual_pct)) / 100.0
        elif main < 5.0:
            want = self.steam_flow + 4.0 * (C.SFW_LEVEL_SP - self.level)
            self.sfw_flow = max(0.0, min(C.SFW_MAX_FLOW, want))
        else:
            self.sfw_flow = 0.0
        self.main_feed = main
        self.feed_flow = main + self.sfw_flow

        # ---- balanco de energia do secundario ------------------------------
        Q_primary = C.H_COOLANT_SG * bus.flow_frac * (bus.T_coolant - self.T_sg)   # MW
        Q_steam = self.steam_flow * C.STEAM_LATENT                                 # MW
        self.T_sg += (Q_primary - Q_steam) / C.C_SG * dt
        self.T_sg = max(20.0, self.T_sg)

        # ---- nivel por balanco de massa ------------------------------------
        self.level += (self.feed_flow - self.steam_flow) * C.SG_LEVEL_GAIN * dt
        self.level = max(0.0, min(100.0, self.level))

        return Q_primary
