"""Ortak HTTP katmanı: 429'da `Retry-After`'a uy, 5xx'te üstel geri çekil, hata yanıtını görünür kıl."""

from __future__ import annotations

import time

import httpx

KULLANICI = "Matbaa/0.1 (private Etsy shop automation)"


class ApiHatasi(RuntimeError):
    def __init__(self, durum: int, govde: str, istek: str):
        super().__init__(f"{istek} → {durum}: {govde[:500]}")
        self.durum = durum
        self.govde = govde


def istek(http: httpx.Client, yontem: str, url: str, deneme: int = 5, bekle=time.sleep, **kw) -> httpx.Response:
    for k in range(deneme):
        r = http.request(yontem, url, **kw)
        if r.status_code == 429 or r.status_code >= 500:
            if k == deneme - 1:
                break
            try:
                sure = float(r.headers.get("Retry-After", ""))
            except ValueError:
                sure = 2.0 * 2**k
            bekle(min(sure, 120.0))
            continue
        if r.status_code >= 400:
            raise ApiHatasi(r.status_code, r.text, f"{yontem} {url}")
        return r
    raise ApiHatasi(r.status_code, r.text, f"{yontem} {url} ({deneme} deneme)")
