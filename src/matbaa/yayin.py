"""Yayın (Faz 6–7): onaylanan tasarım → Printify ürünleri → Etsy'de üretim ortağı + aktif.

Isınma eğrisi (`config/yayin.toml`) günlük tasarım sayısını mağaza yaşına göre sınırlar. Her adım ürün başına
durum makinesine yazar; hata ürünü `hata`ya düşürür, sonraki koşu yeniden dener (diğer ürünleri durdurmaz).
"""

from __future__ import annotations

import json
import re
import tomllib
from datetime import UTC, datetime
from functools import cache

from matbaa import db, tavan
from matbaa.ayar import CONFIG, KOK
from matbaa.entegrasyon import printify as pf
from matbaa.fiyat import urunler
from matbaa.ilan.metin import AI_BEYANI


@cache
def ayar() -> dict:
    return tomllib.loads((CONFIG / "yayin.toml").read_text(encoding="utf-8"))


def magaza_yasi(c) -> int:
    ilk = c.execute("SELECT min(zaman) FROM olay WHERE varlik = 'urun' AND yeni LIKE '%:printify'").fetchone()[0]
    if not ilk:
        return 0
    return (datetime.now(UTC) - datetime.fromisoformat(ilk)).days


def gunluk_sinir(c) -> int:
    yas = magaza_yasi(c)
    for bas, son, sinir in ayar()["isinma"]:
        if bas <= yas < son:
            return sinir
    return 0


def bugun_yayinlanan(c) -> int:
    bugun = datetime.now(UTC).date().isoformat()
    return c.execute(
        "SELECT count(DISTINCT varlik_id) FROM olay WHERE varlik = 'urun' AND yeni LIKE '%:printify' AND zaman >= ?", (bugun,)
    ).fetchone()[0]


def printify_kesif(p: pf.Printify) -> dict:
    """Katalog eşlemesi: her ürün için blueprint ve ABD sağlayıcı adayları. Seçim (K-20: numunesiz) config'e yazılır."""
    sonuc = {}
    for urun, a in ayar()["printify"].items():
        bps = p.blueprint_bul(a["blueprint_ara"])
        sonuc[urun] = []
        for b in bps[:3]:
            saglayicilar = p.saglayicilar(b["id"])
            sonuc[urun].append(
                {
                    "blueprint_id": b["id"],
                    "baslik": b.get("title"),
                    "saglayicilar": [(s["id"], s.get("title"), (s.get("location") or {}).get("country")) for s in saglayicilar],
                }
            )
    return sonuc


def _gorseller(p: pf.Printify, tasarim_id: int, dosyalar: dict, onbellek: dict) -> dict:
    if tasarim_id not in onbellek:
        onbellek[tasarim_id] = {
            m: p.gorsel_yukle(KOK / dosyalar[f"{m}_png"], f"matbaa-{tasarim_id:05d}-{m}.png") for m in ("koyu", "acik")
        }
    return onbellek[tasarim_id]


YAYIN_ADIMLARI = ("bekliyor", "olusturuldu")  # yayinla'nın sahiplendiği adımlar; sonrası etsy_esle'nin


def _yayin_bekleyen(c, tasarim_id: int) -> list[tuple[str, str]]:
    """(ürün, başlanacak adım): henüz Etsy'ye yayın istenmemiş ürünler, düştükleri adımdan."""
    sonuc = []
    for urun, durum in c.execute("SELECT urun, durum FROM urun WHERE tasarim_id = ? ORDER BY rowid", (tasarim_id,)).fetchall():
        adim = db.hata_oncesi(c, tasarim_id, urun) if durum == "hata" else durum
        if adim in YAYIN_ADIMLARI:
            sonuc.append((urun, adim))
    return sonuc


def yayinla(c, p: pf.Printify, yazdir=print) -> dict:
    sayac = {"sinir": gunluk_sinir(c), "bugun_onceki": bugun_yayinlanan(c), "tasarim": 0, "urun": 0, "hata": 0}
    kalan = sayac["sinir"] - sayac["bugun_onceki"]
    if kalan <= 0:
        yazdir(f"  günlük sınır doldu ({sayac['sinir']} tasarım, mağaza yaşı {magaza_yasi(c)} gün)")
        return sayac
    katalog, ycfg = urunler(), ayar()["printify"]
    eksik = [u for u in katalog if not ycfg.get(u, {}).get("blueprint_id")]
    if eksik:
        raise RuntimeError(f"Printify kataloğu eşlenmemiş: {eksik} → `uv run matbaa printify-kesif`, sonra config/yayin.toml")
    varyant_onbellek: dict[str, dict] = {}
    gorsel_onbellek: dict[int, dict] = {}
    # Yalnız yayın bekleyen ürünü olan tasarımlar günlük sınırdan pay alır: Etsy eşlemesini bekleyen tasarım yer tutmaz.
    tasarimlar = [
        (t, b)
        for t in c.execute("SELECT id, dosyalar FROM tasarim WHERE durum = 'onaylandi' ORDER BY durum_zamani").fetchall()
        if (b := _yayin_bekleyen(c, t["id"]))
    ][:kalan]
    for t, bekleyen in tasarimlar:
        dosyalar = json.loads(t["dosyalar"])
        for urun, adim in bekleyen:
            try:
                tavan.ilan_kontrol(c)
            except tavan.TavanAsildi as e:  # para harcamadan dur; kalan ürünler sonraki ay/onaydan sonra açılır
                sayac["tavan"] = str(e)
                yazdir(f"  {e}")
                return sayac
            k, il = katalog[urun], c.execute("SELECT * FROM ilan WHERE tasarim_id = ? AND urun = ?", (t["id"], urun)).fetchone()
            try:
                if c.execute("SELECT durum FROM urun WHERE tasarim_id = ? AND urun = ?", (t["id"], urun)).fetchone()[0] == "hata":
                    db.urun_gecis(c, t["id"], urun, adim, "yeniden deneme")
                if adim == "bekliyor":
                    bp, sg = ycfg[urun]["blueprint_id"], ycfg[urun]["saglayici_id"]
                    if urun not in varyant_onbellek:
                        varyant_onbellek[urun] = pf.varyant_sec(p.varyantlar(bp, sg), k["renkler"], k["bedenler"])
                    govde = pf.urun_govdesi(
                        il["baslik"], il["aciklama"], json.loads(il["etiketler"]), bp, sg,
                        varyant_onbellek[urun], _gorseller(p, t["id"], dosyalar, gorsel_onbellek), il["fiyat"], k.get("buyuk_beden_ek", {}),
                    )  # fmt: skip
                    urun_id = p.urun_olustur(govde)["id"]
                    # Kimlik yayından önce kaydedilir: yayın düşerse sonraki koşu aynı ürünü yayınlar, ikincisini açmaz.
                    db.urun_gecis(c, t["id"], urun, "olusturuldu", "Printify ürünü oluşturuldu", printify_id=urun_id)
                    c.commit()
                else:
                    urun_id = c.execute(
                        "SELECT printify_id FROM urun WHERE tasarim_id = ? AND urun = ?", (t["id"], urun)
                    ).fetchone()[0]
                p.yayinla(urun_id)
                db.urun_gecis(c, t["id"], urun, "printify", "Etsy'ye yayın istendi")
                sayac["urun"] += 1
            except Exception as e:  # ürün başına izole: biri düşerse diğerleri sürer
                db.urun_gecis(c, t["id"], urun, "hata", f"{type(e).__name__}: {e}"[:500])
                sayac["hata"] += 1
                yazdir(f"  hata {t['id']}/{urun}: {e}")
            c.commit()
        sayac["tasarim"] += 1
    return sayac


def _etsy_kimligi(urun: dict) -> str | None:
    dis = urun.get("external")
    if isinstance(dis, list):
        dis = dis[0] if dis else None
    return str(dis["id"]) if isinstance(dis, dict) and dis.get("id") else None


YAYIN_ZAMAN_ASIMI_SAAT = 48  # Printify'ın Etsy ilanını açması dakikalar sürer; bu kadar beklemişse yayın düşmüştür
YENIDEN_YAYIN_MAKS = 2
ELLE = "elle bakılmalı"  # bu hatayla düşen ürün otomatik yeniden denenmez (haftalık rapor ve panel gösterir)


def _yayin_asimi(c, r) -> bool:
    """Etsy ilanı süresinde oluşmadıysa ürünü yeniden yayına gönderir (yayinla `olusturuldu`dan alır); iki denemeden sonra hata."""
    gecen = datetime.now(UTC) - datetime.fromisoformat(r["guncelleme"])
    if gecen.total_seconds() < YAYIN_ZAMAN_ASIMI_SAAT * 3600:
        return False
    onceki = c.execute(
        "SELECT count(*) FROM olay WHERE varlik = 'urun' AND varlik_id = ? AND eski = 'printify' AND yeni = ?",
        (r["tasarim_id"], f"{r['urun']}:olusturuldu"),
    ).fetchone()[0]
    neden = f"Printify yayını {YAYIN_ZAMAN_ASIMI_SAAT} saatte Etsy'ye düşmedi"
    if onceki >= YENIDEN_YAYIN_MAKS:
        db.urun_gecis(
            c, r["tasarim_id"], r["urun"], "hata", f"{neden} ({onceki} yeniden yayından sonra), Printify panelinde {ELLE}"
        )
    else:
        db.urun_gecis(c, r["tasarim_id"], r["urun"], "olusturuldu", f"{neden}: yeniden yayın")
    return True


def etsy_esle(c, p: pf.Printify, etsy, yazdir=print) -> dict:
    """Printify'ın Etsy'ye açtığı ilanı bul → üretim ortağını bağla, AI beyanını doğrula, aktifleştir."""
    ortak = ayar()["etsy"]["uretim_ortagi_id"]
    if not ortak:
        raise RuntimeError(
            "config/yayin.toml [etsy] uretim_ortagi_id boş: Shop Manager'da Printify'ı üretim ortağı olarak ekle, kimliği yaz"
        )
    sayac = {"eslesen": 0, "bekleyen": 0, "aktif": 0, "hata": 0}
    satirlar = [
        r
        for r in c.execute(
            "SELECT tasarim_id, urun, printify_id, durum, etsy_listing_id, guncelleme, hata FROM urun WHERE durum IN ('printify', 'etsy_taslak', 'hata')"
        ).fetchall()
        if r["durum"] != "hata"
        or (ELLE not in (r["hata"] or "") and db.hata_oncesi(c, r["tasarim_id"], r["urun"]) in ("printify", "etsy_taslak"))
    ]
    for r in satirlar:
        try:
            listing = r["etsy_listing_id"]
            if r["durum"] == "hata":
                geri = db.hata_oncesi(c, r["tasarim_id"], r["urun"])
                db.urun_gecis(c, r["tasarim_id"], r["urun"], geri, "Etsy adımı yeniden deneniyor")
                r = {**dict(r), "durum": geri}
            if r["durum"] == "printify":
                listing = _etsy_kimligi(p.urun(r["printify_id"]))
                if not listing:
                    if _yayin_asimi(c, r):
                        sayac["yeniden_yayin"] = sayac.get("yeniden_yayin", 0) + 1
                    else:
                        sayac["bekleyen"] += 1  # Printify yayını sürüyor
                    c.commit()
                    continue
                db.urun_gecis(c, r["tasarim_id"], r["urun"], "etsy_taslak", "Etsy ilanı oluştu", etsy_listing_id=listing)
                sayac["eslesen"] += 1
            ilan = etsy.ilan(int(listing))
            alanlar: dict = {
                "production_partner_ids": [ortak],
                "who_made": "i_did",
                "when_made": "made_to_order",
                "is_supply": "false",
            }
            if AI_BEYANI.split(":")[0] not in re.sub(r"<[^>]+>", " ", ilan.get("description", "")):
                alanlar["description"] = c.execute(
                    "SELECT aciklama FROM ilan WHERE tasarim_id = ? AND urun = ?", (r["tasarim_id"], r["urun"])
                ).fetchone()[0]
            alanlar["state"] = "active"
            etsy.ilan_guncelle(int(listing), **alanlar)
            db.urun_gecis(c, r["tasarim_id"], r["urun"], "aktif", "üretim ortağı bağlandı, AI beyanı doğrulandı, aktif")
            sayac["aktif"] += 1
            if c.execute("SELECT durum FROM tasarim WHERE id = ?", (r["tasarim_id"],)).fetchone()[0] == "onaylandi":
                db.gecis(c, r["tasarim_id"], "yayinda")
        except Exception as e:
            db.urun_gecis(c, r["tasarim_id"], r["urun"], "hata", f"etsy: {type(e).__name__}: {e}"[:500])
            sayac["hata"] += 1
            yazdir(f"  etsy hata {r['tasarim_id']}/{r['urun']}: {e}")
        c.commit()
    return sayac
