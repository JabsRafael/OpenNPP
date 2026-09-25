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

from math import log10

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
from .controllers.steam_dump import SteamDumpControl
from .water import psat


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
        self.steam_dump = SteamDumpControl()
        self.reactor_period = 999.0   # s (positivo=subindo, negativo=descendo)
        # registro de eventos (para o operador entender o que aconteceu)
        self.events = []
        self._evid = 0
        self._prev_ev = {}
        self.sim_t = 0.0
        self._trip_causes = []
        self._trip_details = []
        self._reset_denied = None
        self._block_denied = []
        self._block_events = []
        self._feed_isol_p4 = False
        self.esfas_armed = True   # permissivo P-11 (armado quando pressurizado)
        self.sr_trip_blocked = True          # em potencia: bloqueios ja' feitos
        self.lowpower_trips_blocked = True
        self.rod_withdrawal_block = False
        self._critical = False
        self.hr_writeback = {}    # demandas que a planta impoe aos HR (engine grava)

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
            causas = "; ".join(self._trip_details) or "desconhecida"
            self._log(f"SCRAM do reator — {causas}", "trip")
        if fell("trip_f", cur_trip):
            self._log("Reator rearmado (reset de trip)", "info")
        if rose("turb", di["turbine_tripped"]):
            self._log("Turbina desarmada", "trip")
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
            self._log("SALVAGUARDAS BLOQUEADAS — camada de seguranca inibida!", "warn")
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
            load = self.turbine.load_frac * 100.0
            if load < C.C5_LOAD:
                self._log(f"Controle AUTOMATICO habilitado com carga {load:.0f}% < {C.C5_LOAD:.0f}% "
                          "(C-5): barras NAO retiram sozinhas; a turbina sobe em rampa de 5%/min", "warn")
            else:
                self._log("Controle AUTOMATICO habilitado — turbina em rampa de 5%/min, "
                          "barras no programa de Tavg", "info")
        if self._reset_denied:
            motivos = "; ".join(d for _, _, d in self._reset_denied)
            self._log(f"Rearme NEGADO — condição de trip presente: {motivos}", "warn")
        for msg in self._block_denied:
            self._log(msg[:1].upper() + msg[1:], "warn")
        for msg in getattr(self, "_block_events", []):
            self._log(msg, "info")
        if rose("p6", di["p6_permissive"]):
            self._log("P-6 presente (IR > 1e-10 A) — bloqueie o trip da faixa-fonte antes de 1e5 cps", "info")
        if fell("p6_f", di["p6_permissive"]):
            self._log("P-6 ausente — trip da faixa-fonte de volta em serviço", "info")
        if rose("p10", di["p10_permissive"]):
            self._log("P-10 presente (>10%) — bloqueie os trips de IR/PR-baixo antes de 25%", "info")
        if fell("p10_f", di["p10_permissive"]):
            self._log("P-10 ausente — trips de IR/PR-baixo de volta em serviço", "info")
        if rose("srb", di["sr_trip_blocked"]):
            self._log("Trip da faixa-fonte bloqueado (P-6)", "info")
        if rose("lpb", di["lowpower_trips_blocked"]):
            self._log("Trips de IR/PR-baixo bloqueados (P-10)", "info")
        if rose("rodblk", di["rod_withdrawal_block"]):
            self._log("Bloqueio de retirada de barras (C-1/C-2) — potência alta", "warn")
        if rose("fwisol", di["feedwater_isolated"]):
            self._log("Alimentação principal ISOLADA (P-4/P-14) — SFW assume o nível dos GVs", "warn")
        if fell("fwisol_f", di["feedwater_isolated"]):
            self._log("Isolamento da alimentação principal removido", "info")
        if rose("dump", di["steam_dump_active"]):
            self._log("Despejo de vapor ao condensador atuando (segura Tavg)", "info")
        # criticalidade na partida (histerese: +5 pcm liga, -50 pcm desliga)
        rho = self.core.reactivity
        if rho > 5e-5 and self.core.n < 0.05 and not self.bus.tripped:
            self._critical = True
        elif rho < -5e-4:
            self._critical = False
        if rose("crit", self._critical):
            self._log(f"Reator CRÍTICO — barras em {self.core.rod_steps:.0f} passos, "
                      f"boro {self.primary.boron:.0f} ppm", "info")

    # -------------------------------------------------- cenarios iniciais
    def load_scenario(self, name):
        """Reconfigura a planta para uma condicao inicial realista. A repartida
        a partir de cada uma exige o procedimento real (nada e' facilitado)."""
        b, core, prim, poi, saf = self.bus, self.core, self.primary, self.poisons, self.safety
        # zera registro/derivadas
        self.events, self._evid, self._prev_ev, self.sim_t, self._trip_causes = [], 0, {}, 0.0, []
        self._trip_details, self._reset_denied, self._block_denied = [], None, []
        self._feed_isol_p4, self._critical = False, False
        self.reactor_period = 999.0
        self.esfas_armed = name in ("at_power", "hot_standby")   # P-11: só armado se pressurizado
        at_power = name == "at_power"
        self.sr_trip_blocked = self.lowpower_trips_blocked = at_power
        b.rho_poison = 0.0; b.cooling_factor = 1.0; b.si_flow = 0.0
        b.steam_dump_frac = 0.0; b.feed_isolated = False
        self.steam_dump.frac = 0.0
        # salvaguardas cheias / contencao normal
        saf.reset()
        b.Q_ads = b.Q_break = b.ads_mass_flow = 0.0
        prim.rcp_running = [True, True, True, True]; prim.przr_relief_open = False; prim.inventory = 100.0
        prim.break_flow = prim.cvs_flow = 0.0
        self.control.rod.rod_demand = C.ROD_POS_REF
        self.control.turbine.track(100.0 if at_power else 0.0, 100.0 if at_power else 0.0)

        if at_power:                                 # operando a 100%
            core.set_state(1.0, C.FUEL_TEMP_REF, C.ROD_POS_REF)
            prim.T_coolant, prim.flow, prim.przr_press, prim.przr_level, prim.boron = 305.0, 100.0, 155.0, 55.0, 800.0
            for g in self.sg: g.T_sg, g.level = C.SG_TEMP_NOMINAL, 55.0
            self.turbine.rpm, self.turbine.gen_power, self.turbine.load_frac = 1800.0, 1117.0, 1.0
            # inicio de ciclo (burnup=0): estado autoconsistente critico (rho=0)
            poi.I, poi.Xe, poi.Pm, poi.Sm, poi.bp, poi.burnup = C.XE_I_EQ, 1.0, 1.0, 1.0, 1.0, 0.0
            b.tripped, b.turbine_tripped = False, False
        elif name == "hot_standby":                  # parada quente, ~1 h apos trip de 100%
            age = 3600.0
            core.set_state(1e-9, C.T_NOLOAD, 0.0, decay_age_s=age)
            prim.T_coolant, prim.flow, prim.przr_press = C.T_NOLOAD, 100.0, 155.0
            prim.przr_level = C.PRZR_LEVEL_NOLOAD
            prim.boron = 880.0                       # ECP ~65% das barras (~150 passos)
            for g in self.sg: g.T_sg, g.level = C.T_NOLOAD - 0.5, 50.0
            self.turbine.rpm, self.turbine.gen_power, self.turbine.load_frac = 0.0, 0.0, 0.0
            poi.I, poi.Xe, poi.Pm, poi.Sm, poi.bp, poi.burnup = C.XE_I_EQ, 1.0, 1.0, 1.0, 1.0, 0.0
            for _ in range(36):                      # 1 h de venenos sem fluxo (Xe subindo)
                poi.step(0.0, age / 36)
            b.tripped, b.turbine_tripped = True, True
            self._feed_isol_p4 = True
        else:                                        # cold_shutdown / first_startup
            fresh = (name == "first_startup")
            # parada fria ~30 dias apos desligamento (calor residual ~0,15%);
            # nucleo novo nao tem produtos de fissao -> sem calor de decaimento
            core.set_state(1e-9, 50.0, 0.0, decay_age_s=float("inf") if fresh else 30 * 86400.0)
            prim.rcp_running = [False, False, False, False]
            prim.T_coolant, prim.flow = 50.0, 0.0
            prim.przr_press, prim.przr_level = 28.0, C.PRZR_LEVEL_NOLOAD
            prim.boron = C.BORON_FRESH_CORE if fresh else C.BORON_COLD_SHUTDOWN
            for g in self.sg: g.T_sg, g.level = 50.0, 50.0
            self.turbine.rpm, self.turbine.gen_power, self.turbine.load_frac = 0.0, 0.0, 0.0
            if fresh:
                poi.I, poi.Xe, poi.Pm, poi.Sm, poi.bp, poi.burnup = 0.0, 0.0, 0.0, 0.0, 1.0, 0.0
            else:
                poi.I, poi.Xe, poi.Pm, poi.Sm, poi.bp, poi.burnup = 0.0, 0.0, 1.0, 1.0, 1.0, 25.0
            b.tripped, b.turbine_tripped = True, True

        # reatividade dos venenos coerente com o estado carregado
        b.rho_poison = poi.step(0.0, 0.0)
        b.burnup = poi.burnup
        # sincroniza o barramento com o novo estado (evita transiente no 1o passo)
        b.T_coolant = prim.T_coolant
        b.T_hot = b.T_cold = prim.T_coolant
        b.core_dt = 0.0
        b.flow_frac = prim.flow / 100.0
        b.boron = prim.boron
        if not at_power:                             # subcritico com fonte (equilibrio)
            core.settle_subcritical(core.compute_reactivity(prim.T_coolant, prim.boron,
                                                            b.rho_poison, poi.burnup))
        core.reactivity = core.compute_reactivity(prim.T_coolant, prim.boron, b.rho_poison, poi.burnup)
        b.fission_frac = core.n
        b.decay_frac = sum(core.decay)
        b.power_frac = (1.0 - C.DECAY_HEAT_INIT) * core.n + b.decay_frac
        b.P_th = C.RATED_MWTH * b.power_frac
        b.Q_core = b.Q_sg_total = b.Q_prhr = 0.0
        b.steam_flow_total = b.turbine_steam = 0.0
        b.reactivity = core.reactivity
        b.feed_isolated = self._feed_isol_p4
        for g in self.sg:
            g.pressure = psat(g.T_sg)
            g.steam_flow = g.feed_flow = g.sfw_flow = g.turbine_steam = g.dump_steam = 0.0
            g.relief_open = False

        self._log(f"Cenario carregado: {name}", "info")

    def step(self, dt, cmd, sp, auto, time_scale=1.0, loca_size=0.0):
        bus = self.bus
        self.hr_writeback = {}

        # ---- 0. Venenos (passo acelerado) e LOCA ---------------------------
        bus.rho_poison = self.poisons.step(self.core.n, dt * time_scale)
        bus.burnup = self.poisons.burnup
        self.primary.apply_loca(bus, dt, loca_size, self.safety.cont_press)

        # ---- 1. Demandas de atuador (auto vs manual/PLC) -------------------
        if auto:
            out = self.control.update(self, sp, dt)
            rod_demand = out["rod_demand_pct"]
            feed_valve = out["feed_valve"]
            turbine_valve = out["turbine_valve_pct"]
            self.hr_writeback.update({
                "dmd_rod_pct": rod_demand, "dmd_turbine_valve_pct": turbine_valve,
                "dmd_sg1_feed_valve_pct": feed_valve[0], "dmd_sg2_feed_valve_pct": feed_valve[1],
            })
        else:
            rod_demand = sp["dmd_rod_pct"]
            feed_valve = [sp["dmd_sg1_feed_valve_pct"], sp["dmd_sg2_feed_valve_pct"]]
            turbine_valve = sp["dmd_turbine_valve_pct"]
            # manual: o controlador automatico acompanha (transferencia sem salto)
            self.control.rod.rod_demand = self.core.rod_pos
            self.control.turbine.track(self.turbine.load_frac * 100.0,
                                       0.0 if bus.turbine_tripped else turbine_valve)

        # ---- 2. Atuadores diretos ------------------------------------------
        self.primary.apply_pumps(
            [cmd["cmd_rcp1_start"], cmd["cmd_rcp2_start"],
             cmd["cmd_rcp3_start"], cmd["cmd_rcp4_start"]],
            sp["dmd_rcp_speed_pct"],
        )
        self.primary.apply_boron(cmd["cmd_boron_charge"], cmd["cmd_boron_dilute"], dt)
        self.core.move_rods(rod_demand, dt, bus.tripped, auto, self.rod_withdrawal_block)
        feed_on = cmd["cmd_feed_pump_start"]
        # estacoes AUTO/MANUAL proprias de cada subsistema (independentes do modo
        # mestre, como na sala de controle): pressao e nivel do PZR, despejo, SFW
        press_auto = not cmd.get("cmd_przr_press_manual")
        heater, spray = cmd["cmd_przr_heater"], cmd["cmd_przr_spray"]
        self.primary.cvs_manual = sp["dmd_cvs_flow_kgs"] if cmd.get("cmd_cvs_manual") else None
        dump_man = sp["dmd_steam_dump_pct"] if cmd.get("cmd_steam_dump_manual") else None
        sfw_man = sp["dmd_sfw_pct"] if cmd.get("cmd_sfw_manual") else None
        bus.steam_dump_frac = self.steam_dump.update(
            self.primary.T_coolant, self.turbine.load_frac, bus.turbine_tripped, dt, dump_man)

        # ---- 3. Fisica na ordem do fluxo de energia ------------------------
        self.core.step(bus, dt)

        q_sg = 0.0
        steam = turb_steam = 0.0
        for i, gv in enumerate(self.sg):
            q_sg += gv.step(bus, dt, feed_valve[i], turbine_valve, feed_on, sfw_man)
            steam += gv.steam_flow
            turb_steam += gv.turbine_steam
        bus.Q_sg_total = q_sg
        bus.steam_flow_total = steam
        bus.turbine_steam = turb_steam

        self.primary.step(bus, dt, heater, spray, sp["sp_przr_pressure_bar"], press_auto)
        self.turbine.step(bus, dt)

        # ---- 4. Protecao (RPS/ESFAS) e salvaguardas passivas ---------------
        di, esfas = protection.evaluate(self, cmd)
        self.safety.step(bus, dt, esfas, self.primary)

        # ---- 5. Demandas que acompanham o estado real (anti-salto) ---------
        # estacoes em AUTO: a demanda manual mostra a saida real do controlador
        # (ao passar para MANUAL, nada salta)
        if dump_man is None:
            self.hr_writeback["dmd_steam_dump_pct"] = bus.steam_dump_frac * 100.0
        if sfw_man is None:
            self.hr_writeback["dmd_sfw_pct"] = (self.sg[0].sfw_flow + self.sg[1].sfw_flow) \
                / (2.0 * C.SFW_MAX_FLOW) * 100.0
        if self.primary.cvs_manual is None:
            self.hr_writeback["dmd_cvs_flow_kgs"] = self.primary.cvs_flow
        # Reator desarmado: a demanda de barras acompanha as barras (no fundo) —
        # ao rearmar elas NAO voltam sozinhas para a posicao antiga.
        if bus.tripped:
            self.hr_writeback["dmd_rod_pct"] = self.core.rod_pos
        # Turbina desarmada: valvulas de admissao fecham (demanda vai a zero).
        if bus.turbine_tripped:
            self.hr_writeback["dmd_turbine_valve_pct"] = 0.0
        # Alimentacao principal isolada: valvulas reguladoras fecham.
        if bus.feed_isolated:
            self.hr_writeback["dmd_sg1_feed_valve_pct"] = 0.0
            self.hr_writeback["dmd_sg2_feed_valve_pct"] = 0.0

        self.reactor_period = self.core.period
        self.sim_t += dt
        self._detect_events(di, loca_size)
        return di

    def reset_blockers(self, cmd):
        """O que impede o rearme agora (lista de (causa, rotulo, descricao))."""
        return protection.reset_blockers(self, cmd)

    # -------------------------------------------------------- leitura sensores
    def sensors(self):
        b, core, prim, poi = self.bus, self.core, self.primary, self.poisons
        s1, s2, turb, saf = self.sg[0], self.sg[1], self.turbine, self.safety
        rp = core.rho_parts
        return {
            "reactor_power_pct": core.n * 100.0,
            "neutron_flux_pct": core.n * 100.0,
            "thermal_power_pct": b.P_th / C.RATED_MWTH * 100.0,
            "fuel_temp_c": core.T_fuel,
            "reactivity_pcm": core.reactivity * 1e5,
            "reactor_period_s": self.reactor_period,
            "startup_rate_dpm": core.sur_dpm,
            "sr_log_cps": log10(max(core.sr_cps, 0.1)),
            "ir_log_amps": log10(max(core.ir_amps, 1e-12)),
            "decay_heat_pct": b.decay_frac * 100.0,
            "rod_position_pct": core.rod_pos,
            "rod_steps": core.rod_steps,
            "mtc_pcm_per_c": core.mtc_pcm(prim.T_coolant, prim.boron, poi.burnup),
            "rod_worth_pcm": rp.get("rod", 0.0),
            "doppler_worth_pcm": rp.get("doppler", 0.0),
            "moderator_worth_pcm": rp.get("mod", 0.0),
            "boron_worth_pcm": rp.get("boron", 0.0),
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
            "steam_dump_pct": b.steam_dump_frac * 100.0,
            "sfw_flow_kgs": s1.sfw_flow + s2.sfw_flow,
            "cvs_flow_kgs": prim.cvs_flow,
            "przr_level_program_pct": prim.level_program,
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
