"""
Componente NUCLEO (o reator propriamente dito).

Isolado dos sistemas auxiliares: cuida apenas de neutronica (cinetica pontual,
6 grupos de neutrons atrasados), realimentacao de reatividade e temperatura do
combustivel. Fala com o resto da planta somente pelo ProcessBus:
  le   -> T_coolant, boron, rod_pos, tripped
  escreve -> fission_frac, power_frac, decay_frac, P_th, Q_core, T_fuel, reactivity
"""

from .. import config as C


class ReactorCore:
    def __init__(self):
        self.n = 1.0                       # potencia neutronica normalizada
        self.Cprec = [C.BETA[i] / (C.GEN_TIME * C.LAMBDA[i]) for i in range(6)]
        self.T_fuel = C.FUEL_TEMP_REF
        self.dh_fast = C.DECAY_HEAT_INIT * 0.6
        self.dh_slow = C.DECAY_HEAT_INIT * 0.4
        self.rod_pos = C.ROD_POS_REF       # % retirada (100 = fora)
        self.reactivity = 0.0

    def _reactivity(self, T_coolant, boron, rho_poison):
        rho = C.ROD_WORTH * (self.rod_pos - C.ROD_POS_REF) / 100.0
        rho += C.ALPHA_DOPPLER * (self.T_fuel - C.FUEL_TEMP_REF)
        rho += C.ALPHA_MOD * (T_coolant - C.COOLANT_TEMP_REF)
        rho += C.ALPHA_BORON * (boron - C.BORON_REF)
        rho += rho_poison                    # Xenonio + Samario + veneno queimavel
        return max(-0.20, min(0.02, rho))   # clamp de seguranca numerica

    def move_rods(self, demand, dt, tripped):
        """Movimento das barras com limite de taxa; SCRAM = queda rapida."""
        if tripped:
            demand, rate = 0.0, 30.0
        else:
            rate = 2.0
        demand = max(0.0, min(100.0, demand))
        step = rate * dt
        if self.rod_pos < demand:
            self.rod_pos = min(demand, self.rod_pos + step)
        elif self.rod_pos > demand:
            self.rod_pos = max(demand, self.rod_pos - step)

    def step(self, bus, dt):
        # ---- cinetica pontual (subpassada p/ estabilidade numerica) --------
        rho = self._reactivity(bus.T_coolant, bus.boron, bus.rho_poison)
        self.reactivity = rho
        sub = C.NEUTRONICS_SUBSTEPS
        dtn = dt / sub
        Cp = self.Cprec
        for _ in range(sub):
            src = sum(C.LAMBDA[i] * Cp[i] for i in range(6))
            dn = ((rho - C.BETA_TOTAL) / C.GEN_TIME * self.n + src) * dtn
            for i in range(6):
                Cp[i] += (C.BETA[i] / C.GEN_TIME * self.n - C.LAMBDA[i] * Cp[i]) * dtn
            self.n += dn
            self.n = max(0.0, min(C.MAX_POWER_FRAC, self.n))

        # ---- calor de decaimento (dois polos) ------------------------------
        kf, ks = 0.6 * C.DECAY_HEAT_INIT, 0.4 * C.DECAY_HEAT_INIT
        self.dh_fast += (kf * self.n - self.dh_fast) / C.DECAY_TAU_FAST * dt
        self.dh_slow += (ks * self.n - self.dh_slow) / C.DECAY_TAU_SLOW * dt
        decay = self.dh_fast + self.dh_slow
        power_frac = max(self.n, decay)
        P_th = C.RATED_MWTH * power_frac

        # ---- no de combustivel (transferencia degrada se o nucleo descobre)
        Q_fc = C.H_FUEL_COOLANT * bus.cooling_factor * (self.T_fuel - bus.T_coolant)  # MW
        self.T_fuel += (P_th - Q_fc) / C.C_FUEL * dt
        self.T_fuel = max(20.0, min(3000.0, self.T_fuel))   # clamp (fusao ~2800)

        # ---- publica no barramento ----------------------------------------
        bus.fission_frac = self.n
        bus.decay_frac = decay
        bus.power_frac = power_frac
        bus.P_th = P_th
        bus.Q_core = Q_fc
        bus.T_fuel = self.T_fuel
        bus.reactivity = rho
