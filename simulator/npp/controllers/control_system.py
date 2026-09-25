"""
Sistema de Controle da planta — agrega os controladores individuais.

Espelha a organizacao real: controle de barras (potencia), pressurizador,
turbina e DUAS malhas de nivel de gerador de vapor (uma por GV). Quando o modo
automatico esta ativo, produz as demandas de atuador. Em modo manual/PLC, este
bloco fica inativo e as demandas vem dos holding registers (operador ou OpenPLC).
"""

from .. import config as C
from .pressurizer import PressurizerControl
from .rod_control import RodControl
from .sg_level import SGLevelControl
from .turbine_control import TurbineControl


class ControlSystem:
    def __init__(self):
        self.rod = RodControl(C.ROD_POS_REF)
        self.pzr = PressurizerControl()
        self.turbine = TurbineControl()
        # DUAS malhas de nivel independentes (GV1 e GV2)
        self.sg_level = [
            SGLevelControl("GV1", C.FEED_FLOW_NOMINAL),
            SGLevelControl("GV2", C.FEED_FLOW_NOMINAL),
        ]

    def update(self, plant, sp, dt):
        power = plant.core.n * 100.0
        rod_demand = self.rod.update(power, sp["sp_power_pct"], dt,
                                     tripped=plant.bus.tripped, current_rod=plant.core.rod_pos,
                                     period=plant.reactor_period)
        turbine_valve = self.turbine.update(power, dt)   # turbina segue a potencia real
        heater, spray = self.pzr.update(plant.primary.przr_press, sp["sp_przr_pressure_bar"])

        fv1 = self.sg_level[0].update(plant.sg[0].level, plant.sg[0].steam_flow,
                                      sp["sp_sg1_level_pct"], dt)
        fv2 = self.sg_level[1].update(plant.sg[1].level, plant.sg[1].steam_flow,
                                      sp["sp_sg2_level_pct"], dt)

        return {
            "rod_demand_pct": rod_demand,
            "turbine_valve_pct": turbine_valve,
            "heater": heater,
            "spray": spray,
            "feed_valve": [fv1, fv2],
        }
