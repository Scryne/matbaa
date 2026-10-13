"""Haftalık rapor (Faz 9): ilan, görüntülenme, satış, net; dikkat isteyenler en üstte.

Etsy görüntülenmesi ilan başına birikimli bir sayıdır (günde bir kez sayılır): her koşuda anlık görüntü `goruntulenme`
tablosuna yazılır, haftalık görüntülenme bugünkü toplam ile ≥ 7 gün önceki en yakın görüntünün farkıdır.
Rapor `calisma/rapor/<yıl>-H<hafta>.md` dosyasına yazılır; günlük koşu haftanın ilk koşusunda üretir.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from matbaa import db, siparis, tavan
from matbaa.ayar import KOK

RAPOR_DIZINI = KOK / "calisma" / "rapor"


def hafta_adi(simdi: datetime) -> str:
    y, h, _ = simdi.isocalendar()
    return f"{y}-H{h:02d}"


def goruntu_al(c, etsy, simdi: datetime) -> int:
    tarih = simdi.date().isoformat()
    ilanlar = etsy.aktif_ilanlar()
    c.executemany(
        "INSERT OR REPLACE INTO goruntulenme (tarih, etsy_listing_id, views, favori) VALUES (?, ?, ?, ?)",
        [(tarih, str(i["listing_id"]), i.get("views") or 0, i.get("num_favorers") or 0) for i in ilanlar],
    )
    c.commit()
    return len(ilanlar)


def _goruntulenme(c, simdi: datetime) -> dict:
    bugun = c.execute("SELECT max(tarih) FROM goruntulenme WHERE tarih <= ?", (simdi.date().isoformat(),)).fetchone()[0]
    if not bugun:
        return {"toplam": None, "hafta": None, "favori_hafta": None, "en_cok": []}
    once = c.execute(
        "SELECT max(tarih) FROM goruntulenme WHERE tarih <= ?", ((simdi - timedelta(days=7)).date().isoformat(),)
    ).fetchone()[0]
    simdiki = {
        r[0]: (r[1], r[2]) for r in c.execute("SELECT etsy_listing_id, views, favori FROM goruntulenme WHERE tarih = ?", (bugun,))
    }
    onceki = (
        {
            r[0]: (r[1], r[2])
            for r in c.execute("SELECT etsy_listing_id, views, favori FROM goruntulenme WHERE tarih = ?", (once,))
        }
        if once
        else {}
    )
    fark = {k: v[0] - onceki.get(k, (0, 0))[0] for k, v in simdiki.items()}
    basliklar = dict(
        c.execute(
            "SELECT u.etsy_listing_id, i.baslik FROM urun u JOIN ilan i ON i.tasarim_id = u.tasarim_id AND i.urun = u.urun "
            "WHERE u.etsy_listing_id IS NOT NULL"
        ).fetchall()
    )
    en_cok = sorted(fark.items(), key=lambda x: -x[1])[:5]
    return {
        "toplam": sum(v[0] for v in simdiki.values()),
        # Önceki görüntü yoksa (ilk hafta) haftalık fark = toplam: ilanlar bu hafta açıldı.
        "hafta": sum(fark.values()),
        "favori_hafta": sum(v[1] - onceki.get(k, (0, 0))[1] for k, v in simdiki.items()),
        "en_cok": [(basliklar.get(k, k), n) for k, n in en_cok if n > 0],
        "karsilastirma": once or "yok (ilk görüntü)",
    }


def haftalik(c=None, etsy=None, simdi: datetime | None = None) -> tuple[dict, str]:
    c = c or db.baglan()
    simdi = simdi or datetime.now(UTC)
    bas = (simdi - timedelta(days=7)).isoformat()
    if etsy is not None:
        goruntu_al(c, etsy, simdi)
    tasarim = dict(c.execute("SELECT durum, count(*) FROM tasarim GROUP BY durum").fetchall())
    urun = dict(c.execute("SELECT durum, count(*) FROM urun GROUP BY durum").fetchall())
    yeni_aktif = c.execute(
        "SELECT count(*) FROM olay WHERE varlik = 'urun' AND yeni LIKE '%:aktif' AND zaman >= ?", (bas,)
    ).fetchone()[0]
    s = c.execute(
        f"SELECT count(*), coalesce(sum(brut), 0), coalesce(sum(net), 0) FROM siparis WHERE olusturma >= ? AND {siparis.GECERLI}",
        (bas,),
    ).fetchone()
    gecikme = siparis.geciken(c, simdi)
    # Hangi tasarımlar satıyor (son 30 gün): üretimin neye yöneleceğinin tek gerçek sinyali.
    satanlar = c.execute(
        f"""SELECT i.nis, i.satirlar, count(*) FROM siparis s JOIN tasarim t ON t.id = s.tasarim_id JOIN ifade i ON i.id = t.ifade_id
            WHERE s.olusturma >= ? AND {siparis.GECERLI.replace("durum", "s.durum")} GROUP BY t.id ORDER BY count(*) DESC LIMIT 5""",
        ((simdi - timedelta(days=30)).isoformat(),),
    ).fetchall()
    hatalar = [
        f"{r[0]}/{r[1]}: {(r[2] or '')[:120]}"
        for r in c.execute("SELECT tasarim_id, urun, hata FROM urun WHERE durum = 'hata' ORDER BY tasarim_id").fetchall()
    ]
    veri = {
        "hafta": hafta_adi(simdi),
        "ilan": {
            "aktif": urun.get("aktif", 0),
            "bu_hafta_aktif": yeni_aktif,
            "onay_bekleyen_tasarim": tasarim.get("onay_bekliyor", 0),
            "yayin_bekleyen_tasarim": tasarim.get("onaylandi", 0),
        },
        "goruntulenme": _goruntulenme(c, simdi)
        if etsy is not None or c.execute("SELECT 1 FROM goruntulenme LIMIT 1").fetchone()
        else None,
        "satis": {"siparis": s[0], "brut_usd": round(s[1], 2), "net_usd": round(s[2], 2)},
        "satanlar_30g": [{"nis": r[0], "ifade": " / ".join(json.loads(r[1])), "siparis": r[2]} for r in satanlar],
        "ilan_ucreti_usd": tavan.ilan_ucreti(c, bas),
        "ay": siparis.aylik(c, simdi.strftime("%Y-%m")),
        "dikkat": {"gecikme": gecikme, "urun_hata": hatalar},
    }
    return veri, _metin(veri)


def _metin(v: dict) -> str:
    i, s, g, ay = v["ilan"], v["satis"], v["goruntulenme"], v["ay"]
    satirlar = [f"# Matbaa haftalık rapor — {v['hafta']}", ""]
    dikkat = v["dikkat"]["gecikme"] + v["dikkat"]["urun_hata"]
    if dikkat:
        satirlar += ["## Dikkat", *[f"- {x}" for x in dikkat], ""]
    satirlar += [
        "## İlan",
        f"- Etsy'de aktif ürün: **{i['aktif']}** (bu hafta {i['bu_hafta_aktif']} yeni)",
        f"- Onay bekleyen tasarım: {i['onay_bekleyen_tasarim']} · yayın sırası bekleyen: {i['yayin_bekleyen_tasarim']}",
        "",
        "## Görüntülenme",
    ]
    if not g or g["toplam"] is None:
        satirlar.append("- Veri yok (Etsy bağlantısı kurulmadı ya da aktif ilan yok)")
    else:
        satirlar += [
            f"- Bu hafta: **{g['hafta']}** görüntülenme, {g['favori_hafta']} favori (toplam {g['toplam']}; karşılaştırma: {g['karsilastirma']})",
            *[f"  - {b[:80]} — {n}" for b, n in g["en_cok"]],
        ]
    satirlar += [
        "",
        "## Satış",
        f"- Bu hafta: {s['siparis']} sipariş, brüt ${s['brut_usd']:.2f}, net ${s['net_usd']:.2f}",
        *[f"  - satan (30 gün): {x['ifade']} ({x['nis']}) — {x['siparis']}" for x in v.get("satanlar_30g", [])],
        f"- Bu hafta açılan ilanların listeleme ücreti: ${v['ilan_ucreti_usd']:.2f}",
        f"- {ay['ay']} ayı: {ay['siparis']} sipariş, sipariş neti ${ay['siparis_net_usd']:.2f} − ilan ücreti ${ay['ilan_ucreti_usd']:.2f}"
        f" = **${ay['net_usd']:.2f}** (ilan tavanı ${ay['ilan_tavani_usd']:.0f}, kur {ay['kur_try_usd']:.2f} TRY/USD)",
        "",
    ]
    return "\n".join(satirlar)


def yaz(veri: dict, metin: str) -> str:
    RAPOR_DIZINI.mkdir(parents=True, exist_ok=True)
    yol = RAPOR_DIZINI / f"{veri['hafta']}.md"
    yol.write_text(metin, encoding="utf-8")
    (RAPOR_DIZINI / f"{veri['hafta']}.json").write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(yol.relative_to(KOK)) if yol.is_relative_to(KOK) else str(yol)


def bu_hafta_var_mi(simdi: datetime | None = None) -> bool:
    return (RAPOR_DIZINI / f"{hafta_adi(simdi or datetime.now(UTC))}.md").exists()
