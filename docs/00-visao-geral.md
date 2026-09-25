# Visão geral e glossário

**OpenNPP** é um cyber range de OT/ICS: um simulador virtual de usina nuclear PWR
classe AP1000, para treino **defensivo** de segurança de sistemas de controle
industrial. Ambiente 100% isolado; sem planta física real.

## Índice da documentação

| # | Documento | Conteúdo |
|---|---|---|
| 01 | [Arquitetura](01-arquitetura.md) | Purdue, modularidade, rede, Defense-in-Depth |
| 02 | [Modelo físico](02-modelo-fisico.md) | Neutrônica, termohidráulica, AP1000, validação |
| 03 | [Mapa de I/O Modbus](03-mapa-io-modbus.md) | Todos os pontos de processo (gerado do código) |
| 04 | [Controle e OpenPLC](04-controle-plc.md) | Malhas de controle, modos, CLP |
| 05 | [HMI e ScadaLTS](05-hmi.md) | Operação, API, SCADA |
| 06 | [Modelo de ameaças](06-modelo-ameacas.md) | Superfície de ataque, MITRE ATT&CK for ICS |
| 07 | [Playbooks](07-playbooks-ataque-defesa.md) | Exercícios red/blue com detecção e mitigação |

Guias de configuração: [`plc/README.md`](../plc/README.md) (OpenPLC) e
[`scadalts/README.md`](../scadalts/README.md). Ferramenta de exercício:
[`tools/attacks.py`](../tools/attacks.py).

## A planta em uma frase

Um reator (núcleo) aquece o refrigerante do **primário**, que circula por 4 bombas
e transfere calor a **2 geradores de vapor**; o vapor move a **turbina/gerador**;
o **pressurizador** mantém a pressão; e camadas de **proteção** (RPS) e
**salvaguardas passivas** (PXS) garantem a segurança — a base do Defense-in-Depth.

## Glossário

| Sigla | Significado | No range |
|---|---|---|
| **OT / ICS** | Operational Technology / Industrial Control Systems | o alvo do treino |
| **PWR** | Pressurized Water Reactor | tipo do reator simulado |
| **AP1000** | PWR Gen III+ da Westinghouse | modelo de referência |
| **Purdue** | Modelo de referência de níveis (0–5) de arquitetura ICS | organiza a rede |
| **DID** | Defense-in-Depth (defesa em profundidade) | camadas independentes de segurança |
| **RPS** | Reactor Protection System | trip/SCRAM do reator |
| **ESFAS** | Engineered Safety Features Actuation System | atua as salvaguardas |
| **PXS** | Passive Core Cooling System | segurança passiva do AP1000 |
| **CMT** | Core Makeup Tank | injeção de água borada por gravidade |
| **PRHR** | Passive Residual Heat Removal | remove calor residual pós-trip |
| **ADS** | Automatic Depressurization System | despressuriza o primário (4 estágios) |
| **IRWST** | In-containment Refueling Water Storage Tank | reservatório da contenção |
| **RCP** | Reactor Coolant Pump | bomba do primário (4 unidades) |
| **GV** | Gerador de vapor | 2 unidades, 1 controlador de nível cada |
| **PZR** | Pressurizador | mantém a pressão do primário |
| **SCRAM** | Desligamento rápido (inserção das barras) | parada de emergência |
| **MTC** | Moderator Temperature Coefficient | realimentação negativa de reatividade |
| **pcm** | por cem mil (10⁻⁵ Δk/k) | unidade de reatividade |
| **Xe-135 / I-135** | Xenônio / Iodo (venenos de fissão) | pico pós-SCRAM, "poço de iodo" |
| **Sm-149** | Samário-149 (veneno permanente) | buildup após desligamento |
| **Burnup** | queima do combustível | depleta o veneno queimável |
| **LOCA** | Loss of Coolant Accident | perda de refrigerante do primário |
| **Modbus** | Protocolo industrial (sem autenticação) | barramento de campo / superfície de ataque |
| **HMI** | Human-Machine Interface | supervisão/operação |
| **SCADA** | Supervisory Control and Data Acquisition | ScadaLTS (nível 2) |
| **CLP** | Controlador Lógico Programável (PLC) | OpenPLC (nível 1) |
