"""
Sistema de Controle de Barras (Rod Control System) — esquema Westinghouse.

As barras seguem o PROGRAMA DE TEMPERATURA: Tref cresce linearmente com a carga
da turbina (292 degC sem carga -> 305 degC a 100%). O erro total e'
  (Tavg - Tref) + ganho x (potencia nuclear - carga da turbina)
O canal de descasamento de potencia antecipa a resposta. Banda morta de 0,8 K e
velocidade proporcional ao erro (ate' 72 passos/min).

Intertravamentos:
  * C-5: com carga da turbina < 15% a retirada AUTOMATICA e' bloqueada — a partida
    e' feita em manual e o AUTO so' assume com a turbina carregada.
  * Limite de periodo: se a potencia sobe rapido (periodo curto), para de retirar.

Anti-windup: durante um trip (SCRAM) a demanda ACOMPANHA a posicao real das
barras (que caem a 0).
"""

from .. import config as C


class RodControl:
    def __init__(self, rod_ref):
        self.rod_demand = rod_ref
        self.period_min = 25.0  # s — abaixo disso (subindo rapido) para de retirar
        self.c5_block = False

    def update(self, tavg, tref, power_pct, load_pct, dt, tripped=False,
               current_rod=None, period=999.0):
        if current_rod is None:
            current_rod = self.rod_demand
        if tripped:
            self.rod_demand = current_rod
            return self.rod_demand
        err = (tavg - tref) + C.ROD_MISMATCH_GAIN * (power_pct - load_pct)
        mag = abs(err) - C.ROD_TAVG_DEADBAND
        move = 0.0
        if mag > 0.0:
            speed = min(1.0, mag / 2.0) * C.ROD_SPEED        # %/s proporcional
            move = -speed * dt if err > 0 else speed * dt    # quente -> insere
        self.c5_block = load_pct < C.C5_LOAD
        if move > 0.0 and (self.c5_block or 0.0 < period < self.period_min):
            move = 0.0
        self.rod_demand = max(0.0, min(100.0, current_rod + move))
        return self.rod_demand
