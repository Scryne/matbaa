from __future__ import annotations

import pytest

from matbaa import fiyat
from matbaa.ilan.dogrula import dogrula
from matbaa.ilan.metin import AI_BEYANI, URETIM_ORTAGI, Ilan

ACIKLAMA = f"Intro.\n\n{URETIM_ORTAGI}\n\n{AI_BEYANI}"
ETIKETLER = [f"fishing gift {i}" for i in range(13)]


def test_gecerli_ilan_sorunsuz():
    i = dogrula(Ilan("Funny Fishing Grandpa Shirt, Gift for Papa", ETIKETLER, ACIKLAMA, "alt"))
    assert i.sorunlar == [] and len(i.etiketler) == 13


def test_uzun_baslik_kelime_sinirinda_kisalir():
    i = dogrula(Ilan("Fishing " * 30, ETIKETLER, ACIKLAMA, "alt"))
    assert len(i.baslik) <= 140 and not i.baslik.endswith(" ")


def test_etiket_temizlik_tekrar_ve_uzunluk():
    ham = ["Fishing Gift!!", "fishing gift", "a very long tag that exceeds twenty", "x", *ETIKETLER]
    i = dogrula(Ilan("Fishing Shirt", ham, ACIKLAMA, "alt"))
    assert i.etiketler[0] == "fishing gift"
    assert all(len(t) <= 20 for t in i.etiketler)
    assert len(set(i.etiketler)) == len(i.etiketler) == 13


def test_eksik_etiket_sorun_olur():
    assert "geçerli etiket" in " ".join(dogrula(Ilan("Fishing Shirt", ETIKETLER[:5], ACIKLAMA, "alt")).sorunlar)


@pytest.mark.parametrize("eksik", [AI_BEYANI, URETIM_ORTAGI])
def test_zorunlu_beyanlar(eksik):
    i = dogrula(Ilan("Fishing Shirt", ETIKETLER, ACIKLAMA.replace(eksik, ""), "alt"))
    assert i.sorunlar


def test_fiyat_kirilimi_tutarli():
    k = fiyat.hesap(28.99, 4.99, 16.94)
    assert k.gelir == pytest.approx(33.98)
    assert k.net == pytest.approx(k.gelir - k.etsy_ucret - k.kdv - k.uretim - k.offsite, abs=0.02)
    assert fiyat.hesap(28.99, 4.99, 16.94, offsite=True).net < k.net
    assert fiyat.hesap(28.99, 4.99, 16.94, ilan_try=True).net > k.net  # TRY ilan kur ücretini kaldırır


def test_tum_urunler_karli():
    for u in fiyat.urunler():
        assert fiyat.urun_hesap(u).net > 5, u


def test_mevsim_pencereleri_yil_donumu_ve_nis_filtresi():
    from datetime import date

    from matbaa.ifade.uret import aktif_mevsimler

    adlar = lambda nis, g: {m["ad"].split(" ")[0] for m in aktif_mevsimler(nis, g)}  # noqa: E731
    assert "Valentine's" in adlar("fishing", date(2027, 1, 10))  # 12-01 → 02-07 yıl dönümünü aşar
    assert "Valentine's" in adlar("fishing", date(2026, 12, 15))
    assert "Graduation" in adlar("senior_mom", date(2027, 4, 20))
    assert "Graduation" not in adlar("fishing", date(2027, 4, 20))  # niş filtresi
    assert adlar("fishing", date(2027, 7, 20)) == set()
