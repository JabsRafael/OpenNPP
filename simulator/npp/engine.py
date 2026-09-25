"""
Engine da simulacao: integra planta modular (fisica + controle + protecao) e
mantem o datastore Modbus como fonte unica de estado (mesma tabela servida na
rede OT e lida pela HMI/API). Roda em laco de (quase) tempo real.
"""

import threading
import time

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)

from . import config as C
from .iomap import (
    COILS, DISCRETE_INPUTS, HOLDING_REGISTERS, INPUT_REGISTERS,
    CO_BY_KEY, HR_BY_KEY, decode, encode,
)
from .plant import Plant

# 1=coils | 2=discrete inputs | 3=holding regs | 4=input regs
FC_COIL, FC_DI, FC_HR, FC_IR = 1, 2, 3, 4


class SimEngine:
    def __init__(self):
        self.plant = Plant()
        self.lock = threading.Lock()
        self.t = 0.0                 # segundos reais de simulacao (dinamica rapida)
        self.reactor_seconds = 0.0   # relogio do reator (acelerado p/ venenos)
        self.time_scale = C.TIME_SCALE_DEFAULT
        self.loca_size = 0.0         # 0..1 area de rompimento (LOCA)
        self.sim_speed = 1           # passos de fisica por tick real (planta inteira)
        self.rod_motion = None       # alavanca das barras: None | "in" | "out"
        self._rod_motion_t = 0.0     # ultimo "ainda segurando" (homem-morto)
        self.running = True
        self._was_tripped = False

        self.slave = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0] * len(DISCRETE_INPUTS)),
            co=ModbusSequentialDataBlock(0, [0] * len(COILS)),
            hr=ModbusSequentialDataBlock(0, [0] * len(HOLDING_REGISTERS)),
            ir=ModbusSequentialDataBlock(0, [0] * len(INPUT_REGISTERS)),
            zero_mode=True,
        )
        self.context = ModbusServerContext(slaves=self.slave, single=True)
        self.set_scenario("at_power")   # boot em MANUAL (auto e' opt-in)

    SCENARIOS = ("at_power", "hot_standby", "cold_shutdown", "first_startup")

    def set_scenario(self, name):
        if name not in self.SCENARIOS:
            raise ValueError(f"cenario invalido: {name}")
        with self.lock:
            p = self.plant
            p.load_scenario(name)
            self.scenario = name
            self.t = 0.0
            self.reactor_seconds = 0.0
            self.loca_size = 0.0
            self._was_tripped = p.bus.tripped
            at_power = p.core.n > 0.5
            hr = {
                "sp_power_pct": 100.0 if at_power else 0.0, "dmd_rod_pct": p.core.rod_pos,
                "dmd_rcp_speed_pct": 100.0, "sp_przr_pressure_bar": 155.0,
                "sp_przr_level_pct": 55.0, "sp_boron_ppm": p.primary.boron,
                "dmd_turbine_valve_pct": round(p.core.n * 100.0, 1), "dmd_turbine_load_mwe": C.RATED_MWE,
                "sp_sg1_level_pct": 55.0, "dmd_sg1_feed_valve_pct": (100.0 if at_power else 0.0),
                "sp_sg2_level_pct": 55.0, "dmd_sg2_feed_valve_pct": (100.0 if at_power else 0.0),
            }
            for key, val in hr.items():
                pt = HR_BY_KEY[key]
                self.slave.setValues(FC_HR, pt.addr, [encode(val, pt)])
            for pt in COILS:                       # tudo desligado (AUTO opt-in)
                self.slave.setValues(FC_COIL, pt.addr, [0])
            for i, key in enumerate(("cmd_rcp1_start", "cmd_rcp2_start",
                                     "cmd_rcp3_start", "cmd_rcp4_start")):
                self.slave.setValues(FC_COIL, CO_BY_KEY[key].addr,
                                     [1 if p.primary.rcp_running[i] else 0])
            if at_power:
                # planta operando esta' sob controle AUTOMATICO (realista); os
                # cenarios de PARTIDA (frio/parada quente) iniciam em MANUAL.
                self.slave.setValues(FC_COIL, CO_BY_KEY["cmd_feed_pump_start"].addr, [1])
                self.slave.setValues(FC_COIL, CO_BY_KEY["cmd_auto_control"].addr, [1])

    # coils momentaneos: o comando e' consumido apos um passo (nao fica latchado)
    # (SCRAM e desarme da turbina sao botoeiras: o trip fica travado no
    # disjuntor/turbina ate' o rearme, nao no botao)
    MOMENTARY = ("cmd_reset_trip", "cmd_block_sr_trip", "cmd_block_lowpower_trips",
                 "cmd_manual_scram", "cmd_turbine_trip")

    def _read_cmd_sp(self):
        coils = self.slave.getValues(FC_COIL, 0, len(COILS))
        hr = self.slave.getValues(FC_HR, 0, len(HOLDING_REGISTERS))
        cmd = {p.key: bool(coils[p.addr]) for p in COILS}
        sp = {p.key: decode(hr[p.addr], p) for p in HOLDING_REGISTERS}
        return cmd, sp

    ROD_DEADMAN_S = 0.8   # sem confirmacao da HMI por este tempo -> barras param

    def _apply_rod_lever(self, dt):
        """Alavanca IN-HOLD-OUT: enquanto segurada, a demanda fica logo a frente
        da posicao real (as barras andam na velocidade do mecanismo e a demanda
        mostrada acompanha a posicao, sem saltar para 0/100%)."""
        if self.rod_motion is None:
            return
        pt = HR_BY_KEY["dmd_rod_pct"]
        pos = self.plant.core.rod_pos
        if time.monotonic() - self._rod_motion_t > self.ROD_DEADMAN_S or self.plant.bus.tripped:
            self.rod_motion = None
            self.slave.setValues(FC_HR, pt.addr, [encode(pos, pt)])
            return
        lead = C.ROD_SPEED_MANUAL * dt * 1.5
        target = pos + lead if self.rod_motion == "out" else pos - lead
        self.slave.setValues(FC_HR, pt.addr, [encode(max(0.0, min(100.0, target)), pt)])

    def step_once(self, dt=C.DT):
        with self.lock:
            self._apply_rod_lever(dt)
            cmd, sp = self._read_cmd_sp()
            auto = cmd["cmd_auto_control"]

            di = self.plant.step(dt, cmd, sp, auto, self.time_scale, self.loca_size)
            for key in self.MOMENTARY:
                if cmd[key]:
                    self.slave.setValues(FC_COIL, CO_BY_KEY[key].addr, [0])
            # AO TRIPAR -> transfere para MANUAL: a repartida e' feita na mao, com
            # todas as dificuldades reais (imita um reator de verdade).
            if di["reactor_tripped"] and not self._was_tripped:
                self.slave.setValues(FC_COIL, CO_BY_KEY["cmd_auto_control"].addr, [0])
            self._was_tripped = di["reactor_tripped"]

            # demandas impostas pela planta (controle AUTO, barras no fundo apos
            # o trip, valvulas fechadas por desarme/isolamento) -> HR (p/ HMI/CLP)
            for key, val in self.plant.hr_writeback.items():
                p = HR_BY_KEY[key]
                self.slave.setValues(FC_HR, p.addr, [encode(val, p)])

            self.slave.setValues(FC_DI, 0,
                                 [1 if di[p.key] else 0 for p in DISCRETE_INPUTS])
            sens = self.plant.sensors()
            self.slave.setValues(FC_IR, 0,
                                 [encode(sens[p.key], p) for p in INPUT_REGISTERS])
            self.t += dt
            self.reactor_seconds += dt * self.time_scale

    def snapshot(self):
        with self.lock:
            ir = self.slave.getValues(FC_IR, 0, len(INPUT_REGISTERS))
            di = self.slave.getValues(FC_DI, 0, len(DISCRETE_INPUTS))
            co = self.slave.getValues(FC_COIL, 0, len(COILS))
            hr = self.slave.getValues(FC_HR, 0, len(HOLDING_REGISTERS))
        return {
            "t": round(self.t, 1),
            "rh": round(self.reactor_seconds / 3600.0, 3),   # relogio do reator (h)
            "ts": self.time_scale,
            "loca": round(self.loca_size, 2),
            "speed": self.sim_speed,
            "rod_motion": self.rod_motion,
            "tref": round(self.plant.control.tref, 1),
            "reset_blockers": [d for _, _, d in self.blockers()] if self.plant.bus.tripped else [],
            "scenario": self.scenario,
            "events": list(self.plant.events),
            "ir": {p.key: round(decode(ir[p.addr], p), 2) for p in INPUT_REGISTERS},
            "di": {p.key: bool(di[p.addr]) for p in DISCRETE_INPUTS},
            "co": {p.key: bool(co[p.addr]) for p in COILS},
            "hr": {p.key: round(decode(hr[p.addr], p), 2) for p in HOLDING_REGISTERS},
        }

    def set_coil(self, key, value):
        p = CO_BY_KEY[key]
        with self.lock:
            self.slave.setValues(FC_COIL, p.addr, [1 if value else 0])

    def set_hr(self, key, value):
        p = HR_BY_KEY[key]
        with self.lock:
            self.slave.setValues(FC_HR, p.addr, [encode(float(value), p)])

    def step_hr(self, key, delta):
        """Incrementa um setpoint/demanda (botoes da HMI) de forma atomica."""
        p = HR_BY_KEY[key]
        with self.lock:
            cur = decode(self.slave.getValues(FC_HR, p.addr, 1)[0], p)
            new = max(p.lo, min(p.hi, cur + float(delta)))
            self.slave.setValues(FC_HR, p.addr, [encode(new, p)])
        return new

    def rod_lever(self, direction):
        """Alavanca IN-HOLD-OUT das barras: 'out'/'in' movem enquanto a HMI
        repetir o comando (homem-morto de 0,8 s); 'hold' para onde estiver."""
        if direction not in ("in", "out", "hold"):
            raise ValueError("direcao invalida (use in/out/hold)")
        with self.lock:
            if direction == "hold":
                self.rod_motion = None
                p = HR_BY_KEY["dmd_rod_pct"]
                self.slave.setValues(FC_HR, p.addr, [encode(self.plant.core.rod_pos, p)])
            else:
                self.rod_motion = direction
                self._rod_motion_t = time.monotonic()

    def blockers(self):
        cmd, _ = self._read_cmd_sp()
        return self.plant.reset_blockers(cmd)

    def request_reset(self):
        """Rearme pedido pela HMI: solta o SCRAM manual e pulsa o reset do trip.
        Devolve se o rearme vai passar e, se nao, POR QUE (condicoes de trip
        presentes, com valor medido e setpoint)."""
        with self.lock:
            self.slave.setValues(FC_COIL, CO_BY_KEY["cmd_manual_scram"].addr, [0])
            tripped = self.plant.bus.tripped
            found = self.blockers()
            reasons = [{"cause": k, "label": lbl, "detail": d} for k, lbl, d in found]
            if reasons:
                # resposta autoritativa: negado agora -> nao pulsa o reset
                if tripped:
                    self.plant._log("Rearme NEGADO — condição de trip presente: "
                                    + "; ".join(d for _, _, d in found), "warn")
            else:
                self.slave.setValues(FC_COIL, CO_BY_KEY["cmd_reset_trip"].addr, [1])
        return {"tripped": tripped, "reset": not reasons, "reasons": reasons}

    def set_speed(self, value):
        v = int(value)
        if v not in C.SIM_SPEEDS:
            raise ValueError(f"velocidade invalida: {v} (use {C.SIM_SPEEDS})")
        self.sim_speed = v

    def set_time_scale(self, value):
        self.time_scale = max(1.0, min(C.TIME_SCALE_MAX, float(value)))

    def set_loca(self, value):
        self.loca_size = max(0.0, min(1.0, float(value)))

    def run(self):
        next_t = time.monotonic()
        while self.running:
            for _ in range(self.sim_speed):
                self.step_once(C.DT)
            if C.REALTIME:
                next_t += C.DT
                delay = next_t - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_t = time.monotonic()

    def start_thread(self):
        th = threading.Thread(target=self.run, daemon=True, name="sim-engine")
        th.start()
        return th
