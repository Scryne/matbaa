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


def istek(
    http: httpx.Client, yontem: str, url: str, deneme: int = 5, bekle=time.sleep, tekrar_5xx: bool = True, **kw
) -> httpx.Response:
    """`tekrar_5xx=False`: kaynak oluşturan istek 5xx'te yinelenmez (sunucu oluşturup yanıtı düşürmüş olabilir → mükerrer).
    429 her zaman yinelenir: istek işlenmemiştir.

    Ağ hatası: bağlantı hiç kurulamadıysa (DNS, bağlantı reddi/zaman aşımı) istek sunucuya ulaşmamıştır, her istek yinelenir.
    Bağlantı kurulduktan sonra düşen istek (okuma zaman aşımı, kopan bağlantı) yalnız `tekrar_5xx` ise yinelenir: kaynak
    oluşturan istek işlenmiş olabilir. Önceden tek bir ağ titremesi günlük koşunun bütün adımını düşürüyordu."""
    for k in range(deneme):
        try:
            r = http.request(yontem, url, **kw)
        except httpx.TransportError as e:
            ulasmadi = isinstance(e, httpx.ConnectError | httpx.ConnectTimeout)
            if k == deneme - 1 or not (ulasmadi or tekrar_5xx):
                raise
            bekle(min(2.0 * 2**k, 120.0))
            continue
        if r.status_code == 429 or (r.status_code >= 500 and tekrar_5xx):
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
