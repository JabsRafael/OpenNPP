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

Permissivos (logica Westinghouse), calculados a partir da instrumentacao nuclear:
  P-6   IR > 1e-10 A      -> PERMITE ao operador bloquear/reinstalar (toggle) o
                             trip da faixa-fonte (cmd_block_sr_trip); abaixo de
                             P-6 ele volta sozinho
  P-7   potencia E carga da turbina < 10% -> bloqueia trips "de potencia"
        (pressao baixa do PZR, nivel alto do PZR, vazao baixa)
  P-10  potencia > 10%    -> PERMITE bloquear/reinstalar os trips de IR e
                             PR-baixo (cmd_block_lowpower_trips); tambem BLOQUEIA
                             sozinho a faixa-fonte. Abaixo de P-10 voltam
  P-4   reator desarmado + Tavg baixo -> isola a agua de alimentacao principal
  P-14  nivel muito alto de GV -> isola alimentacao + desarma turbina
  C-1/C-2 IR alta / potencia alta -> bloqueia RETIRADA de barras (nao desarma)
"""

from . import config as C

# rotulos legiveis das causas de trip (registro de eventos e diagnostico)
CAUSE_PT = {
    "hi_flux": "fluxo alto (faixa de potência)",
    "pr_low": "fluxo alto (faixa de potência, setpoint baixo)",
    "ir_high": "fluxo alto (faixa intermediária)",
    "sr_high": "fluxo alto (faixa-fonte)",
    "flux_rate": "taxa positiva de fluxo",
    "hi_przr_press": "pressão alta do PZR",
    "lo_przr_press": "pressão baixa do PZR",
    "hi_przr_level": "nível alto do PZR",
    "lo_sg_level": "nível baixo de GV",
    "hi_fuel_temp": "sobretemperatura do combustível",
    "lo_flow": "vazão baixa do primário",
    "hi_cont_press": "pressão alta da contenção",
    "si": "sinal S (injeção de segurança)",
    "manual": "SCRAM manual",
}


def permissives(plant):
    core, turb = plant.core, plant.turbine
    power = core.n * 100.0
    return {
        "p6": core.ir_amps >= C.P6_IR_AMPS,
        "p7": power < C.P7_POWER and turb.load_frac * 100.0 < C.P7_POWER,  # True = bloqueio ativo
        "p10": power >= C.P10_POWER,
    }


def trip_conditions(plant, cmd, perm, s_signal):
    """Cada causa de trip -> (ativa, descricao com valor medido e setpoint)."""
    core, prim, sg, saf = plant.core, plant.primary, plant.sg, plant.safety
    power = core.n * 100.0
    ir_pct = power                      # IR calibrada em % equivalente
    sgmin = min(sg[0].level, sg[1].level)
    return {
        "hi_flux": (power >= C.TRIP_HI_FLUX,
                    f"potência {power:.1f}% ≥ {C.TRIP_HI_FLUX:.0f}%"),
        "pr_low": (not plant.lowpower_trips_blocked and power >= C.TRIP_PR_LOW,
                   f"potência {power:.1f}% ≥ {C.TRIP_PR_LOW:.0f}% com o trip de PR-baixo em serviço "
                   f"(bloqueie-o acima de P-10)"),
        "ir_high": (not plant.lowpower_trips_blocked and ir_pct >= C.TRIP_IR_HIGH,
                    f"faixa intermediária {ir_pct:.1f}% ≥ {C.TRIP_IR_HIGH:.0f}% com o trip de IR em serviço "
                    f"(bloqueie-o acima de P-10)"),
        "sr_high": (not plant.sr_trip_blocked and core.sr_cps >= C.TRIP_SR_HIGH_CPS,
                    f"faixa-fonte {core.sr_cps:.2e} cps ≥ {C.TRIP_SR_HIGH_CPS:.0e} cps com o trip da "
                    f"faixa-fonte em serviço (bloqueie-o acima de P-6)"),
        "flux_rate": (core.flux_rate_2s >= C.TRIP_FLUX_RATE,
                      f"potência subiu {core.flux_rate_2s:.1f} pontos em 2 s (≥ {C.TRIP_FLUX_RATE:.0f})"),
        "hi_przr_press": (prim.przr_press >= C.TRIP_HI_PRZR_PRESS,
                          f"pressão do PZR {prim.przr_press:.1f} bar ≥ {C.TRIP_HI_PRZR_PRESS:.0f} bar"),
        "lo_przr_press": (not perm["p7"] and prim.przr_press <= C.TRIP_LO_PRZR_PRESS,
                          f"pressão do PZR {prim.przr_press:.1f} bar ≤ {C.TRIP_LO_PRZR_PRESS:.0f} bar "
                          f"(acima de P-7: potência ou carga da turbina ≥ {C.P7_POWER:.0f}%)"),
        "hi_przr_level": (not perm["p7"] and prim.przr_level >= C.TRIP_HI_PRZR_LEVEL,
                          f"nível do PZR {prim.przr_level:.1f}% ≥ {C.TRIP_HI_PRZR_LEVEL:.0f}% (acima de P-7)"),
        "lo_sg_level": (sgmin <= C.TRIP_LO_SG_LEVEL,
                        f"nível de GV {sgmin:.1f}% ≤ {C.TRIP_LO_SG_LEVEL:.0f}% "
                        f"(GV1 {sg[0].level:.1f}%, GV2 {sg[1].level:.1f}%)"),
        "hi_fuel_temp": (core.T_fuel >= C.TRIP_HI_FUEL_TEMP,
                         f"combustível {core.T_fuel:.0f} °C ≥ {C.TRIP_HI_FUEL_TEMP:.0f} °C"),
        "lo_flow": (not perm["p7"] and prim.flow <= C.TRIP_LO_FLOW,
                    f"vazão do primário {prim.flow:.1f}% ≤ {C.TRIP_LO_FLOW:.0f}% (acima de P-7)"),
        "hi_cont_press": (saf.cont_press >= C.TRIP_HI_CONT_PRESS,
                          f"pressão da contenção {saf.cont_press:.2f} bar ≥ {C.TRIP_HI_CONT_PRESS} bar"),
        "si": (s_signal, "sinal S do ESFAS ativo (injeção de segurança) — normalize a pressão/contenção "
                         "e desligue a injeção de segurança manual"),
        "manual": (bool(cmd.get("cmd_manual_scram")), "SCRAM manual acionado pelo operador"),
    }


def reset_blockers(plant, cmd):
    """Lista (causa, descricao) do que impede o rearme agora."""
    perm = permissives(plant)
    s_signal = _s_signal(plant, cmd)
    conds = trip_conditions(plant, cmd, perm, s_signal)
    conds["manual"] = (False, "")          # o rearme ja' solta o botao de SCRAM
    out = [(k, CAUSE_PT[k], desc) for k, (on, desc) in conds.items() if on]
    if plant.bus.tripped and plant.core.rod_pos > 1.0:
        out.append(("rods", "barras fora do fundo",
                    f"barras ainda caindo ({plant.core.rod_pos:.0f}% retirada) — aguarde as barras no fundo"))
    return out


def _s_signal(plant, cmd):
    prim, saf = plant.primary, plant.safety
    lo_press_s = plant.esfas_armed and prim.przr_press <= C.ESFAS_LO_PRZR_PRESS
    return (lo_press_s
            or saf.cont_press >= C.ESFAS_HI_CONT_PRESS
            or bool(cmd.get("cmd_manual_si")))


def evaluate(plant, cmd):
    bus = plant.bus
    core, prim, sg, turb, saf = plant.core, plant.primary, plant.sg, plant.turbine, plant.safety
    power = core.n * 100.0
    perm = permissives(plant)

    # ============================ ESFAS — sinal S ===========================
    # Permissivo P-11: a injecao de seguranca por baixa pressao so' fica ARMADA
    # depois que a planta esteve pressurizada. Evita atuacao espuria durante a
    # partida/parada a frio (quando a pressao e' naturalmente baixa).
    if prim.przr_press >= C.ESFAS_ARM_PRESS:
        plant.esfas_armed = True
    blocked = bool(cmd.get("cmd_block_safety"))
    s_signal = _s_signal(plant, cmd)

    # ---- bloqueios manuais de trips de baixa potencia (toggle) -------------
    # Com o permissivo presente, cada pulso ALTERNA: bloqueia / reinstala.
    # Sem o permissivo o trip fica sempre em servico (reinstalado sozinho).
    plant._block_denied, plant._block_events = [], []
    if not perm["p6"]:
        plant.sr_trip_blocked = False
        if cmd.get("cmd_block_sr_trip"):
            plant._block_denied.append("bloqueio da faixa-fonte negado: P-6 ausente "
                                       f"(IR {core.ir_amps:.1e} A < {C.P6_IR_AMPS:.0e} A)")
    elif perm["p10"]:
        # acima de P-10 a faixa-fonte fica bloqueada automaticamente (detectores
        # desenergizados) e NAO pode ser reinstalada
        plant.sr_trip_blocked = True
        if cmd.get("cmd_block_sr_trip"):
            plant._block_denied.append("faixa-fonte: acima de P-10 fica bloqueada automaticamente "
                                       "(normal em potência)")
    elif cmd.get("cmd_block_sr_trip"):
        if plant.sr_trip_blocked and core.sr_cps >= C.TRIP_SR_HIGH_CPS:
            plant._block_denied.append(f"faixa-fonte: bloqueio obrigatório acima de {C.TRIP_SR_HIGH_CPS:.0e} cps "
                                       f"(voltar o trip a serviço desarmaria o reator)")
        else:
            plant.sr_trip_blocked = not plant.sr_trip_blocked
            if not plant.sr_trip_blocked:
                plant._block_events.append("Trip da faixa-fonte de volta em serviço (desbloqueado pelo operador)")
    if not perm["p10"]:
        plant.lowpower_trips_blocked = False
        if cmd.get("cmd_block_lowpower_trips"):
            plant._block_denied.append("bloqueio de IR/PR-baixo negado: P-10 ausente "
                                       f"(potência {power:.1f}% < {C.P10_POWER:.0f}%)")
    elif cmd.get("cmd_block_lowpower_trips"):
        if plant.lowpower_trips_blocked and power >= min(C.TRIP_PR_LOW, C.TRIP_IR_HIGH):
            plant._block_denied.append(f"IR/PR-baixo: bloqueio obrigatório acima de {C.TRIP_PR_LOW:.0f}% "
                                       f"(voltar os trips a serviço desarmaria o reator)")
        plant.lowpower_trips_blocked = (not plant.lowpower_trips_blocked) or \
            (plant.lowpower_trips_blocked and power >= min(C.TRIP_PR_LOW, C.TRIP_IR_HIGH))
        if not plant.lowpower_trips_blocked:
            plant._block_events.append("Trips de IR/PR-baixo de volta em serviço (desbloqueados pelo operador)")

    # ============================ RPS — trip do reator ======================
    conds = trip_conditions(plant, cmd, perm, s_signal)
    active = [k for k, (on, _) in conds.items() if on]
    plant._trip_causes = active                     # p/ registro de eventos
    plant._trip_details = [conds[k][1] for k in active]
    if active and not bus.tripped:
        bus.tripped = True
        bus.turbine_tripped = True                 # turbina segue o reator

    # P-14: nivel muito alto de GV -> isola alimentacao e desarma a turbina
    hihi = max(sg[0].level, sg[1].level) >= C.SG_HIHI_LEVEL
    if hihi:
        bus.turbine_tripped = True
    if cmd.get("cmd_turbine_trip") or turb.rpm >= C.TURBINE_OVERSPEED_TRIP:
        bus.turbine_tripped = True

    plant._reset_denied = None
    rods_down = core.rod_pos <= 1.0
    if cmd.get("cmd_reset_trip"):
        if not active and (rods_down or not bus.tripped):
            bus.tripped = False
            bus.turbine_tripped = False
            plant._feed_isol_p4 = False
        elif bus.tripped:
            plant._reset_denied = [(k, CAUSE_PT[k], conds[k][1]) for k in active] or \
                [("rods", "barras fora do fundo", f"barras ainda caindo ({core.rod_pos:.0f}%)")]

    # ---- isolamento da alimentacao principal (P-4 + Tavg baixo, P-14) ------
    if bus.tripped and prim.T_coolant < C.P4_TAVG_ISOL:
        plant._feed_isol_p4 = True                 # travado ate o rearme
    bus.feed_isolated = plant._feed_isol_p4 or hihi

    # ---- intertravamento de retirada de barras (nao desarma) ---------------
    rod_block = power >= C.C2_ROD_STOP or (not perm["p10"] and power >= C.C1_IR_ROD_STOP)
    plant.rod_withdrawal_block = rod_block

    lo_sg = min(sg[0].level, sg[1].level) <= C.ESFAS_LO_SG_LEVEL
    esfas_act = {
        "s_signal": s_signal,
        "prhr": s_signal or lo_sg or bool(cmd.get("cmd_manual_prhr")),
        "ads": bool(cmd.get("cmd_manual_ads")),
        "si": s_signal or bool(cmd.get("cmd_manual_si")),
        "blocked": blocked,
        # valvulas de isolamento dos acumuladores so' abrem com o RCS
        # pressurizado (P-11); a frio ficam fechadas
        "accum_armed": plant.esfas_armed,
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
        "alm_hi_flux":       power >= C.C2_ROD_STOP,
        "alm_hi_przr_press": prim.przr_press >= C.TRIP_HI_PRZR_PRESS - 4.0,
        "alm_lo_przr_press": prim.przr_press <= C.TRIP_LO_PRZR_PRESS + 4.0,
        "alm_sg1_lo_level":  sg[0].level <= C.TRIP_LO_SG_LEVEL + 8.0,
        "alm_sg2_lo_level":  sg[1].level <= C.TRIP_LO_SG_LEVEL + 8.0,
        "alm_hi_coolant_temp": bus.T_hot >= 335.0,
        "alm_lo_flow":       prim.flow <= C.TRIP_LO_FLOW + 5.0 and prim.running_count() > 0,
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
        "p6_permissive":     perm["p6"],
        "p7_low_power":      perm["p7"],
        "p10_permissive":    perm["p10"],
        "sr_trip_blocked":   plant.sr_trip_blocked,
        "lowpower_trips_blocked": plant.lowpower_trips_blocked,
        "rod_withdrawal_block": rod_block,
        "steam_dump_active": bus.steam_dump_frac > 0.01,
        "feedwater_isolated": bus.feed_isolated,
        "startup_feed_active": (sg[0].sfw_flow + sg[1].sfw_flow) > 1.0,
        "przr_heater_on":    prim.heater_on,
        "przr_spray_on":     prim.spray_on,
        "main_feed_flowing": (sg[0].main_feed + sg[1].main_feed) > 5.0,
    }
    return di, esfas_act
