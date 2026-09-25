"""
Controle do Despejo de Vapor (Steam Dump / Turbine Bypass) — automatico.

Independente do modo AUTO/MANUAL do reator (como na planta real); tem estacao
A/M propria: em MANUAL o operador define a abertura (0-100%). Armado quando a
turbina desarma ou esta com pouca carga (partida). Modula a abertura para manter
o Tavg no programa: Tref = T_sem_carga + (T_nominal - T_sem_carga) x carga.
Sem ele, um trip do reator a 100% superaqueceria o primario (a turbina fecha e o
calor residual nao teria para onde ir).
"""

from .. import config as C


class SteamDumpControl:
    def __init__(self):
        self.frac = 0.0

    def update(self, tavg, turbine_load, turbine_tripped, dt, manual_pct=None):
        if manual_pct is not None:                # operador abre a valvula direto
            target = max(0.0, min(100.0, manual_pct)) / 100.0
            self.frac += (target - self.frac) * min(1.0, dt / 2.0)
            return self.frac
        armed = turbine_tripped or turbine_load < C.STEAM_DUMP_ARM_LOAD
        tref = C.T_NOLOAD + (C.COOLANT_TEMP_REF - C.T_NOLOAD) * max(0.0, min(1.0, turbine_load))
        err = tavg - tref - C.STEAM_DUMP_DEADBAND
        target = max(0.0, min(1.0, err / C.STEAM_DUMP_FULL_OPEN)) if armed else 0.0
        self.frac += (target - self.frac) * min(1.0, dt / 2.0)   # curso da valvula
        return self.frac
