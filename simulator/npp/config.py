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

from .water import psat

# ============================================================ NUCLEO (REATOR)
# Cinetica pontual, 6 grupos de neutrons atrasados (U-235 termico).
BETA = [0.000215, 0.001424, 0.001274, 0.002568, 0.000748, 0.000273]
LAMBDA = [0.0124, 0.0305, 0.111, 0.301, 1.14, 3.01]
BETA_TOTAL = sum(BETA)          # ~0.0065
GEN_TIME = 2.0e-5               # tempo de geracao de neutrons prontos (s)
# Fonte de neutrons de partida (Cf-252 / Sb-Be) — mantem o nucleo desligado com
# populacao finita (multiplicacao subcritica: n = S*Lambda/|rho|). ~30 cps na
# faixa-fonte com o nucleo a -5000 pcm.
NEUTRON_SOURCE = 7.5e-7         # fracao de potencia nominal por segundo

# ---- Realimentacao de reatividade (Delta-k/k; 1 pcm = 1e-5)
# Doppler ~ raiz quadrada da temperatura absoluta do combustivel:
#   rho_D = -A*(sqrt(Tf) - sqrt(Tf_ref))   ->  -2,5 pcm/K a 900 degC
ALPHA_DOPPLER = -2.5e-5         # /K no ponto nominal (define A)
DOPPLER_A = -2.0 * ALPHA_DOPPLER * (900.0 + 273.15) ** 0.5
# Coeficiente de moderador (MTC) varia com temperatura, boro e burnup:
#   MTC = MTC_REF + MTC_T*(T-Tref) + MTC_B*(B-Bref) + MTC_BU*burnup
# -> ~0 a frio, -20 pcm/K a plena potencia (BOC), ~-55 pcm/K no fim de ciclo;
#    boro alto torna o MTC menos negativo (pode ficar POSITIVO a frio).
MTC_REF = -2.0e-4               # /K   (-20 pcm/K a 305 degC, 800 ppm, BOC)
MTC_T = -7.8e-7                 # /K^2 (menos negativo a frio)
MTC_B = 8.0e-8                  # /K/ppm
MTC_BU = -3.0e-6                # /K por % de burnup do ciclo
ALPHA_BORON = -1.0e-4           # /ppm de boro a quente (-10 pcm/ppm; ~-12 a frio)
# Barras de controle: valor INTEGRAL em curva S (diferencial maximo no meio do
# nucleo, pequeno nas pontas). 228 passos = 100% retirada (mecanismo Westinghouse).
ROD_WORTH = 0.060               # valor total do banco de controle (6000 pcm)
ROD_STEPS = 228
ROD_SPEED = 72 / ROD_STEPS * 100 / 60        # %/s em AUTO   (72 passos/min)
ROD_SPEED_MANUAL = 48 / ROD_STEPS * 100 / 60 # %/s em MANUAL (48 passos/min)
ROD_SPEED_SCRAM = 45.0          # %/s na queda por SCRAM (~2,2 s ate o fundo)
# Boro de referencia por condicao (a frio, denso, exige muito boro p/ subcritico)
BORON_COLD_SHUTDOWN = 1900.0    # ppm — parada fria
BORON_FRESH_CORE = 2100.0       # ppm — nucleo novo pos-recarga (mais reativo)
# Sistema de controle quimico (CVS): boracao/diluicao por "feed & bleed" ->
# variacao EXPONENCIAL (dB/dt = Q/V * (B_fonte - B)). Lenta como na planta real.
CVS_RATE = 4.0e-4               # /s  (vazao de carga / massa do RCS)
BORIC_ACID_PPM = 4000.0         # ppm do tanque de acido borico

FUEL_TEMP_REF = 900.0     # degC — combustivel (media) a 100% nominal
COOLANT_TEMP_REF = 305.0  # degC — Tavg nominal (~302 no AP1000)
BORON_REF = 800.0         # ppm
ROD_POS_REF = 75.0        # % retirada em que a planta fica critica a 100%

RATED_MWTH = 3400.0       # potencia termica nominal (MWth)
RATED_MWE = 1117.0        # potencia eletrica nominal (MWe)
TURBINE_EFF = RATED_MWE / RATED_MWTH

# ~96 t de UO2 + ~25 t de zircaloy -> ~38 MJ/K; constante de tempo ~6,7 s
C_FUEL = 38.0             # capacidade termica do combustivel (MJ/K)
H_FUEL_COOLANT = 5.7      # transferencia combustivel->refrigerante (MW/K)

# Calor de decaimento: 7 grupos exponenciais ajustados a curva ANS-5.1 (apos
# operacao longa). 1 s: 6,2% | 100 s: 3,2% | 1 h: 1,4% | 1 dia: 0,5% | 12 d: 0,2%.
DECAY_GROUPS = [   # (fracao da potencia em equilibrio, constante de tempo s)
    (0.00842, 3.0), (0.02162, 30.0), (0.01399, 300.0), (0.01040, 3000.0),
    (0.00375, 2.0e4), (0.00502, 1.5e5), (0.00242, 1.0e7),
]
DECAY_HEAT_INIT = sum(a for a, _ in DECAY_GROUPS)   # ~6,6% em equilibrio
MAX_POWER_FRAC = 12.0     # clamp numerico

# ---- Instrumentacao nuclear (NIS) — tres faixas sobrepostas
SR_CPS_PER_FRAC = 1.0e11  # faixa-fonte (SR): contagens/s por fracao de potencia
IR_AMP_PER_FRAC = 1.0e-3  # faixa-intermediaria (IR): A por fracao (1e-11..1e-3 A)
# Permissivos / intertravamentos (logica Westinghouse)
P6_IR_AMPS = 1.0e-10      # P-6: IR acima -> bloqueia trip da faixa-fonte
P7_POWER = 10.0           # P-7: abaixo (potencia e turbina) bloqueia trips de baixa potencia
P10_POWER = 10.0          # P-10: acima -> bloqueia trips de IR e PR-baixo
C2_ROD_STOP = 103.0       # C-2: potencia alta -> bloqueia retirada de barras
C1_IR_ROD_STOP = 20.0     # C-1: IR alta (% equiv.) -> bloqueia retirada de barras

# ================================================= PRIMARIO (2 loops, 4 RCPs)
# ~190 t de agua a 300 degC (cp ~5,7 kJ/kg.K) + metal acoplado (vaso, tubos, tubulacao)
C_COOLANT = 1300.0        # capacidade termica do primario (MJ/K)
CP_COOLANT = 5.5e-3       # calor especifico efetivo concentrado (MJ/(kg.K))
N_RCP = 4                 # bombas de refrigerante do reator
RCP_FLOW_NOMINAL = 20000.0  # kg/s totais (4 bombas) a 100%
RCP_COASTDOWN_TAU = 6.0   # s — inercia de rotor (canned motor)
PUMP_HEAT_MW = 5.0        # MW de calor por RCP ligada (aquece o primario a frio ~50 degC/h)
SI_WATER_TEMP = 50.0      # degC da agua injetada pelas salvaguardas (CMT/acumuladores/IRWST)

# ------ Pressurizador
PRZR_PRESS_NOMINAL = 155.0   # bar (15.5 MPa)
PRZR_LEVEL_NOMINAL = 55.0    # % — programa a plena carga
PRZR_LEVEL_NOLOAD = 25.0     # % — programa sem carga (e minimo a frio)
PRZR_LEVEL_EXP = 1.3         # % de nivel por K de Tavg (expansao termica do RCS)
PRZR_KG_PER_PCT = 400.0      # kg de agua por % de nivel do PZR (~60 m3)
PRZR_PRESS_PER_LEVEL = 0.9   # bar por % de nivel (compressao/expansao da bolha)
CVS_LEVEL_TAU = 120.0        # s — controle de nivel do PZR pelo CVS (carga/descarga)
CVS_MAX_FLOW = 20.0          # kg/s — capacidade de reposicao do CVS
PRZR_HEATER_RATE = 0.3       # bar/s — aquecedores (lentos: aquecem a agua do PZR)
PRZR_SPRAY_RATE = 1.5        # bar/s — spray (rapido: condensa o vapor)
PRZR_HEATER_CUTOUT = 17.0    # % de nivel — abaixo disso os aquecedores desligam (protecao)
PRZR_CTRL_GAIN = 0.8         # /s — controle proporcional de pressao (modo auto)
# autoridade do controle automatico = limites fisicos de aquecedor/spray
PRZR_RELIEF_SETPOINT = 172.0 # bar (valvula de alivio / PORV)
PRZR_RELIEF_RESEAT = 165.0   # bar

# ------ Controle automatico (esquema Westinghouse)
# Turbina segue a CARGA pedida (rampa); barras seguem o programa de Tavg:
#   Tref = T_sem_carga + (Tavg_nominal - T_sem_carga) x carga da turbina
LOAD_RAMP = 5.0 / 60.0       # %/s de rampa de carga (5%/min)
ROD_TAVG_DEADBAND = 0.8      # K — banda morta do controle de barras
ROD_MISMATCH_GAIN = 0.1      # K por % de descasamento potencia nuclear x carga
C5_LOAD = 15.0               # % — abaixo, retirada AUTOMATICA de barras bloqueada (C-5)

# ============================================= GERADORES DE VAPOR (2 unidades)
# Pressao secundaria = pressao de SATURACAO da agua do GV (tabela de vapor).
N_SG = 2
SG_TEMP_NOMINAL = 272.0      # degC a plena carga (~57 bar)
SG_PRESS_NOMINAL = psat(SG_TEMP_NOMINAL)   # ~56,7 bar
SG_LEVEL_NOMINAL = 55.0      # %
H_COOLANT_SG = 51.5          # transferencia primario->cada GV (MW/K, x fluxo)
C_SG = 500.0                 # capacidade termica de cada GV (~80 t de agua + metal, MJ/K)
STEAM_LATENT = 1.8           # MJ/kg efetivo (latente + subresfriamento)
SG_LEVEL_GAIN = 0.005        # %/s por kg/s de desbalanco alim-vapor
SG_RELIEF_SETPOINT = 80.0    # bar — PORV / alivio atmosferico (reassenta 3 bar abaixo)
SG_RELIEF_FLOW = 150.0       # kg/s por GV com o alivio aberto
FEED_FLOW_NOMINAL = 950.0    # kg/s por GV a 100% (total ~1900)
SG_HIHI_LEVEL = 80.0         # % -> isolamento da agua de alimentacao + trip da turbina (P-14)
# Alimentacao de partida (SFW, AP1000): assume o nivel quando a alimentacao
# principal nao entrega (partida/parada, pos-trip, isolamento).
SFW_MAX_FLOW = 60.0          # kg/s por GV
SFW_LEVEL_SP = 50.0          # %
P4_TAVG_ISOL = 296.0         # degC — trip (P-4) + Tavg baixo -> isola alimentacao principal
# Despejo de vapor ao condensador (steam dump, 40% no AP1000): no trip ou em baixa
# carga, segura o Tavg no programa (Tref = sem-carga + inclinacao x carga).
STEAM_DUMP_CAPACITY = 0.40   # fracao da vazao nominal de vapor
T_NOLOAD = 292.0             # degC — Tavg sem carga (parada quente)
STEAM_DUMP_DEADBAND = 0.5    # K
STEAM_DUMP_FULL_OPEN = 8.0   # K acima do Tref -> abertura total
STEAM_DUMP_ARM_LOAD = 0.10   # abaixo desta carga de turbina (ou turbina desarmada) fica armado

# ===================================================== TURBINA / GERADOR
TURBINE_RPM_NOMINAL = 1800.0 # rpm (60 Hz). Use 1500 p/ 50 Hz.
TURBINE_INERTIA = 4.0        # s
TURBINE_OVERSPEED_TRIP = 3300.0

# ============================== SEGURANCA PASSIVA (PXS) — Defense-in-Depth L3/L4
# CMT — Core Makeup Tanks (2 x ~70 t), injecao borada por gravidade.
CMT_MASS = 140000.0          # kg (2 tanques)
CMT_FLOW = 60.0              # kg/s total injetando
CMT_BORON = 3400.0           # ppm da agua borada injetada
# Acumuladores (2 x ~57 t, N2 a 48 bar) — injecao rapida quando o RCS despressuriza.
ACCUM_MASS = 114000.0        # kg (2 tanques)
ACCUM_PRESS_NOMINAL = 48.0   # bar (pressao de N2, cheio)
ACCUM_MAX_FLOW = 1000.0      # kg/s total com diferencial alto
ACCUM_GAS_FRAC = 0.5         # fracao inicial de gas (N2 expande ao esvaziar)
# PRHR — Passive Residual Heat Removal HX (remove calor residual para o IRWST).
# Remocao proporcional ao superaquecimento -> auto-limita e atinge equilibrio
# proximo ao calor de decaimento (parada quente ~250-290 degC), sem resfriar demais.
PRHR_K = 0.45                # MW/K de (Tavg - sumidouro)
PRHR_SINK_TEMP = 120.0       # degC — temperatura efetiva do sumidouro (IRWST)
# ADS — Automatic Depressurization System (4 estagios, sequencia AP1000):
#   ADS-1 com nivel da CMT < 67,5% (ou manual); ADS-2 e ADS-3 temporizados;
#   ADS-4 com CMT < 20%. Cada estagio aberto ventila vapor (remove energia e massa).
ADS_CMT_LOW = 67.5           # % -> ADS-1
ADS_CMT_LOWLOW = 20.0        # % -> ADS-4
ADS_STAGE_DELAY = [0.0, 70.0, 120.0, 120.0]   # s entre estagios (minimo)
ADS_STAGE_MW = [100.0, 250.0, 450.0, 1500.0]  # MW de vapor ventilado (acumulado) a 155 bar
ADS_DEPRESS_RATE = 1.0       # bar/s por estagio (vapor do PZR, enquanto houver bolha)
# IRWST — reservatorio de agua dentro da contencao. Com o ADS-4 aberto e o
# primario despressurizado, injeta por gravidade (resfriamento de longo prazo).
IRWST_LEVEL_NOMINAL = 100.0  # %
IRWST_MASS = 2.0e6           # kg
IRWST_INJECT_FLOW = 150.0    # kg/s por gravidade
IRWST_INJECT_PRESS = 3.0     # bar — abaixo disso a coluna d'agua vence a pressao do RCS

# ===================================================== SETPOINTS DE PROTECAO
# --- RPS (Reactor Protection System) — trip do reator
TRIP_HI_FLUX = 109.0         # % — faixa de potencia, setpoint alto
TRIP_PR_LOW = 25.0           # % — faixa de potencia, setpoint baixo (bloqueado acima de P-10)
TRIP_IR_HIGH = 25.0          # % equiv. — faixa intermediaria (bloqueado acima de P-10)
TRIP_SR_HIGH_CPS = 1.0e5     # cps — faixa-fonte (bloqueado acima de P-6)
TRIP_FLUX_RATE = 5.0         # % de subida em 2 s (taxa positiva de fluxo)
TRIP_HI_PRZR_LEVEL = 92.0    # % (bloqueado abaixo de P-7)
TRIP_HI_PRZR_PRESS = 168.0   # bar
TRIP_LO_PRZR_PRESS = 128.0   # bar (bloqueado abaixo de P-7)
TRIP_LO_SG_LEVEL = 20.0      # % (qualquer GV)
TRIP_HI_FUEL_TEMP = 1400.0   # degC
TRIP_LO_FLOW = 87.0          # % vazao primaria (bloqueado abaixo de P-7)
TRIP_HI_CONT_PRESS = 3.5     # bar
# --- ESFAS (Engineered Safety Features Actuation System) — salvaguardas
ESFAS_LO_PRZR_PRESS = 120.0  # bar -> sinal "S" (safeguards): CMT + PRHR
ESFAS_ARM_PRESS = 130.0      # bar -> permissivo P-11: arma a SI por baixa pressao
                             # (evita atuacao espuria durante partida/parada a frio)
ESFAS_HI_CONT_PRESS = 2.5    # bar -> isolamento / salvaguardas
ESFAS_LO_SG_LEVEL = 15.0     # % -> PRHR

# ================================================ LOCA (perda de refrigerante)
# Rompimento no primario: vazao ~ area x sqrt(dP). Esvazia o PZR (a pressao cai),
# o RCS satura e a pressao "pendura" na saturacao ate' a energia sair. Mitigado
# pela seguranca passiva (ESFAS -> CMT -> ADS -> acumuladores -> IRWST).
# Se as salvaguardas estiverem bloqueadas, o nucleo descobre e superaquece.
RCS_MASS = 190000.0          # kg de agua no loop (sem o PZR)
LOCA_MAX_FLOW = 12000.0      # kg/s — guilhotina dupla (area 100%) a 155 bar
LOCA_SPILL_LEVEL = 60.0      # % — inventario na altura do bocal da ruptura (perna fria)
BREAK_ENTHALPY = 1.2         # MJ/kg de energia levada pela mistura bifasica
UNCOVERY_THRESHOLD = 45.0    # % de inventario abaixo do qual o nucleo descobre
UNCOVERED_COOLING = 0.002    # fracao residual (so' vapor) com o nucleo seco -> aquece ~2 K/s

# ============================================================== CONTENCAO
CONT_PRESS_NOMINAL = 1.0     # bar abs
CONT_VOLUME_FACTOR = 0.02    # ganho de pressurizacao por dano
CONT_BAR_PER_MJ = 1.5e-5     # bar por MJ de vapor liberado na contencao
PCS_RATE = 0.003             # /s — resfriamento passivo da contencao (PCS)

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
NEUTRONICS_SUBSTEPS = 50     # subpassos da cinetica pontual por DT (esquema implicito)
REALTIME = True
TIME_SCALE_DEFAULT = 1.0     # acelera SO' a evolucao de venenos/burnup (nao a
                             # dinamica rapida) -> permite ver Xenonio (horas) em
                             # minutos. Ajustavel pela HMI.
TIME_SCALE_MAX = 3600.0
# Velocidade da planta INTEIRA (fisica completa, mais passos por segundo real).
# Util para aquecimento a frio (~4-5 h reais) sem distorcer a dinamica.
SIM_SPEEDS = (1, 2, 5, 10)
