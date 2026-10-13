"""Hattın adımları. Her adım veritabanındaki durumdan okur, sonucunu durum makinesine yazar; yarıda kalırsa yeniden çalıştırmak güvenlidir.

uv run matbaa uret --nis fishing --adet 12    # ifade üret → IP kapısı → tasarım → kalite
uv run matbaa durum                           # kuyruk özeti
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from matbaa import db, tavan
from matbaa.ayar import KOK
from matbaa.fiyat import urunler
from matbaa.ifade import uret as ifade_uret
from matbaa.ilan import metin as ilan_metin
from matbaa.ip import kapi, marka
from matbaa.tasarim import render, sec

URETIM = KOK / "uretim"
METIN_DENEME = 3
KAPI_HATA_MAKS = 3


def _kacinilacak(c, nis: str) -> list[str]:
    satirlar = c.execute("SELECT satirlar FROM ifade WHERE nis = ? ORDER BY id DESC LIMIT 120", (nis,)).fetchall()
    return [" / ".join(json.loads(r[0])) for r in satirlar]


def _son_ciftler(c) -> list[tuple[str, str]]:
    r = c.execute(
        "SELECT sablon, fontlar FROM tasarim WHERE durum != 'ret' ORDER BY id DESC LIMIT ?",
        (max(sec.CESITLILIK_PENCERE, sec.SABLON_PENCERE),),
    ).fetchall()
    return [(s, sec.ana_font(s, json.loads(f))) for s, f in reversed(r)]


def _dosyalari_yaz(c, t: int, secim) -> None:
    klasor = URETIM / f"{t:05d}"
    klasor.mkdir(parents=True, exist_ok=True)
    dosyalar = {}
    vurgu = sec.PALETLER[secim.palet]
    for etiket, img, murekkep, v in (
        ("koyu", secim.koyu, sec.KOYU_MUREKKEP, vurgu[0] if vurgu else None),
        ("acik", secim.acik, sec.ACIK_MUREKKEP, vurgu[1] if vurgu else None),
    ):
        (klasor / f"{etiket}.svg").write_text(secim.cizim.svg(murekkep, v), encoding="utf-8")
        dosyalar[f"{etiket}_png"] = str(render.kaydet(img, klasor / f"{etiket}.png").relative_to(KOK))
        dosyalar[f"{etiket}_svg"] = str((klasor / f"{etiket}.svg").relative_to(KOK))
    c.execute(
        "UPDATE tasarim SET dosyalar = ?, kalite = ?, sablon = ?, fontlar = ? WHERE id = ?",
        (json.dumps(dosyalar), json.dumps(secim.kalite), secim.sablon, json.dumps(secim.fontlar), t),
    )


def _yapi(satir) -> dict:
    """İfadenin üst/ana/alt yapısı; eski kayıtlarda yoksa satırlardan kestirilir (küçük harfli son satır = alt)."""
    y = json.loads(satir["yapi"] or "{}")
    if y.get("ana"):
        return y
    s = json.loads(satir["satirlar"])
    alt = s[-1] if len(s) > 2 and s[-1] != s[-1].upper() else ""
    govde = [x for x in s if x != alt] if alt else s
    ust = ""
    if len(govde) > 3 or (len(govde) > 1 and govde[0] != govde[0].upper() and all(x == x.upper() for x in govde[1:])):
        ust, govde = govde[0], govde[1:]  # "Papa's Rules / 1. CAST / 2. WAIT / 3. REPEAT": ilk satır başlık
    return {"ust": ust, "ana": govde, "alt": alt}


def yeniden_ciz(c=None, yazdir=print) -> dict:
    """Onaylanmamış tasarımları güncel motorla yeniden çizer (palet, yerleşim iyileşince). Onaylı/yayındakine dokunmaz."""
    c = c or db.baglan()
    sayac = {"cizildi": 0, "ret": 0}
    # Çeşitlilik penceresi yeniden çizim sırasına göre yürür: veritabanındaki eski şablonlar zaten değişecek.
    son: list[tuple[str, str]] = []
    for r in c.execute(
        """SELECT t.id, t.ifade_id, i.yapi, i.satirlar, i.nis FROM tasarim t JOIN ifade i ON i.id = t.ifade_id
           WHERE t.durum IN ('kalite_ok', 'metin_ok', 'onay_bekliyor') ORDER BY t.id"""
    ).fetchall():
        y = _yapi(r)
        secim, nedenler = sec.sec(y["ust"], y["ana"], y["alt"], son, tohum=r["ifade_id"], nis=r["nis"])
        if secim is None:
            db.gecis(c, r["id"], "ret", f"yeniden çizim kapılardan geçmedi: {nedenler[-1][:200] if nedenler else ''}")
            sayac["ret"] += 1
        else:
            _dosyalari_yaz(c, r["id"], secim)
            son.append((secim.sablon, sec.ana_font(secim.sablon, secim.fontlar)))
            db.olay(c, "tasarim", r["id"], None, "yeniden_cizildi", f"{secim.sablon} palet={secim.palet}")
            sayac["cizildi"] += 1
        c.commit()
    return sayac


def uret(nis: str, adet: int, c=None, yazdir=print) -> dict:
    c = c or db.baglan()
    sayac = {"uretilen": 0, "bicim_hatali": 0, "tekrar": 0, "ip_ret": 0, "ip_insan": 0, "kalite_ret": 0, "tasarim": 0}
    from matbaa import performans

    adaylar, hatali = ifade_uret.uret(nis, adet, _kacinilacak(c, nis), satanlar=performans.satanlar(c, nis))
    sayac["uretilen"], sayac["bicim_hatali"] = len(adaylar) + len(hatali), len(hatali)
    ust_uste = 0
    for a in adaylar:
        try:
            tavan.ip_kontrol(c)
        except tavan.TavanAsildi as e:
            sayac["tavan"] = str(e)
            yazdir(f"  {e}")
            break
        ifade_id = db.ifade_ekle(c, nis, a.satirlar, yapi={"ust": a.ust, "ana": list(a.ana), "alt": a.alt})
        if ifade_id is None:
            sayac["tekrar"] += 1
            continue
        try:
            k = kapi.denetle(a.satirlar, nis, ana=list(a.ana))
        except Exception as e:  # TypeSafe/ağ hatası: ifade kapısız kalır (tasarıma giremez), birkaç kez üst üste olursa dur
            c.commit()
            sayac["kapi_hata"] = sayac.get("kapi_hata", 0) + 1
            ust_uste += 1
            yazdir(f"  IP kapısı hata: {type(e).__name__}: {str(e)[:150]}")
            if ust_uste >= KAPI_HATA_MAKS:
                raise RuntimeError(f"IP kapısı {KAPI_HATA_MAKS} kez üst üste düştü: {type(e).__name__}: {e}") from e
            continue
        ust_uste = 0
        db.kapi_yaz(c, ifade_id, k.karar, k.nedenler, k.kayit)
        c.commit()
        if k.karar == "ret":
            sayac["ip_ret"] += 1
            yazdir(f"  IP ret: {' / '.join(a.satirlar)} — {'; '.join(k.nedenler)[:120]}")
            continue
        if k.karar == "insan":  # K-13: tasarıma girer, panelde işaretli; karar Scryne'ın onayında
            sayac["ip_insan"] += 1
            yazdir(f"  IP insan (panelde işaretli): {' / '.join(a.satirlar)} — {'; '.join(k.nedenler)[:120]}")
        secim, nedenler = sec.sec(a.ust, list(a.ana), a.alt, _son_ciftler(c), tohum=ifade_id, nis=nis)
        if secim is None:
            sayac["kalite_ret"] += 1
            yazdir(f"  kalite ret: {' / '.join(a.satirlar)} — {nedenler[-1][:120] if nedenler else ''}")
            continue
        t = db.tasarim_ekle(c, ifade_id, secim.sablon, secim.fontlar)
        _dosyalari_yaz(c, t, secim)
        db.gecis(c, t, "kalite_ok", f"{secim.sablon} {secim.fontlar} palet={secim.palet}")
        c.commit()
        sayac["tasarim"] += 1
        yazdir(f"  tasarım {t}: {' / '.join(a.satirlar)} [{secim.sablon}, {secim.fontlar[0]}]")
    return sayac


def _etiket_suz(etiketler: list[str]) -> tuple[list[str], list[str]]:
    """İlan etiketleri de canlı markaya çarpmasın ("reel cool dad"): marka kontrolünden geçmeyen etiket atılır."""
    d = marka.dizin()
    temiz, atilan = [], []
    for t in etiketler:
        (temiz if d.kontrol(t).temiz else atilan).append(t)
    return temiz, atilan


def _ilan_yaz(satirlar: list[str], nis: str, urun: str) -> ilan_metin.Ilan:
    son = None
    for _ in range(2):
        i = ilan_metin.olustur(satirlar, nis, urun)
        i.etiketler, atilan = _etiket_suz(i.etiketler)
        if len(i.etiketler) < 13:  # niş kartının yedek etiketleriyle tamamla (onlar da marka süzgecinden geçer)
            yedek, _ = _etiket_suz([t for t in ifade_uret.nisler()[nis].get("yedek_etiketler", []) if t not in i.etiketler])
            i.etiketler += yedek[: 13 - len(i.etiketler)]
        i.etiketler = i.etiketler[:13]
        i.sorunlar = [x for x in i.sorunlar if "geçerli etiket" not in x]
        if atilan:
            i.sorunlar.append(f"markaya çarpan etiket atıldı: {atilan}")
        if len(i.etiketler) < 13:
            i.sorunlar.append(f"{len(i.etiketler)} etiket kaldı")
        if not [s for s in i.sorunlar if not s.startswith("markaya çarpan")]:
            return i
        son = i
    return son


def metin(c=None, sinir: int = 50, yazdir=print) -> dict:
    """kalite_ok tasarımlar → her ürün için ilan metni → onay kuyruğu."""
    c = c or db.baglan()
    sayac = {"tasarim": 0, "ilan": 0, "ret": 0}
    urun_adlari = list(urunler())
    satirlar = c.execute(
        "SELECT t.id, i.satirlar, i.nis FROM tasarim t JOIN ifade i ON i.id = t.ifade_id WHERE t.durum = 'kalite_ok' ORDER BY t.id LIMIT ?",
        (sinir,),
    ).fetchall()
    for t_id, sat, nis in satirlar:
        s = json.loads(sat)
        with ThreadPoolExecutor(len(urun_adlari)) as havuz:
            ilanlar = dict(zip(urun_adlari, havuz.map(lambda u, s=s, nis=nis: _ilan_yaz(s, nis, u), urun_adlari), strict=True))
        sorunlu = {u: i.sorunlar for u, i in ilanlar.items() if [x for x in i.sorunlar if not x.startswith("markaya çarpan")]}
        if sorunlu:
            # Metin hatası tasarımı öldürmez: kalite_ok'ta kalır, sonraki koşuda yeniden denenir; 3. başarısızlıkta ret.
            db.olay(c, "tasarim", t_id, "kalite_ok", "metin_hata", str(sorunlu)[:500])
            denemeler = c.execute(
                "SELECT count(*) FROM olay WHERE varlik = 'tasarim' AND varlik_id = ? AND yeni = 'metin_hata'", (t_id,)
            ).fetchone()[0]
            if denemeler >= METIN_DENEME:
                db.gecis(c, t_id, "ret", f"ilan metni {denemeler} denemede kurallara uymadı: {sorunlu}")
                sayac["ret"] += 1
            c.commit()
            yazdir(f"  metin hata {t_id} ({denemeler}/{METIN_DENEME}): {sorunlu}")
            continue
        for u, i in ilanlar.items():
            p = urunler()[u]
            c.execute(
                "INSERT OR REPLACE INTO ilan (tasarim_id, urun, baslik, etiketler, aciklama, alt_metin, fiyat, kargo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (t_id, u, i.baslik, json.dumps(i.etiketler), i.aciklama, i.alt_metin, p["fiyat"], p["kargo"]),
            )
            c.execute("INSERT OR IGNORE INTO urun (tasarim_id, urun) VALUES (?, ?)", (t_id, u))
            sayac["ilan"] += 1
        db.gecis(c, t_id, "metin_ok")
        db.gecis(c, t_id, "onay_bekliyor")
        c.commit()
        sayac["tasarim"] += 1
        yazdir(f"  {t_id}: {ilanlar[urun_adlari[0]].baslik[:90]}")
    return sayac


USPTO_YENILEME_GUN = 30  # dosya bu yaştan eskiyse aylık yenileme denenir (K-13)
USPTO_VERI_UYARI_GUN = 45  # verideki en yeni başvuru bu kadar eskiyse kaynak güncellenmiyor olabilir: uyarı
USPTO_VERI_MAKS_GUN = 60  # bundan eskiyse hat durur: bayat marka verisiyle ifade denetlenmez
KUYRUK_TABAN = 20  # onay + yayın bekleyen en az tasarım
KUYRUK_GUN = 14  # kuyruk, günlük yayın sınırının bu kadar gününü karşılasın
SON_KOSU = KOK / "calisma" / "gunluk" / "son.json"


def uspto_tazelik() -> int:
    """Marka dosyasının yaşı (gün): yenileme zamanı buna göre. Dosya yoksa çok büyük döner."""
    import time

    dosya = marka.DOSYA
    return int((time.time() - dosya.stat().st_mtime) / 86400) if dosya.exists() else 10**6


def uspto_veri_yasi() -> int:
    """Verideki en yeni başvurunun yaşı (gün): dosyayı yenilemek kaynağın kendisi bayatsa veriyi tazelemez."""
    from datetime import date

    son = marka.veri_tarihi()
    return (date.today() - son).days if son else 10**6


def _adim(rapor: dict, ad: str, is_, yazdir=print):
    """Bir adımı çalıştırır; hata koşuyu durdurmaz, `rapor["hatalar"]`a yazılır (sonraki adımlar ve haftalık rapor sürer)."""
    try:
        sonuc = is_()
    except Exception as e:
        rapor.setdefault("hatalar", []).append(f"{ad}: {type(e).__name__}: {str(e)[:300]}")
        yazdir(f"  HATA {ad}: {type(e).__name__}: {e}")
        return None
    if sonuc is not None:
        rapor[ad] = sonuc
    return sonuc


def _uspto(yazdir) -> str:
    if uspto_tazelik() > USPTO_YENILEME_GUN:
        yazdir(f"USPTO dosyası {uspto_tazelik()} günlük: aylık yenileme (K-13)")
        import runpy

        try:
            runpy.run_path(str(KOK / "scripts" / "uspto_guncelle.py"), run_name="__main__")
            marka.dizin.cache_clear()
            marka.veri_tarihi.cache_clear()
        except Exception as e:
            yazdir(f"  USPTO yenilenemedi ({type(e).__name__}: {e})")
    yas = uspto_veri_yasi()
    if yas > USPTO_VERI_MAKS_GUN:
        raise RuntimeError(f"USPTO verisi {yas} günlük (en yeni başvuru): ifade üretimi durdu (K-13)")
    if yas > USPTO_VERI_UYARI_GUN:
        return f"UYARI: USPTO verisindeki en yeni başvuru {yas} günlük; kaynak güncellenmiyor olabilir"
    return f"{yas} günlük"


def _etsy_hazir() -> bool:
    import os

    return all(os.environ.get(k) for k in ("ETSY_KEYSTRING", "ETSY_SHARED_SECRET", "ETSY_SHOP_ID"))


def gunluk(nis_sayisi: int = 2, adet: int = 12, yazdir=print) -> dict:
    """Günlük koşu (Windows görevi): marka verisi → kur → üretim → ilan metni → (anahtar varsa) yayın, Etsy eşleme, siparişler
    → haftalık rapor. Her adım ayrı korunur: biri düşerse diğerleri sürer; sonuç `calisma/gunluk/son.json`a yazılır ve
    hata ya da alarm varsa Windows bildirimi çıkar."""
    import os
    import time
    from datetime import UTC, datetime

    from matbaa import bildirim, fiyat, yayin
    from matbaa import rapor as haftalik_rapor
    from matbaa.ayar import env_yukle

    env_yukle()
    bas = time.time()
    rapor: dict = {"basladi": datetime.now(UTC).isoformat(timespec="seconds")}
    yazdir(f"=== Matbaa günlük koşu {rapor['basladi']}")
    uspto_tamam = _adim(rapor, "uspto", lambda: _uspto(yazdir), yazdir) is not None

    def kur():
        try:
            return fiyat.kur_guncelle()
        except Exception as e:  # kur alınamazsa son taze kur ya da config değeri kullanılır: hata değil
            return f"güncellenemedi ({type(e).__name__}); kullanılan {fiyat.try_usd()}"

    _adim(rapor, "kur", kur, yazdir)
    c = db.baglan()
    kuyruk = c.execute(
        "SELECT count(*) FROM tasarim WHERE durum IN ('kalite_ok', 'metin_ok', 'onay_bekliyor', 'onaylandi')"
    ).fetchone()[0]
    hedef = max(KUYRUK_TABAN, yayin.gunluk_sinir(c) * KUYRUK_GUN)
    if kuyruk >= hedef:
        nis_sayisi = 0  # üretim talebe bağlı: kuyruk yayın kapasitesini aşıyorsa Claude kullanımı boşa gitmez
        yazdir(f"kuyruk {kuyruk} ≥ hedef {hedef}: bugün yeni üretim yok")
    elif not uspto_tamam:
        nis_sayisi = 0
        yazdir("marka verisi kullanılamıyor: bugün yeni üretim yok")
    # Faz 13: niş sırası mağaza verisinden (ilan başına satış/favori/görüntülenme + keşif payı); veri azken kuyrukta en az
    # tasarımı olan niş önce (dengeli büyüme).
    sayim = dict(
        c.execute(
            """SELECT i.nis, count(*) FROM tasarim t JOIN ifade i ON i.id = t.ifade_id
               WHERE t.durum IN ('kalite_ok', 'metin_ok', 'onay_bekliyor', 'onaylandi') GROUP BY i.nis"""
        ).fetchall()
    )
    from matbaa import performans

    for n in performans.uretim_sirasi(c, list(ifade_uret.nisler()), sayim)[:nis_sayisi]:
        yazdir(f"== {n}")
        _adim(rapor, f"uret_{n}", lambda n=n: uret(n, adet, c, yazdir), yazdir)
    _adim(rapor, "metin", lambda: metin(c, yazdir=yazdir), yazdir)
    alarmlar: list[str] = []
    if os.environ.get("PRINTIFY_TOKEN") and os.environ.get("PRINTIFY_SHOP_ID"):
        from matbaa.entegrasyon.printify import Printify

        p = Printify()
        _adim(
            rapor, "yayin", lambda: yayin.yayinla(c, p, yazdir), yazdir
        )  # tavanda durmak beklenen davranış: alarm değil, kayıtta
        if _etsy_hazir():
            from matbaa import siparis
            from matbaa.entegrasyon.etsy import Etsy

            e = Etsy()
            _adim(rapor, "etsy", lambda: yayin.etsy_esle(c, p, e, yazdir), yazdir)
            # Görüntülenme her gün: Faz 13 sıralaması ve haftalık rapor farkı bu anlık görüntülerden
            _adim(rapor, "goruntu", lambda: haftalik_rapor.goruntu_al(c, e, datetime.now(UTC)), yazdir)
            s = _adim(rapor, "siparis", lambda: siparis.izle(c, e, p, yazdir=yazdir), yazdir)
            alarmlar += (s or {}).get("alarm", [])
            rapor["kar_30g"] = siparis.ozet(c)
        elif yayin.elle_mod():
            e = _adim(rapor, "etsy_elle", lambda: yayin.elle_denetle(c, p, yazdir), yazdir)
            alarmlar += (e or {}).get("alarm", [])
            from matbaa import siparis

            s = _adim(rapor, "siparis", lambda: siparis.izle_printify(c, p, yazdir=yazdir), yazdir)
            alarmlar += (s or {}).get("alarm", [])
            rapor["kar_30g"] = siparis.ozet(c)
        else:
            rapor["etsy"] = "Etsy anahtarları eksik (ETSY_KEYSTRING / ETSY_SHARED_SECRET / ETSY_SHOP_ID): eşleme atlandı"
    else:
        rapor["yayin"] = "Printify anahtarı yok (Faz 0): yayın atlandı"
    elle = c.execute("SELECT count(*) FROM urun WHERE durum = 'hata' AND hata LIKE ?", (f"%{yayin.ELLE}%",)).fetchone()[0]
    if elle:
        alarmlar.append(f"{elle} ürün yayında takıldı, Printify panelinde elle bakılmalı")
    if isinstance(rapor.get("uspto"), str) and rapor["uspto"].startswith("UYARI"):
        alarmlar.append(rapor["uspto"])
    rapor["durum"] = durum(c)
    if not haftalik_rapor.bu_hafta_var_mi():

        def haftalik():
            from matbaa.entegrasyon.etsy import Etsy

            return haftalik_rapor.yaz(*haftalik_rapor.haftalik(c, Etsy() if _etsy_hazir() else None))

        if _adim(rapor, "haftalik_rapor", haftalik, yazdir):
            yazdir(f"haftalık rapor: {rapor['haftalik_rapor']}")
    rapor["alarmlar"] = alarmlar
    rapor["sure_sn"] = round(time.time() - bas)
    SON_KOSU.parent.mkdir(parents=True, exist_ok=True)
    SON_KOSU.write_text(json.dumps(rapor, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    sorun = rapor.get("hatalar", []) + alarmlar
    if sorun:
        bildirim.goster(
            f"Matbaa: {len(rapor.get('hatalar', []))} hata, {len(alarmlar)} alarm", " · ".join(sorun)[:240], yazdir=yazdir
        )
    return rapor


def durum(c=None) -> dict:
    c = c or db.baglan()
    return dict(c.execute("SELECT durum, count(*) FROM tasarim GROUP BY durum").fetchall()) | {
        "ifade_" + (k or "bekliyor"): n
        for k, n in c.execute("SELECT kapi_karar, count(*) FROM ifade GROUP BY kapi_karar").fetchall()
    }


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="matbaa")
    alt = p.add_subparsers(dest="komut", required=True)
    u = alt.add_parser("uret", help="ifade üret → IP kapısı → tasarım → kalite")
    u.add_argument("--nis", required=True, choices=sorted(ifade_uret.nisler()))
    u.add_argument("--adet", type=int, default=12)
    m = alt.add_parser("metin", help="kalite_ok tasarımlara ilan metni → onay kuyruğu")
    m.add_argument("--sinir", type=int, default=50)
    alt.add_parser("durum", help="kuyruk özeti")
    oz = alt.add_parser("ozet", help="aylık kâr özeti (sipariş neti − ilan ücreti)")
    oz.add_argument("--ay", help="YYYY-MM (varsayılan bu ay)")
    alt.add_parser("rapor", help="haftalık raporu şimdi üret (calisma/rapor/)")
    g = alt.add_parser("gunluk", help="günlük koşu: üretim → metin → yayın (Windows görevi bunu çağırır)")
    g.add_argument("--nis-sayisi", type=int, default=2)
    g.add_argument("--adet", type=int, default=12)
    alt.add_parser("yeniden-ciz", help="onaylanmamış tasarımları güncel motorla yeniden çiz")
    alt.add_parser("printify-kesif", help="Printify kataloğunda blueprint ve sağlayıcı adayları")
    alt.add_parser("yayinla", help="onaylı tasarımları Printify'a (ısınma eğrisi sınırıyla)")
    alt.add_parser("etsy-esle", help="Printify'ın açtığı Etsy ilanlarına üretim ortağı + aktifleştirme")
    alt.add_parser("etsy-kargo-profili", help="Etsy'de ücretsiz ABD kargo profilini aç, config'e yaz (K-23)")
    pn = alt.add_parser("panel", help="yerel onay paneli (127.0.0.1)")
    pn.add_argument("--port", type=int, default=8766)
    a = p.parse_args(argv)
    if a.komut == "uret":
        print(json.dumps(uret(a.nis, a.adet), ensure_ascii=False))
    elif a.komut == "metin":
        print(json.dumps(metin(sinir=a.sinir), ensure_ascii=False))
    elif a.komut == "gunluk":
        r = gunluk(a.nis_sayisi, a.adet)
        print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
        if r.get("hatalar"):
            sys.exit(1)  # Görev Zamanlayıcı "son sonuç" sütununda görünür
    elif a.komut == "yeniden-ciz":
        print(json.dumps(yeniden_ciz(), ensure_ascii=False))
    elif a.komut in ("printify-kesif", "yayinla", "etsy-esle", "etsy-kargo-profili"):
        import os

        from matbaa import yayin
        from matbaa.ayar import env_yukle
        from matbaa.entegrasyon.printify import Printify

        env_yukle()
        p = Printify()
        if a.komut == "printify-kesif":
            dukkanlar = p.dukkanlar()
            etsy_dukkan = [d for d in dukkanlar if str(d.get("sales_channel", "")).lower() == "etsy"]
            if len(etsy_dukkan) == 1 and not os.environ.get("PRINTIFY_SHOP_ID"):
                from matbaa.ayar import env_yaz

                env_yaz("PRINTIFY_SHOP_ID", str(etsy_dukkan[0]["id"]))
                print(f"PRINTIFY_SHOP_ID={etsy_dukkan[0]['id']} ({etsy_dukkan[0].get('title')}) → .env")
            print(json.dumps({"dukkanlar": dukkanlar, "katalog": yayin.printify_kesif(p)}, ensure_ascii=False, indent=1))
        elif a.komut == "yayinla":
            print(json.dumps(yayin.yayinla(db.baglan(), p), ensure_ascii=False))
        else:
            from matbaa.entegrasyon.etsy import Etsy

            if a.komut == "etsy-kargo-profili":
                yayin.kargo_profili_kur(p, Etsy())
            else:
                print(json.dumps(yayin.etsy_esle(db.baglan(), p, Etsy()), ensure_ascii=False))
    elif a.komut == "panel":
        from matbaa.panel.app import calistir

        print(f"Onay paneli: http://127.0.0.1:{a.port}")
        calistir(a.port)
    elif a.komut == "ozet":
        from matbaa import siparis

        print(json.dumps(siparis.aylik(db.baglan(), a.ay), ensure_ascii=False, indent=1))
    elif a.komut == "rapor":
        import os

        from matbaa import rapor as haftalik_rapor
        from matbaa.ayar import env_yukle

        env_yukle()
        e = None
        if os.environ.get("ETSY_KEYSTRING") and os.environ.get("ETSY_SHOP_ID"):
            from matbaa.entegrasyon.etsy import Etsy

            e = Etsy()
        veri, rapor_metni = haftalik_rapor.haftalik(db.baglan(), e)
        print(rapor_metni)
        print(f"→ {haftalik_rapor.yaz(veri, rapor_metni)}")
    elif a.komut == "durum":
        print(json.dumps(durum(), ensure_ascii=False, indent=1))
