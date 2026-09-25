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

        self.slave = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0] * len(DISCRETE_INPUTS)),
            co=ModbusSequentialDataBlock(0, [0] * len(COILS)),
            hr=ModbusSequentialDataBlock(0, [0] * len(HOLDING_REGISTERS)),
            ir=ModbusSequentialDataBlock(0, [0] * len(INPUT_REGISTERS)),
            zero_mode=True,
        )
        self.context = ModbusServerContext(slaves=self.slave, single=True)
        self._init_defaults()

    def _init_defaults(self):
        hr_defaults = {
            "sp_power_pct": 100.0, "dmd_rod_pct": C.ROD_POS_REF,
            "dmd_rcp_speed_pct": 100.0, "sp_przr_pressure_bar": C.PRZR_PRESS_NOMINAL,
            "sp_przr_level_pct": C.PRZR_LEVEL_NOMINAL, "sp_boron_ppm": C.BORON_REF,
            "dmd_turbine_valve_pct": 100.0, "dmd_turbine_load_mwe": C.RATED_MWE,
            "sp_sg1_level_pct": C.SG_LEVEL_NOMINAL, "dmd_sg1_feed_valve_pct": 100.0,
            "sp_sg2_level_pct": C.SG_LEVEL_NOMINAL, "dmd_sg2_feed_valve_pct": 100.0,
        }
        for key, val in hr_defaults.items():
            p = HR_BY_KEY[key]
            self.slave.setValues(FC_HR, p.addr, [encode(val, p)])
        for key in ("cmd_rcp1_start", "cmd_rcp2_start", "cmd_rcp3_start",
                    "cmd_rcp4_start", "cmd_feed_pump_start", "cmd_auto_control"):
            self.slave.setValues(FC_COIL, CO_BY_KEY[key].addr, [1])

    def step_once(self, dt=C.DT):
        with self.lock:
            coils = self.slave.getValues(FC_COIL, 0, len(COILS))
            hr = self.slave.getValues(FC_HR, 0, len(HOLDING_REGISTERS))
            cmd = {p.key: bool(coils[p.addr]) for p in COILS}
            sp = {p.key: decode(hr[p.addr], p) for p in HOLDING_REGISTERS}
            auto = cmd["cmd_auto_control"]

            di = self.plant.step(dt, cmd, sp, auto, self.time_scale, self.loca_size)

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
