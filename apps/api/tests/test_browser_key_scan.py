"""Public Maps credentials are allowed only in compiled frontend artifacts."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("scanner", ROOT / "scripts/scan_secrets.py")
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


@pytest.mark.parametrize(
    "location,credential,expected",
    [
        ("apps/web/.next/static/chunk.js", "public", False),
        ("apps/web/.next/static/chunk.js", "backend", True),
        ("apps/web/src/leak.ts", "public", True),
        ("data/verification/leak.json", "public", True),
        ("apps/web/.next/static/chunk.js", "unknown", True),
    ],
)
def test_only_exact_public_maps_key_in_compiled_bundle(
    monkeypatch, tmp_path, location, credential, expected
):
    keys = {
        name: "AIza" + char * 35
        for name, char in [("public", "x"), ("backend", "y"), ("unknown", "z")]
    }
    (tmp_path / ".env").write_text(
        "NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY="
        + keys["public"]
        + "\nGOOGLE_MAPS_PLATFORM_API_KEY="
        + keys["backend"]
    )
    path = tmp_path / location
    path.parent.mkdir(parents=True)
    path.write_text(keys[credential])
    monkeypatch.setattr(scanner, "ROOT", tmp_path)
    monkeypatch.setattr(scanner.subprocess, "check_output", lambda *a, **kw: location.encode())
    monkeypatch.setattr(sys, "argv", ["scan_secrets.py"])
    with pytest.raises(SystemExit) as result:
        scanner.main()
    assert result.value.code == expected
