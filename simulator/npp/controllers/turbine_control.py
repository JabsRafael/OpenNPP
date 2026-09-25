"""
Controle da Turbina (valvulas de admissao de vapor) — carga pedida com rampa.

O operador (ou o despacho da rede) define a carga desejada (sp_power_pct); a
turbina caminha ate ela a 5%/min, como em uma planta real. Um termo integral
corrige a abertura da valvula para a carga medida bater com a pedida (a vazao
depende da pressao do GV). O reator acompanha: o controle de barras mantem o
Tavg no programa (ver rod_control.py) e o MTC negativo ajuda.

Em MANUAL o controlador acompanha a carga/valvula atuais (transferencia sem
salto ao voltar para AUTO).
"""

from .. import config as C


class TurbineControl:
    def __init__(self):
        self.load_sp = 100.0     # carga-alvo em rampa (%)
        self.trim = 0.0          # correcao integral da valvula (%)
        self.valve = 100.0

    def track(self, load_pct, valve_pct):
        self.load_sp = load_pct
        self.valve = valve_pct
        self.trim = valve_pct - load_pct

    def update(self, sp_load_pct, load_pct, dt):
        sp = max(0.0, min(100.0, sp_load_pct))
        step = C.LOAD_RAMP * dt
        self.load_sp += max(-step, min(step, sp - self.load_sp))
        self.trim += 0.05 * (self.load_sp - load_pct) * dt
        self.trim = max(-30.0, min(30.0, self.trim))
        self.valve = max(0.0, min(100.0, self.load_sp + self.trim))
        return self.valve
