"""Local web UI using only the standard library (no extra dependencies)."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import pipeline
from ..models import catalog, registry

PAGE = (Path(__file__).with_name("index.html")).read_text(encoding="utf-8-sig")


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json")

    def do_GET(self):
        if self.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/models":
            self._json(200, registry.load_registry())
        elif self.path == "/api/catalog":
            try:
                self._json(200, catalog.get_models(refresh=True))
            except Exception as e:
                self._json(500, {"error": str(e)})
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, ValueError) as e:
            self._json(400, {"error": f"Invalid JSON body: {e}"})
            return
        if self.path == "/api/run":
            try:
                result = pipeline.run(
                    data["url"],
                    max_clips=int(data.get("max_clips", 5)),
                    budget_usd=float(data.get("budget", 1.0)),
                    multimodal=bool(data.get("multimodal", False)),
                    scorer=data.get("scorer") or None,
                    refiner=data.get("refiner") or None,
                    multimodal_model=data.get("multimodal_model") or None,
                    genre=data.get("genre") or None,
                )
                self._json(200, result)
            except Exception as e:
                self._json(500, {"error": str(e)})
        elif self.path == "/api/analyze":
            try:
                from ..analyze import analyze
                result = analyze(platform=data.get("platform", "youtube"), title=data.get("title", ""),
                                 description=data.get("description", ""), hook=data.get("hook", ""),
                                 transcript=data.get("transcript", ""),
                                 web_search_enabled=bool(data.get("web_search", False)),
                                 model=data.get("model") or None)
                self._json(200, result)
            except Exception as e:
                self._json(500, {"error": str(e)})
        else:
            self._send(404, b"not found", "text/plain")


def serve(port: int = 8765) -> None:
    print(f"KirimaruAI UI: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()

