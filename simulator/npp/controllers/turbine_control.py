"""
Controle da Turbina (valvula de admissao de vapor).

A abertura da valvula acompanha a POTENCIA REAL do reator (modo turbina-segue-
reator). Assim, em baixa potencia (ex.: logo apos um SCRAM), a valvula fica quase
fechada e nao ha super-resfriamento do primario por extracao de vapor — o que
permite repartir o reator sem derrubar a pressao. Conforme a potencia sobe, a
valvula abre e a geracao acompanha.
"""

from .. import config as C


class TurbineControl:
    def __init__(self):
        self.valve = 100.0

    def update(self, power_pct, dt):
        target = max(0.0, min(100.0, power_pct))
        self.valve += (target - self.valve) * min(1.0, dt / 3.0)
        self.valve = max(0.0, min(100.0, self.valve))
        return self.valve
