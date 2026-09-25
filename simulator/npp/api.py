"""
API HTTP + SSE que serve a HMI web (Nivel Purdue 2 — supervisao).

Endpoints:
  GET  /                -> HMI (web/index.html)
  GET  /help            -> manual do operador (significados, permissivos, siglas)
  GET  /app.js /style.css
  GET  /api/meta        -> metadados dos pontos (rotulos, unidades, faixas, sistema)
  GET  /api/state       -> snapshot unico (JSON)
  GET  /api/stream      -> Server-Sent Events (~4 Hz) com o estado ao vivo
  POST /api/command     -> {"kind":"coil"|"hr"|"hr_step", "key":..., "value":...}
                           {"kind":"reset"} -> rearme; responde {reset, reasons[]}
                           {"kind":"rod", "value":"in"|"out"|"hold"} -> alavanca das barras
                           {"kind":"timescale"|"speed"|"loca"|"scenario", "value":...}

Somente biblioteca padrao (sem Flask/websockets). Os comandos da HMI escrevem nos
MESMOS registradores Modbus: um operador legitimo e um atacante Modbus tem efeito
identico — didatico para o cyber range.
"""

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .iomap import COILS, DISCRETE_INPUTS, HOLDING_REGISTERS, INPUT_REGISTERS

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")


def _meta():
    def pack(points):
        return [{"key": p.key, "label": p.label, "unit": p.unit,
                 "lo": p.lo, "hi": p.hi, "system": p.system} for p in points]
    return {"ir": pack(INPUT_REGISTERS), "di": pack(DISCRETE_INPUTS),
            "co": pack(COILS), "hr": pack(HOLDING_REGISTERS)}


def make_handler(engine):
    meta_json = json.dumps(_meta()).encode()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass  # silencioso

        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _static(self, fname, ctype):
            path = os.path.join(WEB_DIR, fname)
            try:
                with open(path, "rb") as f:
                    self._send(200, f.read(), ctype)
            except FileNotFoundError:
                self._send(404, b"not found", "text/plain")

        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self._static("index.html", "text/html; charset=utf-8")
            elif self.path in ("/help", "/help.html", "/manual"):
                self._static("help.html", "text/html; charset=utf-8")
            elif self.path == "/app.js":
                self._static("app.js", "application/javascript")
            elif self.path == "/style.css":
                self._static("style.css", "text/css")
            elif self.path == "/api/meta":
                self._send(200, meta_json)
            elif self.path == "/api/state":
                self._send(200, json.dumps(engine.snapshot()).encode())
            elif self.path == "/api/stream":
                self._stream()
            else:
                self._send(404, b"not found", "text/plain")

        def _stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                while True:
                    payload = json.dumps(engine.snapshot())
                    self.wfile.write(f"data: {payload}\n\n".encode())
                    self.wfile.flush()
                    time.sleep(0.25)
            except (BrokenPipeError, ConnectionResetError):
                return

        def do_POST(self):
            if self.path != "/api/command":
                self._send(404, b"not found", "text/plain")
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
                kind, value = data["kind"], data.get("value")
                key = data.get("key")
                result = {"ok": True}
                if kind == "coil":
                    engine.set_coil(key, bool(value))
                elif kind == "hr":
                    engine.set_hr(key, float(value))
                elif kind == "hr_step":
                    result["value"] = engine.step_hr(key, float(value))
                elif kind == "rod":
                    engine.rod_lever(str(value))
                elif kind == "reset":
                    result.update(engine.request_reset())
                elif kind == "speed":
                    engine.set_speed(value)
                elif kind == "timescale":
                    engine.set_time_scale(value)
                elif kind == "loca":
                    engine.set_loca(value)
                elif kind == "scenario":
                    engine.set_scenario(value)
                else:
                    raise ValueError("kind invalido")
                self._send(200, json.dumps(result).encode())
            except Exception as e:  # noqa: BLE001 — API de laboratorio
                self._send(400, json.dumps({"ok": False, "error": str(e)}).encode())

    return Handler


def start_api(engine, host="0.0.0.0", port=5000):
    httpd = ThreadingHTTPServer((host, port), make_handler(engine))
    httpd.serve_forever()
