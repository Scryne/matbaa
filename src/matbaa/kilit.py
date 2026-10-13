"""Tek koşu kilidi: günlük koşu aynı anda iki kez çalışmasın (görev + elle başlatma).

İki koşu aynı onaylı tasarımı aynı anda Printify'a açar: kimlik ancak oluşturmadan sonra kaydedildiği için mükerrer ürün ve
mükerrer Etsy ilanı (listeleme ücreti) doğar. Kilit işletim sisteminin dosya kilididir: süreç ölünce kendiliğinden kalkar, bayat
kilit dosyası bir sonraki koşuyu tıkamaz.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


class Kilitli(RuntimeError):
    pass


def _kilitle(fd: int, ac: bool = False) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)  # msvcrt bulunulan konumdan kilitler: hep ilk bayt
        msvcrt.locking(fd, msvcrt.LK_UNLCK if ac else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN if ac else fcntl.LOCK_EX | fcntl.LOCK_NB)


@contextmanager
def tek_kosu(yol: Path):
    yol.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(yol, os.O_RDWR | os.O_CREAT)
    try:
        try:
            _kilitle(fd)
        except OSError as e:
            raise Kilitli(f"başka bir koşu sürüyor ({yol})") from e
        try:
            os.ftruncate(fd, 0)
            os.write(fd, str(os.getpid()).encode())  # tanı için: kilidi tutan süreç
            yield
        finally:
            _kilitle(fd, ac=True)
    finally:
        os.close(fd)
