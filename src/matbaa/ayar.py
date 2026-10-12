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
