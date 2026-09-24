"""
Controle de Pressao do Pressurizador.

Mantem a pressao do primario no setpoint via aquecedor (sobe) e spray (desce),
em controle bang-bang com banda morta.
"""


class PressurizerControl:
    def __init__(self, deadband=1.0):
        self.deadband = deadband

    def update(self, przr_press, sp_press):
        heater = przr_press < sp_press - self.deadband
        spray = przr_press > sp_press + self.deadband
        return heater, spray
