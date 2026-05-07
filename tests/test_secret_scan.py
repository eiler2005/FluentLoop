from __future__ import annotations

import importlib.util
from pathlib import Path


def load_secret_scan_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "secret_scan.py"
    spec = importlib.util.spec_from_file_location("secret_scan", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_secret_scan_placeholder_values_are_safe() -> None:
    scanner = load_secret_scan_module()

    assert scanner.is_placeholder("<telegram-allowed-user-id>")
    assert scanner.is_placeholder("${VPS_HOST:-}")
    assert scanner.is_placeholder("STUB_OVERNIGHT_BUILD")


def test_secret_scan_public_ip_detection() -> None:
    scanner = load_secret_scan_module()

    assert scanner.is_public_ip(".".join(("93", "184", "216", "34")))
    assert not scanner.is_public_ip("192.168.1.10")
    assert not scanner.is_public_ip("127.0.0.1")
