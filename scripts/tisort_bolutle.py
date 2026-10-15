"""Tişört maskesi (SAM 2.1, Apache-2.0): ComfyUI'nin Python ortamında çalışır (torch + transformers orada; projeye ağır bağımlılık
girmez). `src/matbaa/giyim.py` alt süreç olarak çağırır.

    <ComfyUI>/.venv/Scripts/python.exe scripts/tisort_bolutle.py giris.png cikis.png

Kişi kadrajın ortasında, belden yukarı (istem böyle): göğüs ve karın hizasındaki iki nokta tişörte düşer. SAM'in üç maske
önerisinden alanı makul (%8-%65) ve puanı en yüksek olan seçilir; çıktı 0/255 tek kanallı PNG.
"""

import sys

import numpy as np
import torch
from PIL import Image
from transformers import Sam2Model, Sam2Processor

MODEL = "facebook/sam2.1-hiera-small"


def main(giris: str, cikis: str) -> None:
    cihaz = "cuda" if torch.cuda.is_available() else "cpu"
    model = Sam2Model.from_pretrained(MODEL).to(cihaz)
    islemci = Sam2Processor.from_pretrained(MODEL)
    img = Image.open(giris).convert("RGB")
    g, y = img.size
    noktalar = [[[[g * 0.5, y * 0.6], [g * 0.5, y * 0.75]]]]
    girdi = islemci(images=img, input_points=noktalar, input_labels=[[[1, 1]]], return_tensors="pt").to(cihaz)
    with torch.no_grad():
        cikti = model(**girdi, multimask_output=True)
    maskeler = islemci.post_process_masks(cikti.pred_masks.cpu(), girdi["original_sizes"])[0][0].numpy()  # (3, y, g)
    puan = cikti.iou_scores.cpu().numpy().reshape(-1)
    adaylar = [(float(puan[i]), maskeler[i] > 0) for i in range(len(maskeler)) if 0.08 < (maskeler[i] > 0).mean() < 0.65]
    secilen = max(adaylar, key=lambda a: a[0])[1] if adaylar else np.zeros((y, g), bool)
    Image.fromarray((secilen * 255).astype(np.uint8)).save(cikis)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
