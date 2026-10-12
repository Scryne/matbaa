"""Etsy Open API v3 istemcisi — yalnız kendi mağazamız (Seller App).

Şemadan doğrulandı (etsy.com/openapi/generated/oas/3.0.0.json, 2026-10-13): `x-api-key` = `keystring:shared_secret`;
token adresi `https://openapi.etsy.com/v3/public/oauth/token`; `updateListing` gövdesi form-urlencoded ve
`production_partner_ids`, `state`, `tags` alanlarını taşır. Erişim token'ı 1 saat, yenileme token'ı 90 gün ve
her yenilemede değişir: yeni yenileme token'ı `ETSY_TOKEN_DOSYASI`na yazılır.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

from matbaa.ayar import KOK

from .http import KULLANICI, istek

TABAN = "https://openapi.etsy.com/v3/application"
TOKEN_URL = "https://openapi.etsy.com/v3/public/oauth/token"
TOKEN_DOSYASI = KOK / ".etsy_token.json"  # git dışı


class Etsy:
    def __init__(
        self,
        keystring: str | None = None,
        shared_secret: str | None = None,
        shop_id: str | None = None,
        http: httpx.Client | None = None,
        token_dosyasi: Path = TOKEN_DOSYASI,
        bekle=None,
    ):
        self.keystring = keystring or os.environ["ETSY_KEYSTRING"]
        self.secret = shared_secret or os.environ["ETSY_SHARED_SECRET"]
        self.shop_id = shop_id or os.environ.get("ETSY_SHOP_ID")
        self.http = http or httpx.Client(timeout=60)
        self.http.headers.update({"x-api-key": f"{self.keystring}:{self.secret}", "User-Agent": KULLANICI})
        self.token_dosyasi = token_dosyasi
        self._bekle = bekle
        self._erisim: str | None = None
        self._bitis = 0.0

    def _yenile(self) -> None:
        kayit = json.loads(self.token_dosyasi.read_text()) if self.token_dosyasi.exists() else {}
        yenileme = kayit.get("refresh_token") or os.environ.get("ETSY_REFRESH_TOKEN")
        if not yenileme:
            raise RuntimeError("Etsy yenileme token'ı yok: önce `uv run python scripts/etsy_yetki.py`")
        r = istek(
            self.http,
            "POST",
            TOKEN_URL,
            data={"grant_type": "refresh_token", "client_id": self.keystring, "refresh_token": yenileme},
        )
        d = r.json()
        self._erisim, self._bitis = d["access_token"], time.time() + d.get("expires_in", 3600) - 120
        self.token_dosyasi.write_text(json.dumps({"refresh_token": d["refresh_token"], "yenilendi": int(time.time())}))

    def _i(self, yontem: str, yol: str, **kw) -> dict:
        if not self._erisim or time.time() > self._bitis:
            self._yenile()
        ek = {"bekle": self._bekle} if self._bekle else {}
        r = istek(self.http, yontem, f"{TABAN}{yol}", headers={"Authorization": f"Bearer {self._erisim}"}, **ek, **kw)
        return r.json() if r.content else {}

    def uretim_ortaklari(self) -> list[dict]:
        return self._i("GET", f"/shops/{self.shop_id}/production-partners")["results"]

    def ilan(self, listing_id: int) -> dict:
        return self._i("GET", f"/listings/{listing_id}")

    def ilan_guncelle(self, listing_id: int, **alanlar) -> dict:
        # Form gövdesinde dizi alanları virgülle birleşir (şema: "A comma-separated list").
        form = {k: ",".join(map(str, v)) if isinstance(v, list | tuple) else v for k, v in alanlar.items()}
        return self._i("PATCH", f"/shops/{self.shop_id}/listings/{listing_id}", data=form)

    def makbuzlar(self, min_son_degisim: int | None = None, limit: int = 100) -> list[dict]:
        params = {"limit": limit, "was_paid": "true"}
        if min_son_degisim:
            params["min_last_modified"] = min_son_degisim
        return self._i("GET", f"/shops/{self.shop_id}/receipts", params=params)["results"]
