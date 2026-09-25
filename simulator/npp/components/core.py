"""
Componente NUCLEO (o reator propriamente dito).

Isolado dos sistemas auxiliares: cuida de neutronica, realimentacao de
reatividade, calor de decaimento e temperatura do combustivel. Fala com o resto
da planta somente pelo ProcessBus:
  le      -> T_coolant, boron, rho_poison, burnup, cooling_factor
  escreve -> fission_frac, power_frac, decay_frac, P_th, Q_core, T_fuel, reactivity

Fisica modelada:
  * Cinetica pontual com 6 grupos de neutrons atrasados + FONTE de neutrons
    (multiplicacao subcritica: o nucleo desligado tem populacao finita que sobe
    ao se aproximar da criticalidade — base do procedimento real de partida).
    Integracao implicita (estavel mesmo com -10000 pcm).
  * Reatividade: barras em curva S, Doppler ~ sqrt(T), MTC dependente de
    temperatura/boro/burnup, boro com valor dependente da temperatura, venenos.
  * Calor de decaimento em 7 grupos (curva ANS-5.1), com memoria do historico
    de potencia: horas depois do trip ainda ha ~1% de potencia termica.
"""

from math import log, sin, pi

from .. import config as C

_TREF_K = C.FUEL_TEMP_REF + 273.15


def rod_integral_worth(pos):
    """Fracao (0..1) do valor total do banco retirada ate `pos` (% retirada).
    Curva S: pouco efeito nas pontas, maximo no meio do nucleo."""
    x = max(0.0, min(100.0, pos)) / 100.0
    return x - sin(2.0 * pi * x) / (2.0 * pi)


_ROD_REF = rod_integral_worth(C.ROD_POS_REF)


class ReactorCore:
    def __init__(self):
        self.n = 1.0                       # potencia neutronica normalizada
        self.Cprec = [C.BETA[i] / (C.GEN_TIME * C.LAMBDA[i]) for i in range(6)]
        self.T_fuel = C.FUEL_TEMP_REF
        self.decay = [a for a, _ in C.DECAY_GROUPS]   # grupos em equilibrio
        self.rod_pos = C.ROD_POS_REF       # % retirada (100 = fora)
        self.reactivity = 0.0
        self.rho_parts = {}                # componentes da reatividade (pcm) p/ HMI
        self.log_rate = 0.0                # d(ln n)/dt filtrado (1/s)
        self._n_hist = []                  # ultimos 2 s de potencia (trip de taxa)

    # ---------------------------------------------------------- reatividade
    def compute_reactivity(self, T_coolant, boron, rho_poison, burnup):
        dT = T_coolant - C.COOLANT_TEMP_REF
        dB = boron - C.BORON_REF
        rho_rod = C.ROD_WORTH * (rod_integral_worth(self.rod_pos) - _ROD_REF)
        rho_dop = -C.DOPPLER_A * ((self.T_fuel + 273.15) ** 0.5 - _TREF_K ** 0.5)
        # integral do MTC(T, B, burnup) desde Tref (termo cruzado T x B = valor
        # do boro maior a frio, agua mais densa)
        rho_mod = ((C.MTC_REF + C.MTC_B * dB + C.MTC_BU * burnup) * dT
                   + 0.5 * C.MTC_T * dT * dT)
        rho_bor = C.ALPHA_BORON * dB
        rho = rho_rod + rho_dop + rho_mod + rho_bor + rho_poison
        self.rho_parts = {"rod": rho_rod * 1e5, "doppler": rho_dop * 1e5,
                          "mod": rho_mod * 1e5, "boron": rho_bor * 1e5,
                          "poison": rho_poison * 1e5}
        return max(-0.30, min(0.02, rho))   # clamp de seguranca numerica

    def mtc_pcm(self, T_coolant, boron, burnup):
        """MTC instantaneo (pcm/K) — mostrado na HMI (pode ficar positivo)."""
        return 1e5 * (C.MTC_REF + C.MTC_T * (T_coolant - C.COOLANT_TEMP_REF)
                      + C.MTC_B * (boron - C.BORON_REF) + C.MTC_BU * burnup)

    # ---------------------------------------------------------- estado inicial
    def set_state(self, n, T_fuel, rod_pos, decay_age_s=None):
        """Define potencia com precursores em equilibrio. decay_age_s: tempo (s)
        desde o desligamento apos operacao longa a 100% (None = em potencia n;
        float('inf') = sem historico, nucleo novo)."""
        self.n = n
        self.Cprec = [C.BETA[i] / (C.GEN_TIME * C.LAMBDA[i]) * n for i in range(6)]
        self.T_fuel, self.rod_pos = T_fuel, rod_pos
        if decay_age_s is None:
            self.decay = [a * n for a, _ in C.DECAY_GROUPS]
        elif decay_age_s == float("inf"):
            self.decay = [0.0] * len(C.DECAY_GROUPS)
        else:
            from math import exp
            self.decay = [a * exp(-decay_age_s / tau) for a, tau in C.DECAY_GROUPS]
        self.log_rate = 0.0
        self._n_hist = []

    def settle_subcritical(self, rho):
        """Nucleo subcritico com fonte: n de equilibrio = S*Lambda/|rho|."""
        if rho < -1e-4:
            n = C.NEUTRON_SOURCE * C.GEN_TIME / -rho
            self.n = n
            self.Cprec = [C.BETA[i] / (C.GEN_TIME * C.LAMBDA[i]) * n for i in range(6)]

    # ---------------------------------------------------------- barras
    def move_rods(self, demand, dt, tripped, auto=False, withdraw_block=False):
        """Movimento das barras com limite de taxa (passos/min reais); SCRAM =
        queda por gravidade. withdraw_block = intertravamento C-1/C-2."""
        if tripped:
            demand, rate = 0.0, C.ROD_SPEED_SCRAM
        else:
            rate = C.ROD_SPEED if auto else C.ROD_SPEED_MANUAL
        demand = max(0.0, min(100.0, demand))
        if withdraw_block:
            demand = min(demand, self.rod_pos)
        step = rate * dt
        if self.rod_pos < demand:
            self.rod_pos = min(demand, self.rod_pos + step)
        elif self.rod_pos > demand:
            self.rod_pos = max(demand, self.rod_pos - step)

    @property
    def rod_steps(self):
        return self.rod_pos / 100.0 * C.ROD_STEPS

    # ---------------------------------------------------------- passo
    def step(self, bus, dt):
        n_old = self.n
        rho = self.compute_reactivity(bus.T_coolant, bus.boron, bus.rho_poison, bus.burnup)
        self.reactivity = rho

        # ---- cinetica pontual: Euler implicito (Gauss-Seidel n -> C_i) ------
        sub = C.NEUTRONICS_SUBSTEPS
        h = dt / sub
        Cp, lam, beta, L = self.Cprec, C.LAMBDA, C.BETA, C.GEN_TIME
        a = (rho - C.BETA_TOTAL) / L
        denom = 1.0 - h * a
        n = self.n
        for _ in range(sub):
            src = lam[0] * Cp[0] + lam[1] * Cp[1] + lam[2] * Cp[2] \
                + lam[3] * Cp[3] + lam[4] * Cp[4] + lam[5] * Cp[5]
            n = (n + h * (src + C.NEUTRON_SOURCE)) / denom
            if n > C.MAX_POWER_FRAC:
                n = C.MAX_POWER_FRAC
            for i in range(6):
                Cp[i] = (Cp[i] + h * beta[i] / L * n) / (1.0 + h * lam[i])
        self.n = n

        # taxa logaritmica filtrada (periodo / SUR) e historico p/ trip de taxa
        inst = log(max(n, 1e-30) / max(n_old, 1e-30)) / dt
        self.log_rate += (inst - self.log_rate) * min(1.0, dt / 1.0)
        self._n_hist.append(n)
        if len(self._n_hist) > int(round(2.0 / dt)) + 1:
            self._n_hist.pop(0)

        # ---- calor de decaimento (7 grupos, memoria do historico) ----------
        for i, (ai, tau) in enumerate(C.DECAY_GROUPS):
            self.decay[i] += (ai * n - self.decay[i]) * min(1.0, dt / tau)
        decay = sum(self.decay)
        # potencia termica = fissao "pronta" + decaimento (soma 1,0 em equilibrio)
        power_frac = (1.0 - C.DECAY_HEAT_INIT) * n + decay
        P_th = C.RATED_MWTH * power_frac

        # ---- no de combustivel (transferencia degrada se o nucleo descobre)
        Q_fc = C.H_FUEL_COOLANT * bus.cooling_factor * (self.T_fuel - bus.T_coolant)  # MW
        self.T_fuel += (P_th - Q_fc) / C.C_FUEL * dt
        self.T_fuel = max(20.0, min(3000.0, self.T_fuel))   # clamp (fusao ~2800)

        # ---- publica no barramento ----------------------------------------
        bus.fission_frac = n
        bus.decay_frac = decay
        bus.power_frac = power_frac
        bus.P_th = P_th
        bus.Q_core = Q_fc
        bus.T_fuel = self.T_fuel
        bus.reactivity = rho

    # ---------------------------------------------------------- leituras NIS
    @property
    def period(self):
        """Periodo do reator (s); +-999 = estavel."""
        r = self.log_rate
        if abs(r) < 1.0 / 999.0:
            return 999.0
        return max(-999.0, min(999.0, 1.0 / r))

    @property
    def sur_dpm(self):
        """Startup rate em decadas por minuto (26,06 / periodo)."""
        return self.log_rate * 60.0 / log(10.0)

    @property
    def flux_rate_2s(self):
        """Variacao da potencia (pontos %) nos ultimos 2 s."""
        return (self.n - self._n_hist[0]) * 100.0 if self._n_hist else 0.0

    @property
    def sr_cps(self):
        return self.n * C.SR_CPS_PER_FRAC

    @property
    def ir_amps(self):
        return self.n * C.IR_AMP_PER_FRAC
