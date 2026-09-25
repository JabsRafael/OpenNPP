# Mapa de I/O Modbus — referência

Fonte única de verdade: `simulator/npp/iomap.py`. **Gerado automaticamente** do código.

Codificação: `valor_engenharia = raw / escala`. Registradores de 16 bits; pontos com sinal usam complemento de dois.

> A planta é SIMULADA — estes registradores não controlam hardware real.

## Input Registers — sensores (FC4, leitura)

| Addr | Chave | Rótulo | Sistema | Unid. | Escala | Sinal |
|---|---|---|---|---|---|---|
| 0 | `reactor_power_pct` | Potencia do reator | nucleo | % | ×10 | — |
| 1 | `neutron_flux_pct` | Fluxo de neutrons | nucleo | % | ×10 | — |
| 2 | `fuel_temp_c` | Temp. combustivel | nucleo | degC | ×1 | — |
| 3 | `reactivity_pcm` | Reatividade total | nucleo | pcm | ×1 | sim |
| 4 | `decay_heat_pct` | Calor de decaimento | nucleo | % | ×10 | — |
| 5 | `rod_position_pct` | Posicao barras (retirada) | nucleo | % | ×10 | — |
| 6 | `coolant_tavg_c` | Temp. media (Tavg) | primario | degC | ×10 | — |
| 7 | `coolant_thot_c` | Temp. ramo quente | primario | degC | ×10 | — |
| 8 | `coolant_tcold_c` | Temp. ramo frio | primario | degC | ×10 | — |
| 9 | `core_dt_c` | Delta-T do nucleo | primario | degC | ×10 | — |
| 10 | `rcp_flow_pct` | Vazao primaria total | primario | % | ×10 | — |
| 11 | `przr_pressure_bar` | Pressao pressurizador | primario | bar | ×10 | — |
| 12 | `przr_level_pct` | Nivel pressurizador | primario | % | ×10 | — |
| 13 | `boron_ppm` | Concentracao de boro | primario | ppm | ×1 | — |
| 14 | `sg1_pressure_bar` | GV1 pressao | gv1 | bar | ×10 | — |
| 15 | `sg1_level_pct` | GV1 nivel | gv1 | % | ×10 | — |
| 16 | `sg1_steam_flow_kgs` | GV1 vazao vapor | gv1 | kg/s | ×1 | — |
| 17 | `sg1_feed_flow_kgs` | GV1 vazao alim. | gv1 | kg/s | ×1 | — |
| 18 | `sg2_pressure_bar` | GV2 pressao | gv2 | bar | ×10 | — |
| 19 | `sg2_level_pct` | GV2 nivel | gv2 | % | ×10 | — |
| 20 | `sg2_steam_flow_kgs` | GV2 vazao vapor | gv2 | kg/s | ×1 | — |
| 21 | `sg2_feed_flow_kgs` | GV2 vazao alim. | gv2 | kg/s | ×1 | — |
| 22 | `turbine_rpm` | Rotacao da turbina | turbina | rpm | ×1 | — |
| 23 | `gen_power_mwe` | Potencia eletrica | turbina | MWe | ×10 | — |
| 24 | `cmt1_level_pct` | CMT1 nivel | pxs | % | ×10 | — |
| 25 | `cmt2_level_pct` | CMT2 nivel | pxs | % | ×10 | — |
| 26 | `accum_press_bar` | Acumulador pressao | pxs | bar | ×10 | — |
| 27 | `prhr_flow_pct` | PRHR vazao | pxs | % | ×10 | — |
| 28 | `irwst_level_pct` | IRWST nivel | pxs | % | ×10 | — |
| 29 | `ads_stage` | ADS estagio ativo | pxs | — | ×1 | — |
| 30 | `si_flow_kgs` | Vazao inj. seguranca | pxs | kg/s | ×1 | — |
| 31 | `containment_press_bar` | Contencao pressao | contencao | bar | ×100 | — |
| 32 | `containment_rad_msvh` | Contencao radiacao | contencao | mSv/h | ×100 | — |
| 33 | `containment_temp_c` | Contencao temperatura | contencao | degC | ×10 | — |
| 34 | `xenon_worth_pcm` | Reatividade Xenonio | nucleo | pcm | ×1 | sim |
| 35 | `xenon_pct` | Concentracao Xe-135 | nucleo | % | ×10 | — |
| 36 | `iodine_pct` | Concentracao I-135 | nucleo | % | ×10 | — |
| 37 | `samarium_worth_pcm` | Reatividade Samario | nucleo | pcm | ×1 | sim |
| 38 | `burnable_poison_pct` | Veneno queimavel restante | nucleo | % | ×10 | — |
| 39 | `burnup_pct` | Burnup do ciclo | nucleo | % | ×10 | — |
| 40 | `primary_inventory_pct` | Inventario primario | primario | % | ×10 | — |

## Discrete Inputs — status/alarmes (FC2, leitura)

| Addr | Chave | Rótulo | Sistema |
|---|---|---|---|
| 0 | `reactor_tripped` | SCRAM ativo | nucleo |
| 1 | `turbine_tripped` | Turbina desarmada | turbina |
| 2 | `rcp1_running` | RCP1 ligada | primario |
| 3 | `rcp2_running` | RCP2 ligada | primario |
| 4 | `rcp3_running` | RCP3 ligada | primario |
| 5 | `rcp4_running` | RCP4 ligada | primario |
| 6 | `feedwater_running` | Agua alim. ligada | geral |
| 7 | `alm_hi_flux` | Alarme fluxo alto | nucleo |
| 8 | `alm_hi_przr_press` | Alarme pressao alta PZR | primario |
| 9 | `alm_lo_przr_press` | Alarme pressao baixa PZR | primario |
| 10 | `alm_sg1_lo_level` | Alarme nivel baixo GV1 | gv1 |
| 11 | `alm_sg2_lo_level` | Alarme nivel baixo GV2 | gv2 |
| 12 | `alm_hi_coolant_temp` | Alarme temp. alta | primario |
| 13 | `alm_lo_flow` | Alarme vazao baixa | primario |
| 14 | `alm_hi_cont_press` | Alarme pressao contencao | contencao |
| 15 | `alm_hi_cont_rad` | Alarme radiacao alta | contencao |
| 16 | `przr_relief_open` | Alivio PZR aberto | primario |
| 17 | `rod_bottom` | Barras no fundo | nucleo |
| 18 | `auto_control_active` | Controle automatico | geral |
| 19 | `esfas_actuated` | ESFAS atuado (sinal S) | pxs |
| 20 | `cmt_injecting` | CMT injetando | pxs |
| 21 | `prhr_actuated` | PRHR atuado | pxs |
| 22 | `accum_injecting` | Acumulador injetando | pxs |
| 23 | `ads_actuated` | ADS atuado | pxs |
| 24 | `sg1_relief_open` | Alivio GV1 aberto | gv1 |
| 25 | `sg2_relief_open` | Alivio GV2 aberto | gv2 |
| 26 | `safety_blocked` | Salvaguardas bloqueadas | pxs |

## Coils — comandos digitais (FC1/5/15, escrita)

| Addr | Chave | Rótulo | Sistema |
|---|---|---|---|
| 0 | `cmd_manual_scram` | SCRAM manual | nucleo |
| 1 | `cmd_reset_trip` | Reset de trip | geral |
| 2 | `cmd_rcp1_start` | Liga RCP1 | primario |
| 3 | `cmd_rcp2_start` | Liga RCP2 | primario |
| 4 | `cmd_rcp3_start` | Liga RCP3 | primario |
| 5 | `cmd_rcp4_start` | Liga RCP4 | primario |
| 6 | `cmd_feed_pump_start` | Liga bomba agua alim. | geral |
| 7 | `cmd_przr_heater` | Aquecedor PZR | primario |
| 8 | `cmd_przr_spray` | Spray PZR | primario |
| 9 | `cmd_turbine_trip` | Desarme turbina | turbina |
| 10 | `cmd_auto_control` | Habilita controle auto | geral |
| 11 | `cmd_boron_charge` | Injeta boro | primario |
| 12 | `cmd_boron_dilute` | Dilui boro | primario |
| 13 | `cmd_manual_si` | Injecao seguranca manual | pxs |
| 14 | `cmd_manual_prhr` | PRHR manual | pxs |
| 15 | `cmd_manual_ads` | ADS manual | pxs |
| 16 | `cmd_block_safety` | Bloqueia salvaguardas | pxs |

## Holding Registers — setpoints/demandas (FC3/6/16, escrita)

| Addr | Chave | Rótulo | Sistema | Unid. | Escala | Faixa |
|---|---|---|---|---|---|---|
| 0 | `sp_power_pct` | Setpoint de potencia | nucleo | % | ×10 | 0–100 |
| 1 | `dmd_rod_pct` | Barras controle (% retirada) | nucleo | % | ×10 | 0–100 |
| 2 | `dmd_rcp_speed_pct` | Rotacao bombas RCP | primario | % | ×10 | 0–100 |
| 3 | `sp_przr_pressure_bar` | Setpoint pressao PZR | primario | bar | ×10 | 120–175 |
| 4 | `sp_przr_level_pct` | Setpoint nivel PZR | primario | % | ×10 | 0–100 |
| 5 | `sp_boron_ppm` | Setpoint boro | primario | ppm | ×1 | 0–3500 |
| 6 | `dmd_turbine_valve_pct` | Valvula admissao turbina | turbina | % | ×10 | 0–100 |
| 7 | `dmd_turbine_load_mwe` | Carga da turbina | turbina | MWe | ×10 | 0–1300 |
| 8 | `sp_sg1_level_pct` | Setpoint nivel GV1 | gv1 | % | ×10 | 0–100 |
| 9 | `dmd_sg1_feed_valve_pct` | Valvula agua alim. GV1 | gv1 | % | ×10 | 0–100 |
| 10 | `sp_sg2_level_pct` | Setpoint nivel GV2 | gv2 | % | ×10 | 0–100 |
| 11 | `dmd_sg2_feed_valve_pct` | Valvula agua alim. GV2 | gv2 | % | ×10 | 0–100 |

---

### Controles fora do Modbus (meta-simulação, via API HTTP)

Não são pontos de processo — não integram a superfície de ataque OT:

- `escala de tempo` (`POST /api/command {kind:"timescale"}`) — acelera só a evolução de venenos/burnup.
- `LOCA` (`POST /api/command {kind:"loca", value:0..1}`) — insere rompimento no primário.

### Contagem

- Input Registers: **41** · Discrete Inputs: **27** · Coils: **17** · Holding Registers: **12**
