"""Performansa göre üretim (Faz 13): günlük üretim hangi nişe gidecek, Claude'a hangi satan ifade örnek verilecek.

Puan = ilan başına beklenen satış (son `PENCERE_GUN`): ilan başına görüntülenme × nişin yumuşatılmış dönüşüm oranı.
Oran = (satış + 0,1 × favori + önsel) / (görüntülenme + önsel ağırlık), önsel %2: az veride oran %2'ye yakın kalır, veri
biriktikçe nişin kendi oranına kayar. Böylece çok görülüp satmayan niş, az görülüp satan nişin önüne geçmez. Az ilanlı niş
keşif payı alır (veri birikmeden gömülmesin). Mağazada `VERI_ESIGI`nden az aktif ilan varken veri gürültüdür: sıra eski kurala
(kuyrukta en az tasarımı olan niş önce) düşer.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from matbaa.siparis import GECERLI

PENCERE_GUN = 30
VERI_ESIGI = 30  # bu kadar aktif ilan olmadan sıralama veriyle yapılmaz
ONSEL_ORAN = 0.02  # Etsy dönüşümü ~%1–3
ONSEL_GORUNTU = 100  # önselin ağırlığı (görüntülenme cinsinden)
FAVORI_SATIS = 0.1  # bir favori ≈ 0,1 satış niyeti
KESIF = 0.5  # beklenen satış/ilan biriminde; ilan sayısı arttıkça erir (KESIF / (1 + ilan))


def _goruntulenme_farki(c, bas: str) -> dict[str, tuple[int, int]]:
    """İlan → (görüntülenme, favori) farkı: en son anlık görüntü − pencere başındaki (yoksa 0: ilan pencerede açıldı)."""
    son = c.execute("SELECT max(tarih) FROM goruntulenme").fetchone()[0]
    if not son:
        return {}
    once = c.execute("SELECT max(tarih) FROM goruntulenme WHERE tarih <= ?", (bas[:10],)).fetchone()[0]
    oku = lambda t: {  # noqa: E731
        r[0]: (r[1] or 0, r[2] or 0)
        for r in c.execute("SELECT etsy_listing_id, views, favori FROM goruntulenme WHERE tarih = ?", (t,))
    }
    simdi, eski = oku(son), (oku(once) if once else {})
    return {k: (v - eski.get(k, (0, 0))[0], f - eski.get(k, (0, 0))[1]) for k, (v, f) in simdi.items()}


def nis_puanlari(c, simdi: datetime | None = None) -> dict[str, dict]:
    simdi = simdi or datetime.now(UTC)
    bas = (simdi - timedelta(days=PENCERE_GUN)).isoformat()
    fark = _goruntulenme_farki(c, bas)
    sonuc: dict[str, dict] = {}

    def nis(n: str) -> dict:
        return sonuc.setdefault(n, {"ilan": 0, "goruntulenme": 0, "favori": 0, "satis": 0})

    for n, listing in c.execute(
        """SELECT i.nis, u.etsy_listing_id FROM urun u JOIN tasarim t ON t.id = u.tasarim_id JOIN ifade i ON i.id = t.ifade_id
           WHERE u.durum = 'aktif'"""
    ).fetchall():
        d = nis(n)
        d["ilan"] += 1
        g, f = fark.get(str(listing), (0, 0))
        d["goruntulenme"] += max(g, 0)
        d["favori"] += max(f, 0)
    for n, adet in c.execute(
        f"""SELECT i.nis, count(*) FROM siparis s JOIN tasarim t ON t.id = s.tasarim_id JOIN ifade i ON i.id = t.ifade_id
            WHERE s.olusturma >= ? AND {GECERLI.replace("durum", "s.durum")} GROUP BY i.nis""",
        (bas,),
    ).fetchall():
        nis(n)["satis"] += adet
    for d in sonuc.values():
        oran = (d["satis"] + FAVORI_SATIS * d["favori"] + ONSEL_ORAN * ONSEL_GORUNTU) / (d["goruntulenme"] + ONSEL_GORUNTU)
        d["donusum"] = round(oran, 4)
        d["puan"] = round(d["goruntulenme"] / max(d["ilan"], 1) * oran, 4)
    return sonuc


def uretim_sirasi(c, nisler: list[str], kuyruk: dict[str, int], simdi: datetime | None = None) -> list[str]:
    """Bugün üretilecek nişlerin sırası. Veri azsa: kuyrukta en az tasarımı olan önce (dengeli büyüme)."""
    puan = nis_puanlari(c, simdi)
    if sum(d["ilan"] for d in puan.values()) < VERI_ESIGI:
        return sorted(nisler, key=lambda n: kuyruk.get(n, 0))

    def oncelik(n: str) -> tuple[float, int]:
        d = puan.get(n, {"ilan": 0, "puan": 0.0})
        return (d["puan"] + KESIF / (1 + d["ilan"]), -kuyruk.get(n, 0))

    return sorted(nisler, key=oncelik, reverse=True)


def satanlar(c, nis: str, gun: int = 60, adet: int = 5) -> list[str]:
    """Nişin en çok satan ifadeleri (iptal/iade hariç): Claude'a "bu ruhta yeni yaz" örneği."""
    bas = (datetime.now(UTC) - timedelta(days=gun)).isoformat()
    return [
        " / ".join(json.loads(r[0]))
        for r in c.execute(
            f"""SELECT i.satirlar FROM siparis s JOIN tasarim t ON t.id = s.tasarim_id JOIN ifade i ON i.id = t.ifade_id
                WHERE i.nis = ? AND s.olusturma >= ? AND {GECERLI.replace("durum", "s.durum")}
                GROUP BY i.id ORDER BY count(*) DESC LIMIT ?""",
            (nis, bas, adet),
        ).fetchall()
    ]
