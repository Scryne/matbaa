"""Metin üretimi için başsız Claude çağrısı (`claude -p`, K-14). Yapılandırılmış çıktı JSON şemasıyla zorlanır.

Araç yok, ayar dosyası yok, kendi sistem istemi: çağrı yalnız verilen işi yapar.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

from matbaa.ayar import modeller


class LLMHatasi(RuntimeError):
    pass


def calistir(komut: list[str], zaman_asimi: int) -> tuple[int, bytes, bytes]:
    """Alt süreci çalıştırır; süre dolarsa süreç ağacının tamamını öldürür.

    `subprocess.run(capture_output=True, timeout=...)` 2026-10-13'te ilan metni adımını bir saat kilitledi: zaman aşımında yalnız
    `claude` öldürülüyor, borunun ucunu tutan torun süreç yaşadığı için okuma hiç bitmiyordu. Çıktı boru yerine geçici dosyaya
    yazılır (okuma beklemez), süre dolunca Windows'ta `taskkill /T` ile ağaç kapanır. Bayt okunur, utf-8 çözülür (cp1254 tuzağı).
    """
    with tempfile.TemporaryFile() as cikis, tempfile.TemporaryFile() as hata:
        p = subprocess.Popen(komut, stdout=cikis, stderr=hata, stdin=subprocess.DEVNULL)
        try:
            kod = p.wait(timeout=zaman_asimi)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True, check=False)
            else:
                p.kill()
            p.wait(timeout=30)
            raise TimeoutError(f"{komut[0]} {zaman_asimi} sn'de bitmedi, süreç ağacı kapatıldı") from None
        cikis.seek(0)
        hata.seek(0)
        return kod, cikis.read(), hata.read()


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
        try:
            kod, cikis, hata = calistir(komut, zaman_asimi)
        except TimeoutError as e:
            son_hata = str(e)
            continue
        if kod != 0:
            son_hata = f"claude -p çıkış {kod}: {hata.decode('utf-8', 'replace')[:400]}"
            continue
        try:
            cikti = json.loads(cikis.decode("utf-8"))
        except json.JSONDecodeError as e:
            son_hata = f"JSON değil: {e}"
            continue
        sonuc = cikti.get("structured_output")
        if isinstance(sonuc, dict):
            return sonuc
        son_hata = f"yapılandırılmış çıktı yok: {str(cikti.get('result'))[:300]}"
    raise LLMHatasi(son_hata)
