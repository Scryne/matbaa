"""Hattın adımları. Her adım veritabanındaki durumdan okur, sonucunu durum makinesine yazar; yarıda kalırsa yeniden çalıştırmak güvenlidir.

uv run matbaa uret --nis fishing --adet 12    # ifade üret → IP kapısı → tasarım → kalite
uv run matbaa durum                           # kuyruk özeti
"""

from __future__ import annotations

import argparse
import json
import sys

from matbaa import db
from matbaa.ayar import KOK
from matbaa.ifade import uret as ifade_uret
from matbaa.ip import kapi
from matbaa.tasarim import render, sec

URETIM = KOK / "uretim"


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
        ifade_id = db.ifade_ekle(c, nis, a.satirlar)
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
    alt.add_parser("durum", help="kuyruk özeti")
    a = p.parse_args(argv)
    if a.komut == "uret":
        print(json.dumps(uret(a.nis, a.adet), ensure_ascii=False))
    elif a.komut == "durum":
        print(json.dumps(durum(), ensure_ascii=False, indent=1))
