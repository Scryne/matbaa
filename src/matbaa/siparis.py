"""Sipariş ve kâr defteri (Faz 8–9): Etsy makbuzları + Printify sipariş maliyeti → sipariş başı gerçek net; gecikme alarmı.

Etsy sipariş tutarını, Printify üretim + kargo maliyetini verir; Etsy ücretleri `fiyat.hesap` ile (TR ücret yığını).
Eşleme: makbuzun ilanları (`transactions[].listing_id`) `urun` tablosundan tasarıma ve ürün türüne bağlanır. Printify siparişi
önce `metadata.shop_order_id` / `shop_order_label` ile, tutmazsa aynı Printify ürünlerini taşıyan en yakın siparişle eşlenir
(Printify dokümanı bu alanın Etsy makbuz kimliği olduğunu yazmıyor, 2026-10-13). Printify maliyeti henüz yoksa katalog tahmini.
Takip numarası Printify sevkiyatından, yoksa Etsy makbuzunun `shipments[].tracking_code` alanından.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from matbaa import db, fiyat, tavan

GECIKME_IS_GUNU = 5
KAPANMIS = ("completed", "canceled", "fully refunded")  # takip beklenmeyen makbuz durumları
IPTAL = ("canceled", "fully refunded")  # gelirden düşülür
GECERLI = f"lower(coalesce(durum, '')) NOT IN ({', '.join(repr(x) for x in IPTAL)})"  # SQL: iptal/iade olmayan sipariş
ESLEME_GUN = 4  # Printify siparişi Etsy makbuzundan en geç bu kadar gün sonra açılmış olur


def _para(m: dict | None) -> float:
    """Etsy para nesnesi {"amount": 2899, "divisor": 100} → 28.99"""
    if not m:
        return 0.0
    return m["amount"] / (m.get("divisor") or 100)


def is_gunu_farki(bas: datetime, son: datetime) -> int:
    gun, n = bas.date(), 0
    while gun < son.date():
        gun += timedelta(days=1)
        if gun.weekday() < 5:
            n += 1
    return n


def _zaman(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        z = datetime.fromisoformat(s.replace(" ", "T").replace("Z", "+00:00"))
    except ValueError:
        return None
    return z if z.tzinfo else z.replace(tzinfo=UTC)


def _printify_ozeti(o: dict) -> dict:
    meta = o.get("metadata") or {}
    return {
        "id": str(o.get("id")),
        "maliyet": (o.get("total_price", 0) + o.get("total_shipping", 0) + o.get("total_tax", 0)) / 100,
        "takip": next((s.get("number") for s in o.get("shipments") or [] if s.get("number")), None),
        "urunler": {str(li.get("product_id")) for li in o.get("line_items") or [] if li.get("product_id")},
        "zaman": _zaman(o.get("created_at")),
        "anahtarlar": {str(meta[k]) for k in ("shop_order_id", "shop_order_label") if meta.get(k)},
    }


def _printify_esle(
    makbuz: str, olusma: datetime, printify_ids: set[str], siparisler: list[dict], kullanilan: set[str]
) -> dict | None:
    for o in siparisler:
        if makbuz in o["anahtarlar"] and o["id"] not in kullanilan:
            return o
    adaylar = [
        o
        for o in siparisler
        if o["id"] not in kullanilan
        and o["urunler"] & printify_ids
        and o["zaman"]
        and timedelta(hours=-1) <= o["zaman"] - olusma <= timedelta(days=ESLEME_GUN)
    ]
    return min(adaylar, key=lambda o: o["zaman"] - olusma, default=None)


def geciken(c, simdi: datetime | None = None) -> list[str]:
    """Takipsiz, kapanmamış ve `GECIKME_IS_GUNU`'nden eski makbuzlar: veritabanının tamamından, yalnız bugün değişenlerden değil."""
    simdi = simdi or datetime.now(UTC)
    sonuc = []
    for makbuz, olusma in c.execute(
        "SELECT etsy_receipt_id, olusturma FROM siparis WHERE (takip IS NULL OR takip = '') "
        f"AND lower(coalesce(durum, '')) NOT IN ({', '.join('?' * len(KAPANMIS))}) ORDER BY olusturma",
        KAPANMIS,
    ).fetchall():
        if olusma and (g := is_gunu_farki(datetime.fromisoformat(olusma), simdi)) > GECIKME_IS_GUNU:
            sonuc.append(f"makbuz {makbuz}: {g} iş günü, takip yok")
    return sonuc


def izle(c, etsy, printify, simdi: datetime | None = None, yazdir=print) -> dict:
    simdi = simdi or datetime.now(UTC)
    son = c.execute("SELECT max(guncelleme) FROM siparis").fetchone()[0]
    min_degisim = int(datetime.fromisoformat(son).timestamp()) - 86400 if son else None
    siparisler = [_printify_ozeti(o) for o in printify.son_siparisler()]
    kullanilan = {r[0] for r in c.execute("SELECT printify_order_id FROM siparis WHERE printify_order_id IS NOT NULL")}
    sayac: dict = {"yeni": 0, "guncel": 0, "printify_eslesmedi": 0}
    for r in etsy.makbuzlar(min_degisim):
        makbuz = str(r["receipt_id"])
        olusma = datetime.fromtimestamp(r.get("create_timestamp") or r.get("created_timestamp") or 0, UTC)
        brut = _para(r.get("grandtotal")) - _para(r.get("total_tax_cost")) - _para(r.get("total_vat_cost"))
        kargo = _para(r.get("total_shipping_cost"))
        # Makbuz kalemleri → bizim ürünlerimiz (tasarım, ürün türü, Printify ürünü); bizim olmayan ilan None.
        kalemler = [
            (
                c.execute(
                    "SELECT tasarim_id, urun, printify_id FROM urun WHERE etsy_listing_id = ?", (str(tr.get("listing_id")),)
                ).fetchone(),
                int(tr.get("quantity") or 1),
            )
            for tr in r.get("transactions") or []
        ]
        onceki = c.execute("SELECT printify_order_id FROM siparis WHERE etsy_receipt_id = ?", (makbuz,)).fetchone()
        o = next((x for x in siparisler if onceki and x["id"] == onceki[0]), None)
        if o is None:
            o = _printify_esle(
                makbuz, olusma, {u["printify_id"] for u, _ in kalemler if u and u["printify_id"]}, siparisler, kullanilan
            )
        if o:
            kullanilan.add(o["id"])
        tahmin = sum(fiyat.urun_hesap(u["urun"] if u else "tisort").uretim * n for u, n in kalemler)
        uretim = o["maliyet"] if o else tahmin or fiyat.urun_hesap("tisort").uretim
        takip = (o or {}).get("takip") or next(
            (s.get("tracking_code") for s in r.get("shipments") or [] if s.get("tracking_code")), None
        )
        tasarim = next((u["tasarim_id"] for u, _ in kalemler if u), None)
        k = fiyat.hesap(brut - kargo, kargo, uretim)
        c.execute(
            """INSERT INTO siparis (etsy_receipt_id, printify_order_id, tasarim_id, brut, net, para_birimi, durum, takip, olusturma, guncelleme)
               VALUES (?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
               ON CONFLICT(etsy_receipt_id) DO UPDATE SET printify_order_id = coalesce(excluded.printify_order_id, printify_order_id),
                 tasarim_id = coalesce(excluded.tasarim_id, tasarim_id), net = excluded.net, durum = excluded.durum,
                 takip = coalesce(excluded.takip, takip), guncelleme = excluded.guncelleme""",
            (
                makbuz, o and o["id"], tasarim, round(brut, 2), k.net, str(r.get("status") or "").lower(), takip,
                olusma.isoformat(), simdi.isoformat(timespec="seconds"),
            ),
        )  # fmt: skip
        sayac["guncel" if onceki else "yeni"] += 1
        sayac["printify_eslesmedi"] += o is None
    sayac["alarm"] = geciken(c, simdi)
    db.olay(c, "siparis", None, None, "izlendi", f"{sayac['yeni']} yeni, {len(sayac['alarm'])} alarm")
    c.commit()
    for a in sayac["alarm"]:
        yazdir(f"  ALARM {a}")
    return sayac


def ozet(c, gun: int = 30) -> dict:
    bas = (datetime.now(UTC) - timedelta(days=gun)).isoformat()
    r = c.execute(
        f"SELECT count(*), coalesce(sum(brut), 0), coalesce(sum(net), 0) FROM siparis WHERE olusturma >= ? AND {GECERLI}", (bas,)
    ).fetchone()
    return {"gun": gun, "siparis": r[0], "brut_usd": round(r[1], 2), "net_usd": round(r[2], 2)}


def aylik(c, ay: str | None = None) -> dict:
    """Takvim ayı özeti (Faz 8): sipariş, brüt, sipariş başı net toplamı, o ay açılan ilanların listeleme ücreti ve kalan net.

    Sipariş netinde Etsy satış/ödeme/kur ücretleri ve Printify maliyeti düşülmüştür (`fiyat.hesap`); ilan açma ücreti ayrı kalemdir.
    """
    ay = ay or datetime.now(UTC).strftime("%Y-%m")
    yil, a = map(int, ay.split("-"))
    bas = datetime(yil, a, 1, tzinfo=UTC)
    son = datetime(yil + (a == 12), a % 12 + 1, 1, tzinfo=UTC)
    r = c.execute(
        f"SELECT count(*), coalesce(sum(brut), 0), coalesce(sum(net), 0) FROM siparis WHERE olusturma >= ? AND olusturma < ? AND {GECERLI}",
        (bas.isoformat(), son.isoformat()),
    ).fetchone()
    ilan = tavan.ilan_ucreti(c, bas.isoformat(), son.isoformat())
    return {
        "ay": ay,
        "siparis": r[0],
        "brut_usd": round(r[1], 2),
        "siparis_net_usd": round(r[2], 2),
        "ilan_ucreti_usd": ilan,
        "net_usd": round(r[2] - ilan, 2),
        "ilan_tavani_usd": tavan.tavanlar()["aylik_ilan_ucreti_usd"],
        "kur_try_usd": fiyat.try_usd(),
    }
