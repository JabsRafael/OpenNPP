(*
   OpenNPP — Programa de controle de referencia (OpenPLC / IEC 61131-3)
   ====================================================================
   Roda no OpenPLC atuando como MESTRE Modbus, lendo os sensores e escrevendo
   as demandas de atuador no simulador da planta (172.28.10.10:502).

   Modo "CLP-no-laco": o simulador deve estar em MANUAL (coil cmd_auto_control=0);
   este programa passa a ser o sistema de controle. Assim o OpenPLC vira um alvo
   realista de exercicio (ver docs/07): comprometer o CLP = perder o controle.

   ------------------------------------------------------------------
   MAPEAMENTO (alinhe com a config do Slave Device na UI do OpenPLC —
   ver plc/README.md). Convencao usada aqui: os pontos do simulador
   mapeiam para enderecos remotos base 100.
     Input Registers  IRn  -> %IW(100+n)     (sensores, leitura)
     Discrete Inputs  DIn  -> %IX(100 + n/8).(n mod 8)
     Holding-Write    HRn  -> %QW(100+n)     (demandas, escrita)
     Coils            COn  -> %QX(100 + n/8).(n mod 8)
   ------------------------------------------------------------------
*)
PROGRAM npp_control
  VAR
    (* ---- Sensores (Input Registers, valor bruto = engenharia x escala) ---- *)
    ir_power     AT %IW100 : INT;   (* reactor_power_pct  x10 *)
    ir_fuel      AT %IW102 : INT;   (* fuel_temp_c        x1  *)
    ir_tavg      AT %IW106 : INT;   (* coolant_tavg_c     x10 *)
    ir_flow      AT %IW110 : INT;   (* rcp_flow_pct       x10 *)
    ir_przr      AT %IW111 : INT;   (* przr_pressure_bar  x10 *)
    ir_sg1_lvl   AT %IW115 : INT;   (* sg1_level_pct      x10 *)
    ir_sg2_lvl   AT %IW119 : INT;   (* sg2_level_pct      x10 *)

    (* ---- Status (Discrete Inputs) ---- *)
    di_tripped   AT %IX100.0 : BOOL; (* reactor_tripped *)

    (* ---- Demandas de atuador (Holding-Write) ---- *)
    qw_rod       AT %QW101 : INT;   (* dmd_rod_pct            x10 *)
    qw_turb      AT %QW106 : INT;   (* dmd_turbine_valve_pct  x10 *)
    qw_feed1     AT %QW109 : INT;   (* dmd_sg1_feed_valve_pct x10 *)
    qw_feed2     AT %QW111 : INT;   (* dmd_sg2_feed_valve_pct x10 *)

    (* ---- Comandos (Coils) ---- *)
    co_scram     AT %QX100.0 : BOOL; (* cmd_manual_scram *)
    co_heater    AT %QX100.7 : BOOL; (* cmd_przr_heater *)
    co_spray     AT %QX101.0 : BOOL; (* cmd_przr_spray *)
    co_auto      AT %QX101.2 : BOOL; (* cmd_auto_control (forcamos 0) *)
    co_przr_man  AT %QX102.3 : BOOL; (* cmd_przr_press_manual (forcamos 1: o CLP comanda aquecedor/spray) *)

    (* ---- Setpoints internos do CLP ---- *)
    sp_power   : REAL := 100.0;   (* % potencia desejada *)
    sp_przr    : REAL := 155.0;   (* bar *)
    sp_sg_lvl  : REAL := 55.0;    (* % nivel dos GVs *)

    (* ---- Variaveis de trabalho ---- *)
    power, fuel, tavg, flow, przr, sg1, sg2 : REAL;
    rod_dmd  : REAL := 75.0;
    ff1, ff2, feed1, feed2 : REAL;
    trip : BOOL;
    first_scan : BOOL := TRUE;
  END_VAR

  (* Assume o controle: tira o simulador do automatico interno *)
  co_auto := FALSE;
  co_przr_man := TRUE;   (* pressao do PZR tem estacao A/M propria no simulador *)

  (* ---- Escala bruta -> engenharia ---- *)
  power := INT_TO_REAL(ir_power) / 10.0;
  fuel  := INT_TO_REAL(ir_fuel);
  tavg  := INT_TO_REAL(ir_tavg) / 10.0;
  flow  := INT_TO_REAL(ir_flow) / 10.0;
  przr  := INT_TO_REAL(ir_przr) / 10.0;
  sg1   := INT_TO_REAL(ir_sg1_lvl) / 10.0;
  sg2   := INT_TO_REAL(ir_sg2_lvl) / 10.0;

  (* ================= PROTECAO (redundante ao RPS do simulador) ============ *)
  trip := (power >= 118.0) OR (przr >= 168.0) OR (przr <= 128.0)
          OR (sg1 <= 20.0) OR (sg2 <= 20.0) OR (fuel >= 1400.0) OR (flow <= 40.0);
  co_scram := trip;

  (* ================= CONTROLE DE POTENCIA (barras) ======================== *)
  (* controle proporcional incremental; MTC negativo estabiliza *)
  IF NOT trip THEN
    rod_dmd := rod_dmd + 0.004 * (sp_power - power);
    IF rod_dmd > 100.0 THEN rod_dmd := 100.0; END_IF;
    IF rod_dmd < 0.0 THEN rod_dmd := 0.0; END_IF;
  END_IF;
  qw_rod := REAL_TO_INT(rod_dmd * 10.0);

  (* ================= TURBINA ============================================== *)
  qw_turb := REAL_TO_INT(sp_power * 10.0);

  (* ================= NIVEL DOS GERADORES DE VAPOR (2 malhas) ============== *)
  ff1 := sp_power;  (* feedforward pela carga *)
  ff2 := sp_power;
  feed1 := ff1 + 2.0 * (sp_sg_lvl - sg1);
  feed2 := ff2 + 2.0 * (sp_sg_lvl - sg2);
  IF feed1 > 100.0 THEN feed1 := 100.0; END_IF; IF feed1 < 0.0 THEN feed1 := 0.0; END_IF;
  IF feed2 > 100.0 THEN feed2 := 100.0; END_IF; IF feed2 < 0.0 THEN feed2 := 0.0; END_IF;
  qw_feed1 := REAL_TO_INT(feed1 * 10.0);
  qw_feed2 := REAL_TO_INT(feed2 * 10.0);

  (* ================= PRESSURIZADOR (bang-bang) ============================ *)
  co_heater := przr < (sp_przr - 1.0);
  co_spray  := przr > (sp_przr + 1.0);

  first_scan := FALSE;
END_PROGRAM

CONFIGURATION Config0
  RESOURCE Res0 ON PLC
    TASK Main(INTERVAL := T#100ms, PRIORITY := 0);
    PROGRAM Inst0 WITH Main : npp_control;
  END_RESOURCE
END_CONFIGURATION
