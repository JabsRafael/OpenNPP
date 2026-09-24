"""
Ponto de entrada do simulador OpenNPP (planta AP1000-like).

Sobe tres coisas:
  1. Engine de simulacao (laco de fisica em tempo real)      -> thread
  2. Servidor Modbus TCP (rede OT / Nivel Purdue 1)           -> thread, porta 502
  3. API HTTP + HMI web (supervisao / Nivel Purdue 2)         -> principal, porta 5000

Variaveis de ambiente:
  MODBUS_PORT (default 502), API_PORT (default 5000), BIND (default 0.0.0.0)
"""

import os

from npp.api import start_api
from npp.engine import SimEngine
from npp.modbus_server import start_modbus_server


def main():
    bind = os.environ.get("BIND", "0.0.0.0")
    modbus_port = int(os.environ.get("MODBUS_PORT", "502"))
    api_port = int(os.environ.get("API_PORT", "5000"))

    engine = SimEngine()
    engine.start_thread()
    start_modbus_server(engine.context, bind, modbus_port)

    print(f"[OpenNPP] simulador AP1000-like ativo")
    print(f"[OpenNPP] Modbus TCP (rede OT)  -> {bind}:{modbus_port}")
    print(f"[OpenNPP] HMI web + API         -> http://{bind}:{api_port}")
    start_api(engine, bind, api_port)


if __name__ == "__main__":
    main()
