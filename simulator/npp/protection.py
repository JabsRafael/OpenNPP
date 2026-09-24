"""
Sistemas de protecao — RPS e ESFAS (independentes do controle).

RPS (Reactor Protection System): desarma o reator (SCRAM) em condicoes anormais.
ESFAS (Engineered Safety Features Actuation System): atua as salvaguardas
passivas (CMT, PRHR, ADS) — Defense-in-Depth nivel 3.

Em uma usina real ambos sao sistemas de seguranca qualificados, redundantes e
SEPARADOS do CLP de controle. Aqui sao modelados dentro do simulador como a
camada de ultima instancia. Licoes de defesa exploradas nos playbooks:

  * RPS/ESFAS leem SENSORES — injetar valor falso no sensor engana a protecao.
  * cmd_block_safety simula um bypass de manutencao: se um atacante o aciona,
    derruba a camada DID 3 (salvaguardas) sem tocar no controle. Deteccao: esse
    bit jamais deveria estar ativo em operacao normal.
"""

from . import config as C


def evaluate(plant, cmd):
    bus = plant.bus
    core, prim, sg, turb, saf = plant.core, plant.primary, plant.sg, plant.turbine, plant.safety
    power = core.n * 100.0

    # ============================ RPS — trip do reator ======================
    trip_causes = {
        "hi_flux":       power >= C.TRIP_HI_FLUX,
        "hi_przr_press": prim.przr_press >= C.TRIP_HI_PRZR_PRESS,
        "lo_przr_press": prim.przr_press <= C.TRIP_LO_PRZR_PRESS,
        "lo_sg_level":   min(sg[0].level, sg[1].level) <= C.TRIP_LO_SG_LEVEL,
        "hi_fuel_temp":  core.T_fuel >= C.TRIP_HI_FUEL_TEMP,
        "lo_flow":       prim.flow <= C.TRIP_LO_FLOW,
        "hi_cont_press": saf.cont_press >= C.TRIP_HI_CONT_PRESS,
        "manual":        bool(cmd.get("cmd_manual_scram")),
    }
    if any(trip_causes.values()) and not bus.tripped:
        bus.tripped = True
        bus.turbine_tripped = True                 # turbina segue o reator

    if cmd.get("cmd_turbine_trip") or turb.rpm >= C.TURBINE_OVERSPEED_TRIP:
        bus.turbine_tripped = True

    if cmd.get("cmd_reset_trip") and not any(trip_causes.values()):
        bus.tripped = False
        bus.turbine_tripped = False

    # ============================ ESFAS — salvaguardas ======================
    blocked = bool(cmd.get("cmd_block_safety"))
    s_signal = (prim.przr_press <= C.ESFAS_LO_PRZR_PRESS
                or saf.cont_press >= C.ESFAS_HI_CONT_PRESS
                or bool(cmd.get("cmd_manual_si")))
    lo_sg = min(sg[0].level, sg[1].level) <= C.ESFAS_LO_SG_LEVEL
    esfas_act = {
        "s_signal": s_signal,
        "prhr": s_signal or lo_sg or bool(cmd.get("cmd_manual_prhr")),
        "ads": bool(cmd.get("cmd_manual_ads")),
        "si": s_signal or bool(cmd.get("cmd_manual_si")),
        "blocked": blocked,
    }

    # ============================ status / alarmes (DI) =====================
    di = {
        "reactor_tripped":   bus.tripped,
        "turbine_tripped":   bus.turbine_tripped,
        "rcp1_running":      prim.rcp_running[0] and prim.flow > 5.0,
        "rcp2_running":      prim.rcp_running[1] and prim.flow > 5.0,
        "rcp3_running":      prim.rcp_running[2] and prim.flow > 5.0,
        "rcp4_running":      prim.rcp_running[3] and prim.flow > 5.0,
        "feedwater_running": (sg[0].feed_flow + sg[1].feed_flow) > 5.0,
        "alm_hi_flux":       power >= C.TRIP_HI_FLUX - 3.0,
        "alm_hi_przr_press": prim.przr_press >= C.TRIP_HI_PRZR_PRESS - 4.0,
        "alm_lo_przr_press": prim.przr_press <= C.TRIP_LO_PRZR_PRESS + 4.0,
        "alm_sg1_lo_level":  sg[0].level <= C.TRIP_LO_SG_LEVEL + 8.0,
        "alm_sg2_lo_level":  sg[1].level <= C.TRIP_LO_SG_LEVEL + 8.0,
        "alm_hi_coolant_temp": bus.T_hot >= 335.0,
        "alm_lo_flow":       prim.flow <= C.TRIP_LO_FLOW + 15.0,
        "alm_hi_cont_press": saf.cont_press >= C.TRIP_HI_CONT_PRESS - 1.0,
        "alm_hi_cont_rad":   saf.cont_rad >= 5.0,
        "przr_relief_open":  prim.przr_relief_open,
        "rod_bottom":        core.rod_pos <= 1.0,
        "auto_control_active": bool(cmd.get("cmd_auto_control")),
        "esfas_actuated":    s_signal and not blocked,
        "cmt_injecting":     saf.cmt_injecting,
        "prhr_actuated":     saf.prhr_actuated,
        "accum_injecting":   saf.accum_injecting,
        "ads_actuated":      saf.ads_actuated,
        "sg1_relief_open":   sg[0].relief_open,
        "sg2_relief_open":   sg[1].relief_open,
        "safety_blocked":    blocked,
    }
    return di, esfas_act
