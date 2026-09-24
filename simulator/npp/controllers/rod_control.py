"""
Sistema de Controle de Barras (Rod Control System).

Ajusta a posicao do banco de controle para casar a potencia do reator ao
setpoint. Com MTC negativo, mover as barras -> muda reatividade -> potencia
converge de forma estavel.
"""


class RodControl:
    def __init__(self, rod_ref):
        self.rod_demand = rod_ref
        self.gain = 0.04

    def update(self, power_pct, sp_power_pct, dt):
        err = sp_power_pct - power_pct
        self.rod_demand += self.gain * err * dt
        self.rod_demand = max(0.0, min(100.0, self.rod_demand))
        return self.rod_demand
