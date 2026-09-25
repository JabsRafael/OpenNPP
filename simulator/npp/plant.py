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

        self.primary.step(bus, dt, heater, spray)
        self.turbine.step(bus, dt)

        # ---- 4. Protecao (RPS/ESFAS) e salvaguardas passivas ---------------
        di, esfas = protection.evaluate(self, cmd)
        self.safety.step(bus, dt, esfas, self.primary)

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
