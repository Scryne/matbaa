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
from pathlib import Path

from matbaa import db, tavan
from matbaa.ayar import CONFIG, KOK
from matbaa.entegrasyon import printify as pf
from matbaa.fiyat import mevsimde, urunler
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
    """Bugün ilk kez yayına giren tasarımlar: önceden yayında olana sonradan eklenen ürün (süs) tasarım sınırını yemez."""
    bugun = datetime.now(UTC).date().isoformat()
    return c.execute(
        """SELECT count(DISTINCT varlik_id) FROM olay o WHERE varlik = 'urun' AND yeni LIKE '%:printify' AND zaman >= ?
           AND NOT EXISTS (SELECT 1 FROM olay e WHERE e.varlik = 'urun' AND e.varlik_id = o.varlik_id
                           AND e.yeni LIKE '%:printify' AND e.zaman < ?)""",
        (bugun, bugun),
    ).fetchone()[0]


ONAY_PIST_GUN = 5  # onaylı kuyruk bu kadar günlük yayından azsa ve onay bekleyen varsa alarm


def onay_pisti(c) -> str | None:
    """Yayın onaylı tasarımla beslenir; üretim kendiliğinden sürer ama onay insanın (panel). Onaylı kuyruk bitince yayın sessizce
    durur: kalan gün azaldığında onay bekleyen varsa alarm (bekleyen yoksa günlük üretim kuyruğu zaten dolduruyor)."""
    sinir = gunluk_sinir(c)
    if not sinir:
        return None
    onayli, bekleyen = (
        c.execute("SELECT count(*) FROM tasarim WHERE durum = ?", (d,)).fetchone()[0] for d in ("onaylandi", "onay_bekliyor")
    )
    if onayli >= sinir * ONAY_PIST_GUN or not bekleyen:
        return None
    return f"onaylı kuyruk {onayli} tasarım (~{onayli // sinir} günlük yayın): panelde {bekleyen} tasarım onay bekliyor"


def etsy_disi_ilanlar(c, tarih: str) -> list[str]:
    """Veritabanında `aktif` olup o günün Etsy aktif ilan anlık görüntüsünde (`goruntulenme`, `rapor.goruntu_al`) bulunmayan ilanlar.

    Etsy bir ilanı marka bildirimiyle ya da kural ihlaliyle kendisi kaldırır; tekrarında mağazayı kapatır (araştırma 06). Bunu
    gün içinde görmek gerekir: ilan sessizce satıştan düşer, hat onu canlı sanmaya devam eder. Anlık görüntü yoksa (Etsy okunamadı)
    karşılaştırma yapılmaz: yanlış alarm yerine sessizlik."""
    gorulen = {r[0] for r in c.execute("SELECT etsy_listing_id FROM goruntulenme WHERE tarih = ?", (tarih,))}
    if not gorulen:
        return []
    return [
        f"#{t}/{u}: Etsy ilanı {lid} artık aktif değil (kaldırılmış, süresi dolmuş ya da pasife alınmış olabilir): "
        "Shop Manager → Listings ve mesajlar/bildirimler"
        for t, u, lid in c.execute(
            "SELECT tasarim_id, urun, etsy_listing_id FROM urun WHERE durum = 'aktif' AND etsy_listing_id IS NOT NULL ORDER BY 1, 2"
        )
        if str(lid) not in gorulen
    ]


def printify_kesif(p: pf.Printify) -> dict:
    """Katalog eşlemesi: her ürün için blueprint ve ABD sağlayıcı adayları. Seçim (K-20: numunesiz) config'e yazılır."""
    sonuc = {}
    for urun, a in ayar()["printify"].items():
        if not a.get("blueprint_ara"):  # markasız katalog ürünü (kupa): blueprint elle seçildi
            continue
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


def susleme_dosyalari(dosyalar: dict, fontlar: list[str], nis: str, yil: int | None = None) -> dict[str, Path]:
    """K-30: süsün ön/arka baskı dosyaları (bu Noel'in yılıyla), yoksa çizilir."""
    from matbaa.tasarim import susleme

    return susleme.kaydet(dosyalar, fontlar, nis, yil or datetime.now(UTC).year, KOK)


def _gorseller(p: pf.Printify, tasarim_id: int, dosyalar: dict, onbellek: dict, urun: str = "", t=None) -> dict:
    if urun == "susleme":  # K-30: iki yüzlü yuvarlak süs
        anahtar = (tasarim_id, "susleme")
        if anahtar not in onbellek:
            yollar = susleme_dosyalari(dosyalar, json.loads(t["fontlar"] or "[]"), t["nis"])
            onbellek[anahtar] = {"koyu": p.gorsel_yukle(yollar["on"], f"matbaa-{tasarim_id:05d}-susleme-on.png")}
            if urunler()["susleme"].get("iki_yuz"):  # arka baskı maliyeti ekler (urunler.toml)
                onbellek[anahtar]["arka"] = p.gorsel_yukle(yollar["arka"], f"matbaa-{tasarim_id:05d}-susleme-arka.png")
        return onbellek[anahtar]
    if urun == "kupa":  # Faz 14: yatay sarma görseli, tişörtün açık zemin sürümünden üretilir
        from matbaa.tasarim import kupa

        anahtar = (tasarim_id, "kupa")
        if anahtar not in onbellek:
            yol = KOK / Path(dosyalar["koyu_png"]).parent / "kupa.png"
            if not yol.exists():
                kupa.kaydet(KOK / dosyalar["koyu_png"], yol)
            onbellek[anahtar] = {"koyu": p.gorsel_yukle(yol, f"matbaa-{tasarim_id:05d}-kupa.png")}
        return onbellek[anahtar]
    if tasarim_id not in onbellek:
        onbellek[tasarim_id] = {
            m: p.gorsel_yukle(KOK / dosyalar[f"{m}_png"], f"matbaa-{tasarim_id:05d}-{m}.png") for m in ("koyu", "acik")
        }
    return onbellek[tasarim_id]


EK_URUN_GUNLUK = 3  # yayında olan tasarımlara günde en çok bu kadar tasarımın sonradan eklenen ürünü (süs) açılır
YAYIN_ADIMLARI = ("bekliyor", "olusturuldu")  # yayinla'nın sahiplendiği adımlar; sonrası etsy_esle'nin


def _yayin_bekleyen(c, tasarim_id: int) -> list[tuple[str, str]]:
    """(ürün, başlanacak adım): henüz Etsy'ye yayın istenmemiş ürünler, düştükleri adımdan."""
    sonuc = []
    for urun, durum in c.execute("SELECT urun, durum FROM urun WHERE tasarim_id = ? ORDER BY rowid", (tasarim_id,)).fetchall():
        adim = db.hata_oncesi(c, tasarim_id, urun) if durum == "hata" else durum
        if adim in YAYIN_ADIMLARI:
            sonuc.append((urun, adim))
    return sonuc


def kupa_ac(c, ilan_yaz, yazdir=print) -> dict:
    """Faz 14: satışı olan (iptal değil) tasarıma `yalniz_satan` ürünleri (kupa) açar: ilan metni + `urun` satırı; yayını `yayinla` yapar.

    `ilan_yaz(satirlar, nis, urun) -> Ilan`: hat'ın marka süzgeçli ilan yazıcısı (döngüsel içe aktarmayı önlemek için dışarıdan).
    """
    from matbaa import siparis

    kosullu = [u for u, p in urunler().items() if p.get("yalniz_satan")]
    sayac = {"acilan": 0}
    for urun in kosullu:
        for t_id, sat, nis in c.execute(
            f"""SELECT DISTINCT t.id, i.satirlar, i.nis FROM siparis s JOIN tasarim t ON t.id = s.tasarim_id JOIN ifade i ON i.id = t.ifade_id
                WHERE {siparis.GECERLI.replace("coalesce(durum", "coalesce(s.durum")} AND t.durum = 'yayinda'
                AND NOT EXISTS (SELECT 1 FROM urun u WHERE u.tasarim_id = t.id AND u.urun = ?)""",
            (urun,),
        ).fetchall():
            ilan = ilan_yaz(json.loads(sat), nis, urun)
            if [x for x in ilan.sorunlar if not x.startswith("markaya çarpan")]:
                yazdir(f"  {urun} ilanı yazılamadı ({t_id}): {ilan.sorunlar}")
                continue
            p_ = urunler()[urun]
            c.execute(
                "INSERT OR REPLACE INTO ilan (tasarim_id, urun, baslik, etiketler, aciklama, alt_metin, fiyat, kargo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (t_id, urun, ilan.baslik, json.dumps(ilan.etiketler), ilan.aciklama, ilan.alt_metin, p_["fiyat"], p_["kargo"]),
            )
            c.execute("INSERT OR IGNORE INTO urun (tasarim_id, urun) VALUES (?, ?)", (t_id, urun))
            db.olay(c, "urun", t_id, None, f"{urun}:bekliyor", "satan tasarım (Faz 14)")
            c.commit()
            sayac["acilan"] += 1
            yazdir(f"  {urun} açıldı: tasarım {t_id}")
    return sayac


MEVSIMLIK_DURUMLAR = ("onay_bekliyor", "onaylandi", "yayinda")


def mevsimlik_ac(c, ilan_yaz, gun=None, sinir: int = 12, yazdir=print) -> dict:
    """K-30: mevsimlik ürünü (süs) penceresi açıkken uygun ve henüz o ürünü olmayan tasarımlara açar: ilan metni + `urun` satırı.

    Yeni tasarımlar süsü metin adımında zaten alır; bu adım pencere açılmadan önce üretilmiş/onaylanmış/yayınlanmış olanlar
    içindir. `sinir`: bir koşuda en çok tasarım (her biri bir `claude -p` çağrısı)."""
    from matbaa.fiyat import urun_uygun

    sayac = {"acilan": 0, "hata": 0}
    for urun, p_ in urunler().items():
        if not p_.get("kosul"):
            continue
        for r in c.execute(
            f"""SELECT t.id, i.satirlar, i.nis FROM tasarim t JOIN ifade i ON i.id = t.ifade_id
                WHERE t.durum IN ({",".join("?" * len(MEVSIMLIK_DURUMLAR))})
                AND NOT EXISTS (SELECT 1 FROM urun u WHERE u.tasarim_id = t.id AND u.urun = ?)
                ORDER BY t.durum = 'yayinda' DESC, t.durum = 'onaylandi' DESC, t.durum_zamani""",
            (*MEVSIMLIK_DURUMLAR, urun),
        ).fetchall():
            satirlar = json.loads(r["satirlar"])
            if not urun_uygun(urun, r["nis"], satirlar, gun):
                continue
            if sayac["acilan"] + sayac["hata"] >= sinir:
                sayac["kalan"] = sayac.get("kalan", 0) + 1
                continue
            try:
                ilan = ilan_yaz(satirlar, r["nis"], urun)
            except Exception as e:  # claude -p zaman aşımı: ertesi koşu yeniden dener
                sayac["hata"] += 1
                yazdir(f"  {urun} ilanı yazılamadı ({r['id']}): {type(e).__name__}: {str(e)[:150]}")
                continue
            if [x for x in ilan.sorunlar if not x.startswith("markaya çarpan")]:
                sayac["hata"] += 1
                yazdir(f"  {urun} ilanı yazılamadı ({r['id']}): {ilan.sorunlar}")
                continue
            c.execute(
                "INSERT OR REPLACE INTO ilan (tasarim_id, urun, baslik, etiketler, aciklama, alt_metin, fiyat, kargo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (r["id"], urun, ilan.baslik, json.dumps(ilan.etiketler), ilan.aciklama, ilan.alt_metin, p_["fiyat"], p_["kargo"]),
            )
            c.execute("INSERT OR IGNORE INTO urun (tasarim_id, urun) VALUES (?, ?)", (r["id"], urun))
            db.olay(c, "urun", r["id"], None, f"{urun}:bekliyor", "mevsimlik ürün (K-30)")
            c.commit()
            sayac["acilan"] += 1
            yazdir(f"  {urun} açıldı: tasarım {r['id']}: {ilan.baslik[:70]}")
    return sayac


def mevsim_kapat(c, etsy, gun=None, yazdir=print) -> dict:
    """K-30: mevsimi biten ürünün (yıllı süs) aktif ilanları Etsy'de pasife alınır (`kaldirildi`): Ocak'ta "Christmas 2026"
    satmaz, otomatik yenileme ücreti boşa gitmez. Henüz yayınlanmamış olanlara dokunulmaz (yayinla pencere dışında açmaz)."""
    from matbaa.fiyat import mevsim_bitti

    sayac = {"kapanan": 0, "hata": 0}
    for urun in [u for u in urunler() if mevsim_bitti(u, gun)]:
        for r in c.execute(
            "SELECT tasarim_id, etsy_listing_id FROM urun WHERE urun = ? AND durum = 'aktif' AND etsy_listing_id IS NOT NULL",
            (urun,),
        ).fetchall():
            try:
                etsy.ilan_guncelle(int(r["etsy_listing_id"]), state="inactive", should_auto_renew="false")
            except Exception as e:  # ertesi koşu yeniden dener
                sayac["hata"] += 1
                yazdir(f"  mevsim kapatma hata {r['tasarim_id']}/{urun}: {type(e).__name__}: {str(e)[:150]}")
                continue
            db.urun_gecis(c, r["tasarim_id"], urun, "kaldirildi", "mevsim bitti: Etsy'de pasif (K-30)")
            c.commit()
            sayac["kapanan"] += 1
    return sayac


def gorselleri_tamamla(c, etsy, sinir: int = 9, yazdir=print) -> dict:
    """Etsy'de aktif ve kendi görsellerimizi (yakın plan, beden tablosu, renkler, güven kartı) henüz almamış ilanlar.

    Bir kez yapılır (`olay`: "<ürün>:gorsel"); hata ilanı düşürmez, ertesi gün yeniden denenir. `sinir`: bir koşuda en çok ilan
    (her ilan ~5 Etsy isteği; Etsy hız sınırı 5/sn).
    """
    from matbaa import isimli
    from matbaa.ilan import gorsel

    sayac = {"tamam": 0, "hata": 0}
    for r in c.execute(
        """SELECT u.tasarim_id, u.urun, u.etsy_listing_id, t.dosyalar, t.fontlar, i.nis FROM urun u
           JOIN tasarim t ON t.id = u.tasarim_id JOIN ifade i ON i.id = t.ifade_id
           WHERE u.durum = 'aktif' AND u.etsy_listing_id IS NOT NULL AND NOT EXISTS (
             SELECT 1 FROM olay o WHERE o.varlik = 'urun' AND o.varlik_id = u.tasarim_id AND o.yeni = u.urun || ':gorsel')
           ORDER BY u.guncelleme LIMIT ?""",
        (sinir,),
    ).fetchall():
        ham = json.loads(r["dosyalar"])
        dos = {k: KOK / v for k, v in ham.items() if k.endswith("_png")}
        if r["urun"] == "kupa":
            dos["kupa_png"] = KOK / Path(ham["koyu_png"]).parent / "kupa.png"
        if r["urun"] == "susleme":
            y = susleme_dosyalari(ham, json.loads(r["fontlar"] or "[]"), r["nis"])
            dos["susleme_on_png"], dos["susleme_arka_png"] = y["on"], y["arka"]
        if r["urun"] == isimli.URUN:
            dos["isimli_ornekler"] = isimli.ornekler(ham)
        try:
            s = gorsel.ilana_ekle(etsy, int(r["etsy_listing_id"]), r["urun"], dos, tohum=r["tasarim_id"])
        except Exception as e:  # görsel eklenemezse ilan yine satışta; ertesi koşu yeniden dener
            sayac["hata"] += 1
            yazdir(f"  görsel hata {r['tasarim_id']}/{r['urun']}: {type(e).__name__}: {str(e)[:150]}")
            continue
        db.olay(c, "urun", r["tasarim_id"], None, f"{r['urun']}:gorsel", f"vitrin={s['vitrin']} eklenen={s['eklenen']}")
        c.commit()
        sayac["tamam"] += 1
    return sayac


def oznitelikleri_esitle(c, etsy, sinir: int = 30, gun=None, yazdir=print) -> dict:
    """Aktif ilanların Etsy özniteliklerini istenene çeker (`ilan/oznitelik.py`); yalnız istenen değiştiyse Etsy'ye gidilir.

    Son yazılan istek `olay`da ("<ürün>:oznitelik", açıklama = JSON) durur: mevsim dönünce (Christmas → yok) ilan yeniden
    yazılır, artık istenmeyen özellik silinir. `sinir`: bir koşuda en çok ilan (ilan başına ~6 Etsy isteği)."""
    from matbaa.ilan import oznitelik

    sayac = {"yazilan": 0, "hata": 0}
    for r in c.execute(
        """SELECT u.tasarim_id, u.urun, u.etsy_listing_id, i.satirlar, i.nis, il.baslik FROM urun u
           JOIN tasarim t ON t.id = u.tasarim_id JOIN ifade i ON i.id = t.ifade_id
           LEFT JOIN ilan il ON il.tasarim_id = u.tasarim_id AND il.urun = u.urun
           WHERE u.durum = 'aktif' AND u.etsy_listing_id IS NOT NULL ORDER BY u.tasarim_id, u.urun"""
    ).fetchall():
        istek = oznitelik.istenen(r["urun"], r["nis"], json.loads(r["satirlar"]), r["baslik"] or "", gun)
        imza = json.dumps(istek, sort_keys=True, ensure_ascii=False)
        onceki = c.execute(
            "SELECT aciklama FROM olay WHERE varlik = 'urun' AND varlik_id = ? AND yeni = ? ORDER BY id DESC LIMIT 1",
            (r["tasarim_id"], f"{r['urun']}:oznitelik"),
        ).fetchone()
        if onceki and onceki[0] == imza:
            continue
        if sayac["yazilan"] + sayac["hata"] >= sinir:
            sayac["kalan"] = sayac.get("kalan", 0) + 1
            continue
        lid = int(r["etsy_listing_id"])
        try:
            ozellikler = etsy.taksonomi_ozellikleri(int(etsy.ilan(lid)["taxonomy_id"]))
            hedef, atlanan = oznitelik.cozumle(istek, ozellikler)
            if onceki:  # artık istenmeyen (mevsimi geçen tatil gibi) özellik silinir
                eski, _ = oznitelik.cozumle(json.loads(onceki[0]), ozellikler)
                for pid in eski.keys() - hedef.keys():
                    etsy.ozellik_sil(lid, pid)
            for pid, (ids, adlar) in hedef.items():
                etsy.ozellik_yaz(lid, pid, ids, adlar)
        except Exception as e:  # öznitelik yazılamazsa ilan yine satışta; ertesi koşu yeniden dener
            sayac["hata"] += 1
            yazdir(f"  öznitelik hata {r['tasarim_id']}/{r['urun']}: {type(e).__name__}: {str(e)[:150]}")
            continue
        if atlanan:
            yazdir(f"  öznitelik {r['tasarim_id']}/{r['urun']}: kategoride yok, atlandı {atlanan}")
        db.olay(c, "urun", r["tasarim_id"], None, f"{r['urun']}:oznitelik", imza)
        c.commit()
        sayac["yazilan"] += 1
    return sayac


YALNIZ_YENILEME = "-"  # "<ürün>:vitrin" olayında: otomatik yenileme açıldı, bölüm henüz atanamadı


def vitrin_esitle(c, etsy, sinir: int = 30, yazdir=print) -> dict:
    """Aktif ilanın otomatik yenilemesini açar ve ilanı niş bölümüne (Shop section, `config/nisler.toml` `vitrin_bolumu`) koyar.

    Printify ikisini de boş bırakıyor (2026-10-14 canlı: bölüm yok, `should_auto_renew` false). Yenileme kapalıyken ilan 4 ayda
    sona erer ve mağaza sessizce boşalır; yenileme ücreti ($0,20) tavanlar.toml'da zaten hesap dışı varsayılmıştı. Bölüm açmak
    `shops_w` yetkisi ister (2026-10-14 token'ında yok, 403): o zaman yalnız yenileme yazılır, bölüm yetki gelince ya da bölüm
    Etsy'de elle açılınca atanır. Olay "<ürün>:vitrin", açıklama = atanan bölüm (ya da `YALNIZ_YENILEME`)."""
    from matbaa.entegrasyon.http import ApiHatasi
    from matbaa.ifade.uret import nisler

    sayac: dict = {"yazilan": 0, "hata": 0}
    acilamayan: set[str] = set()  # bu koşuda açılamayan bölümler (aynı 403 her ilanda yinelenmez)
    for r in c.execute(
        """SELECT u.tasarim_id, u.urun, u.etsy_listing_id, i.nis FROM urun u
           JOIN tasarim t ON t.id = u.tasarim_id JOIN ifade i ON i.id = t.ifade_id
           WHERE u.durum = 'aktif' AND u.etsy_listing_id IS NOT NULL ORDER BY u.tasarim_id, u.urun"""
    ).fetchall():
        bolum = nisler().get(r["nis"], {}).get("vitrin_bolumu") or r["nis"].replace("_", " ").title()
        onceki = c.execute(
            "SELECT aciklama FROM olay WHERE varlik = 'urun' AND varlik_id = ? AND yeni = ? ORDER BY id DESC LIMIT 1",
            (r["tasarim_id"], f"{r['urun']}:vitrin"),
        ).fetchone()
        if onceki and (onceki[0] == bolum or (onceki[0] == YALNIZ_YENILEME and bolum in acilamayan)):
            continue
        if sayac["yazilan"] + sayac["hata"] >= sinir:
            sayac["kalan"] = sayac.get("kalan", 0) + 1
            continue
        try:
            bolum_id = None
            if bolum not in acilamayan:
                try:
                    bolum_id = etsy.bolum_kimligi(bolum)
                except ApiHatasi as e:
                    if e.durum != 403:
                        raise
                    acilamayan.add(bolum)
                    sayac["bolum_yok"] = "Etsy token'ında shops_w yok: `uv run python scripts/etsy_yetki.py` ile yeniden yetki"
                    yazdir(f"  vitrin: '{bolum}' bölümü açılamadı, {sayac['bolum_yok']}")
            if bolum_id is None and onceki:
                continue  # yenileme zaten açık, bölüm hâlâ açılamıyor
            etsy.ilan_guncelle(
                int(r["etsy_listing_id"]),
                should_auto_renew="true",
                **({"shop_section_id": bolum_id} if bolum_id else {}),
            )
        except Exception as e:  # ilan yine satışta; ertesi koşu yeniden dener
            sayac["hata"] += 1
            yazdir(f"  vitrin hata {r['tasarim_id']}/{r['urun']}: {type(e).__name__}: {str(e)[:150]}")
            continue
        db.olay(c, "urun", r["tasarim_id"], None, f"{r['urun']}:vitrin", bolum if bolum_id else YALNIZ_YENILEME)
        c.commit()
        sayac["yazilan"] += 1
    return sayac


def etsy_eksik() -> list[str]:
    """Yayından önce Etsy'de kurulu olması gerekenler. Biri eksikken Printify'ın açtığı ilan üretim ortağısız ve Printify'ın
    ücretli kargo profiliyle kalır; K-23 fiyatı kargoyu içerdiği için alıcı kargoyu iki kez öder."""
    e = ayar()["etsy"]
    if (
        elle_mod()
    ):  # K-27: üretim ortağını Printify kendisi bağlar (Etsy'de "Printify" adlı ortak var), kargo profili Etsy'de elle kurulur
        return [] if e.get("elle_kargo_hazir") else ["elle_kargo_hazir"]
    return [k for k in ("uretim_ortagi_id", "kargo_profili_id") if not e.get(k)]


def elle_mod() -> bool:
    return ayar()["etsy"].get("mod", "api") == "elle"


def yayinla(c, p: pf.Printify, yazdir=print, etsy=None) -> dict:
    """`etsy`: isimli süs (kanal "etsy", Faz 11) ilanı doğrudan Etsy'de açılır; istemci yoksa o ürün bekler."""
    from matbaa import isimli

    if eksik := etsy_eksik():
        yazdir(f"  Etsy hazır değil ({', '.join(eksik)} boş): yayın bekletildi")
        return {"bekliyor": f"Etsy hazır değil: {', '.join(eksik)}", "tasarim": 0, "urun": 0, "hata": 0}
    sayac = {"sinir": gunluk_sinir(c), "bugun_onceki": bugun_yayinlanan(c), "tasarim": 0, "urun": 0, "hata": 0}
    kalan = sayac["sinir"] - sayac["bugun_onceki"]
    if kalan <= 0:  # yeni tasarım yok; yayındaki tasarımlara sonradan eklenen ürün (süs) yine açılır
        yazdir(f"  günlük sınır doldu ({sayac['sinir']} tasarım, mağaza yaşı {magaza_yasi(c)} gün)")
    katalog, ycfg = urunler(), ayar()["printify"]
    # Koşullu ürün (kupa, süs) ve ayrı türden ürün (çizimli, K-37) yalnız bekleyen satırı varsa eşleme ister: eşlenmemiş
    # kupa tişört yayınını durdurmasın.
    bekleyen = {r[0] for r in c.execute("SELECT DISTINCT urun FROM urun WHERE durum IN ('bekliyor', 'olusturuldu', 'hata')")}
    eksik = [
        u
        for u in katalog
        if not ycfg.get(u, {}).get("blueprint_id")
        and (not (katalog[u].get("yalniz_satan") or katalog[u].get("kosul") or katalog[u].get("tur")) or u in bekleyen)
    ]
    if eksik:
        raise RuntimeError(f"Printify kataloğu eşlenmemiş: {eksik} → `uv run matbaa printify-kesif`, sonra config/yayin.toml")
    varyant_onbellek: dict[str, dict] = {}
    gorsel_onbellek: dict = {}
    # Yalnız yayın bekleyen ürünü olan tasarımlar günlük sınırdan pay alır: Etsy eşlemesini bekleyen tasarım yer tutmaz.
    # Mevsim dışı ürün (süs, K-30) yayın bekleyen sayılmaz. Mevsimlik ürünü olan onaylı tasarım sırada öne geçer (Q4'te süs
    # talebi tişörtün 2-4 katı). Zaten yayında olan tasarıma sonradan eklenen ürün (süs) tasarım sınırından değil, ayrı
    # `EK_URUN_GUNLUK` sınırından pay alır: yeni tasarım akışını durdurmaz.
    mevsimlik = json.dumps([u for u, p_ in katalog.items() if p_.get("kosul")])
    izinli = set(ayar().get("yayin_nisleri") or [])  # K-37: boş değilse yalnız bu nişlerin tasarımları (ve ek ürünleri)
    adaylar = [
        (t, b)
        for t in c.execute(
            """SELECT t.id, t.dosyalar, t.durum, t.fontlar, i.nis FROM tasarim t JOIN ifade i ON i.id = t.ifade_id
               WHERE t.durum IN ('onaylandi', 'yayinda')
               ORDER BY t.durum = 'onaylandi', EXISTS (SELECT 1 FROM urun u WHERE u.tasarim_id = t.id
                 AND u.urun IN (SELECT value FROM json_each(?))) DESC, t.durum_zamani""",
            (mevsimlik,),
        ).fetchall()
        if (not izinli or t["nis"] in izinli) and (b := [(u, a) for u, a in _yayin_bekleyen(c, t["id"]) if mevsimde(u)])
    ]
    yeni = [x for x in adaylar if x[0]["durum"] == "onaylandi"][: max(kalan, 0)]
    ek = [x for x in adaylar if x[0]["durum"] == "yayinda"][:EK_URUN_GUNLUK]
    for t, bekleyen in ek + yeni:
        dosyalar = json.loads(t["dosyalar"])
        for urun, adim in bekleyen:
            if isimli.etsy_kanali(urun) and etsy is None:
                continue
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
                    c.commit()  # yazma kilidi Printify çağrıları boyunca tutulmasın (panel aynı anda onay yazabilir)
                if isimli.etsy_kanali(urun):
                    isimli.ilan_ac(c, etsy, p, t, il, yazdir)
                    sayac["urun"] += 1
                    c.commit()
                    continue
                if adim == "bekliyor":
                    bp, sg = ycfg[urun]["blueprint_id"], ycfg[urun]["saglayici_id"]
                    anahtar = k.get("beden_anahtari", "size")
                    if urun not in varyant_onbellek:
                        varyant_onbellek[urun] = pf.varyant_sec(p.varyantlar(bp, sg), k["renkler"], k["bedenler"], anahtar)
                    # Fiyat yayın anındaki katalogdan (config/urunler.toml): metin yazıldıktan sonra değişen fiyat eski kalmasın.
                    govde = pf.urun_govdesi(
                        il["baslik"], il["aciklama"], json.loads(il["etiketler"]), bp, sg,
                        varyant_onbellek[urun], _gorseller(p, t["id"], dosyalar, gorsel_onbellek, urun, t), k["fiyat"],
                        k.get("buyuk_beden_ek", {}), anahtar,
                    )  # fmt: skip
                    urun_id = p.urun_olustur(govde)["id"]
                    c.execute(
                        "UPDATE ilan SET fiyat = ?, kargo = ? WHERE tasarim_id = ? AND urun = ?",
                        (k["fiyat"], k["kargo"], t["id"], urun),
                    )
                    # Kimlik yayından önce kaydedilir: yayın düşerse sonraki koşu aynı ürünü yayınlar, ikincisini açmaz.
                    db.urun_gecis(c, t["id"], urun, "olusturuldu", "Printify ürünü oluşturuldu", printify_id=urun_id)
                    c.commit()
                else:
                    urun_id = c.execute(
                        "SELECT printify_id FROM urun WHERE tasarim_id = ? AND urun = ?", (t["id"], urun)
                    ).fetchone()[0]
                # Kargo şablonu açık: Printify, Publishing preferences'ta seçili "Free US shipping" profilini atar (K-27 testi:
                # şablon kapalıyken de kendi ücretli profillerini bağladı, ilk 3 ilan elle düzeltildi).
                p.yayinla(urun_id)
                db.urun_gecis(c, t["id"], urun, "printify", "Etsy'ye yayın istendi")
                sayac["urun"] += 1
            except Exception as e:  # ürün başına izole: biri düşerse diğerleri sürer
                db.urun_gecis(c, t["id"], urun, "hata", f"{type(e).__name__}: {e}"[:500])
                sayac["hata"] += 1
                yazdir(f"  hata {t['id']}/{urun}: {e}")
            c.commit()
        tur = "ek_urun" if t["durum"] == "yayinda" else "tasarim"
        sayac[tur] = sayac.get(tur, 0) + 1
    return sayac


def _etsy_kimligi(urun: dict) -> str | None:
    dis = urun.get("external")
    if isinstance(dis, list):
        dis = dis[0] if dis else None
    return str(dis["id"]) if isinstance(dis, dict) and dis.get("id") else None


ETSY_DENEME_MAKS = 3  # Etsy adımı bu kadar kez düşerse ürün "elle bakılmalı"ya alınır (alarm), her gün sessizce yinelenmez
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


def elle_denetle(c, p: pf.Printify, yazdir=print) -> dict:
    """Elle mod (K-27): Etsy'ye düşen ilanı kaydeder ve kargo profilini denetler; API'siz yolun günlük gözü.

    Printify'ın bildirdiği profil "Free US shipping" (`kargo_profili_id`) değilse alarm: alıcı fiyata dahil kargoyu bir daha öder.
    Alarm bir kez verilir, ürün yine `aktif`e geçer (Etsy'de elle düzeltilen profil Printify'a geri yansımıyor, alarm tekrar etmesin).
    """
    beklenen = str(ayar()["etsy"].get("kargo_profili_id") or "")
    sayac: dict = {"etsy": 0, "bekleyen": 0, "alarm": []}
    for r in c.execute(
        "SELECT tasarim_id, urun, printify_id, durum, guncelleme FROM urun WHERE durum IN ('printify', 'etsy_taslak')"
    ).fetchall():
        try:
            u = p.urun(r["printify_id"])
        except Exception as e:  # tek ürünün okunamaması diğerlerinin denetimini durdurmaz; ertesi koşu yeniden bakar
            sayac["hata"] = sayac.get("hata", 0) + 1
            yazdir(f"  printify okuma hata {r['tasarim_id']}/{r['urun']}: {type(e).__name__}: {str(e)[:150]}")
            continue
        listing = _etsy_kimligi(u)
        if not listing:
            if not _yayin_asimi(c, r):
                sayac["bekleyen"] += 1
            c.commit()
            continue
        if r["durum"] == "printify":
            db.urun_gecis(c, r["tasarim_id"], r["urun"], "etsy_taslak", "Etsy ilanı oluştu (elle mod)", etsy_listing_id=listing)
        dis = u.get("external")
        dis = dis[0] if isinstance(dis, list) and dis else dis
        profil = str((dis or {}).get("shipping_template_id") or "")
        not_ = "kargo profili doğru"
        if beklenen and profil != beklenen:
            not_ = f"kargo profili {profil}, beklenen {beklenen}: Etsy'de elle düzeltilmeli"
            sayac["alarm"].append(
                f"{r['tasarim_id']}/{r['urun']} Etsy ilanı {listing} ücretsiz kargoda değil: Shop Manager → Listings → Change shipping profiles"
            )
        db.urun_gecis(c, r["tasarim_id"], r["urun"], "aktif", f"Etsy'de aktif (elle mod), {not_}")
        if c.execute("SELECT durum FROM tasarim WHERE id = ?", (r["tasarim_id"],)).fetchone()[0] == "onaylandi":
            db.gecis(c, r["tasarim_id"], "yayinda")
        sayac["etsy"] += 1
        c.commit()
    for a in sayac["alarm"]:
        yazdir(f"  ALARM {a}")
    return sayac


KARGO_PROFILI = {  # K-23: ABD'ye ücretsiz kargo; üretim 2–5 iş günü (Printify), teslim 3–7 iş günü
    "title": "Free US shipping",
    "origin_country_iso": "US",
    "primary_cost": 0,
    "secondary_cost": 0,
    "destination_country_iso": "US",
    "min_processing_time": 2,
    "max_processing_time": 5,
    "processing_time_unit": "business_days",
    "min_delivery_days": 3,
    "max_delivery_days": 7,
}


def kargo_profili_kur(p: pf.Printify, etsy, yazdir=print) -> int:
    """Etsy'de ücretsiz ABD kargo profilini açar (varsa aynısını kullanır), kimliği config/yayin.toml'a yazar."""
    var = [k for k in etsy.kargo_profilleri() if k.get("title") == KARGO_PROFILI["title"]]
    if var:
        kimlik = int(var[0]["shipping_profile_id"])
    else:
        konum = p.saglayici(ayar()["printify"]["tisort"]["saglayici_id"]).get("location") or {}
        if not konum.get("zip"):
            raise RuntimeError(f"Printify sağlayıcısının posta kodu yok ({konum}): önce printify-kesif ve saglayici_id")
        kimlik = int(etsy.kargo_profili_olustur(**KARGO_PROFILI, origin_postal_code=konum["zip"])["shipping_profile_id"])
    dosya = CONFIG / "yayin.toml"
    t = dosya.read_text(encoding="utf-8")
    t, n = re.subn(r"(?m)^kargo_profili_id = \d+", f"kargo_profili_id = {kimlik}", t)
    if n != 1:
        raise RuntimeError("config/yayin.toml: kargo_profili_id satırı yok")
    dosya.write_text(t, encoding="utf-8")
    ayar.cache_clear()
    yazdir(f"Etsy kargo profili {kimlik} ({KARGO_PROFILI['title']}) → config/yayin.toml")
    return kimlik


def etsy_esle(c, p: pf.Printify, etsy, yazdir=print, hata_dene: bool = True) -> dict:
    """Printify'ın Etsy'ye açtığı ilanı bul → üretim ortağını bağla, AI beyanını doğrula, aktifleştir.

    `hata_dene=False`: yalnız Etsy ilanı beklenenlere bakılır (aynı koşu içindeki tekrar turları hatalı ürünü dakikalar içinde
    `ETSY_DENEME_MAKS`'a taşımasın; hata günde bir kez yeniden denenir)."""
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
        or (
            hata_dene
            and ELLE not in (r["hata"] or "")
            and db.hata_oncesi(c, r["tasarim_id"], r["urun"]) in ("printify", "etsy_taslak")
        )
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
                **({"shipping_profile_id": kp} if (kp := ayar()["etsy"].get("kargo_profili_id")) else {}),
                "production_partner_ids": [ortak],
                "who_made": "i_did",
                "when_made": "made_to_order",
                "is_supply": "false",
                "should_auto_renew": "true",  # Printify kapalı açıyor: 4 ayda ilan sona erer (vitrin_esitle eskileri düzeltir)
            }
            if AI_BEYANI.split(":")[0] not in re.sub(r"<[^>]+>", " ", ilan.get("description", "")):
                alanlar["description"] = c.execute(
                    "SELECT aciklama FROM ilan WHERE tasarim_id = ? AND urun = ?", (r["tasarim_id"], r["urun"])
                ).fetchone()[0]
            alanlar["state"] = "active"
            etsy.ilan_guncelle(int(listing), **alanlar)
            if hp := ayar()["etsy"].get("hazirlama_profili_id"):
                etsy.hazirlama_ayarla(int(listing), hp)
            db.urun_gecis(c, r["tasarim_id"], r["urun"], "aktif", "üretim ortağı bağlandı, AI beyanı doğrulandı, aktif")
            sayac["aktif"] += 1
            if c.execute("SELECT durum FROM tasarim WHERE id = ?", (r["tasarim_id"],)).fetchone()[0] == "onaylandi":
                db.gecis(c, r["tasarim_id"], "yayinda")
        except Exception as e:
            onceki = c.execute(
                "SELECT count(*) FROM olay WHERE varlik = 'urun' AND varlik_id = ? AND yeni = ? AND aciklama LIKE 'etsy:%'",
                (r["tasarim_id"], f"{r['urun']}:hata"),
            ).fetchone()[0]
            ek = f" ({onceki + 1}. deneme, Etsy panelinde {ELLE})" if onceki + 1 >= ETSY_DENEME_MAKS else ""
            neden = f"etsy: {type(e).__name__}: {e}"[: 500 - len(ek)] + ek
            db.urun_gecis(c, r["tasarim_id"], r["urun"], "hata", neden)
            sayac["hata"] += 1
            yazdir(f"  etsy hata {r['tasarim_id']}/{r['urun']}: {e}")
        c.commit()
    return sayac
