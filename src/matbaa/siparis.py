"""Sipariş ve kâr defteri (Faz 8–9): Etsy makbuzları + Printify sipariş maliyeti → sipariş başı gerçek net; gecikme alarmı.

Etsy sipariş tutarını, Printify üretim + kargo maliyetini verir; Etsy ücretleri `fiyat.hesap` ile (TR ücret yığını).
Printify siparişi Etsy makbuz numarasıyla eşlenir (`metadata.shop_order_id`).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from matbaa import db, fiyat

GECIKME_IS_GUNU = 5


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


def izle(c, etsy, printify, simdi: datetime | None = None, yazdir=print) -> dict:
    simdi = simdi or datetime.now(UTC)
    son = c.execute("SELECT max(guncelleme) FROM siparis").fetchone()[0]
    min_degisim = int(datetime.fromisoformat(son).timestamp()) - 86400 if son else None
    maliyet: dict[str, tuple[str, float, str | None]] = {}  # etsy makbuz → (printify id, maliyet, takip)
    sayfa = printify.siparisler(1)
    for o in sayfa.get("data", []):
        makbuz = str((o.get("metadata") or {}).get("shop_order_id") or "")
        if not makbuz:
            continue
        tutar = (o.get("total_price", 0) + o.get("total_shipping", 0) + o.get("total_tax", 0)) / 100
        takip = next((s.get("number") for s in o.get("shipments") or [] if s.get("number")), None)
        maliyet[makbuz] = (str(o.get("id")), tutar, takip)
    sayac = {"yeni": 0, "guncel": 0, "alarm": []}
    for r in etsy.makbuzlar(min_degisim):
        makbuz = str(r["receipt_id"])
        brut = _para(r.get("grandtotal")) - _para(r.get("total_tax_cost")) - _para(r.get("total_vat_cost"))
        kargo = _para(r.get("total_shipping_cost"))
        pid, uretim, takip = maliyet.get(makbuz, (None, None, None))
        # Printify maliyeti henüz yoksa katalog tahminiyle (ürün türü başlıktan bilinemez: tişört varsayımı, sonra düzelir)
        k = fiyat.hesap(brut - kargo, kargo, uretim if uretim is not None else fiyat.urun_hesap("tisort").uretim)
        olusma = datetime.fromtimestamp(r.get("create_timestamp") or r.get("created_timestamp") or 0, UTC)
        var = c.execute("SELECT 1 FROM siparis WHERE etsy_receipt_id = ?", (makbuz,)).fetchone()
        c.execute(
            """INSERT INTO siparis (etsy_receipt_id, printify_order_id, brut, net, para_birimi, durum, takip, olusturma, guncelleme)
               VALUES (?, ?, ?, ?, 'USD', ?, ?, ?, ?)
               ON CONFLICT(etsy_receipt_id) DO UPDATE SET printify_order_id = excluded.printify_order_id, net = excluded.net,
                 durum = excluded.durum, takip = excluded.takip, guncelleme = excluded.guncelleme""",
            (makbuz, pid, round(brut, 2), k.net, r.get("status"), takip, olusma.isoformat(), simdi.isoformat(timespec="seconds")),
        )
        sayac["guncel" if var else "yeni"] += 1
        if not takip and not r.get("is_shipped") and is_gunu_farki(olusma, simdi) > GECIKME_IS_GUNU:
            sayac["alarm"].append(f"makbuz {makbuz}: {is_gunu_farki(olusma, simdi)} iş günü, takip yok")
    db.olay(c, "siparis", None, None, "izlendi", f"{sayac['yeni']} yeni, {len(sayac['alarm'])} alarm")
    c.commit()
    for a in sayac["alarm"]:
        yazdir(f"  ALARM {a}")
    return sayac


def ozet(c, gun: int = 30) -> dict:
    bas = (datetime.now(UTC) - timedelta(days=gun)).isoformat()
    r = c.execute(
        "SELECT count(*), coalesce(sum(brut), 0), coalesce(sum(net), 0) FROM siparis WHERE olusturma >= ?", (bas,)
    ).fetchone()
    return {"gun": gun, "siparis": r[0], "brut_usd": round(r[1], 2), "net_usd": round(r[2], 2)}
