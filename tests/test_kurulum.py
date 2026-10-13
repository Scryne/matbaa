"""Faz 0 kurulum yardımcıları: kimlikleri elle kopyalatmadan `.env` ve config'e yazar."""

from __future__ import annotations

import importlib.util
import os

from matbaa.ayar import KOK, env_yaz, env_yukle


def test_env_yaz_satiri_gunceller_ya_da_ekler(tmp_path, monkeypatch):
    e = tmp_path / ".env"
    e.write_text("# yorum\nPRINTIFY_TOKEN=gizli\nETSY_SHOP_ID=\n", encoding="utf-8")
    monkeypatch.setattr(os, "environ", {})  # gerçek ortam değişmesin
    env_yaz("ETSY_SHOP_ID", "123", e)
    env_yaz("PRINTIFY_SHOP_ID", "9", e)
    assert e.read_text(encoding="utf-8") == "# yorum\nPRINTIFY_TOKEN=gizli\nETSY_SHOP_ID=123\nPRINTIFY_SHOP_ID=9\n"
    assert os.environ["ETSY_SHOP_ID"] == "123"
    env_yukle(e)
    assert os.environ["PRINTIFY_TOKEN"] == "gizli"


def test_etsy_yetki_uretim_ortagini_configa_yazar(tmp_path):
    spec = importlib.util.spec_from_file_location("etsy_yetki", KOK / "scripts" / "etsy_yetki.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    cfg = tmp_path / "yayin.toml"
    cfg.write_text((KOK / "config" / "yayin.toml").read_text(encoding="utf-8"), encoding="utf-8")
    m.ortak_yaz(4242, cfg)
    import tomllib

    assert tomllib.loads(cfg.read_text(encoding="utf-8"))["etsy"]["uretim_ortagi_id"] == 4242
