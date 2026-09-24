# 01 — Arquitetura do OpenNPP

Documento de arquitetura do **OpenNPP**, um cyber range de OT/ICS construido
sobre um simulador **100% virtual** de uma usina nuclear PWR classe **AP1000**.
Nao existe planta fisica: processo, sensores e atuadores sao software. O ambiente
serve a exercicios defensivos de seguranca de OT (red team / blue team) em
laboratorio isolado.

## 1. Visao geral e principios

O range e organizado sobre tres principios:

- **Modularidade espelhando a planta real.** Cada sistema fisico da usina vira um
  modulo de software independente (`simulator/npp/components/`), e cada malha de
  controle vira um controlador (`simulator/npp/controllers/`). A topologia de
  software reproduz a topologia de engenharia da usina.
- **Ambiente simulado e defensivo.** As vulnerabilidades (ex.: Modbus sem
  autenticacao) sao intencionais e realistas, reproduzindo OT legado. O objetivo
  e entender a superficie de ataque para saber defende-la.
- **Fonte unica de estado.** Todo o processo vive no datastore Modbus (`pymodbus`),
  exposto identicamente na rede OT e para a HMI. Isso torna visivel a licao
  central: no chao de fabrica, um comando legitimo e uma escrita de atacante sao
  indistinguiveis.

Fluxo fisico de energia (macro):

```
REATOR (nucleo) -> PRIMARIO (2 loops, 4 RCPs, pressurizador) -> 2x GERADOR DE VAPOR
     |                                                                |
 neutronica + reatividade                                  SECUNDARIO -> TURBINA/GERADOR
     |
     +-- SALVAGUARDAS PASSIVAS (PXS): CMT . ACUM . PRHR . ADS . IRWST
         + PROTECAO (RPS trip / ESFAS)  <- Defense-in-Depth
```

## 2. Modelo Purdue e mapeamento dos containers

O modelo Purdue organiza sistemas OT em niveis. O `docker-compose.yml` do range
mapeia cada container a um nivel logico:

```
+-------------------------------------------------------------+
| Nivel 3  DADOS / HISTORIADOR    database (MySQL) .40         |
+-------------------------------------------------------------+
| Nivel 2  SUPERVISAO             scadalts .30                 |
|                                 HMI web do simulator (:5000) |
+-------------------------------------------------------------+
| Nivel 1  CONTROLE               openplc .20  (CLP)           |
|                                 simulator Modbus (:502)      |
+-------------------------------------------------------------+
| Nivel 0  PROCESSO / CAMPO       simulator .10 (fisica)       |
+-------------------------------------------------------------+
```

O container `simulator` acumula Niveis 0/1/2: modela o processo (Nivel 0),
publica os sensores/atuadores via servidor Modbus (Nivel 1) e serve a HMI web
(Nivel 2). Essa concentracao e uma simplificacao de laboratorio.

### Tabela de servicos, IPs e portas

Rede unica `opennpp_net` (bridge), subnet `172.28.10.0/24`.

| Servico     | Container       | IP fixo        | Nivel Purdue | Portas (host -> container)          |
|-------------|-----------------|----------------|--------------|-------------------------------------|
| simulator   | npp-simulator   | 172.28.10.10   | 0 / 1 / 2    | 5000:5000 (HMI+API), 5020:502 (Modbus) |
| openplc     | npp-openplc     | 172.28.10.20   | 1            | 8082:8081 (web), 5021:502 (Modbus)  |
| scadalts    | npp-scadalts    | 172.28.10.30   | 2            | 8080:8080 (SCADA web)               |
| database    | npp-mysql       | 172.28.10.40   | 3            | (sem publicacao no host)            |

Observacoes:

- `5020->502` expoe o Modbus da planta a ferramentas rodando no host.
- `5021->502` e o servidor Modbus do proprio OpenPLC.
- O simulator recebe `MODBUS_PORT=502` e `API_PORT=5000` por variavel de ambiente.
- `openplc` roda `privileged: true` e depende de `simulator`; `scadalts` depende
  de `database` saudavel (healthcheck via `mysqladmin ping`).

## 3. Arquitetura modular do simulador

Os modulos fisicos vivem em `simulator/npp/components/` e sao montados por
`simulator/npp/plant.py` na classe `Plant`:

- `ReactorCore` (`core.py`) — nucleo / neutronica.
- `PrimarySystem` (`primary.py`) — 2 loops, 4 RCPs, pressurizador, boro.
- `SteamGenerator` (`steam_generator.py`) — instanciado **duas vezes**: `GV1`, `GV2`.
- `Turbine` (`turbine.py`) — turbina/gerador.
- `PassiveSafety` (`safety.py`) — salvaguardas passivas PXS + contencao.

### ProcessBus: desacoplamento intencional

Os modulos **nao se conhecem**. Toda variavel de acoplamento passa pelo
`ProcessBus` (`components/bus.py`): cada componente le do bus o que precisa e
escreve suas saidas. O nucleo nao referencia o gerador de vapor; ambos so falam
com o bus. Esse desacoplamento e deliberado e espelha as interfaces fisicas
reais entre sistemas da planta (temperaturas `T_hot`/`T_cold`, `Q_sg_total`,
`Q_prhr`, `si_flow`, flags `tripped`/`turbine_tripped`, etc.).

```
        +-----------------------------------------------+
        |                 ProcessBus                    |
        |  P_th, reactivity, T_fuel, T_hot/T_cold,      |
        |  core_dt, flow_frac, boron, Q_core,           |
        |  Q_sg_total, Q_prhr, steam_flow_total,        |
        |  si_flow, tripped, turbine_tripped            |
        +-----------------------------------------------+
           ^        ^         ^        ^         ^
           |        |         |        |         |
       ReactorCore  SG(GV1/GV2)  PrimarySystem  Turbine  PassiveSafety
```

### Ordem de avaliacao por passo

`Plant.step(dt, cmd, sp, auto)` respeita o fluxo de energia:

```
1. nucleo               core.step(bus, dt)
2. geradores de vapor   for gv in [GV1, GV2]: gv.step(bus, dt, ...)
3. primario             primary.step(bus, dt, heater, spray)
4. turbina              turbine.step(bus, dt)
5. protecao             protection.evaluate(plant, cmd)  -> RPS/ESFAS
6. salvaguardas         safety.step(bus, dt, esfas, primary)
```

Antes disso, o passo resolve as **demandas de atuador** (secao 4) e aplica
atuadores diretos (partida de RCPs, carga/diluicao de boro, movimento de barras).

## 4. Separacao controle x protecao

Duas responsabilidades ficam deliberadamente separadas:

- **Controle** (`controllers/`) — regulacao da operacao normal. `ControlSystem`
  agrega `RodControl` (potencia via barras), `PressurizerControl` (pressao,
  bang-bang com banda morta), `TurbineControl` (valvula de admissao) e **duas**
  `SGLevelControl` independentes (nivel de `GV1` e `GV2`, com feedforward de vapor).
- **Protecao** (`protection.py`) — camadas de seguranca independentes do controle.
  `RPS` (Reactor Protection System) desarma o reator (SCRAM); `ESFAS` (Engineered
  Safety Features Actuation System) atua as salvaguardas passivas. Em uma usina
  real sao sistemas qualificados, redundantes e separados do CLP; aqui sao a
  camada de ultima instancia.

### Dois modos de operacao

O bit (coil) `cmd_auto_control` seleciona quem gera as demandas:

| Modo               | cmd_auto_control | Origem das demandas                                  |
|--------------------|------------------|------------------------------------------------------|
| AUTO               | 1                | Malhas internas do simulador (`ControlSystem.update`) |
| MANUAL / CLP-no-laco | 0              | Holding registers escritos pelo OpenPLC ou operador   |

Em AUTO, o `ControlSystem` calcula `rod_demand_pct`, `turbine_valve_pct`,
`feed_valve[GV1/GV2]`, `heater`, `spray`; o `engine` ainda escreve essas demandas
de volta nos holding registers (`dmd_*`) para a HMI exibir. Em MANUAL, o
`ControlSystem` fica inativo e as demandas vem de `sp["dmd_rod_pct"]`,
`sp["dmd_sg1_feed_valve_pct"]`, `sp["dmd_sg2_feed_valve_pct"]`,
`sp["dmd_turbine_valve_pct"]` e dos comandos `cmd_przr_heater`/`cmd_przr_spray`.

## 5. Fluxo de dados

O datastore Modbus (`pymodbus`, montado no `SimEngine`) e a **fonte unica de
estado**. Quatro tabelas: coils (comandos), discrete inputs (status/alarmes),
holding registers (setpoints/demandas) e input registers (sensores).

```
        +---------------------------- SimEngine (engine.py) ----------------------------+
        |  step_once():                                                                 |
        |    le  COILS + HOLDING_REGISTERS  -> cmd, sp, auto                             |
        |    roda plant.step(dt, cmd, sp, auto)                                          |
        |    escreve DISCRETE_INPUTS (status) + INPUT_REGISTERS (sensores)              |
        |    [AUTO] escreve de volta demandas calculadas nos HOLDING_REGISTERS          |
        +----------------------------------+--------------------------------------------+
                                           |
                     datastore Modbus (mesma tabela)
                          /                         \
             porta 502 (rede OT)              API HTTP/SSE (api.py)
             OpenPLC, ferramentas red          HMI web (:5000)
```

O engine roda em thread propria, em laco de (quase) tempo real. A mesma tabela
servida na porta 502 e lida pela HMI via API HTTP/SSE.

**Consequencia de seguranca:** como HMI, OpenPLC e atacante escrevem no *mesmo*
datastore sem autenticacao, um comando legitimo de HMI e uma escrita maliciosa
tem efeito **identico**. Nao ha, no protocolo, como distinguir origem ou intencao.

## 6. Defense-in-Depth (DID)

As cinco camadas conceituais de Defense-in-Depth (IAEA) mapeadas ao simulador:

| Camada DID | Conceito                          | No OpenNPP                                                      |
|------------|-----------------------------------|----------------------------------------------------------------|
| 1          | Prevencao / projeto conservador   | Fisica do modelo (ex.: MTC negativo -> resposta estavel)        |
| 2          | Controle da operacao normal       | `controllers/` (barras, pressurizador, turbina, nivel GV1/GV2)  |
| 3          | Protecao                          | `RPS` trip / SCRAM (`protection.py`)                            |
| 4          | Salvaguardas de engenharia        | `ESFAS` + PXS passiva: CMT, PRHR, ACUM, ADS, IRWST (`safety.py`) |
| 5          | Mitigacao / contencao             | Barreira de contencao (pressao/temp/radiacao em `safety.py`)    |

Licao central: **vencer uma camada nao causa dano se as seguintes atuam.** Se o
atacante domina o controle (camada 2) e leva o reator a condicao anormal, o RPS
(camada 3) desarma; se a despressurizacao avanca, o ESFAS/PXS (camada 4) injeta
inventario; a contencao (camada 5) e a barreira final. Por isso ataques realistas
miram **multiplas camadas ao mesmo tempo** — por exemplo, injetar valores falsos
de sensor (RPS/ESFAS leem sensores) ou acionar `cmd_block_safety`, um bypass de
manutencao que derruba a camada 4 sem tocar no controle. Deteccao no blue team:
`cmd_block_safety` jamais deveria estar ativo em operacao normal.

## 7. Segmentacao de rede

Hoje a rede e uma **unica sub-rede plana** `172.28.10.0/24`, com todos os
containers no mesmo dominio de broadcast e sem controle de trafego entre niveis.
Isso e **intencionalmente fraco**: reproduz o cenario comum de OT legado onde IT,
supervisao e controle compartilham a mesma rede, e serve de ponto de partida para
exercicios de hardening.

```
HOJE (plano, inseguro):
  simulator .10   openplc .20   scadalts .30   database .40
        \_____________|______________|______________/
                  172.28.10.0/24  (tudo se ve)

ALVO DE HARDENING (exercicio):
  [ IT / corporativo ] --firewall-- [ DMZ de dados ] --diodo de dados--> [ OT ]
                                    (historiador,               (Nivel 0/1:
                                     replica read-only)          simulator, openplc)
```

Exercicios de segmentacao sugeridos:

- **Firewall / zonas e conduites** — separar Nivel 3 (dados) dos Niveis 0/1
  (controle), permitindo apenas fluxos necessarios.
- **DMZ de dados** — o historiador (MySQL/ScadaLTS) fica numa zona intermediaria;
  IT nunca fala direto com o controle.
- **Diodo de dados** — impor fluxo unidirecional OT -> IT para telemetria,
  bloqueando qualquer escrita de volta ao processo.

Comparar a superficie de ataque antes e depois da segmentacao e o objetivo
pedagogico: mostrar quanto do vetor "escrita Modbus direta no processo" desaparece
quando o acesso ao Nivel 1 e restringido.
