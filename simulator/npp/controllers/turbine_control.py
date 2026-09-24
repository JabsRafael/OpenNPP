"""
Controle da Turbina (valvula de admissao de vapor).

A abertura da valvula segue a demanda de potencia. Em uma planta real e' o
"reactor-follows-turbine": a turbina define a carga e o reator acompanha via
controle de barras. Aqui a valvula persegue o setpoint de potencia.
"""


class TurbineControl:
    def __init__(self):
        self.valve = 100.0

    def update(self, sp_power_pct, dt):
        self.valve += (sp_power_pct - self.valve) * min(1.0, dt / 3.0)
        self.valve = max(0.0, min(100.0, self.valve))
        return self.valve
