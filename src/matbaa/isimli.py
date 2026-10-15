"""İsimli yılbaşı süsü (Faz 11, 2026-10-15 öne alındı): ilan doğrudan Etsy'de, sipariş Printify API'siyle.

Neden Printify yayını değil: Printify'ın kendi Etsy kişiselleştirmesi her siparişi panelde elle onay bekletir ve katmanı API'den
tanımlatmaz (2026-10-15 araştırma). Printify'a bağlı olmayan ilanın Etsy siparişi Printify'a otomatik aktarılmaz ("Other orders"):
siparişi yalnız biz açarız, çift üretim olmaz.

İlan (`ilan_ac`, `yayin.yayinla` "bekliyor"/"olusturuldu" adımında çağırır): taslak ilan → iki varyantlı envanter (SKU =
Printify varyantı) → isim sorusu → Printify'ın örnek isimli geçici ürününden mockup'lar + isim/güven kartları → `etsy_taslak`;
aktifleştirmeyi `yayin.etsy_esle` yapar (üretim ortağı, kargo profili, AI beyanı, işlem süresi).

Sipariş (`siparisleri_isle`, günlük koşu): ödenmiş makbuzdaki isimli kalemler → isimli baskı dosyası → Printify'da tek seferlik
ürün → API siparişi (`external_id` = makbuz; `siparis.izle` buradan eşler) → on-hold olunca üretime → takip Etsy'ye.
Her makbuz `isimli_siparis` tablosunda tek satır; Printify'da aynı makbuzlu iptal olmamış sipariş varsa ikincisi açılmaz.
Açılamayan sipariş (`hata`, ör. fontta glifi olmayan isim) her gün yeniden denenir ve alarm verir; panelden elle isim verilirse
(`duzeltme`) o isimle açılır. Printify'ın iptal ettiği sipariş `elle`ye düşer: otomatik yeniden açılmaz (çift üretim riski).
"""

from __future__ import annotations

import io
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from matbaa import db
from matbaa.entegrasyon import printify as pf
from matbaa.fiyat import urunler

URUN = "isimli_susleme"
KOK = Path(__file__).resolve().parents[2]
CIKTI = KOK / "calisma" / "isimli"
KISISEL_OZELLIK = 54  # Etsy makbuzunda alıcının kişiselleştirme cevabı
SEKIL_OZELLIK, SEKIL_ADI = 513, "Ornament shapes"  # Printify'ın süs ilanlarıyla aynı varyant özelliği
SKU_ON = "MATBAA-ISIM"
MOCKUP_MAKS = 10
# Printify süs mockup kameraları (`mockup_id` sonu), galeri sırasıyla. "back", "back-2", "front-and-back" boş arka yüzü gösterir
# (tek yüzlü üründe satışa zayıf, 2026-10-15 canlı taslak): alınmaz.
KAMERALAR = ("front", "context", "context-2", "giftbox", "context-3", "context-4", "front-2", "flatlay")
BEKLE_SN = 90  # API siparişi on-hold'a geçene kadar (canlı: ~10 sn)
KAPALI_MAKBUZ = ("canceled", "fully refunded")


def ayar() -> dict:
    return urunler()[URUN]


def etsy_kanali(urun: str) -> bool:
    return urunler()[urun].get("kanal") == "etsy"


# --- baskı dosyası ---


def on_png(dosyalar: dict, isim: str, yil: int, hedef: Path) -> Path:
    from matbaa.tasarim import susleme

    koyu = KOK / dosyalar["koyu_png"]
    svg = KOK / dosyalar.get("koyu_svg", str(Path(dosyalar["koyu_png"]).with_suffix(".svg")))
    vurgu = susleme.vurgu_rengi(svg) if svg.exists() else susleme.KOYU_MUREKKEP
    hedef.parent.mkdir(parents=True, exist_ok=True)
    susleme.on_yuz(koyu, vurgu, yil, isim).save(hedef, dpi=(600, 600), optimize=True)
    return hedef


def ornekler(dosyalar: dict, yil: int | None = None) -> list[Path]:
    """İlan görselleri için örnek isimli ön yüzler (tasarım klasöründe, varsa yeniden çizilmez)."""
    yil = yil or datetime.now(UTC).year
    klasor = (KOK / dosyalar["koyu_png"]).parent
    sonuc = []
    for i, ad in enumerate(ayar()["ornek_isimler"]):
        yol = klasor / f"isimli_{yil}_{i}.png"
        sonuc.append(yol if yol.exists() else on_png(dosyalar, ad, yil, yol))
    return sonuc


def varyantlar(p: pf.Printify) -> dict[str, int]:
    """Beden adı ("Round", "Round + White Gift Packaging") → Printify varyant kimliği."""
    k = ayar()
    y = _printify_ayar()
    gruplar = pf.varyant_sec(p.varyantlar(y["blueprint_id"], y["saglayici_id"]), k["renkler"], k["bedenler"], k["beden_anahtari"])
    sonuc = {str(v["options"][k["beden_anahtari"]]): v["id"] for vs in gruplar.values() for v in vs}
    if set(sonuc) != set(k["bedenler"]):
        raise ValueError(f"Printify varyantları eksik: {sorted(set(k['bedenler']) - set(sonuc))}")
    return sonuc


def _printify_ayar() -> dict:
    from matbaa import yayin

    return yayin.ayar()["printify"][URUN]


def _urun_govdesi(p: pf.Printify, png: Path, ad: str, baslik: str, vmap: dict[str, int], fiyat: float) -> dict:
    gid, kutu, tuval = p.gorsel_yukle(png, ad)
    y = _printify_ayar()
    v0 = next(v for v in p.varyantlar(y["blueprint_id"], y["saglayici_id"]) if v["id"] in vmap.values())
    poz, ag, ay = pf.on_yer_tutucu(v0)
    yer = pf.yerlesim(kutu, tuval, (ag, ay))
    return {
        "title": baslik,
        "description": baslik,
        "blueprint_id": y["blueprint_id"],
        "print_provider_id": y["saglayici_id"],
        "variants": [{"id": vid, "price": round(fiyat * 100), "is_enabled": True} for vid in vmap.values()],
        "print_areas": [
            {
                "variant_ids": list(vmap.values()),
                "placeholders": [
                    {"position": poz, "images": [{"id": gid, "x": yer.x, "y": yer.y, "scale": yer.scale, "angle": 0}]}
                ],
            }
        ],
    }


# --- ilan ---


def envanter_govdesi(tasarim_id: int, vmap: dict[str, int]) -> dict:
    k = ayar()
    from matbaa import yayin

    hp = yayin.ayar()["etsy"].get("hazirlama_profili_id")
    return {
        "products": [
            {
                "sku": f"{SKU_ON}-{tasarim_id}-{vmap[b]}",
                "property_values": [
                    {"property_id": SEKIL_OZELLIK, "property_name": SEKIL_ADI, "values": [b], "value_ids": [], "scale_id": None}
                ],
                "offerings": [
                    {
                        "price": round(k["fiyat"] + k.get("buyuk_beden_ek", {}).get(b, 0.0), 2),
                        "quantity": 999,
                        "is_enabled": True,
                        **({"readiness_state_id": hp} if hp else {}),
                    }
                ],
            }
            for b in k["bedenler"]
        ],
        "price_on_property": [SEKIL_OZELLIK],
        "quantity_on_property": [],
        "sku_on_property": [SEKIL_OZELLIK],
        "readiness_state_on_property": [],
    }


def kisisel_sorular() -> list[dict]:
    s = ayar()["kisisel"]
    return [
        {
            "question_type": "text_input",
            "question_text": s["soru"],
            "required": True,
            "instructions": s["aciklama"][:120],
            "max_allowed_characters": s["maks"],
        }
    ]


def _mockuplar(p: pf.Printify, t, vmap: dict[str, int], indir=None) -> list[bytes]:
    """Printify'da örnek isimli geçici ürün → mockup'lar (kopyasız, en çok `MOCKUP_MAKS`) → ürün silinir."""
    import httpx
    from PIL import Image

    from matbaa.ilan import gorsel

    indir = indir or (lambda url: httpx.get(url, timeout=60, follow_redirects=True).content)
    dos = json.loads(t["dosyalar"])
    png = ornekler(dos)[0]
    u = p.urun_olustur(
        _urun_govdesi(p, png, f"matbaa-{t['id']:05d}-isimli-ornek.png", "TEMP mockup source", vmap, ayar()["fiyat"])
    )
    try:
        secilen: dict[str, dict] = {}
        for g in u.get("images") or []:  # ilk varyantın kamerası esas; hediye kutusu yalnız kutulu varyantta
            secilen.setdefault(str(g.get("mockup_id", "")).rsplit("_", 1)[-1], g)
        sirali = [secilen[e] for e in KAMERALAR if e in secilen]
        ham: list[tuple[dict, bytes]] = []
        for g in sirali:
            for deneme in range(3):  # mockup ilk istekte üretiliyor olabilir
                try:
                    ham.append(({"listing_image_id": len(ham), "src": g["src"]}, indir(g["src"])))
                    break
                except Exception:
                    if deneme == 2:
                        raise
                    time.sleep(3)
        goruntu = [(g, Image.open(io.BytesIO(b))) for g, b in ham]
        kopya = {g["listing_image_id"] for g in gorsel.kopyalar(goruntu)}
        return [b for g, b in ham if g["listing_image_id"] not in kopya][:MOCKUP_MAKS]
    finally:
        p.urun_sil(u["id"])


def ilan_ac(c, etsy, p: pf.Printify, t, il, yazdir=print, indir=None, gorsel_indir=None) -> str:
    """Taslak ilanı açar ya da yarıda kalanı tamamlar; sonunda ürün `etsy_taslak` (aktifleştirme `etsy_esle`'de)."""
    from matbaa import yayin
    from matbaa.ilan import gorsel

    k, e_ayar = ayar(), yayin.ayar()["etsy"]
    tid = t["id"]
    satir = c.execute("SELECT durum, etsy_listing_id FROM urun WHERE tasarim_id = ? AND urun = ?", (tid, URUN)).fetchone()
    vmap = varyantlar(p)
    lid = satir["etsy_listing_id"]
    if not lid:
        alanlar = {
            "quantity": 999,
            "title": il["baslik"],
            "description": il["aciklama"],
            "price": k["fiyat"],
            "who_made": "i_did",
            "when_made": "made_to_order",
            "is_supply": "false",
            "taxonomy_id": k["etsy_taksonomi"],
            "type": "physical",
            "tags": json.loads(il["etiketler"]),
            "should_auto_renew": "true",
            "production_partner_ids": [e_ayar["uretim_ortagi_id"]],
            "shipping_profile_id": e_ayar["kargo_profili_id"],
            **({"return_policy_id": rp} if (rp := e_ayar.get("iade_politikasi_id")) else {}),
            **({"readiness_state_id": hp} if (hp := e_ayar.get("hazirlama_profili_id")) else {}),
        }
        lid = str(etsy.taslak_ilan(**alanlar)["listing_id"])
        # Kimlik hemen kaydedilir: sonraki adım düşerse ertesi koşu aynı taslağı tamamlar, ikinci taslak açmaz.
        db.urun_gecis(c, tid, URUN, "olusturuldu", "Etsy taslak ilanı açıldı (isimli)", etsy_listing_id=lid)
        c.commit()
    etsy.envanter_yaz(int(lid), envanter_govdesi(tid, vmap))
    etsy.kisisellestirme_yaz(int(lid), kisisel_sorular())
    if not etsy.ilan_gorselleri(int(lid)):
        for rank, b in enumerate(_mockuplar(p, t, vmap, indir), start=1):
            etsy.gorsel_yukle(int(lid), b, rank, f"mockup-{rank}.jpg")
    dos = {"isimli_ornekler": ornekler(json.loads(t["dosyalar"]))}
    s = gorsel.ilana_ekle(etsy, int(lid), URUN, dos, tohum=tid, indir=gorsel_indir)
    db.olay(c, "urun", tid, None, f"{URUN}:gorsel", f"vitrin={s['vitrin']} eklenen={s['eklenen']}")
    db.urun_gecis(c, tid, URUN, "printify", "isimli: Printify yayını yok, ilan doğrudan Etsy'de (listeleme ücreti sayılır)")
    db.urun_gecis(c, tid, URUN, "etsy_taslak", "isimli taslak hazır: envanter, isim sorusu, görseller", etsy_listing_id=lid)
    c.commit()
    yazdir(f"  isimli ilan hazır: tasarım {tid} → {lid}")
    return lid


# --- sipariş ---


def kalemler(makbuz: dict, ilanlar: dict[str, int]) -> list[dict]:
    """Makbuzdaki isimli kalemler: {transaction_id, tasarim_id, isim, varyant_id, adet}. `ilanlar`: listing_id → tasarım.
    İsim yoksa `isim` None (zorunlu soru; yine de gelirse sipariş insana düşer)."""
    sonuc = []
    for tr in makbuz.get("transactions") or []:
        tid = ilanlar.get(str(tr.get("listing_id")))
        if tid is None:
            continue
        isim = next(
            (
                str(v.get("formatted_value") or "").strip()
                for v in tr.get("variations") or []
                if v.get("property_id") == KISISEL_OZELLIK and str(v.get("formatted_value") or "").strip()
            ),
            None,
        )
        sku = str(tr.get("sku") or "")
        varyant = int(sku.rsplit("-", 1)[1]) if sku.startswith(SKU_ON) else None
        sonuc.append(
            {
                "transaction_id": str(tr.get("transaction_id")),
                "tasarim_id": tid,
                "isim": isim,
                "varyant_id": varyant,
                "adet": int(tr.get("quantity") or 1),
            }
        )
    return sonuc


def adres(makbuz: dict) -> dict:
    ad = " ".join(str(makbuz.get("name") or "").split()) or "Customer"
    on, _, son = ad.rpartition(" ")
    return {
        "first_name": on or son,
        "last_name": son if on else ".",
        "email": makbuz.get("buyer_email") or "",
        "phone": "",
        "country": makbuz.get("country_iso") or "US",
        "region": makbuz.get("state") or "",
        "address1": makbuz.get("first_line") or "",
        "address2": makbuz.get("second_line") or "",
        "city": makbuz.get("city") or "",
        "zip": makbuz.get("zip") or "",
    }


def _kaydet(c, makbuz: str, **alanlar) -> None:
    simdi = datetime.now(UTC).isoformat(timespec="seconds")
    if c.execute("SELECT 1 FROM isimli_siparis WHERE etsy_receipt_id = ?", (makbuz,)).fetchone():
        ek = "".join(f", {k} = ?" for k in alanlar)
        c.execute(f"UPDATE isimli_siparis SET guncelleme = ?{ek} WHERE etsy_receipt_id = ?", (simdi, *alanlar.values(), makbuz))
    else:
        alanlar = {"durum": "yeni"} | alanlar
        c.execute(
            f"INSERT INTO isimli_siparis (etsy_receipt_id, olusturma, guncelleme, {', '.join(alanlar)}) VALUES (?, ?, ?{', ?' * len(alanlar)})",
            (makbuz, simdi, simdi, *alanlar.values()),
        )
    c.commit()


def _var_olan(p: pf.Printify, makbuz: str) -> dict | None:
    """Printify'da bu makbuzla açılmış, iptal edilmemiş sipariş (yarıda kalan koşu kimliği kaydedemeden düştüyse)."""
    for o in p.son_siparisler(sayfa_maks=5):
        if str((o.get("metadata") or {}).get("shop_order_id")) == makbuz and o.get("status") != "canceled":
            return o
    return None


def _ac(c, p: pf.Printify, makbuz: dict, ks: list[dict], yil: int) -> str:
    mid = str(makbuz["receipt_id"])
    if o := _var_olan(p, mid):
        return str(o["id"])
    vmap = varyantlar(p)
    satirlar = []
    for k in ks:
        if not k["isim"]:
            raise ValueError(f"kalem {k['transaction_id']}: isim yok")
        if k["varyant_id"] not in vmap.values():
            raise ValueError(f"kalem {k['transaction_id']}: SKU'dan varyant çıkmadı")
        from matbaa.tasarim import susleme

        isim = susleme.isim_temizle(k["isim"])  # glifi olmayan isim burada düşer (EksikGlif)
        dos = json.loads(c.execute("SELECT dosyalar FROM tasarim WHERE id = ?", (k["tasarim_id"],)).fetchone()[0])
        png = on_png(dos, isim, yil, CIKTI / f"{mid}-{k['transaction_id']}.png")
        govde = _urun_govdesi(
            p, png, f"matbaa-isimli-{mid}-{k['transaction_id']}.png", f"Order {mid} - {isim}", vmap, ayar()["fiyat"]
        )
        u = p.urun_olustur(govde)
        satirlar.append({"product_id": u["id"], "variant_id": k["varyant_id"], "quantity": k["adet"]})
    o = p.siparis_ac(
        {
            "external_id": mid,
            "label": f"Etsy {mid}",
            "line_items": satirlar,
            "shipping_method": 1,
            "send_shipping_notification": False,
            "address_to": adres(makbuz),
        }
    )
    return str(o["id"])


def _uretime(p: pf.Printify, oid: str, bekle_sn: float = BEKLE_SN, uyu=time.sleep) -> bool:
    """On-hold olunca üretime gönderir. Hâlâ hesaplanıyorsa False (ertesi koşu yeniden dener)."""
    son = time.monotonic() + bekle_sn
    while True:
        durum = p.siparis(oid).get("status")
        if durum == "on-hold":
            p.uretime_gonder(oid)
            return True
        if durum not in ("pending", "cost-calculation") or time.monotonic() >= son:
            if durum in ("pending", "cost-calculation"):
                return False
            raise RuntimeError(f"Printify siparişi {oid}: beklenmeyen durum {durum!r}")
        uyu(5)


TASIYICI = {"usps": "usps", "ups": "ups", "fedex": "fedex", "dhl": "dhl", "dhl ecommerce": "dhl-global-mail"}


def siparisleri_isle(c, etsy, p: pf.Printify, simdi: datetime | None = None, yazdir=print, bekle_sn: float = BEKLE_SN) -> dict:
    simdi = simdi or datetime.now(UTC)
    sayac: dict = {"yeni": 0, "uretimde": 0, "takip": 0, "iptal": 0, "hata": 0, "alarm": []}
    ilanlar = {
        r[0]: r[1]
        for r in c.execute("SELECT etsy_listing_id, tasarim_id FROM urun WHERE urun = ? AND etsy_listing_id IS NOT NULL", (URUN,))
    }
    if not ilanlar and not c.execute("SELECT 1 FROM isimli_siparis LIMIT 1").fetchone():
        return sayac
    kayit = {r["etsy_receipt_id"]: dict(r) for r in c.execute("SELECT * FROM isimli_siparis")}
    son = (simdi - timedelta(days=30)).timestamp()
    for m in etsy.makbuzlar(int(son)) if ilanlar else []:
        mid = str(m["receipt_id"])
        ks = kalemler(m, ilanlar)
        if not ks:
            continue
        r = kayit.get(mid)
        duzeltme = json.loads((r or {}).get("duzeltme") or "{}")  # panelden elle verilen isim (basılamayan isim)
        for k in ks:
            k["isim"] = duzeltme.get(k["transaction_id"], k["isim"])
        if str(m.get("status") or "").lower() in KAPALI_MAKBUZ:
            if r and r.get("printify_order_id") and r["durum"] in ("acildi", "hata"):
                try:
                    p.siparis_iptal(r["printify_order_id"])
                    _kaydet(c, mid, durum="iptal")
                    sayac["iptal"] += 1
                except Exception as e:
                    sayac["alarm"].append(f"isimli makbuz {mid} iptal edildi ama Printify siparişi iptal olmadı: {e}"[:200])
            elif r and r["durum"] == "uretimde":  # üretimdeki sipariş API'den iptal edilemez: insan bakar (bir kez, `elle`)
                _kaydet(c, mid, durum="elle", hata="makbuz iptal/iade edildi ama Printify siparişi üretimde")
            elif r and r["durum"] == "takip_yazildi":  # kargodan sonra iade: Printify'da yapılacak bir şey yok
                _kaydet(c, mid, durum="iptal")
            elif not r:
                _kaydet(c, mid, durum="iptal", kalemler=json.dumps(ks, ensure_ascii=False))
            continue
        if r and r["durum"] != "hata":
            continue
        try:
            _kaydet(c, mid, kalemler=json.dumps(ks, ensure_ascii=False))
            oid = _ac(c, p, m, ks, _yil(m, simdi))
            _kaydet(c, mid, durum="acildi", printify_order_id=oid, hata=None)
            sayac["yeni"] += 1
            yazdir(f"  isimli sipariş açıldı: makbuz {mid} → Printify {oid} ({', '.join(str(k['isim']) for k in ks)})")
        except Exception as e:
            _kaydet(c, mid, durum="hata", hata=f"{type(e).__name__}: {e}"[:500])
            sayac["hata"] += 1
            sayac["alarm"].append(f"isimli makbuz {mid}: sipariş açılamadı ({type(e).__name__}: {str(e)[:120]})")
    for r in c.execute("SELECT * FROM isimli_siparis WHERE durum = 'acildi'").fetchall():
        try:
            if _uretime(p, r["printify_order_id"], bekle_sn):
                _kaydet(c, r["etsy_receipt_id"], durum="uretimde")
                sayac["uretimde"] += 1
        except Exception as e:
            _kaydet(c, r["etsy_receipt_id"], hata=f"{type(e).__name__}: {e}"[:500])
            sayac["alarm"].append(f"isimli makbuz {r['etsy_receipt_id']}: üretime gönderilemedi ({str(e)[:120]})")
    for r in c.execute("SELECT * FROM isimli_siparis WHERE durum = 'uretimde'").fetchall():
        try:
            o = p.siparis(r["printify_order_id"])
            if o.get("status") == "canceled":  # Printify iptal etti (ödeme, üretim sorunu) ya da panelden iptal: alıcıya gitmiyor
                neden = f"Printify siparişi {r['printify_order_id']} iptal edildi, makbuz hâlâ açık: Printify'da yeniden aç ya da Etsy'de iade et"
                _kaydet(c, r["etsy_receipt_id"], durum="elle", hata=neden)
                continue
            g = next((s for s in o.get("shipments") or [] if s.get("number")), None)
            if not g:
                continue
            tasiyici = TASIYICI.get(str(g.get("carrier") or "").lower(), str(g.get("carrier") or "other").lower())
            etsy.takip_yaz(int(r["etsy_receipt_id"]), g["number"], tasiyici)
            _kaydet(c, r["etsy_receipt_id"], durum="takip_yazildi", takip=g["number"], hata=None)
            sayac["takip"] += 1
        except Exception as e:
            _kaydet(c, r["etsy_receipt_id"], hata=f"takip: {type(e).__name__}: {e}"[:500])
            sayac["alarm"].append(f"isimli makbuz {r['etsy_receipt_id']}: takip Etsy'ye yazılamadı ({str(e)[:120]})")
    # İnsan bekleyenler panelden "elle hallettim" denene kadar her gün hatırlatılır.
    for r in c.execute("SELECT etsy_receipt_id, hata FROM isimli_siparis WHERE durum = 'elle'").fetchall():
        sayac["alarm"].append(f"isimli makbuz {r[0]}: elle bakılmalı ({(r[1] or '')[:160]})")
    return sayac


class DurumUyumsuz(RuntimeError):
    """Panel eylemi siparişin şu anki durumunda yapılamaz (ör. üretimdeki siparişin ismi değişmez)."""


def elle_isim(c, makbuz: str, isimler: dict[str, str]) -> dict[str, str]:
    """Panelden verilen isimler {transaction_id: isim}: basılabilir mi denetlenir (`EksikGlif`/boş isim hatası yükselir), kayda
    yazılır, sipariş `hata`ya alınır; sonraki koşu (ya da `matbaa isimli`) o isimle açar. Yalnız açılmamış siparişe uygulanır."""
    from matbaa.tasarim import susleme

    r = c.execute("SELECT durum, duzeltme FROM isimli_siparis WHERE etsy_receipt_id = ?", (makbuz,)).fetchone()
    if r is None:
        raise KeyError(makbuz)
    if r["durum"] not in ("yeni", "hata"):
        raise DurumUyumsuz(f"sipariş {r['durum']} durumunda: isim yalnız açılmamış siparişte düzeltilir")
    temiz = {str(t): susleme.isim_temizle(i) for t, i in isimler.items()}
    duz = json.loads(r["duzeltme"] or "{}") | temiz
    _kaydet(
        c, makbuz, durum="hata", duzeltme=json.dumps(duz, ensure_ascii=False), hata="panelden isim verildi, sonraki koşu açar"
    )
    return temiz


def elle_kapat(c, makbuz: str) -> None:
    """Panel: "elle hallettim" (Printify'da elle açıldı, iade edildi…): sipariş bir daha denenmez, alarm kalkar."""
    r = c.execute("SELECT durum FROM isimli_siparis WHERE etsy_receipt_id = ?", (makbuz,)).fetchone()
    if r is None:
        raise KeyError(makbuz)
    if r["durum"] not in ("yeni", "hata", "elle"):
        raise DurumUyumsuz(f"sipariş {r['durum']} durumunda: kapatılacak bir sorun yok")
    _kaydet(c, makbuz, durum="kapandi")
    db.olay(c, "isimli", None, r["durum"], "kapandi", f"makbuz {makbuz} elle kapatıldı")
    c.commit()


def _yil(makbuz: dict, simdi: datetime) -> int:
    """Süsün yılı siparişin Noel'i: Ocak'ta verilen (gecikmiş) sipariş yine geçen yılın Noel'idir."""
    z = datetime.fromtimestamp(makbuz.get("create_timestamp") or makbuz.get("created_timestamp") or simdi.timestamp(), UTC)
    return z.year - (z.month == 1)
