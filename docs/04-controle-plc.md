# Controle e OpenPLC

O sistema de controle regula a planta para os setpoints. Ele existe em **duas
implementações equivalentes**, selecionadas pela coil `cmd_auto_control`:

| Modo | `cmd_auto_control` | Quem controla | Uso |
|---|---|---|---|
| **AUTO** | 1 | Malhas internas do simulador (`controllers/`) | Operação normal + HMI, planta usável sem CLP |
| **CLP-no-laço** | 0 | OpenPLC rodando `plc/npp_control.st` (mestre Modbus) | Exercícios que atacam o CLP |

Ambos implementam a mesma lógica; o segundo a executa num CLP real (OpenPLC),
tornando-o alvo de exercício. Configuração do OpenPLC: **`plc/README.md`**.

## Malhas de controle (espelham a planta real)

| Controlador | Arquivo | Entrada → Saída | Estratégia |
|---|---|---|---|
| Barras (potência) | `controllers/rod_control.py` | erro de potência → demanda de barras | proporcional incremental; MTC negativo estabiliza |
| Nível GV1 | `controllers/sg_level.py` (inst. 1) | nível + vazão de vapor → válvula de alim. | três elementos (nível + feedforward) |
| Nível GV2 | `controllers/sg_level.py` (inst. 2) | idem, **independente** | idem |
| Pressurizador | `controllers/pressurizer.py` | pressão → aquecedor/spray | bang-bang com banda morta |
| Turbina | `controllers/turbine_control.py` | demanda de potência → válvula | reator-segue-turbina |

As **duas malhas de nível de GV são independentes** (como no AP1000). No cyber
range isso permite atacar só o GV1 e observar a resposta assimétrica entre os
geradores — assinatura útil para detecção.

O assembler `controllers/control_system.py` agrega os controladores e produz as
demandas quando em AUTO. Em CLP-no-laço, ficam inativos e as demandas vêm dos
*holding registers* `dmd_*` escritos pelo OpenPLC.

## Controle × Proteção (independência)

O controle **não** é a proteção. Mesmo com o controle comprometido, o **RPS**
(`protection.py`) desarma o reator e o **ESFAS** atua as salvaguardas passivas.
Essa separação é a base do Defense-in-Depth (ver `docs/01` e `docs/06`) — e o
motivo pelo qual os ataques mais severos precisam também **enganar ou bloquear a
proteção** (injeção de sensor, `cmd_block_safety`), não só o controle.

## Fluxo de escrita/leitura (CLP-no-laço)

```
OpenPLC (mestre)  --read IR/DI-->  simulador (172.28.10.10:502)   sensores, status
OpenPLC (mestre)  --write HR/CO->  simulador                       demandas, comandos
ScadaLTS          --read/write-->  OpenPLC (:502) ou simulador     supervisão
HMI web           --HTTP/SSE---->  simulador                       operação
```

Detalhe do programa ST e do mapeamento de endereços: **`plc/npp_control.st`** e
**`plc/README.md`**. Mapa completo de pontos: **`docs/03-mapa-io-modbus.md`**.
