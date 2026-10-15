"""Yerel panel: takip panosu (`/`, 2026-10-15) ve onay masası (`/onay`, Faz 5: onay_bekliyor tasarımlar → Scryne'ın onayı/reddi).

    uv run matbaa panel         # http://127.0.0.1:8766

Yalnız 127.0.0.1'e bağlanır; kimlik doğrulama yok, dışarı açılmaz. Tarayıcıda açık başka bir sitenin panele istek atması
(DNS rebinding, siteler arası POST) Host ve Origin denetimiyle reddedilir.
"""

from __future__ import annotations

import io
import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from PIL import Image
from pydantic import BaseModel

from matbaa import db, fiyat, siparis
from matbaa.ayar import KOK

SAYFA = Path(__file__).with_name("index.html")  # onay masası
PANO = Path(__file__).with_name("pano.html")  # takip panosu (açılış sayfası)
RET_NEDENLERI = ["okunmuyor", "espri zayıf", "marka şüphesi", "tekrar / benzer", "niş dışı", "tasarım çirkin"]

YEREL = {"127.0.0.1", "localhost"}

app = FastAPI(title="Matbaa onay paneli", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def yalniz_yerel(istek: Request, sonraki):
    """Host yerel değilse (DNS rebinding) ya da yazma isteği başka bir kökenden geliyorsa (siteler arası POST) 403."""
    host = (istek.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
    koken = istek.headers.get("origin")
    if host not in YEREL or (istek.method != "GET" and koken and urlsplit(koken).hostname not in YEREL):
        return JSONResponse({"detail": "yalnız yerel panel"}, status_code=403)
    return await sonraki(istek)


def _c():
    c = db.baglan(thread_serbest=True)  # FastAPI eşzamanlı bağımlılığı açar ve kapatırken iş parçacığı değişebilir
    try:
        yield c
    finally:
        c.close()


Baglanti = Annotated[sqlite3.Connection, Depends(_c)]  # istek başına bir bağlantı, yanıttan sonra kapanır


def _dosya(c, tasarim_id: int, murekkep: str) -> Path:
    if murekkep not in ("koyu", "acik"):
        raise HTTPException(404)
    r = c.execute("SELECT dosyalar FROM tasarim WHERE id = ?", (tasarim_id,)).fetchone()
    yol = KOK / json.loads(r[0]).get(f"{murekkep}_png", "") if r and r[0] else None
    if yol is None or not yol.is_file():
        raise HTTPException(404, "baskı dosyası yok")
    return yol


@app.get("/", response_class=HTMLResponse)
def pano_sayfa() -> str:
    return PANO.read_text(encoding="utf-8")


@app.get("/onay", response_class=HTMLResponse)
def sayfa() -> str:
    return SAYFA.read_text(encoding="utf-8")


FONTLAR = {"serif": "DMSerifDisplay-Regular.ttf"}  # panoda başlık fontu; yerelden, dış istek yok (OFL, varliklar/fontlar)


@app.get("/font/{ad}")
def font_dosyasi(ad: str) -> FileResponse:
    if ad not in FONTLAR:
        raise HTTPException(404)
    return FileResponse(
        KOK / "varliklar" / "fontlar" / FONTLAR[ad], media_type="font/ttf", headers={"Cache-Control": "max-age=604800"}
    )


@app.get("/api/pano")
def pano_veri(c: Baglanti) -> dict:
    from matbaa.panel import pano

    return pano.pano(c)


def _csv_yanit(dosya: str, veri: bytes) -> Response:
    return Response(
        veri, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{dosya}"'}
    )


@app.post("/pinterest/indir")
def pinterest_indir(c: Baglanti) -> Response:
    """Bekleyen pinlere yayın saati verip CSV olarak indirir (POST: pinleri `verildi` sayar, yan etkili)."""
    from matbaa import pinterest

    dosya, veri, n = pinterest.csv_uret(c)
    if not n:
        raise HTTPException(409, "bekleyen pin yok ya da 14 günlük takvim dolu")
    return _csv_yanit(dosya, veri)


@app.get("/pinterest/son")
def pinterest_son(c: Baglanti) -> Response:
    from matbaa import pinterest

    son = pinterest.son_csv(c)
    if son is None:
        raise HTTPException(404, "henüz indirilmiş dosya yok")
    return _csv_yanit(son[0], son[1])


def _kanit(kayit_json: str | None) -> dict:
    """IP kapısının ham kaydından panelde gösterilecek özet: aday/benzer markalar, Jev olasılıkları."""
    if not kayit_json:
        return {}
    kayit = json.loads(kayit_json)
    adaylar = sorted({a for k in kayit for a in k.get("adaylar", [])})
    benzer = sorted({b for k in kayit for b in k.get("benzerler", [])})
    anlam = next((k for k in kayit if "anlam" in k), {})
    olas = anlam.get("olasiliklar", {})
    one_cikan = {k: v for k, v in olas.items() if not k.startswith("kaynak.") and v >= 0.2}
    kaynak = max(((k[7:], v) for k, v in olas.items() if k.startswith("kaynak.")), key=lambda x: x[1], default=None)
    return {
        "aday_markalar": adaylar[:12],
        "benzer_markalar": benzer[:8],
        "jev": one_cikan,
        "kaynak": kaynak,
        "model": anlam.get("model"),
    }


@app.get("/api/kuyruk")
def kuyruk(c: Baglanti) -> dict:
    satirlar = c.execute(
        """SELECT t.id, t.sablon, t.fontlar, t.dosyalar, i.satirlar, i.nis, i.kapi_kayit, i.kapi_karar, i.kapi_nedenler
           FROM tasarim t JOIN ifade i ON i.id = t.ifade_id WHERE t.durum = 'onay_bekliyor' ORDER BY t.id"""
    ).fetchall()
    urun_kat = fiyat.urunler()
    sonuc = []
    for r in satirlar:
        ilanlar = {
            x["urun"]: {
                "baslik": x["baslik"],
                "etiketler": json.loads(x["etiketler"]),
                "aciklama": x["aciklama"],
                "fiyat": x["fiyat"],
                "kargo": x["kargo"],
                "net": fiyat.beklenen_net(x["urun"]),
            }
            for x in c.execute("SELECT * FROM ilan WHERE tasarim_id = ?", (r["id"],)).fetchall()
        }
        ilanlar = {u: ilanlar[u] for u in urun_kat if u in ilanlar}  # katalog sırası: tişört önce
        sonuc.append(
            {
                "id": r["id"],
                "nis": r["nis"],
                "satirlar": json.loads(r["satirlar"]),
                "sablon": r["sablon"],
                "fontlar": json.loads(r["fontlar"]),
                "kanit": _kanit(r["kapi_kayit"]),
                "ip": {"karar": r["kapi_karar"], "nedenler": json.loads(r["kapi_nedenler"] or "[]")},
                "ilanlar": ilanlar,
            }
        )
    renkler = {
        u: [{"ad": x["ad"], "hex": x["hex"], "murekkep": x["murekkep"]} for x in p["renkler"]] for u, p in urun_kat.items()
    }
    ozet = dict(c.execute("SELECT durum, count(*) FROM tasarim GROUP BY durum").fetchall())
    return {
        "tasarimlar": sonuc,
        "renkler": renkler,
        "urun_adlari": {u: p["etsy_turu"] for u, p in urun_kat.items()},
        "ret_nedenleri": RET_NEDENLERI,
        "ozet": ozet,
        "kar": siparis.ozet(c),
        **_dikkat(c),
    }


def _dikkat(c) -> dict:
    """Onaydan önce görülmesi gerekenler: son günlük koşunun hata/alarmları, şu an geciken sipariş, takılan ürün."""
    from matbaa import hat, yayin

    son, dikkat = None, []
    try:
        k = json.loads(hat.SON_KOSU.read_text(encoding="utf-8"))
        son = {"zaman": k.get("basladi"), "hata": len(k.get("hatalar", []))}
        dikkat += [f"son koşu: {h}" for h in k.get("hatalar", [])]
        dikkat += [a for a in k.get("alarmlar", []) if not a.startswith("makbuz ")]  # gecikme aşağıda güncel hâliyle
    except (OSError, ValueError):
        pass
    dikkat += siparis.geciken(c)
    elle = c.execute("SELECT tasarim_id, urun, hata FROM urun WHERE durum = 'hata' AND hata LIKE ?", (f"%{yayin.ELLE}%",))
    dikkat += [f"#{r[0]} {r[1]}: {r[2][:160]}" for r in elle.fetchall()]
    return {"dikkat": list(dict.fromkeys(dikkat)), "son_kosu": son}


@lru_cache(maxsize=256)
def _onizleme(yol: str, mtime: float) -> bytes:
    img = Image.open(yol).convert("RGBA")
    kutu = img.getchannel("A").getbbox() or (0, 0, img.width, img.height)
    img = img.crop((0, 0, img.width, min(img.height, kutu[3] + 60)))  # alt boşluğu at: göğüs baskısı provası
    img.thumbnail((900, 900))
    b = io.BytesIO()
    img.save(b, "WEBP", quality=90)
    return b.getvalue()


@app.get("/onizleme/{tasarim_id}/{murekkep}")
def onizleme(tasarim_id: int, murekkep: str, c: Baglanti) -> Response:
    yol = _dosya(c, tasarim_id, murekkep)
    return Response(_onizleme(str(yol), yol.stat().st_mtime), media_type="image/webp", headers={"Cache-Control": "max-age=3600"})


@app.get("/tam/{tasarim_id}/{murekkep}")
def tam(tasarim_id: int, murekkep: str, c: Baglanti) -> FileResponse:
    return FileResponse(_dosya(c, tasarim_id, murekkep))


class Karar(BaseModel):
    karar: str  # "onay" | "ret"
    neden: str = ""


@app.post("/api/karar/{tasarim_id}")
def karar(tasarim_id: int, k: Karar, c: Baglanti) -> dict:
    durum = c.execute("SELECT durum FROM tasarim WHERE id = ?", (tasarim_id,)).fetchone()
    if durum is None:
        raise HTTPException(404, "tasarım yok")
    if durum[0] != "onay_bekliyor":
        raise HTTPException(409, f"tasarım {durum[0]} durumunda")
    if k.karar == "onay":
        db.gecis(c, tasarim_id, "onaylandi", "Scryne onayı (panel)")
    elif k.karar == "ret":
        db.gecis(c, tasarim_id, "ret", f"Scryne: {k.neden or 'neden belirtilmedi'}")
    else:
        raise HTTPException(422, "karar onay ya da ret olmalı")
    c.commit()
    return {"id": tasarim_id, "durum": "onaylandi" if k.karar == "onay" else "ret"}


@app.post("/api/geri-al/{tasarim_id}")
def geri_al(tasarim_id: int, c: Baglanti) -> dict:
    """Son onayı geri alır (yanlış tuş). Ret geri alınmaz: ret son durumdur, tasarım yeniden üretilir."""
    durum = c.execute("SELECT durum FROM tasarim WHERE id = ?", (tasarim_id,)).fetchone()
    if durum is None or durum[0] != "onaylandi":
        raise HTTPException(409, "yalnız henüz yayına girmemiş onay geri alınır")
    db.gecis(c, tasarim_id, "onay_bekliyor", "onay geri alındı (panel)")
    c.commit()
    return {"id": tasarim_id, "durum": "onay_bekliyor"}


class IlanDuzelt(BaseModel):
    baslik: str
    etiketler: list[str]


@app.post("/api/ilan/{tasarim_id}/{urun}")
def ilan_duzelt(tasarim_id: int, urun: str, d: IlanDuzelt, c: Baglanti) -> dict:
    """Faz 5 "düzelt": yayından önce başlık ve etiketler elle düzeltilir; ilan doğrulayıcısından ve marka süzgecinden geçmeyen
    düzeltme kaydedilmez (Etsy'nin reddedeceği ya da markaya çarpan metin panelden de yayına giremez)."""
    from matbaa.ilan.dogrula import dogrula
    from matbaa.ilan.metin import Ilan
    from matbaa.ip import marka

    t = c.execute("SELECT durum FROM tasarim WHERE id = ?", (tasarim_id,)).fetchone()
    il = c.execute("SELECT aciklama, alt_metin FROM ilan WHERE tasarim_id = ? AND urun = ?", (tasarim_id, urun)).fetchone()
    if t is None or il is None:
        raise HTTPException(404, "ilan yok")
    if t[0] not in ("onay_bekliyor", "onaylandi"):
        raise HTTPException(409, f"tasarım {t[0]} durumunda: yalnız yayından önce düzeltilir")
    if c.execute("SELECT 1 FROM urun WHERE tasarim_id = ? AND urun = ? AND durum != 'bekliyor'", (tasarim_id, urun)).fetchone():
        raise HTTPException(409, "ürün Printify'a açıldı: düzeltme Etsy'de yapılır")
    sonuc = dogrula(Ilan(d.baslik, d.etiketler, il["aciklama"], il["alt_metin"] or ""))
    dizin = marka.dizin()
    carpan = [e for e in sonuc.etiketler if not dizin.kontrol(e).temiz]  # hat'taki gibi: etiketler marka süzgecinden
    sorunlar = sonuc.sorunlar + ([f"markaya çarpıyor: {', '.join(carpan)}"] if carpan else [])
    if sorunlar:
        raise HTTPException(422, "; ".join(sorunlar))
    c.execute(
        "UPDATE ilan SET baslik = ?, etiketler = ? WHERE tasarim_id = ? AND urun = ?",
        (sonuc.baslik, json.dumps(sonuc.etiketler), tasarim_id, urun),
    )
    db.olay(c, "ilan", tasarim_id, None, f"{urun}:duzeltildi", sonuc.baslik[:200])
    c.commit()
    return {"baslik": sonuc.baslik, "etiketler": sonuc.etiketler}


def _video_klasoru(c, tasarim_id: int) -> Path:
    from matbaa import tiktok

    r = c.execute("SELECT klasor FROM video WHERE tasarim_id = ?", (tasarim_id,)).fetchone()
    if r is None or not r[0]:
        raise HTTPException(404, "video yok")
    return tiktok.KOK / r[0]  # kayıt proje köküne göreli


@app.get("/tiktok/{tasarim_id}/{dosya}")
def tiktok_dosya(tasarim_id: int, dosya: str, c: Baglanti) -> Response:
    """Hazır TikTok videosu ya da kapağı. Dosya adı sabit listeden: yol enjeksiyonu yok."""
    klasor = _video_klasoru(c, tasarim_id)
    ad = f"hobbyheartprints-{tasarim_id:05d}"
    if dosya not in ("video.mp4", "kapak.jpg") or not (klasor / dosya).is_file():
        raise HTTPException(404, "dosya yok")
    if dosya == "kapak.jpg":
        return FileResponse(klasor / dosya, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})
    return FileResponse(klasor / dosya, media_type="video/mp4", filename=f"{ad}.mp4")


@app.post("/api/tiktok/{tasarim_id}/paylasildi")
def tiktok_paylasildi(tasarim_id: int, c: Baglanti) -> dict:
    from matbaa import tiktok

    try:
        tiktok.paylasildi(c, tasarim_id)
    except KeyError:
        raise HTTPException(409, "paylaşılmayı bekleyen video yok") from None
    return {"durum": "paylasildi"}


class IsimliIsim(BaseModel):
    isimler: dict[str, str]  # transaction_id → basılacak isim


@app.post("/api/isimli/{makbuz}/isim")
def isimli_isim(makbuz: str, d: IsimliIsim, c: Baglanti) -> dict:
    """Açılamayan isimli süs siparişine (ör. fontta olmayan harf) elle isim: basılabilirse kaydedilir, sonraki koşu açar."""
    from matbaa import isimli

    if not d.isimler:
        raise HTTPException(422, "isim yok")
    try:
        return {"isimler": isimli.elle_isim(c, makbuz, d.isimler)}
    except KeyError:
        raise HTTPException(404, "makbuz yok") from None
    except isimli.DurumUyumsuz as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:  # boş isim ya da fontta glifi olmayan harf
        raise HTTPException(422, f"bu isim basılamıyor: {e}") from None


@app.post("/api/isimli/{makbuz}/kapat")
def isimli_kapat(makbuz: str, c: Baglanti) -> dict:
    """ "Elle hallettim": sipariş otomatik denenmez, alarm kalkar."""
    from matbaa import isimli

    try:
        isimli.elle_kapat(c, makbuz)
    except KeyError:
        raise HTTPException(404, "makbuz yok") from None
    except isimli.DurumUyumsuz as e:
        raise HTTPException(409, str(e)) from None
    return {"durum": "kapandi"}


def calistir(port: int = 8766) -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
