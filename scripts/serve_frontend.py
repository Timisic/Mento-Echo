from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class SpaHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        requested = Path(self.translate_path(self.path))
        if not requested.exists() and "." not in Path(self.path).name:
            self.path = "/index.html"
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()

    dist_dir = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    handler = lambda *handler_args, **handler_kwargs: SpaHandler(  # noqa: E731
        *handler_args,
        directory=str(dist_dir),
        **handler_kwargs,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving frontend from {dist_dir} on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
