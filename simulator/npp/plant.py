"""
Planta AP1000-like — montagem dos modulos e orquestracao do passo de simulacao.

Estrutura (espelha a planta real):
  REATOR        -> ReactorCore
  PRIMARIO      -> PrimarySystem (2 loops, 4 RCPs, pressurizador)
  SECUNDARIO    -> 2x SteamGenerator + Turbine
  SALVAGUARDAS  -> PassiveSafety (PXS) + protecao (RPS/ESFAS)

Acoplamento entre modulos passa pelo ProcessBus. A ordem de avaliacao por passo
respeita o fluxo de energia: nucleo -> geradores de vapor -> primario -> turbina
-> protecao -> salvaguardas.
"""

import math

from . import config as C
from . import protection
from .components.bus import ProcessBus
from .components.core import ReactorCore
from .components.primary import PrimarySystem
from .components.reactor_poisons import ReactorPoisons
from .components.safety import PassiveSafety
from .components.steam_generator import SteamGenerator
from .components.turbine import Turbine
from .controllers.control_system import ControlSystem


class Plant:
    def __init__(self):
        self.bus = ProcessBus()
        self.core = ReactorCore()
        self.poisons = ReactorPoisons()
        self.primary = PrimarySystem()
        self.sg = [SteamGenerator("GV1"), SteamGenerator("GV2")]
        self.turbine = Turbine()
        self.safety = PassiveSafety()
        self.control = ControlSystem()
        self._prev_power = 1.0
        self.reactor_period = 999.0   # s (positivo=subindo, negativo=descendo)
        # registro de eventos (para o operador entender o que aconteceu)
        self.events = []
        self._evid = 0
        self._prev_ev = {}
        self.sim_t = 0.0
        self._trip_causes = []
        self.esfas_armed = True   # permissivo P-11 (armado quando pressurizado)

    # ---- rotulos legiveis das causas de trip (registro de eventos) ----------
    _CAUSE_PT = {
        "hi_flux": "fluxo de neutrons alto", "hi_przr_press": "pressao alta do PZR",
        "lo_przr_press": "pressao baixa do PZR", "lo_sg_level": "nivel baixo de GV",
        "hi_fuel_temp": "temperatura alta do combustivel", "lo_flow": "vazao baixa do primario",
        "hi_cont_press": "pressao alta da contencao", "manual": "SCRAM manual",
    }

    def _log(self, msg, lvl="info"):
        self._evid += 1
        self.events.append({"id": self._evid, "t": round(self.sim_t, 1), "msg": msg, "lvl": lvl})
        if len(self.events) > 60:
            self.events = self.events[-60:]

    def _detect_events(self, di, loca_size):
        prev = self._prev_ev
        def rose(key, cur):
            was = prev.get(key, cur)
            prev[key] = cur
            return cur and not was
        def fell(key, cur):
            was = prev.get(key, cur)
            prev[key] = cur
            return was and not cur

        # trip do reator (com causa)
        cur_trip = di["reactor_tripped"]
        if rose("trip", cur_trip):
            causas = ", ".join(self._CAUSE_PT.get(c, c) for c in self._trip_causes) or "desconhecida"
            self._log(f"SCRAM do reator — causa: {causas}", "trip")
        if fell("trip_f", cur_trip):
            self._log("Reator rearmado (reset de trip)", "info")
        if rose("turb", di["turbine_tripped"]):
            self._log("Turbina desarmada", "warn")
        if rose("esfas", di["esfas_actuated"]):
            self._log("ESFAS atuado — salvaguardas de engenharia (sinal S)", "warn")
        if rose("cmt", di["cmt_injecting"]):
            self._log("CMT injetando agua borada no primario", "warn")
        if rose("accum", di["accum_injecting"]):
            self._log("Acumuladores injetando (baixa pressao)", "warn")
        if rose("prhr", di["prhr_actuated"]):
            self._log("PRHR atuado — remocao passiva de calor residual", "info")
        if rose("ads", di["ads_actuated"]):
            self._log("ADS atuado — despressurizacao automatica", "warn")
        if rose("blocked", di["safety_blocked"]):
            self._log("SALVAGUARDAS BLOQUEADAS — camada de seguranca inibida!", "trip")
        if fell("blocked_f", di["safety_blocked"]):
            self._log("Salvaguardas reabilitadas", "info")
        if rose("relief", di["przr_relief_open"]):
            self._log("Valvula de alivio do pressurizador aberta (alta pressao)", "warn")
        if rose("loca", loca_size > 0.0):
            self._log("LOCA iniciado — rompimento no primario (perda de refrigerante)", "trip")
        if fell("loca_f", loca_size > 0.0):
            self._log("LOCA cessado (rompimento isolado)", "info")
        if rose("damage", self.core.T_fuel > 1200.0):
            self._log("DANO AO NUCLEO — combustivel > 1200 C, liberacao de radiacao", "trip")
        if fell("auto_f", di["auto_control_active"]):
            self._log("Controle transferido para MANUAL — repartida na mao", "warn")
        if rose("auto_r", di["auto_control_active"]):
            self._log("Controle AUTOMATICO habilitado", "info")

    # -------------------------------------------------- cenarios iniciais
    def load_scenario(self, name):
        """Reconfigura a planta para uma condicao inicial realista. A repartida
        a partir de cada uma exige o procedimento real (nada e' facilitado)."""
        b, core, prim, poi, saf = self.bus, self.core, self.primary, self.poisons, self.safety
        # zera registro/derivadas
        self.events, self._evid, self._prev_ev, self.sim_t, self._trip_causes = [], 0, {}, 0.0, []
        self.reactor_period = 999.0
        self.esfas_armed = name in ("at_power", "hot_standby")   # P-11: só armado se pressurizado
        b.rho_poison = 0.0; b.cooling_factor = 1.0; b.si_flow = 0.0
        # salvaguardas cheias / contencao normal
        saf.cmt1 = saf.cmt2 = 100.0; saf.accum_press = C.ACCUM_PRESS_NOMINAL
        saf.prhr_flow = 0.0; saf.irwst = C.IRWST_LEVEL_NOMINAL; saf.ads_stage = 0; saf.si_flow = 0.0
        saf.cmt_injecting = saf.accum_injecting = saf.prhr_actuated = saf.ads_actuated = False
        saf.cont_press, saf.cont_rad, saf.cont_temp = 1.0, 0.1, 40.0
        prim.rcp_running = [True, True, True, True]; prim.przr_relief_open = False; prim.inventory = 100.0

        def set_power(n):
            core.n = n
            core.Cprec = [C.BETA[i] / (C.GEN_TIME * C.LAMBDA[i]) * n for i in range(6)]

        if name == "at_power":                       # operando a 100%
            set_power(1.0); core.T_fuel = 900.0; core.rod_pos = 75.0
            core.dh_fast, core.dh_slow = 0.6 * C.DECAY_HEAT_INIT, 0.4 * C.DECAY_HEAT_INIT
            prim.T_coolant, prim.flow, prim.przr_press, prim.przr_level, prim.boron = 305.0, 100.0, 155.0, 55.0, 800.0
            for g in self.sg: g.T_sg, g.level = 272.0, 55.0
            self.turbine.rpm, self.turbine.gen_power = 1800.0, 1117.0
            # inicio de ciclo (burnup=0): estado autoconsistente critico (rho=0)
            poi.I, poi.Xe, poi.Pm, poi.Sm, poi.bp, poi.burnup = C.XE_I_EQ, 1.0, 1.0, 1.0, 1.0, 0.0
            b.tripped, b.turbine_tripped = False, False
        elif name == "hot_standby":                  # parada quente (pos-trip)
            set_power(0.001); core.T_fuel = 290.0; core.rod_pos = 0.0
            core.dh_fast, core.dh_slow = 0.6 * 0.02, 0.4 * 0.02
            prim.T_coolant, prim.flow, prim.przr_press, prim.przr_level, prim.boron = 290.0, 100.0, 155.0, 55.0, 1000.0
            for g in self.sg: g.T_sg, g.level = 285.0, 55.0
            self.turbine.rpm, self.turbine.gen_power = 0.0, 0.0
            poi.I, poi.Xe, poi.Pm, poi.Sm, poi.bp, poi.burnup = C.XE_I_EQ, 1.0, 1.0, 1.0, 1.0, 0.0
            b.tripped, b.turbine_tripped = True, True
        else:                                        # cold_shutdown / first_startup
            fresh = (name == "first_startup")
            set_power(1e-8); core.T_fuel = 50.0; core.rod_pos = 0.0
            core.dh_fast = core.dh_slow = 0.0
            prim.rcp_running = [False, False, False, False]
            prim.T_coolant, prim.flow = 50.0, 0.0
            prim.przr_press, prim.przr_level = 28.0, 30.0
            prim.boron = C.BORON_FRESH_CORE if fresh else C.BORON_COLD_SHUTDOWN
            for g in self.sg: g.T_sg, g.level = 50.0, 30.0
            self.turbine.rpm, self.turbine.gen_power = 0.0, 0.0
            if fresh:
                poi.I, poi.Xe, poi.Pm, poi.Sm, poi.bp, poi.burnup = 0.0, 0.0, 0.0, 0.0, 1.0, 0.0
            else:
                poi.I, poi.Xe, poi.Pm, poi.Sm, poi.bp, poi.burnup = 0.0, 0.0, 1.0, 1.0, 1.0, 25.0
            b.tripped, b.turbine_tripped = True, True

        # sincroniza o barramento com o novo estado (evita transiente no 1o passo)
        b.T_coolant = prim.T_coolant
        b.T_hot = b.T_cold = prim.T_coolant
        b.core_dt = 0.0
        b.flow_frac = prim.flow / 100.0
        b.boron = prim.boron
        b.fission_frac = core.n
        b.decay_frac = core.dh_fast + core.dh_slow
        b.power_frac = max(core.n, b.decay_frac)
        b.P_th = C.RATED_MWTH * b.power_frac
        b.Q_core = b.Q_sg_total = b.Q_prhr = 0.0
        b.steam_flow_total = 0.0
        b.reactivity = 0.0
        for g in self.sg:
            g.pressure = C.SG_PRESS_NOMINAL + C.SG_SAT_SLOPE * (g.T_sg - C.SG_TEMP_NOMINAL)
            g.steam_flow = g.feed_flow = 0.0
            g.relief_open = False

        self._prev_power = core.n
        self._log(f"Cenario carregado: {name}", "info")

    def step(self, dt, cmd, sp, auto, time_scale=1.0, loca_size=0.0):
        bus = self.bus

        # ---- 0. Venenos (passo acelerado) e LOCA ---------------------------
        bus.rho_poison = self.poisons.step(self.core.n, dt * time_scale)
        self.primary.apply_loca(bus, dt, loca_size)

        # ---- 1. Demandas de atuador (auto vs manual/PLC) -------------------
        if auto:
            out = self.control.update(self, sp, dt)
            rod_demand = out["rod_demand_pct"]
            feed_valve = out["feed_valve"]
            turbine_valve = out["turbine_valve_pct"]
            heater, spray = out["heater"], out["spray"]
            self._auto_out = out            # exposto p/ engine devolver aos HR
        else:
            rod_demand = sp["dmd_rod_pct"]
            feed_valve = [sp["dmd_sg1_feed_valve_pct"], sp["dmd_sg2_feed_valve_pct"]]
            turbine_valve = sp["dmd_turbine_valve_pct"]
            heater, spray = cmd["cmd_przr_heater"], cmd["cmd_przr_spray"]
            self._auto_out = None

        # ---- 2. Atuadores diretos ------------------------------------------
        self.primary.apply_pumps(
            [cmd["cmd_rcp1_start"], cmd["cmd_rcp2_start"],
             cmd["cmd_rcp3_start"], cmd["cmd_rcp4_start"]],
            sp["dmd_rcp_speed_pct"],
        )
        self.primary.apply_boron(cmd["cmd_boron_charge"], cmd["cmd_boron_dilute"], dt)
        self.core.move_rods(rod_demand, dt, bus.tripped)
        feed_on = cmd["cmd_feed_pump_start"]

        # ---- 3. Fisica na ordem do fluxo de energia ------------------------
        self.core.step(bus, dt)

        q_sg = 0.0
        steam = 0.0
        for i, gv in enumerate(self.sg):
            q_sg += gv.step(bus, dt, feed_valve[i], turbine_valve, feed_on)
            steam += gv.steam_flow
        bus.Q_sg_total = q_sg
        bus.steam_flow_total = steam

        self.primary.step(bus, dt, heater, spray, sp["sp_przr_pressure_bar"], auto)
        self.turbine.step(bus, dt)

        # ---- 4. Protecao (RPS/ESFAS) e salvaguardas passivas ---------------
        di, esfas = protection.evaluate(self, cmd)
        self.safety.step(bus, dt, esfas, self.primary)

        # período do reator (tempo de e-folding da potência) — feedback ao operador
        n, prev = self.core.n, self._prev_power
        if n > 1e-9 and prev > 1e-9:
            r = math.log(n / prev)
            self.reactor_period = max(-999.0, min(999.0, dt / r)) if abs(r) > 1e-5 else 999.0
        else:
            self.reactor_period = 999.0
        self._prev_power = n

        self.sim_t += dt
        self._detect_events(di, loca_size)
        return di

    # -------------------------------------------------------- leitura sensores
    def sensors(self):
        b, core, prim, poi = self.bus, self.core, self.primary, self.poisons
        s1, s2, turb, saf = self.sg[0], self.sg[1], self.turbine, self.safety
        return {
            "reactor_power_pct": core.n * 100.0,
            "neutron_flux_pct": core.n * 100.0,
            "fuel_temp_c": core.T_fuel,
            "reactivity_pcm": core.reactivity * 1e5,
            "reactor_period_s": self.reactor_period,
            "decay_heat_pct": b.decay_frac * 100.0,
            "rod_position_pct": core.rod_pos,
            "xenon_worth_pcm": poi.rho_xe * 1e5,
            "xenon_pct": poi.Xe * 100.0,
            "iodine_pct": poi.I * 100.0,
            "samarium_worth_pcm": poi.rho_sm * 1e5,
            "burnable_poison_pct": poi.bp * 100.0,
            "burnup_pct": poi.burnup,
            "primary_inventory_pct": prim.inventory,
            "coolant_tavg_c": prim.T_coolant,
            "coolant_thot_c": b.T_hot,
            "coolant_tcold_c": b.T_cold,
            "core_dt_c": b.core_dt,
            "rcp_flow_pct": prim.flow,
            "przr_pressure_bar": prim.przr_press,
            "przr_level_pct": prim.przr_level,
            "boron_ppm": prim.boron,
            "sg1_pressure_bar": s1.pressure,
            "sg1_level_pct": s1.level,
            "sg1_steam_flow_kgs": s1.steam_flow,
            "sg1_feed_flow_kgs": s1.feed_flow,
            "sg2_pressure_bar": s2.pressure,
            "sg2_level_pct": s2.level,
            "sg2_steam_flow_kgs": s2.steam_flow,
            "sg2_feed_flow_kgs": s2.feed_flow,
            "turbine_rpm": turb.rpm,
            "gen_power_mwe": turb.gen_power,
            "cmt1_level_pct": saf.cmt1,
            "cmt2_level_pct": saf.cmt2,
            "accum_press_bar": saf.accum_press,
            "prhr_flow_pct": saf.prhr_flow,
            "irwst_level_pct": saf.irwst,
            "ads_stage": saf.ads_stage,
            "si_flow_kgs": saf.si_flow,
            "containment_press_bar": saf.cont_press,
            "containment_rad_msvh": saf.cont_rad,
            "containment_temp_c": saf.cont_temp,
        }
