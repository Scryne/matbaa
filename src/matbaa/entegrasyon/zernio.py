"""Zernio (eski Late) birleşik paylaşım API'si istemcisi (K-38, docs/arastirma/08).

Neden aracı: TikTok ve Pinterest kendi denetimsiz uygulamamızın gönderisini yalnız sahibine gösteriyor; Zernio'nun uygulaması
denetimden geçmiş. Instagram, Facebook ve YouTube da aynı API'den gider: Meta ve Google geliştirici uygulaması kurulmaz, zamanlama
Zernio sunucusunda durur (bilgisayar o saatte kapalı olsa da yayınlanır). Fiyat (2026-10-20): ilk 2 hesap ücretsiz, 3-10. hesap
6 $/ay; gönderi sınırsız.

Doküman (docs.zernio.com, 2026-10-20 okundu): taban `https://zernio.com/api/v1`, `Authorization: Bearer <anahtar>`. Medya:
`POST /media/presign` → `PUT uploadUrl` (yetki başlığı yok) → `publicUrl`; yükleme 7 gün saklanır, bu yüzden gönderi en çok
7 gün ileri zamanlanır. `POST /posts`: `platforms[{platform, accountId, platformSpecificData}]`, `scheduledFor` (ISO, UTC) ya da
`publishNow`; `Idempotency-Key` aynı isteğin yinelenmesini tek gönderi yapar (ağ düşüp yeniden denenince mükerrer yok).
"""

from __future__ import annotations

import mimetypes
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx

from .http import KULLANICI, ApiHatasi, istek

TABAN = "https://zernio.com/api/v1"


class Zernio:
    def __init__(self, anahtar: str | None = None, http: httpx.Client | None = None, bekle=None):
        self.anahtar = anahtar or os.environ["ZERNIO_API_KEY"]
        self.http = http or httpx.Client(timeout=300)
        self._bekle = bekle
        self._hesaplar: dict[str, str] | None = None
        self._medya: dict[Path, str] = {}  # aynı video birkaç platforma aynı koşuda bir kez yüklenir
        self._panolar: dict[str, str] | None = None

    def _istek(self, yontem: str, yol: str, basliklar: dict | None = None, **kw) -> httpx.Response:
        h = {"Authorization": f"Bearer {self.anahtar}", "User-Agent": KULLANICI} | (basliklar or {})
        ek = {"bekle": self._bekle} if self._bekle else {}
        return istek(self.http, yontem, f"{TABAN}{yol}", headers=h, **ek, **kw)

    def hesaplar(self) -> dict[str, str]:
        """platform → accountId; yalnız etkin bağlantılar (Scryne Zernio panelinden bağlar)."""
        if self._hesaplar is None:
            self._hesaplar = {}
            for a in self._istek("GET", "/accounts").json().get("accounts", []):
                if a.get("isActive", True) and a.get("platform") and a["platform"] not in self._hesaplar:
                    self._hesaplar[a["platform"]] = a["_id"]
        return self._hesaplar

    def medya(self, dosya: Path) -> str:
        """Yerel dosya → Zernio'nun herkese açık adresi."""
        if dosya not in self._medya:
            tur = mimetypes.guess_type(dosya.name)[0] or "video/mp4"
            ad = f"{dosya.parent.name}-{dosya.name}"  # her tasarımın dosyası video.mp4: ad klasörden ayrışır
            j = self._istek(
                "POST", "/media/presign", json={"filename": ad, "contentType": tur, "size": dosya.stat().st_size}
            ).json()
            istek(self.http, "PUT", j["uploadUrl"], content=dosya.read_bytes(), headers={"Content-Type": tur}, tekrar_5xx=True)
            self._medya[dosya] = j["publicUrl"]
        return self._medya[dosya]

    def panolar(self) -> dict[str, str]:
        """Pinterest pano adı → boardId."""
        if self._panolar is None:
            hesap = self.hesaplar()["pinterest"]
            j = self._istek("GET", f"/accounts/{hesap}/pinterest-boards").json()
            self._panolar = {b["name"]: str(b["id"]) for b in j.get("boards", [])}
        return self._panolar

    def pano(self, ad: str) -> str:
        """Pano yoksa açar (niş panoları kuyruktaki ilanlardan çıkar; Scryne elle açmaz)."""
        if ad not in self.panolar():
            hesap = self.hesaplar()["pinterest"]
            j = self._istek("POST", f"/accounts/{hesap}/pinterest-boards", json={"name": ad, "privacy": "PUBLIC"}).json()
            self._panolar[ad] = str((j.get("board") or j)["id"])
        return self._panolar[ad]

    def gonder(
        self,
        platform: str,
        metin: str,
        medya: list[dict],
        zaman: datetime | None,
        ozel: dict,
        anahtar: str,
        kok: dict | None = None,
    ) -> dict:
        """Tek platforma tek gönderi. `zaman` None: hemen yayınla. `kok`: gövdenin kökündeki platform ayarı (TikTok için
        `tiktokSettings`). Kaynak oluşturan istek 5xx'te yinelenmez; `Idempotency-Key` ağ düşüşünde mükerrer gönderiyi önler."""
        govde: dict = {
            "content": metin,
            "mediaItems": medya,
            "platforms": [{"platform": platform, "accountId": self.hesaplar()[platform], "platformSpecificData": ozel}],
            **(kok or {}),
        }
        if zaman is None:
            govde["publishNow"] = True
        else:
            govde["scheduledFor"] = zaman.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = self._istek("POST", "/posts", basliklar={"Idempotency-Key": anahtar}, json=govde, tekrar_5xx=False)
        if r.status_code == 207:  # tek platformlu gönderide kısmi başarı = o platform reddetti
            raise ApiHatasi(207, r.text, f"POST {TABAN}/posts")
        j = r.json()
        return j.get("post") or (j.get("data") or {}).get("post") or j

    def gonderi(self, post_id: str) -> dict:
        j = self._istek("GET", f"/posts/{post_id}").json()
        return j.get("post") or (j.get("data") or {}).get("post") or j


def platform_url(post: dict) -> str | None:
    """Yayınlanmış gönderinin platformdaki adresi (`platforms[].platformPostUrl`); dokümanda yanıt şeması tam değil."""
    for p in post.get("platforms") or []:
        if p.get("platformPostUrl"):
            return p["platformPostUrl"]
    return post.get("platformPostUrl")
