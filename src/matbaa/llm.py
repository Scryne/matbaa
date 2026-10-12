"""Metin üretimi için başsız Claude çağrısı (`claude -p`, K-14). Yapılandırılmış çıktı JSON şemasıyla zorlanır.

Araç yok, ayar dosyası yok, kendi sistem istemi: çağrı yalnız verilen işi yapar.
"""

from __future__ import annotations

import json
import subprocess

from matbaa.ayar import modeller


class LLMHatasi(RuntimeError):
    pass


def yapilandirilmis(istem: str, sistem: str, sema: dict, zaman_asimi: int = 240, deneme: int = 2) -> dict:
    model = modeller().get("claude", {}).get("model", "sonnet")
    komut = [
        "claude", "-p", istem,
        "--model", model,
        "--output-format", "json",
        "--system-prompt", sistem,
        "--tools", "",
        "--json-schema", json.dumps(sema),
        "--setting-sources", "",
    ]  # fmt: skip
    son_hata = ""
    for _ in range(deneme):
        # Windows'ta alt süreç çıktısı cp1254 gelebilir: bayt al, utf-8 çöz (vault: windows-altsurec-kodlama-tuzagi).
        p = subprocess.run(komut, capture_output=True, timeout=zaman_asimi, check=False)
        if p.returncode != 0:
            son_hata = f"claude -p çıkış {p.returncode}: {p.stderr.decode('utf-8', 'replace')[:400]}"
            continue
        try:
            cikti = json.loads(p.stdout.decode("utf-8"))
        except json.JSONDecodeError as e:
            son_hata = f"JSON değil: {e}"
            continue
        sonuc = cikti.get("structured_output")
        if isinstance(sonuc, dict):
            return sonuc
        son_hata = f"yapılandırılmış çıktı yok: {str(cikti.get('result'))[:300]}"
    raise LLMHatasi(son_hata)
