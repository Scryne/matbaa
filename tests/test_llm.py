"""LLM alt süreci: süre dolunca torun süreç boruyu tutsa bile çağrı takılmaz (2026-10-13'te metin adımı bir saat kilitlendi)."""

from __future__ import annotations

import sys
import time

import pytest

from matbaa import llm


def test_zaman_asimi_torun_surec_varken_de_doner():
    # Ebeveyn, çıktıyı miras alan ve 60 sn yaşayan bir torun başlatır, sonra kendisi de uyur.
    kod = "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"
    bas = time.time()
    with pytest.raises(TimeoutError):
        llm.calistir([sys.executable, "-c", kod], zaman_asimi=2)
    assert time.time() - bas < 20


def test_normal_cikti_bayt_olarak_doner():
    kod, cikis, _ = llm.calistir(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write('merhaba ğ'.encode('utf-8'))"], zaman_asimi=30
    )
    assert kod == 0 and "merhaba ğ" in cikis.decode("utf-8")
