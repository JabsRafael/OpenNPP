"""
Servidor Modbus TCP — a interface de campo (rede OT) do simulador.

Serve o mesmo datastore usado pela fisica (engine.context). Qualquer mestre
Modbus na rede pode ler sensores e ESCREVER coils/holding registers, sem
autenticacao — exatamente como um CLP/RTU industrial legado. Essa ausencia de
autenticacao e' o ponto central dos exercicios de cyber range (ver docs/07).

Nivel Purdue 1 (controle). Porta 502/tcp (Modbus).
"""

import asyncio
import threading

from pymodbus.server import StartAsyncTcpServer


def start_modbus_server(context, host="0.0.0.0", port=502):
    def _run():
        asyncio.run(StartAsyncTcpServer(context=context, address=(host, port)))

    th = threading.Thread(target=_run, daemon=True, name="modbus-server")
    th.start()
    return th
