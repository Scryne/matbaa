"""Hattın adımları. Her adım veritabanındaki durumdan okur, sonucunu durum makinesine yazar; yarıda kalırsa yeniden çalıştırmak güvenlidir.

uv run matbaa uret --nis fishing --adet 12    # ifade üret → IP kapısı → tasarım → kalite
uv run matbaa durum                           # kuyruk özeti
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from matbaa import db
from matbaa.ayar import KOK
from matbaa.fiyat import urunler
from matbaa.ifade import uret as ifade_uret
from matbaa.ilan import metin as ilan_metin
from matbaa.ip import kapi, marka
from matbaa.tasarim import render, sec

URETIM = KOK / "uretim"
METIN_DENEME = 3


def _kacinilacak(c, nis: str) -> list[str]:
    satirlar = c.execute("SELECT satirlar FROM ifade WHERE nis = ? ORDER BY id DESC LIMIT 120", (nis,)).fetchall()
    return [" / ".join(json.loads(r[0])) for r in satirlar]


def _son_ciftler(c) -> list[tuple[str, str]]:
    r = c.execute(
        "SELECT sablon, fontlar FROM tasarim WHERE durum != 'ret' ORDER BY id DESC LIMIT ?", (sec.CESITLILIK_PENCERE,)
    ).fetchall()
    return [(s, json.loads(f)[0 if s == "yigin" else 1]) for s, f in reversed(r)]


def uret(nis: str, adet: int, c=None, yazdir=print) -> dict:
    c = c or db.baglan()
    sayac = {"uretilen": 0, "bicim_hatali": 0, "tekrar": 0, "ip_ret": 0, "ip_insan": 0, "kalite_ret": 0, "tasarim": 0}
    adaylar, hatali = ifade_uret.uret(nis, adet, _kacinilacak(c, nis))
    sayac["uretilen"], sayac["bicim_hatali"] = len(adaylar) + len(hatali), len(hatali)
    for a in adaylar:
        ifade_id = db.ifade_ekle(c, nis, a.satirlar, yapi={"ust": a.ust, "ana": list(a.ana), "alt": a.alt})
        if ifade_id is None:
            sayac["tekrar"] += 1
            continue
        k = kapi.denetle(a.satirlar, nis, ana=list(a.ana))
        db.kapi_yaz(c, ifade_id, k.karar, k.nedenler, k.kayit)
        c.commit()
        if k.karar != "temiz":
            sayac["ip_ret" if k.karar == "ret" else "ip_insan"] += 1
            yazdir(f"  IP {k.karar}: {' / '.join(a.satirlar)} — {'; '.join(k.nedenler)[:120]}")
            continue
        secim, nedenler = sec.sec(a.ust, list(a.ana), a.alt, _son_ciftler(c), tohum=ifade_id)
        if secim is None:
            sayac["kalite_ret"] += 1
            yazdir(f"  kalite ret: {' / '.join(a.satirlar)} — {nedenler[-1][:120] if nedenler else ''}")
            continue
        t = db.tasarim_ekle(c, ifade_id, secim.sablon, secim.fontlar)
        klasor = URETIM / f"{t:05d}"
        klasor.mkdir(parents=True, exist_ok=True)
        dosyalar = {}
        for etiket, img, murekkep in (("koyu", secim.koyu, sec.KOYU_MUREKKEP), ("acik", secim.acik, sec.ACIK_MUREKKEP)):
            (klasor / f"{etiket}.svg").write_text(secim.cizim.svg(murekkep), encoding="utf-8")
            dosyalar[f"{etiket}_png"] = str(render.kaydet(img, klasor / f"{etiket}.png").relative_to(KOK))
            dosyalar[f"{etiket}_svg"] = str((klasor / f"{etiket}.svg").relative_to(KOK))
        c.execute("UPDATE tasarim SET dosyalar = ?, kalite = ? WHERE id = ?", (json.dumps(dosyalar), json.dumps(secim.kalite), t))
        db.gecis(c, t, "kalite_ok", f"{secim.sablon} {secim.fontlar}")
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
    pn = alt.add_parser("panel", help="yerel onay paneli (127.0.0.1)")
    pn.add_argument("--port", type=int, default=8766)
    a = p.parse_args(argv)
    if a.komut == "uret":
        print(json.dumps(uret(a.nis, a.adet), ensure_ascii=False))
    elif a.komut == "metin":
        print(json.dumps(metin(sinir=a.sinir), ensure_ascii=False))
    elif a.komut == "panel":
        from matbaa.panel.app import calistir

        print(f"Onay paneli: http://127.0.0.1:{a.port}")
        calistir(a.port)
    elif a.komut == "durum":
        print(json.dumps(durum(), ensure_ascii=False, indent=1))
