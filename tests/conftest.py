"""Testler canlı harcama ayarına bağlı kalmaz: `config/tavanlar.toml` işletme kararıyla değişir (K-37'de ilan tavanı 0),
yayın testleri bundan etkilenmemeli. Tavanı sınayan test kendi değerini ayrıca verir."""

from __future__ import annotations

import pytest

from matbaa import tavan


@pytest.fixture(autouse=True)
def _sabit_tavanlar(monkeypatch):
    monkeypatch.setattr(
        tavan, "tavanlar", lambda: {"aylik_ilan_ucreti_usd": 60.0, "yeniden_yatirim_orani": 0.5, "gunluk_ip_denetim": 120}
    )
