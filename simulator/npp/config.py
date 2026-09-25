"""
Parametros da planta — PWR classe AP1000 (Westinghouse Gen III+).

Dados publicos aproximados do AP1000, calibrados para dinamica estavel e
didatica. NAO e' um modelo licenciado nem validado de nenhuma unidade real;
serve a treino de OT/ICS em cyber range. Arquitetura modular espelhando a
planta real: nucleo, primario (2 loops / 4 RCPs / pressurizador), 2 geradores
de vapor, turbina/secundario e sistemas passivos de seguranca (PXS).

Referencias de dominio publico: potencia termica 3400 MWth, eletrica ~1117 MWe,
2 geradores de vapor, 4 bombas de refrigerante do reator (canned motor),
seguranca passiva (CMT, acumuladores, PRHR, ADS, IRWST, PCS).
"""

# ============================================================ NUCLEO (REATOR)
# Cinetica pontual, 6 grupos de neutrons atrasados (U-235 termico).
BETA = [0.000215, 0.001424, 0.001274, 0.002568, 0.000748, 0.000273]
LAMBDA = [0.0124, 0.0305, 0.111, 0.301, 1.14, 3.01]
BETA_TOTAL = sum(BETA)          # ~0.0065
GEN_TIME = 2.0e-5               # tempo de geracao de neutrons prontos (s)

# Realimentacao de reatividade (Delta-k/k; 1 pcm = 1e-5). Todos negativos.
ALPHA_DOPPLER = -2.5e-5   # /K de temp. combustivel   (-2.5 pcm/K)
ALPHA_MOD = -1.5e-4       # /K de temp. refrigerante  (-15 pcm/K)
ALPHA_BORON = -8.0e-6     # /ppm de boro              (-0.8 pcm/ppm)
ROD_WORTH = 0.060         # valor total do banco de controle (6000 pcm)

FUEL_TEMP_REF = 900.0     # degC — combustivel a 100% nominal
COOLANT_TEMP_REF = 305.0  # degC — Tavg nominal (~302 no AP1000)
BORON_REF = 800.0         # ppm
ROD_POS_REF = 75.0        # % retirada em que a planta fica critica a 100%

RATED_MWTH = 3400.0       # potencia termica nominal (MWth)
RATED_MWE = 1117.0        # potencia eletrica nominal (MWe)
TURBINE_EFF = RATED_MWE / RATED_MWTH

C_FUEL = 70.0             # capacidade termica do combustivel (MJ/K)
H_FUEL_COOLANT = 5.7      # transferencia combustivel->refrigerante (MW/K)

# Calor de decaimento (dois polos, ~6.5% inicial caindo devagar).
DECAY_HEAT_INIT = 0.065
DECAY_TAU_FAST = 15.0     # s
DECAY_TAU_SLOW = 400.0    # s
MAX_POWER_FRAC = 12.0     # clamp numerico

# ================================================= PRIMARIO (2 loops, 4 RCPs)
C_COOLANT = 140.0         # capacidade termica do primario (MJ/K)
CP_COOLANT = 5.5e-3       # calor especifico efetivo concentrado (MJ/(kg.K))
N_RCP = 4                 # bombas de refrigerante do reator
RCP_FLOW_NOMINAL = 20000.0  # kg/s totais (4 bombas) a 100%
RCP_COASTDOWN_TAU = 6.0   # s — inercia de rotor (canned motor)

# ------ Pressurizador
PRZR_PRESS_NOMINAL = 155.0   # bar (15.5 MPa)
PRZR_LEVEL_NOMINAL = 55.0    # %
PRZR_HEATER_RATE = 1.2       # bar/s
PRZR_SPRAY_RATE = 1.5        # bar/s
PRZR_THERMAL_EXP = 1.2       # bar por K de variacao de Tavg
PRZR_RELIEF_SETPOINT = 172.0 # bar (valvula de alivio / PORV)
PRZR_RELIEF_RESEAT = 165.0   # bar

# ============================================= GERADORES DE VAPOR (2 unidades)
N_SG = 2
SG_PRESS_NOMINAL = 57.6      # bar (5.76 MPa)
SG_LEVEL_NOMINAL = 55.0      # %
SG_TEMP_NOMINAL = 272.0      # degC (saturacao a 57.6 bar)
SG_SAT_SLOPE = 0.55          # bar/degC (linearizacao pressao-temp)
H_COOLANT_SG = 51.5          # transferencia primario->cada GV (MW/K, x fluxo)
C_SG = 120.0                 # capacidade termica de cada GV (MJ/K)
STEAM_LATENT = 1.8           # MJ/kg efetivo (latente + subresfriamento)
SG_LEVEL_GAIN = 0.005        # %/s por kg/s de desbalanco alim-vapor
SG_RELIEF_SETPOINT = 66.0    # bar
FEED_FLOW_NOMINAL = 950.0    # kg/s por GV a 100% (total ~1900)

# ===================================================== TURBINA / GERADOR
TURBINE_RPM_NOMINAL = 1800.0 # rpm (60 Hz). Use 1500 p/ 50 Hz.
TURBINE_INERTIA = 4.0        # s
TURBINE_OVERSPEED_TRIP = 3300.0

# ============================== SEGURANCA PASSIVA (PXS) — Defense-in-Depth L3/L4
# CMT — Core Makeup Tanks (2), injecao por gravidade/circulacao natural.
CMT_INJECT_RATE = 4.0        # %/s de esvaziamento quando injetando
CMT_BORON = 3400.0           # ppm da agua borada injetada
# Acumuladores — injecao rapida a pressao mais baixa.
ACCUM_PRESS_NOMINAL = 48.0   # bar (pressao de N2)
ACCUM_INJECT_PRESS = 45.0    # abaixo disso, injeta no primario
# PRHR — Passive Residual Heat Removal HX (remove calor residual para o IRWST).
# Remocao proporcional ao superaquecimento -> auto-limita e atinge equilibrio
# proximo ao calor de decaimento (parada quente ~250-290 degC), sem resfriar demais.
PRHR_K = 0.45                # MW/K de (Tavg - sumidouro)
PRHR_SINK_TEMP = 120.0       # degC — temperatura efetiva do sumidouro (IRWST)
# ADS — Automatic Depressurization System (4 estagios).
ADS_STAGE_PRESS = [110.0, 70.0, 40.0, 20.0]   # bar de abertura por estagio
ADS_DEPRESS_RATE = 3.0       # bar/s por estagio ativo
# IRWST — reservatorio de agua dentro da contencao.
IRWST_LEVEL_NOMINAL = 100.0  # %

# ===================================================== SETPOINTS DE PROTECAO
# --- RPS (Reactor Protection System) — trip do reator
TRIP_HI_FLUX = 118.0         # % potencia
TRIP_HI_PRZR_PRESS = 168.0   # bar
TRIP_LO_PRZR_PRESS = 128.0   # bar
TRIP_LO_SG_LEVEL = 20.0      # % (qualquer GV)
TRIP_HI_FUEL_TEMP = 1400.0   # degC
TRIP_LO_FLOW = 40.0          # % vazao primaria
TRIP_HI_CONT_PRESS = 3.5     # bar
# --- ESFAS (Engineered Safety Features Actuation System) — salvaguardas
ESFAS_LO_PRZR_PRESS = 120.0  # bar -> sinal "S" (safeguards): CMT + PRHR
ESFAS_HI_CONT_PRESS = 2.5    # bar -> isolamento / salvaguardas
ESFAS_LO_SG_LEVEL = 15.0     # % -> PRHR

# ================================================ LOCA (perda de refrigerante)
# Rompimento no primario: perde inventario e despressuriza. Mitigado pela
# seguranca passiva (baixa pressao -> ESFAS -> CMT/acumuladores/ADS reenchem).
# Se as salvaguardas estiverem bloqueadas, o nucleo descobre e superaquece.
LOCA_DRAIN_RATE = 9.0        # %/s de inventario a rompimento=1,0 e pressao nominal
LOCA_DEPRESS_RATE = 7.0      # bar/s a rompimento=1,0
SI_REFILL_GAIN = 0.02        # %/s de inventario por kg/s de injecao de seguranca
UNCOVERY_THRESHOLD = 45.0    # % de inventario abaixo do qual o nucleo descobre

# ============================================================== CONTENCAO
CONT_PRESS_NOMINAL = 1.0     # bar abs
CONT_VOLUME_FACTOR = 0.02    # ganho de pressurizacao por dano

# ============================ VENENOS (Xenonio/Iodo, Samario, veneno queimavel)
# Modelo normalizado: concentracoes em unidades de equilibrio a 100% de potencia
# (I_eq = Xe_eq = 1). Reatividade em forma de DESVIO do equilibrio -> zero no
# inicio (preserva a criticalidade) e mostra os transientes (pico de Xenonio pos-
# desligamento, "poço de iodo", buildup permanente de Samario).
XE_LAMBDA_I  = 2.926e-5   # /s  decaimento do I-135 (T½ 6,58 h)
XE_LAMBDA_XE = 2.106e-5   # /s  decaimento do Xe-135 (T½ 9,14 h)
XE_SIGMA_PHI = 6.0e-5     # /s  queima do Xe por absorcao a 100% de fluxo
# I_eq > Xe_eq (estoque de iodo alto por causa da queima) -> gera o PICO de
# Xenonio pos-desligamento. Normalizado: Xe_eq = 1, I_eq = XE_I_EQ a 100%.
XE_I_EQ = 2.3
XE_GI  = XE_LAMBDA_I * XE_I_EQ                              # producao de I
XE_GXE = (XE_LAMBDA_XE + XE_SIGMA_PHI) - XE_LAMBDA_I * XE_I_EQ  # producao de Xe (Xe_eq=1)
XENON_WORTH = 0.028       # Δk/k por unidade de desvio de Xe (~2800 pcm)

SM_LAMBDA_PM = 3.63e-6    # /s  decaimento do Pm-149 (T½ ~53 h)
SM_SIGMA_PHI = 3.63e-6    # /s  queima do Sm-149 a 100% (= lambda_Pm -> Sm_eq=1)
SM_GPM = SM_LAMBDA_PM                                  # producao de Pm (Pm_eq=1)
SAMARIUM_WORTH = 0.007    # Δk/k por unidade de desvio de Sm (~700 pcm)

# Veneno queimavel (gadolinia/IFBA) + burnup — evolucao MUITO lenta (meses).
BURNABLE_WORTH = 0.020    # Δk/k liberado ao longo da queima (~2000 pcm)
BURNUP_RATE = 100.0 / 4.7e7   # % de ciclo por segundo a 100% (ciclo ~18 meses)
BP_TAU = 45.0             # constante de queima do veneno (% de burnup)

# ============================================================== SIMULACAO
DT = 0.1                     # passo do laco externo (s), dinamica rapida
NEUTRONICS_SUBSTEPS = 200    # subpassos da cinetica pontual por DT
REALTIME = True
TIME_SCALE_DEFAULT = 1.0     # acelera SO' a evolucao de venenos/burnup (nao a
                             # dinamica rapida) -> permite ver Xenonio (horas) em
                             # minutos. Ajustavel pela HMI.
TIME_SCALE_MAX = 3600.0
