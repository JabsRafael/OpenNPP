# Playbooks de ataque/defesa (red / blue)

> Exercícios contra o ambiente **SIMULADO e isolado** OpenNPP. Objetivo **defensivo**:
> executar o ataque para depois **detectá-lo e mitigá-lo**. Não use fora do laboratório.

Cada playbook segue: **objetivo → red (executar) → efeito no processo → blue
(detectar) → blue (mitigar) → lição DID**. As ações "red" usam a HMI (porta 5000),
o Modbus direto (`tools/attacks.py`, alvo `127.0.0.1:5020`) ou o ScadaLTS/OpenPLC.

## Preparação do blue team (monitoração)

Antes de começar, ligue a captura de tráfego OT para reproduzir a detecção:

```bash
# capturar Modbus (porta 502) na rede do range
docker run --rm --net container:npp-simulator nicolaka/netshoot \
  tcpdump -i any -w /tmp/modbus.pcap 'tcp port 502'
# depois abra no Wireshark: filtro  modbus  — inspecione write_coil / write_register,
# a origem (IP), a frequencia e a funcao. Escrita vinda de host != CLP/operador = suspeita.
```

Baseline esperado (operação normal): o **mestre legítimo** (CLP/HMI) escreve num
ritmo estável; leituras periódicas. Desvios (novo IP escrevendo, rajadas, escrita
em coils de segurança) são o sinal.

---

## PB-01 — Reconhecimento Modbus

- **Objetivo (red):** mapear os pontos de processo sem credenciais.
- **Red:** `python3 tools/attacks.py recon`
- **Efeito:** nenhum no processo; atacante obtém o mapa completo (tags, faixas).
- **Blue (detectar):** host desconhecido lendo faixas amplas/incomuns; varredura
  sequencial de registradores. `MITRE T0846 / T0861`.
- **Blue (mitigar):** allow-list de mestres Modbus; segmentar a rede; IDS de OT
  (ex.: Zeek/Suricata com dissector Modbus) alarmando enumeração.
- **DID:** reconhecimento é pré-ataque — a barreira certa é de **rede**, não de processo.

---

## PB-02 — SCRAM indevido (parada forçada)

- **Objetivo (red):** derrubar a usina escrevendo um único coil.
- **Red:** `python3 tools/attacks.py scram`  (ou HMI → botão "SCRAM manual", ou
  `write_coil(0, True)`).
- **Efeito:** reator desarma, potência → calor de decaimento, geração a zero.
  Perda de produção; disponibilidade comprometida.
- **Blue (detectar):** `cmd_manual_scram=1` vindo de origem não autorizada; **trip
  sem causa de processo** (nenhum sensor fora de faixa antes do trip). `T0855 / T0827`.
- **Blue (mitigar):** allow-list de mestres; registro imutável de comandos com
  origem; correlação "comando × condição de processo".
- **DID:** aqui o atacante *usa* a proteção como arma — a defesa é de acesso/origem.

---

## PB-03 — Excursão de potência via barras (camada única, contida)

- **Objetivo (red):** inserir reatividade positiva puxando as barras.
- **Red:** `python3 tools/attacks.py rod_pull` (força manual e `dmd_rod=100%`).
- **Efeito:** potência sobe rápido → **o RPS desarma por fluxo alto** → potência
  colapsa. O ataque é **contido** pela proteção.
- **Blue (detectar):** `cmd_auto_control` caiu para 0 e `dmd_rod` subiu sem ordem;
  `neutron_flux` subindo antes do trip. `T0836 / T0831`.
- **Blue (mitigar):** proteger setpoints/modo; alarmar mudança de auto→manual;
  intertravamento de taxa de retirada de barras.
- **DID:** **lição-chave** — vencer só o controle (nível 2) não causa dano porque a
  proteção (nível 3) atua. Ataques sérios precisam de mais de uma camada (→ PB-05).

---

## PB-04 — Perda de vazão / desarme de turbina

- **Objetivo (red):** provocar transiente térmico desligando bombas ou a turbina.
- **Red:** `python3 tools/attacks.py stop_pumps`  ou  `... turbine_trip`.
- **Efeito:** *stop_pumps* → vazão cai, Thot dispara, RPS desarma por baixa vazão.
  *turbine_trip* → perde geração, reator faz runback/trip.
- **Blue (detectar):** coils `cmd_rcpN_start`/`cmd_turbine_trip` comandados sem
  falha de máquina correlata; queda de vazão/rotação correlacionada ao comando.
- **Blue (mitigar):** allow-list; intertravamentos físicos de bomba; alarme de
  parada não comandada.
- **DID:** proteção contém, mas há transiente térmico — mostra o custo mesmo com trip.

---

## PB-05 — Bypass de salvaguardas + transiente (camada dupla)

- **Objetivo (red):** inibir a camada de salvaguardas **antes** de provocar dano —
  o padrão de ataques a segurança física (tipo "defeat the safety system").
- **Red:**
  1. `python3 tools/attacks.py block_safety`  (`cmd_block_safety=1` → ESFAS/PXS inibido)
  2. Em seguida provoque perda de inventário/calor (ex.: desligue a água de
     alimentação pela HMI: coils `cmd_feed_pump_start=0`, e/ou `stop_pumps`).
- **Efeito:** com as salvaguardas passivas bloqueadas, os transientes evoluem sem a
  mitigação passiva (PRHR/CMT não atuam) — consequências mais severas.
- **Blue (detectar):** **`safety_blocked=1` em operação normal é anomalia crítica**
  — jamais deveria ocorrer; alarme imediato de altíssima prioridade. `T0804 / T0880`.
- **Blue (mitigar):** o bypass de manutenção deve exigir **chave física** e estar
  fora da rede de controle; alarmar qualquer ativação; RPS/ESFAS em rede segregada.
- **DID:** demonstra por que a **independência das camadas** é vital — o ataque só
  é grave porque derruba a barreira de segurança, não só o controle.

---

## PB-06 — Pivô TI → OT (rede plana)

- **Objetivo (red):** alcançar o CLP/simulador a partir de um host "de TI".
- **Red:** de qualquer host na `172.28.10.0/24` (rede **plana**, sem firewall),
  alcance o ScadaLTS (`:8080`, Tomcat/Java legado) ou o OpenPLC (`:8082`) e, dali,
  escreva no Modbus (`:502`). Ex.: subir um container atacante na mesma rede.
- **Efeito:** movimento lateral livre — TI e OT no mesmo domínio.
- **Blue (detectar):** conexões cruzando fronteira lógica TI↔OT; acesso à web de
  engenharia do CLP de origem inesperada. `T0819`.
- **Blue (mitigar):** **segmentação** (firewall entre TI e OT, DMZ de dados,
  idealmente diodo de dados); MFA/hardening nas HMIs; remover exposição direta.
- **DID:** a barreira de **rede** é a primeira linha; sua ausência habilita tudo acima.

---

## Detecção baseada em processo (o diferencial de OT)

Além de rede, o blue team de OT detecta pela **física**: um estado que viola o
modelo esperado indica manipulação, mesmo que o comando pareça "válido".

| Regra de detecção | Racional |
|---|---|
| Potência muda sem comando de barras correspondente | injeção/manipulação de atuador |
| `GV1` e `GV2` divergem persistentemente | ataque a uma única malha de nível |
| Trip sem sensor fora de faixa nos segundos anteriores | comando de SCRAM injetado |
| `safety_blocked=1` a qualquer momento em operação | bypass indevido |
| Escrita em coil de origem ≠ mestre legítimo | comando não autorizado |

Implemente estas regras lendo o `/api/state` (ou o Modbus) e comparando com a
física esperada — é o embrião de um **IDS de processo**.

## Objetivos de treino (scorecard)

- **Red:** conseguir impacto (parada/transiente) e, no PB-05, dano com salvaguarda
  vencida.
- **Blue:** para cada PB, (1) detectar em captura/telemetria, (2) nomear a técnica
  MITRE, (3) propor e, quando possível, aplicar a mitigação (allow-list,
  segmentação, alarme de anomalia).
