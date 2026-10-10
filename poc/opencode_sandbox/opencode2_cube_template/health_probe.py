"""Cube Guest readiness endpoint, no Jupyter dependency.

Returns healthy only after the Cube envd command/file TCP port is accepting.
This is not an OpenCode API endpoint.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import socket

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        try:
            with socket.create_connection(("127.0.0.1", 49983), timeout=1):
                pass
        except OSError:
            self.send_error(503)
            return
        payload = b'{"status":"ok","backend":"cube-envd"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self, *_args):
        return

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("CODE_INTERPRETER_PORT", "49999"))), Handler).serve_forever()
