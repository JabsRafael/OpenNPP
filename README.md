# OpenNPP — Cyber Range de OT/ICS (Usina Nuclear AP1000-like)

Simulador **100% virtual** de uma usina nuclear PWR classe **AP1000**, montado como
**cyber range de Tecnologia Operacional (OT/ICS)** para treino de segurança
cibernética em infraestrutura crítica: entender a superfície de ataque de
sistemas de controle industrial (CLP, SCADA, Modbus) para **saber defendê-los**.

> ⚠️ **Ambiente educacional e defensivo.** Não há planta física real. O processo,
> os sensores e os atuadores são simulados por software. As vulnerabilidades (ex.:
> Modbus sem autenticação) são **intencionais e realistas** — reproduzem sistemas
> OT legados para exercícios de red team / blue team em laboratório isolado.
> Use apenas no seu ambiente. Ver [docs/06](docs/06-modelo-ameacas.md).

## O que compõe o range

| Componente | Papel | Nível Purdue | Porta |
|---|---|---|---|
| **Simulador de processo** (Python) | A "planta": física do reator AP1000 + servidor Modbus + HMI web | 0/1/2 | 5000 (HMI), 5020→502 (Modbus) |
| **OpenPLC** | CLP de controle (lógica IEC 61131-3, mestre Modbus) | 1 | 8082 (web), 5021→502 |
| **ScadaLTS** | SCADA/HMI supervisório | 2 | 8080 |
| **MySQL** | Backend/historiador do ScadaLTS | 3 | — |

A planta é **modular**, espelhando uma usina real (ver [docs/01](docs/01-arquitetura.md)):

```
REATOR (núcleo)  →  PRIMÁRIO (2 loops, 4 RCPs, pressurizador)  →  2× GERADOR DE VAPOR
     │                                                                    │
 neutrônica                                                          SECUNDÁRIO → TURBINA/GERADOR
 + reatividade                                                            │
     └──────────────  SALVAGUARDAS PASSIVAS (PXS): CMT · ACUM · PRHR · ADS · IRWST
                       + PROTEÇÃO (RPS trip / ESFAS)  ← Defense-in-Depth
```

## Início rápido

```bash
# subir todo o range
docker compose up -d --build

# HMI da planta (mímico ao vivo, alarmes, controle)
#   http://localhost:5000
# OpenPLC (configurar como mestre Modbus -> ver plc/README.md)
#   http://localhost:8082      (login padrão openplc / openplc)
# ScadaLTS
#   http://localhost:8080      (ver scadalts/README.md)
```

Só a planta (sem CLP/SCADA), útil para desenvolver:

```bash
docker compose up -d --build simulator
```

## Documentação

1. [Arquitetura](docs/01-arquitetura.md) — Purdue, modularidade, rede, DID
2. [Modelo físico](docs/02-modelo-fisico.md) — neutrônica, termohidráulica, AP1000
3. [Mapa de I/O Modbus](docs/03-mapa-io-modbus.md) — todos os pontos de processo
4. [Controle e OpenPLC](docs/04-controle-plc.md) — malhas + programa ST
5. [HMI e ScadaLTS](docs/05-hmi.md) — operação
6. [Modelo de ameaças](docs/06-modelo-ameacas.md) — superfície de ataque, MITRE ATT&CK for ICS
7. [Playbooks ataque/defesa](docs/07-playbooks-ataque-defesa.md) — exercícios red/blue

## Estrutura

```
simulator/            planta simulada (Python)
  npp/
    components/        REATOR, primário, gerador de vapor, turbina, segurança
    controllers/       controle de barras, pressurizador, nível (1 por GV), turbina
    iomap.py           mapa Modbus (fonte única de verdade)
    protection.py      RPS + ESFAS
    plant.py           montagem/orquestração
    engine.py          laço de tempo real + datastore Modbus
    modbus_server.py   servidor Modbus TCP (rede OT)
    api.py             HTTP + SSE (HMI)
  web/                 HMI web (mímico SVG)
plc/                   programa de controle OpenPLC (Structured Text)
scadalts/              configuração do SCADA
tools/                 ferramentas de exercício (red/blue)
docs/                  documentação
```
