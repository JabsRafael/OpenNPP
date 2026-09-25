"""
Mapa de I/O Modbus — fonte unica de verdade do cyber range OpenNPP (AP1000-like).

Define TODOS os pontos de processo trocados na rede OT e a codificacao de cada
grandeza de engenharia (float) nos registradores Modbus de 16 bits. Simulador,
logica do CLP (OpenPLC) e HMI referenciam este mesmo mapa.

Organizado por SISTEMA (espelha a modularidade da planta):
  nucleo | primario | GV1 | GV2 | turbina | seguranca passiva (PXS) | contencao

Convencao Modbus:
  COILS (FC1/5/15)=comandos digitais | DISCRETE INPUTS (FC2)=status/alarme
  INPUT REGISTERS (FC4)=sensores analog | HOLDING REGISTERS (FC3/6/16)=setpoints

valor_eng = raw / scale. Pontos com sinal usam complemento de dois 16 bits.

NOTA (cyber range): a ausencia de autenticacao no Modbus e' INTENCIONAL. Planta
e processo sao SIMULADOS, para treino de deteccao e defesa de OT/ICS.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    addr: int
    key: str
    label: str
    unit: str = ""
    scale: float = 1.0
    signed: bool = False
    lo: float = 0.0
    hi: float = 100.0
    system: str = ""      # nucleo | primario | gv1 | gv2 | turbina | pxs | contencao | geral


# --------------------------------------------------------------- INPUT REGISTERS
INPUT_REGISTERS = [
    # -- nucleo (reator)
    Point(0,  "reactor_power_pct", "Potencia do reator",      "%",    10.0, hi=120, system="nucleo"),
    Point(1,  "neutron_flux_pct",  "Fluxo de neutrons",       "%",    10.0, hi=120, system="nucleo"),
    Point(2,  "fuel_temp_c",       "Temp. combustivel",       "degC",  1.0, hi=2200, system="nucleo"),
    Point(3,  "reactivity_pcm",    "Reatividade total",       "pcm",   1.0, signed=True, lo=-2000, hi=1000, system="nucleo"),
    Point(4,  "decay_heat_pct",    "Calor de decaimento",     "%",    10.0, hi=10, system="nucleo"),
    Point(5,  "rod_position_pct",  "Posicao barras (retirada)","%",   10.0, hi=100, system="nucleo"),
    # -- primario
    Point(6,  "coolant_tavg_c",    "Temp. media (Tavg)",      "degC", 10.0, lo=250, hi=340, system="primario"),
    Point(7,  "coolant_thot_c",    "Temp. ramo quente",       "degC", 10.0, lo=250, hi=360, system="primario"),
    Point(8,  "coolant_tcold_c",   "Temp. ramo frio",         "degC", 10.0, lo=250, hi=340, system="primario"),
    Point(9,  "core_dt_c",         "Delta-T do nucleo",       "degC", 10.0, hi=60, system="primario"),
    Point(10, "rcp_flow_pct",      "Vazao primaria total",    "%",    10.0, hi=110, system="primario"),
    Point(11, "przr_pressure_bar", "Pressao pressurizador",   "bar",  10.0, lo=100, hi=180, system="primario"),
    Point(12, "przr_level_pct",    "Nivel pressurizador",     "%",    10.0, hi=100, system="primario"),
    Point(13, "boron_ppm",         "Concentracao de boro",    "ppm",   1.0, hi=3500, system="primario"),
    # -- gerador de vapor 1
    Point(14, "sg1_pressure_bar",  "GV1 pressao",             "bar",  10.0, lo=40, hi=90, system="gv1"),
    Point(15, "sg1_level_pct",     "GV1 nivel",               "%",    10.0, hi=100, system="gv1"),
    Point(16, "sg1_steam_flow_kgs","GV1 vazao vapor",         "kg/s",  1.0, hi=1200, system="gv1"),
    Point(17, "sg1_feed_flow_kgs", "GV1 vazao alim.",         "kg/s",  1.0, hi=1200, system="gv1"),
    # -- gerador de vapor 2
    Point(18, "sg2_pressure_bar",  "GV2 pressao",             "bar",  10.0, lo=40, hi=90, system="gv2"),
    Point(19, "sg2_level_pct",     "GV2 nivel",               "%",    10.0, hi=100, system="gv2"),
    Point(20, "sg2_steam_flow_kgs","GV2 vazao vapor",         "kg/s",  1.0, hi=1200, system="gv2"),
    Point(21, "sg2_feed_flow_kgs", "GV2 vazao alim.",         "kg/s",  1.0, hi=1200, system="gv2"),
    # -- turbina / gerador
    Point(22, "turbine_rpm",       "Rotacao da turbina",      "rpm",   1.0, hi=4000, system="turbina"),
    Point(23, "gen_power_mwe",     "Potencia eletrica",       "MWe",  10.0, hi=1300, system="turbina"),
    # -- seguranca passiva (PXS)
    Point(24, "cmt1_level_pct",    "CMT1 nivel",              "%",    10.0, hi=100, system="pxs"),
    Point(25, "cmt2_level_pct",    "CMT2 nivel",              "%",    10.0, hi=100, system="pxs"),
    Point(26, "accum_press_bar",   "Acumulador pressao",      "bar",  10.0, hi=60, system="pxs"),
    Point(27, "prhr_flow_pct",     "PRHR vazao",              "%",    10.0, hi=100, system="pxs"),
    Point(28, "irwst_level_pct",   "IRWST nivel",             "%",    10.0, hi=100, system="pxs"),
    Point(29, "ads_stage",         "ADS estagio ativo",       "",      1.0, hi=4, system="pxs"),
    Point(30, "si_flow_kgs",       "Vazao inj. seguranca",    "kg/s",  1.0, hi=2000, system="pxs"),
    # -- contencao
    Point(31, "containment_press_bar","Contencao pressao",    "bar", 100.0, lo=0, hi=6, system="contencao"),
    Point(32, "containment_rad_msvh","Contencao radiacao",    "mSv/h",100.0, hi=1000, system="contencao"),
    Point(33, "containment_temp_c","Contencao temperatura",   "degC", 10.0, hi=150, system="contencao"),
    # -- venenos (Xenonio/Iodo, Samario, veneno queimavel)
    Point(34, "xenon_worth_pcm",   "Reatividade Xenonio",     "pcm",   1.0, signed=True, lo=-4000, hi=1000, system="nucleo"),
    Point(35, "xenon_pct",         "Concentracao Xe-135",     "%",    10.0, hi=300, system="nucleo"),
    Point(36, "iodine_pct",        "Concentracao I-135",      "%",    10.0, hi=300, system="nucleo"),
    Point(37, "samarium_worth_pcm","Reatividade Samario",     "pcm",   1.0, signed=True, lo=-2000, hi=1000, system="nucleo"),
    Point(38, "burnable_poison_pct","Veneno queimavel restante","%",  10.0, hi=100, system="nucleo"),
    Point(39, "burnup_pct",        "Burnup do ciclo",         "%",    10.0, hi=100, system="nucleo"),
    # -- inventario do primario (LOCA)
    Point(40, "primary_inventory_pct","Inventario primario",  "%",    10.0, hi=100, system="primario"),
    # -- periodo do reator (feedback de taxa)
    Point(41, "reactor_period_s",  "Periodo do reator",       "s",     1.0, signed=True, lo=-999, hi=999, system="nucleo"),
]

# --------------------------------------------------------------- DISCRETE INPUTS
DISCRETE_INPUTS = [
    Point(0,  "reactor_tripped",   "SCRAM ativo", system="nucleo"),
    Point(1,  "turbine_tripped",   "Turbina desarmada", system="turbina"),
    Point(2,  "rcp1_running",      "RCP1 ligada", system="primario"),
    Point(3,  "rcp2_running",      "RCP2 ligada", system="primario"),
    Point(4,  "rcp3_running",      "RCP3 ligada", system="primario"),
    Point(5,  "rcp4_running",      "RCP4 ligada", system="primario"),
    Point(6,  "feedwater_running", "Agua alim. ligada", system="geral"),
    Point(7,  "alm_hi_flux",       "Alarme fluxo alto", system="nucleo"),
    Point(8,  "alm_hi_przr_press", "Alarme pressao alta PZR", system="primario"),
    Point(9,  "alm_lo_przr_press", "Alarme pressao baixa PZR", system="primario"),
    Point(10, "alm_sg1_lo_level",  "Alarme nivel baixo GV1", system="gv1"),
    Point(11, "alm_sg2_lo_level",  "Alarme nivel baixo GV2", system="gv2"),
    Point(12, "alm_hi_coolant_temp","Alarme temp. alta", system="primario"),
    Point(13, "alm_lo_flow",       "Alarme vazao baixa", system="primario"),
    Point(14, "alm_hi_cont_press", "Alarme pressao contencao", system="contencao"),
    Point(15, "alm_hi_cont_rad",   "Alarme radiacao alta", system="contencao"),
    Point(16, "przr_relief_open",  "Alivio PZR aberto", system="primario"),
    Point(17, "rod_bottom",        "Barras no fundo", system="nucleo"),
    Point(18, "auto_control_active","Controle automatico", system="geral"),
    # -- salvaguardas (ESFAS) / DID
    Point(19, "esfas_actuated",    "ESFAS atuado (sinal S)", system="pxs"),
    Point(20, "cmt_injecting",     "CMT injetando", system="pxs"),
    Point(21, "prhr_actuated",     "PRHR atuado", system="pxs"),
    Point(22, "accum_injecting",   "Acumulador injetando", system="pxs"),
    Point(23, "ads_actuated",      "ADS atuado", system="pxs"),
    Point(24, "sg1_relief_open",   "Alivio GV1 aberto", system="gv1"),
    Point(25, "sg2_relief_open",   "Alivio GV2 aberto", system="gv2"),
    Point(26, "safety_blocked",    "Salvaguardas bloqueadas", system="pxs"),
]

# ----------------------------------------------------------------------- COILS
COILS = [
    Point(0,  "cmd_manual_scram",    "SCRAM manual", system="nucleo"),
    Point(1,  "cmd_reset_trip",      "Reset de trip", system="geral"),
    Point(2,  "cmd_rcp1_start",      "Liga RCP1", system="primario"),
    Point(3,  "cmd_rcp2_start",      "Liga RCP2", system="primario"),
    Point(4,  "cmd_rcp3_start",      "Liga RCP3", system="primario"),
    Point(5,  "cmd_rcp4_start",      "Liga RCP4", system="primario"),
    Point(6,  "cmd_feed_pump_start", "Liga bomba agua alim.", system="geral"),
    Point(7,  "cmd_przr_heater",     "Aquecedor PZR", system="primario"),
    Point(8,  "cmd_przr_spray",      "Spray PZR", system="primario"),
    Point(9,  "cmd_turbine_trip",    "Desarme turbina", system="turbina"),
    Point(10, "cmd_auto_control",    "Habilita controle auto", system="geral"),
    Point(11, "cmd_boron_charge",    "Injeta boro", system="primario"),
    Point(12, "cmd_boron_dilute",    "Dilui boro", system="primario"),
    Point(13, "cmd_manual_si",       "Injecao seguranca manual", system="pxs"),
    Point(14, "cmd_manual_prhr",     "PRHR manual", system="pxs"),
    Point(15, "cmd_manual_ads",      "ADS manual", system="pxs"),
    Point(16, "cmd_block_safety",    "Bloqueia salvaguardas", system="pxs"),
]

# --------------------------------------------------------------- HOLDING REGISTERS
HOLDING_REGISTERS = [
    Point(0,  "sp_power_pct",        "Setpoint de potencia",       "%",   10.0, hi=100, system="nucleo"),
    Point(1,  "dmd_rod_pct",         "Barras controle (% retirada)","%",   10.0, hi=100, system="nucleo"),
    Point(2,  "dmd_rcp_speed_pct",   "Rotacao bombas RCP",         "%",   10.0, hi=100, system="primario"),
    Point(3,  "sp_przr_pressure_bar","Setpoint pressao PZR",       "bar", 10.0, lo=120, hi=175, system="primario"),
    Point(4,  "sp_przr_level_pct",   "Setpoint nivel PZR",         "%",   10.0, hi=100, system="primario"),
    Point(5,  "sp_boron_ppm",        "Setpoint boro",              "ppm",  1.0, hi=3500, system="primario"),
    Point(6,  "dmd_turbine_valve_pct","Valvula admissao turbina",  "%",   10.0, hi=100, system="turbina"),
    Point(7,  "dmd_turbine_load_mwe","Carga da turbina",           "MWe", 10.0, hi=1300, system="turbina"),
    Point(8,  "sp_sg1_level_pct",    "Setpoint nivel GV1",         "%",   10.0, hi=100, system="gv1"),
    Point(9,  "dmd_sg1_feed_valve_pct","Valvula agua alim. GV1",   "%", 10.0, hi=100, system="gv1"),
    Point(10, "sp_sg2_level_pct",    "Setpoint nivel GV2",         "%",   10.0, hi=100, system="gv2"),
    Point(11, "dmd_sg2_feed_valve_pct","Valvula agua alim. GV2",   "%", 10.0, hi=100, system="gv2"),
]


IR_BY_KEY = {p.key: p for p in INPUT_REGISTERS}
DI_BY_KEY = {p.key: p for p in DISCRETE_INPUTS}
CO_BY_KEY = {p.key: p for p in COILS}
HR_BY_KEY = {p.key: p for p in HOLDING_REGISTERS}


def encode(value: float, p: Point) -> int:
    raw = int(round(value * p.scale))
    if p.signed:
        raw = max(-32768, min(32767, raw))
        if raw < 0:
            raw += 65536
    else:
        raw = max(0, min(65535, raw))
    return raw


def decode(raw: int, p: Point) -> float:
    raw &= 0xFFFF
    if p.signed and raw >= 32768:
        raw -= 65536
    return raw / p.scale
