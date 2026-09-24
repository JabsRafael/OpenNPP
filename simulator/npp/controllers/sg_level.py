"""
Controle de Nivel do Gerador de Vapor (Feedwater Control System).

UMA instancia por gerador de vapor -> no AP1000 sao DUAS malhas independentes
(GV1 e GV2). Controle a tres elementos (simplificado): erro de nivel + termo de
vazao de vapor (feedforward) definem a abertura da valvula de agua de alimentacao.

Cada controlador e' um alvo distinto no cyber range: um atacante pode manipular
apenas a malha do GV1 e observar a resposta assimetrica entre os dois geradores.
"""


class SGLevelControl:
    def __init__(self, name, feed_nominal):
        self.name = name                 # "GV1" / "GV2"
        self.feed_nominal = feed_nominal  # kg/s a 100%
        self.feed_valve = 100.0
        self.gain = 2.0

    def update(self, sg_level, steam_flow, sp_level, dt):
        err = sp_level - sg_level
        feedforward = (steam_flow / self.feed_nominal) * 100.0
        self.feed_valve = feedforward + self.gain * err
        self.feed_valve = max(0.0, min(100.0, self.feed_valve))
        return self.feed_valve
