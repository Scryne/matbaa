"""Yerel onay paneli (Faz 5): onay_bekliyor tasarımlar → Scryne'ın onayı/reddi.

    uv run matbaa panel         # http://127.0.0.1:8766

Yalnız 127.0.0.1'e bağlanır; kimlik doğrulama yok, dışarı açılmaz.
"""

from __future__ import annotations

import io
import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from PIL import Image
from pydantic import BaseModel

from matbaa import db, fiyat, siparis
from matbaa.ayar import KOK

SAYFA = Path(__file__).with_name("index.html")
RET_NEDENLERI = ["okunmuyor", "espri zayıf", "marka şüphesi", "tekrar / benzer", "niş dışı", "tasarım çirkin"]

app = FastAPI(title="Matbaa onay paneli", docs_url=None, redoc_url=None)


def _c():
    return db.baglan()


@app.get("/", response_class=HTMLResponse)
def sayfa() -> str:
    return SAYFA.read_text(encoding="utf-8")


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
def kuyruk() -> dict:
    c = _c()
    satirlar = c.execute(
        """SELECT t.id, t.sablon, t.fontlar, t.dosyalar, i.satirlar, i.nis, i.kapi_kayit
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
    }


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
def onizleme(tasarim_id: int, murekkep: str) -> Response:
    if murekkep not in ("koyu", "acik"):
        raise HTTPException(404)
    r = _c().execute("SELECT dosyalar FROM tasarim WHERE id = ?", (tasarim_id,)).fetchone()
    if r is None or not r[0]:
        raise HTTPException(404)
    yol = KOK / json.loads(r[0])[f"{murekkep}_png"]
    return Response(_onizleme(str(yol), yol.stat().st_mtime), media_type="image/webp", headers={"Cache-Control": "max-age=3600"})


@app.get("/tam/{tasarim_id}/{murekkep}")
def tam(tasarim_id: int, murekkep: str) -> FileResponse:
    r = _c().execute("SELECT dosyalar FROM tasarim WHERE id = ?", (tasarim_id,)).fetchone()
    if r is None or murekkep not in ("koyu", "acik"):
        raise HTTPException(404)
    return FileResponse(KOK / json.loads(r[0])[f"{murekkep}_png"])


class Karar(BaseModel):
    karar: str  # "onay" | "ret"
    neden: str = ""


@app.post("/api/karar/{tasarim_id}")
def karar(tasarim_id: int, k: Karar) -> dict:
    c = _c()
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
def geri_al(tasarim_id: int) -> dict:
    """Son onayı geri alır (yanlış tuş). Ret geri alınmaz: ret son durumdur, tasarım yeniden üretilir."""
    c = _c()
    durum = c.execute("SELECT durum FROM tasarim WHERE id = ?", (tasarim_id,)).fetchone()
    if durum is None or durum[0] != "onaylandi":
        raise HTTPException(409, "yalnız henüz yayına girmemiş onay geri alınır")
    db.gecis(c, tasarim_id, "onay_bekliyor", "onay geri alındı (panel)")
    c.commit()
    return {"id": tasarim_id, "durum": "onay_bekliyor"}


def calistir(port: int = 8766) -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
