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
                "sp_power_pct": 100.0, "dmd_rod_pct": p.core.rod_pos,
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

    def step_once(self, dt=C.DT):
        with self.lock:
            coils = self.slave.getValues(FC_COIL, 0, len(COILS))
            hr = self.slave.getValues(FC_HR, 0, len(HOLDING_REGISTERS))
            cmd = {p.key: bool(coils[p.addr]) for p in COILS}
            sp = {p.key: decode(hr[p.addr], p) for p in HOLDING_REGISTERS}
            auto = cmd["cmd_auto_control"]

            di = self.plant.step(dt, cmd, sp, auto, self.time_scale, self.loca_size)
            # reset de trip e' momentaneo: consome o comando para nao ficar latchado
            if cmd["cmd_reset_trip"]:
                self.slave.setValues(FC_COIL, CO_BY_KEY["cmd_reset_trip"].addr, [0])
            # AO TRIPAR -> transfere para MANUAL: a repartida e' feita na mao, com
            # todas as dificuldades reais (imita um reator de verdade).
            if di["reactor_tripped"] and not self._was_tripped:
                self.slave.setValues(FC_COIL, CO_BY_KEY["cmd_auto_control"].addr, [0])
            self._was_tripped = di["reactor_tripped"]

            # devolve demandas calculadas pelo controle auto aos HR (p/ HMI)
            if auto and self.plant._auto_out is not None:
                out = self.plant._auto_out
                writeback = {
                    "dmd_rod_pct": out["rod_demand_pct"],
                    "dmd_turbine_valve_pct": out["turbine_valve_pct"],
                    "dmd_sg1_feed_valve_pct": out["feed_valve"][0],
                    "dmd_sg2_feed_valve_pct": out["feed_valve"][1],
                }
                for key, val in writeback.items():
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

    def set_time_scale(self, value):
        self.time_scale = max(1.0, min(C.TIME_SCALE_MAX, float(value)))

    def set_loca(self, value):
        self.loca_size = max(0.0, min(1.0, float(value)))

    def run(self):
        next_t = time.monotonic()
        while self.running:
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
