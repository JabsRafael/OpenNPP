# ScadaLTS — camada SCADA supervisória (OpenNPP)

Guia para configurar o **ScadaLTS** como SCADA supervisório apontando para o
simulador/OpenPLC via **Modbus TCP**. O ScadaLTS roda no container `npp-scadalts`
(`172.28.10.30`) e é publicado em **http://localhost:8080**.

> Ambiente 100% SIMULADO para treino de OT/ICS. Aqui tratamos só da configuração
> funcional. As atividades de exercício (o ScadaLTS é um alvo realista — stack
> Java/Tomcat legado) ficam em `docs/07`.

## 1. Login inicial

1. Abra **http://localhost:8080** (o primeiro boot do Tomcat/MySQL pode levar
   1–2 min).
2. Usuário/senha padrão: **`admin` / `admin`**.
3. **Troque a senha** logo após entrar (menu do usuário → *Change password*).
   Mesmo sendo laboratório, a credencial padrão faz parte da superfície de ataque.

## 2. Alvo Modbus

O ScadaLTS é **cliente/mestre** Modbus. Aponte para um destes escravos na rede
`opennpp` (172.28.10.0/24):

| Alvo | IP interno | Porta | Uso |
|---|---|---|---|
| Simulador (planta) | `172.28.10.10` | `502` | leitura direta do processo simulado |
| OpenPLC (CLP) | `172.28.10.20` | `502` | leitura/escrita passando pela lógica do CLP |

Use os IPs internos (não `localhost`): o ScadaLTS resolve a rede Docker interna.

## 3. Criar o Data Source (Modbus IP)

1. Menu **Data sources** → **Add data source** → tipo **Modbus IP**.
2. Campos:
   - **Name:** `OpenNPP-Sim` (ou `OpenNPP-PLC`).
   - **Transport type:** `TCP`.
   - **Host:** `172.28.10.10` (simulador) ou `172.28.10.20` (OpenPLC).
   - **Port:** `502`.
   - **Update period:** `1 second` (o simulador atualiza rápido; 1 s basta).
   - **Timeout / Retries:** deixe o padrão (ex.: 500 ms / 2).
3. **Save** e habilite o Data Source (ícone de ligado/desligado).

## 4. Ranges e escalas do Modbus

Fonte única dos pontos: `simulator/npp/iomap.py` (ver `docs/03`). Conceitos que
você vai usar em cada Data Point:

- **Modbus register range:**
  - **Input Register** (FC4, só leitura) → sensores. Ex.: `reactor_power_pct`.
  - **Holding Register** (FC3/6/16, leitura/escrita) → setpoints. Ex.: `sp_power_pct`.
  - **Coil Status** (FC1/5, leitura/escrita, bit) → comandos. Ex.: `cmd_manual_scram`.
- **Offset:** é **0-based**. `IR0` = offset `0`, `HR0` = offset `0`, `coil0` =
  offset `0`. (O ScadaLTS pergunta o offset diretamente; não some/subtraia 40001
  etc.)
- **Escala:** o simulador guarda inteiros de 16 bits com `valor_eng = raw /
  scale`. Para desfazer, use um **multiplicador** no Data Point. Escala `×10`
  ⇒ multiplicador **`0.1`**. Escala `×100` ⇒ **`0.01`**. Escala `×1` ⇒ sem
  multiplicador.

## 5. Criar Data Points (mapeamento de exemplo)

Dentro do Data Source, **Add point** para cada registrador. `Data type` =
`Numeric` para registradores; `Binary` para coils.

| Nome | Range | Offset | Data type | Multiplicador |
|---|---|---|---|---|
| Potência do reator (%) | Input Register | `0` | Numeric (2-byte int) | `0.1` |
| Tavg (°C) | Input Register | `6` | Numeric (2-byte int) | `0.1` |
| Pressão PZR (bar) | Input Register | `11` | Numeric (2-byte int) | `0.1` |
| Nível GV1 (%) | Input Register | `15` | Numeric (2-byte int) | `0.1` |
| SCRAM manual | Coil Status | `0` | Binary | — |
| SP potência (%) | Holding Register | `0` | Numeric (2-byte int) | `0.1` |

Passos por ponto:
1. **Point locator:** escolha o *range* (Input/Holding Register ou Coil Status),
   informe o **offset** (coluna acima) e, para registradores, o tipo binário
   `2-byte unsigned/signed integer`.
2. Em **Numeric** aplique o multiplicador na aba de *rendering*/*text renderer*
   (ex.: multiplicador `0.1`, sufixo ` %` / ` °C` / ` bar`).
3. Ative o ponto (ícone verde) e **Save**.

> Escrita: `SP potencia` (HR0) e `SCRAM manual` (coil0) são graváveis. Setar o
> *Settable* no ponto permite comandar a planta pelo SCADA — isso escreve nos
> mesmos registradores da rede OT (ver nota de segurança em `docs/05-hmi.md`).

## 6. Watchlist e tela gráfica

**Watchlist** (rápido):
1. Menu **Watch list** → arraste os Data Points criados para a lista.
2. Confira os valores atualizando (~1 s) e já convertidos pela escala.

**Graphical View** (tela simples):
1. Menu **Graphical Views** → **Add view**, dê um nome (`OpenNPP Overview`).
2. Faça upload de uma imagem de fundo (opcional) ou use fundo liso.
3. Arraste componentes (ex.: *Analog/Simple point*) para a tela e associe cada um
   a um Data Point: Potência, Tavg, Pressão PZR, Nível GV1, badge do SCRAM.
4. **Save**. Abra a view para supervisão ao vivo.

## 7. Nota didática

O ScadaLTS aqui é a camada supervisória **e** um alvo realista (Java/Tomcat
legado, credencial padrão, Modbus sem autenticação a jusante). Esta página cobre
apenas a configuração funcional; os cenários de exercício (ataque/detecção)
estão em `docs/07`.
