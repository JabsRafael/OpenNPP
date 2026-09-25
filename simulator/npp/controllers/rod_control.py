"""
Sistema de Controle de Barras (Rod Control System).

Ajusta a posicao do banco de controle para casar a potencia do reator ao
setpoint. Com MTC negativo, mover as barras -> muda reatividade -> potencia
converge de forma estavel.

Anti-windup: durante um trip (SCRAM) a demanda ACOMPANHA a posicao real das
barras (que caem a 0). Assim, ao repartir, o controlador comeca do fundo e retira
as barras gradualmente (limite de taxa), sem um salto acumulado.
"""


class RodControl:
    def __init__(self, rod_ref):
        self.rod_demand = rod_ref
        self.gain = 0.04
        self.lead = 12.0        # demanda pode liderar a posicao real em no maximo 12%
        self.period_min = 25.0  # s — abaixo disso (subindo rapido) para de retirar

    def update(self, power_pct, sp_power_pct, dt, tripped=False, current_rod=None, period=999.0):
        if tripped:
            if current_rod is not None:
                self.rod_demand = current_rod
            return self.rod_demand
        err = sp_power_pct - power_pct
        self.rod_demand += self.gain * err * dt
        # limite de PERIODO: se a potencia sobe rapido (periodo curto positivo),
        # nao retira mais barras -> arresta a subida (como um operador faz).
        if current_rod is not None:
            if 0.0 < period < self.period_min:
                self.rod_demand = min(self.rod_demand, current_rod)
            # governador: demanda nao fica longe da posicao real (reverte a tempo)
            self.rod_demand = max(current_rod - self.lead, min(current_rod + self.lead, self.rod_demand))
        self.rod_demand = max(0.0, min(100.0, self.rod_demand))
        return self.rod_demand
