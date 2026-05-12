from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


WEBAPP_ROOT = Path(__file__).resolve().parent.parent / "webapp"


class WebAppRequestHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".mjs": "application/javascript",
    }

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve(*, host: str = "127.0.0.1", port: int = 4173) -> None:
    handler = partial(WebAppRequestHandler, directory=str(WEBAPP_ROOT))
    with ThreadingHTTPServer((host, port), handler) as server:
        print(f"Webapp disponible sur http://{host}:{port}")
        server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lance la webapp statique connectee a l'API."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host d'ecoute local.")
    parser.add_argument("--port", type=int, default=4173, help="Port HTTP local.")
    args = parser.parse_args()
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
