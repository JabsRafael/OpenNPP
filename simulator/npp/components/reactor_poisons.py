"""
Componente VENENOS do reator — Xenonio-135/Iodo-135, Samario-149/Promecio-149 e
veneno queimavel/burnup.

Estes sao produtos de fissao (ou aditivos) que absorvem neutrons e inserem
reatividade negativa. Sua dinamica e' LENTA (horas a meses), por isso e' integrada
com um passo acelerado `dt_slow = dt * time_scale` — assim da' para observar o
pico de Xenonio (~9-11 h apos desligamento) em minutos.

Concentracoes normalizadas: 1,0 = equilibrio a 100% de potencia. Reatividade em
forma de DESVIO do equilibrio (zero no inicio -> preserva a criticalidade).

Fenomenos reproduzidos:
  * Pico de Xenonio pos-SCRAM ("poço de iodo"): apos desligar, o I-135 continua
    virando Xe-135 mas a queima por fluxo cessa -> Xe sobe, atinge pico em ~9-11 h
    e depois decai. Pode impedir a repartida ("xenon precluded start").
  * Transiente de Xenonio na mudanca de potencia (undershoot/overshoot).
  * Buildup permanente de Samario apos desligamento.
  * Depleção lenta do veneno queimavel com o burnup (libera reatividade positiva).
"""

from math import exp

from .. import config as C


class ReactorPoisons:
    def __init__(self):
        # concentracoes em unidades de equilibrio (100% potencia)
        self.I = C.XE_I_EQ       # estoque de iodo (> Xe) -> alimenta o pico
        self.Xe = 1.0
        self.Pm = 1.0
        self.Sm = 1.0
        self.bp = 1.0            # fracao de veneno queimavel restante
        self.burnup = 0.0        # % do ciclo
        # reatividades (Δk/k, desvio do equilibrio)
        self.rho_xe = 0.0
        self.rho_sm = 0.0
        self.rho_bp = 0.0

    def step(self, power_frac, dt_slow):
        P = max(0.0, power_frac)   # fluxo ~ potencia de fissao

        # ---- Iodo-135 / Xenonio-135 ---------------------------------------
        self.I += (C.XE_GI * P - C.XE_LAMBDA_I * self.I) * dt_slow
        self.Xe += (C.XE_GXE * P + C.XE_LAMBDA_I * self.I
                    - C.XE_LAMBDA_XE * self.Xe - C.XE_SIGMA_PHI * P * self.Xe) * dt_slow
        self.I = max(0.0, self.I)
        self.Xe = max(0.0, self.Xe)

        # ---- Promecio-149 / Samario-149 (buildup permanente) --------------
        self.Pm += (C.SM_GPM * P - C.SM_LAMBDA_PM * self.Pm) * dt_slow
        self.Sm += (C.SM_LAMBDA_PM * self.Pm - C.SM_SIGMA_PHI * P * self.Sm) * dt_slow
        self.Pm = max(0.0, self.Pm)
        self.Sm = max(0.0, self.Sm)

        # ---- Veneno queimavel / burnup (muito lento) ----------------------
        self.burnup += C.BURNUP_RATE * P * dt_slow
        self.burnup = min(100.0, self.burnup)
        self.bp = exp(-self.burnup / C.BP_TAU)

        # ---- Reatividades (desvio do equilibrio) --------------------------
        self.rho_xe = -C.XENON_WORTH * (self.Xe - 1.0)
        self.rho_sm = -C.SAMARIUM_WORTH * (self.Sm - 1.0)
        self.rho_bp = -C.BURNABLE_WORTH * (self.bp - 1.0)   # bp<1 -> reatividade +

        return self.rho_xe + self.rho_sm + self.rho_bp
