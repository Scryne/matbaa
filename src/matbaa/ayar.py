"""Proje yolları ve yapılandırma."""

from __future__ import annotations

import tomllib
from functools import cache
from pathlib import Path

KOK = Path(__file__).resolve().parents[2]
CONFIG = KOK / "config"
VERI = KOK / "veri"


@cache
def modeller() -> dict:
    return tomllib.loads((CONFIG / "modeller.toml").read_text(encoding="utf-8"))


def env_yukle(dosya=None) -> None:
    """`.env` satırlarını ortam değişkenine yükler (var olanı ezmez). Gizli bilgiler git dışında kalır."""
    import os

    dosya = dosya or KOK / ".env"
    if not dosya.exists():
        return
    for satir in dosya.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if satir and not satir.startswith("#") and "=" in satir:
            k, v = satir.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip().strip('"'))
