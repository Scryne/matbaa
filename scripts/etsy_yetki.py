"""Etsy Seller App için bir kerelik OAuth 2.0 (PKCE) yetkilendirmesi → .etsy_token.json

Ön koşul: etsy.com/developers/your-apps'te uygulama; "Callback URLs" listesine http://localhost:3003/callback eklenmiş;
.env'de ETSY_KEYSTRING ve ETSY_SHARED_SECRET.

    uv run python scripts/etsy_yetki.py

Tarayıcıda Etsy izin sayfası açılır; Scryne "Allow Access" der; yönlendirme bu betiğin yerel sunucusuna düşer,
kod token'a çevrilir ve yenileme token'ı git dışı dosyaya yazılır. Mağaza kimliği `.env`'e (ETSY_SHOP_ID), adı "Printify"
olan tek üretim ortağı `config/yayin.toml`'a yazılır; birden çok ya da hiç yoksa liste basılır, seçim elle.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import sys
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

from matbaa.ayar import CONFIG, env_yaz, env_yukle
from matbaa.entegrasyon.etsy import TOKEN_DOSYASI, TOKEN_URL

YONLENDIRME = "http://localhost:3003/callback"
KAPSAM = "listings_r listings_w shops_r shops_w transactions_r transactions_w"  # shops_w: mağaza bölümleri (yayin.vitrin_esitle)


def ortak_yaz(ortak_id: int, dosya=CONFIG / "yayin.toml") -> None:
    t = dosya.read_text(encoding="utf-8")
    t, n = re.subn(r"(?m)^uretim_ortagi_id = \d+", f"uretim_ortagi_id = {ortak_id}", t)
    if n != 1:
        raise SystemExit(f"{dosya}: uretim_ortagi_id satırı bulunamadı")
    dosya.write_text(t, encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolu cp1254: "→" token kaydından sonra betiği düşürüyordu
    env_yukle()
    if not (os.environ.get("ETSY_KEYSTRING") and os.environ.get("ETSY_SHARED_SECRET")):
        raise SystemExit(".env'de ETSY_KEYSTRING ve ETSY_SHARED_SECRET dolu olmalı (docs/Faz0-Rehber.md, 3. bölüm)")
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
    if not dukkan.get("shop_id"):
        raise SystemExit(f"Mağaza bulunamadı: {dukkan}")
    env_yaz("ETSY_SHOP_ID", str(dukkan["shop_id"]))
    print(f"Mağaza: {dukkan.get('shop_name')} — ETSY_SHOP_ID={dukkan['shop_id']} → .env")
    ortaklar = (
        httpx.get(
            f"https://openapi.etsy.com/v3/application/shops/{dukkan['shop_id']}/production-partners",
            headers=basliklar,
            timeout=30,
        )
        .json()
        .get("results", [])
    )
    printify = [p for p in ortaklar if "printify" in str(p.get("partner_name", "")).lower()]
    # API ortağı vitrindeki "Descriptive title" ile döndürüyor ("A print-on-demand print shop", 2026-10-13): tek ortak varsa odur.
    if not printify and len(ortaklar) == 1:
        printify = ortaklar
    if len(printify) == 1:
        ortak_yaz(int(printify[0]["production_partner_id"]))
        print(f"Üretim ortağı: {printify[0].get('partner_name')} ({printify[0]['production_partner_id']}) → config/yayin.toml")
    else:
        print(
            "Üretim ortağı seçilemedi (Printify adlı tek ortak yok):",
            [(p.get("production_partner_id"), p.get("partner_name")) for p in ortaklar],
        )


if __name__ == "__main__":
    main()
