from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_serve_frontend_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "serve_frontend.py"
    spec = importlib.util.spec_from_file_location("serve_frontend", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_api_paths_are_reserved_for_backend_proxy():
    serve_frontend = _load_serve_frontend_module()

    assert serve_frontend.is_api_path("/api")
    assert serve_frontend.is_api_path("/api/health")
    assert serve_frontend.is_api_path("/api/participant/entry")
    assert not serve_frontend.is_api_path("/assets/index.js")
    assert not serve_frontend.is_api_path("/participant")


def test_backend_target_preserves_api_path_and_query_string():
    serve_frontend = _load_serve_frontend_module()

    assert (
        serve_frontend.backend_target_url("http://127.0.0.1:8000/", "/api/health?deep=1")
        == "http://127.0.0.1:8000/api/health?deep=1"
    )


def test_self_registration_enabled_reads_environment(monkeypatch):
    serve_frontend = _load_serve_frontend_module()

    monkeypatch.delenv("SELF_REGISTRATION_ENABLED", raising=False)
    assert serve_frontend.self_registration_enabled()

    monkeypatch.setenv("SELF_REGISTRATION_ENABLED", "false")
    assert not serve_frontend.self_registration_enabled()
