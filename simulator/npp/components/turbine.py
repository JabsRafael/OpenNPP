"""
Componente TURBINA / GERADOR (sistema auxiliar do secundario).

Recebe o vapor combinado dos 2 geradores de vapor e produz potencia eletrica.
Modela rotacao com inercia e desarme por sobrevelocidade.

Bus: le steam_flow_total, P_th, turbine_tripped. Escreve nada no bus (a potencia
eletrica e a rotacao sao lidas via getters pelo Plant/sensors).
"""

from .. import config as C


class Turbine:
    def __init__(self):
        self.rpm = C.TURBINE_RPM_NOMINAL
        self.gen_power = C.RATED_MWE

    def step(self, bus, dt):
        steam_nominal = C.FEED_FLOW_NOMINAL * C.N_SG
        steam_frac = bus.steam_flow_total / steam_nominal if steam_nominal else 0.0

        # potencia limitada pelo vapor disponivel E pela potencia termica
        self.gen_power = min(C.RATED_MWE * steam_frac, bus.P_th * C.TURBINE_EFF)
        self.gen_power = max(0.0, self.gen_power)
        load_frac = self.gen_power / C.RATED_MWE

        if bus.turbine_tripped:
            rpm_target = 0.0
        else:
            # descasamento vapor/carga -> tendencia a acelerar (sobrevelocidade)
            rpm_target = C.TURBINE_RPM_NOMINAL * (1.0 + 0.15 * (steam_frac - load_frac))
        self.rpm += (rpm_target - self.rpm) / C.TURBINE_INERTIA * dt
        self.rpm = max(0.0, self.rpm)
