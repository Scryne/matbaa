"""Etsy Seller App için bir kerelik OAuth 2.0 (PKCE) yetkilendirmesi → .etsy_token.json

Ön koşul: etsy.com/developers/your-apps'te uygulama; "Callback URLs" listesine http://localhost:3003/callback eklenmiş;
.env'de ETSY_KEYSTRING ve ETSY_SHARED_SECRET.

    uv run python scripts/etsy_yetki.py

Tarayıcıda Etsy izin sayfası açılır; Scryne "Allow Access" der; yönlendirme bu betiğin yerel sunucusuna düşer,
kod token'a çevrilir ve yenileme token'ı git dışı dosyaya yazılır. Ardından mağaza kimliği ve üretim ortakları yazdırılır.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

from matbaa.entegrasyon.etsy import TOKEN_DOSYASI, TOKEN_URL

YONLENDIRME = "http://localhost:3003/callback"
KAPSAM = "listings_r listings_w shops_r transactions_r transactions_w"


def main() -> None:
    anahtar = os.environ["ETSY_KEYSTRING"]
    dogrulayici = secrets.token_urlsafe(64)[:96]
    meydan = base64.urlsafe_b64encode(hashlib.sha256(dogrulayici.encode()).digest()).rstrip(b"=").decode()
    durum = secrets.token_urlsafe(16)
    url = "https://www.etsy.com/oauth/connect?" + urllib.parse.urlencode(
        {
            "response_type": "code",
            "redirect_uri": YONLENDIRME,
            "scope": KAPSAM,
            "client_id": anahtar,
            "state": durum,
            "code_challenge": meydan,
            "code_challenge_method": "S256",
        }
    )
    gelen: dict = {}

    class Isleyici(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            gelen.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("Matbaa: Etsy yetkisi alındı, bu sekmeyi kapatabilirsin.".encode())

        def log_message(self, *a):
            pass

    print("Tarayıcıda Etsy izin sayfası açılıyor. Açılmazsa bu adresi yapıştır:\n" + url)
    webbrowser.open(url)
    sunucu = HTTPServer(("127.0.0.1", 3003), Isleyici)
    while "code" not in gelen and "error" not in gelen:
        sunucu.handle_request()
    if gelen.get("error") or gelen.get("state") != durum:
        raise SystemExit(f"Yetki alınamadı: {gelen}")
    r = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": anahtar,
            "redirect_uri": YONLENDIRME,
            "code": gelen["code"],
            "code_verifier": dogrulayici,
        },
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    TOKEN_DOSYASI.write_text(json.dumps({"refresh_token": d["refresh_token"], "yenilendi": int(time.time())}))
    kullanici = d["access_token"].split(".")[0]  # Etsy erişim token'ı "<user_id>.<...>" biçiminde
    basliklar = {"x-api-key": f"{anahtar}:{os.environ['ETSY_SHARED_SECRET']}", "Authorization": f"Bearer {d['access_token']}"}
    dukkan = httpx.get(f"https://openapi.etsy.com/v3/application/users/{kullanici}/shops", headers=basliklar, timeout=30).json()
    print(f"Token kaydedildi → {TOKEN_DOSYASI}")
    print(f"Mağaza: {dukkan.get('shop_name')} — ETSY_SHOP_ID={dukkan.get('shop_id')} (.env'e yaz)")
    ortak = httpx.get(
        f"https://openapi.etsy.com/v3/application/shops/{dukkan.get('shop_id')}/production-partners",
        headers=basliklar,
        timeout=30,
    ).json()
    print("Üretim ortakları:", [(p.get("production_partner_id"), p.get("partner_name")) for p in ortak.get("results", [])])


if __name__ == "__main__":
    main()
