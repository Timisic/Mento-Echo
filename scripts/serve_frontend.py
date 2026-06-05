from __future__ import annotations

import argparse
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

SELF_REGISTRATION_CLOSED_BODY = '{"detail":"人数过多，被试已招满"}'.encode()


def is_api_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def backend_target_url(backend_url: str, path: str) -> str:
    return f"{backend_url.rstrip('/')}{path}"


def self_registration_enabled() -> bool:
    return os.environ.get("SELF_REGISTRATION_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


class SpaHandler(SimpleHTTPRequestHandler):
    backend_url = "http://127.0.0.1:8000"

    def _proxy_api_request(self) -> None:
        if self.command == "POST" and self.path == "/api/participant/self-register" and not self_registration_enabled():
            self.send_response(403)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(SELF_REGISTRATION_CLOSED_BODY)))
            self.end_headers()
            self.wfile.write(SELF_REGISTRATION_CLOSED_BODY)
            return
        target = backend_target_url(self.backend_url, self.path)
        length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(length) if length else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "host"
        }
        proxied = request.Request(target, data=body, headers=headers, method=self.command)
        try:
            with request.urlopen(proxied, timeout=30) as response:
                response_body = b"" if self.command == "HEAD" else response.read()
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "content-length":
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                if response_body:
                    self.wfile.write(response_body)
        except error.HTTPError as exc:
            response_body = b"" if self.command == "HEAD" else exc.read()
            self.send_response(exc.code)
            for key, value in exc.headers.items():
                if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "content-length":
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            if response_body:
                self.wfile.write(response_body)
        except error.URLError:
            response_body = b"Bad Gateway"
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(response_body)

    def _map_spa_path(self) -> None:
        if self.path == "/favicon.ico":
            self.path = "/favicon.svg"
            return
        requested = Path(self.translate_path(self.path))
        if not requested.exists() and "." not in Path(self.path).name:
            self.path = "/index.html"

    def do_GET(self) -> None:
        if is_api_path(self.path):
            self._proxy_api_request()
            return
        self._map_spa_path()
        super().do_GET()

    def do_HEAD(self) -> None:
        if is_api_path(self.path):
            self._proxy_api_request()
            return
        self._map_spa_path()
        super().do_HEAD()

    def do_POST(self) -> None:
        if is_api_path(self.path):
            self._proxy_api_request()
            return
        self.send_error(405, "Method Not Allowed")

    def do_PUT(self) -> None:
        if is_api_path(self.path):
            self._proxy_api_request()
            return
        self.send_error(405, "Method Not Allowed")

    def do_PATCH(self) -> None:
        if is_api_path(self.path):
            self._proxy_api_request()
            return
        self.send_error(405, "Method Not Allowed")

    def do_DELETE(self) -> None:
        if is_api_path(self.path):
            self._proxy_api_request()
            return
        self.send_error(405, "Method Not Allowed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--backend-url", default=os.environ.get("BACKEND_URL", "http://127.0.0.1:8000"))
    args = parser.parse_args()

    dist_dir = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    handler_class = type("ConfiguredSpaHandler", (SpaHandler,), {"backend_url": args.backend_url})
    handler = lambda *handler_args, **handler_kwargs: handler_class(  # noqa: E731
        *handler_args,
        directory=str(dist_dir),
        **handler_kwargs,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        f"Serving frontend from {dist_dir} on http://{args.host}:{args.port}; "
        f"proxying /api to {args.backend_url}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
