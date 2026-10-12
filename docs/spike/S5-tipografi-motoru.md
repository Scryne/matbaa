---
title: S5 — tipografik tasarım motoru ve kalite kapıları
created: 2026-10-13
type: spike
status: tamamlandi
---
# S5 — Tipografik tasarım motoru

**Soru:** Yazı ağırlıklı POD tasarımları otomatik, baskıya hazır ve okunur üretilebilir mi; maliyeti ne?
**Karar sebebi:** Makinede ücretli görsel API anahtarı yok; yerelde RTX 4060 (8 GB). Yazı ağırlıklı tasarımda AI görsel
yazım hatası, hale ve upscale sorunu getirir (araştırma 04). Bu yüzden yazı **kodla** çiziliyor.

## Kurulan
- `src/matbaa/tasarim/yazi.py` — HarfBuzz şekillendirme + fontTools: metin → vektör yol (kerning, ligatür), ölçülebilir genişlik,
  fontta olmayan karakterde `EksikGlif` (sessiz kutu yok).
- `sablonlar.py` — dört şablon: `yigin` (blok satırlar), `kavis` (kolej tarzı yay + düz satır), `rozet` ("EST." çizgili),
  `el_yazisi_blok` (blok + oyulmuş el yazısı). Tuval 4500x5400 (15x18 in @300 DPI), tek renk, iki mürekkep (koyu/açık kumaş).
- `render.py` — resvg ile SVG → şeffaf PNG; sistem fontu yüklenmez (yazı yol), her makinede aynı çıktı.
- `kapilar.py` — boyut, kenar payı (≥60 px), serbest yarı saydamlık (hale), ince çizgi (r=3 px açma kaybı), kontrast (WCAG ≥3),
  en küçük yazı (≥150 px), OCR okunurluk (RapidOCR, iki ölçek, ≥%80 kelime).
- Fontlar: Google Fonts'tan 11 OFL font, lisans dosyalarıyla `varliklar/fontlar/`.

## Ölçülen
- Tasarım başına ~6 sn (iki mürekkep, render + kapılar + OCR), **maliyet $0**.
- İlk tur: 20/20 kapı geçti ama göz kontrolü 3 gerçek kusur buldu (el yazısı bloğu okunmaz yapıyor, kavis ortası çok küçük ve
  yay uçlarına yakın, ikincil satırlar okunamayacak kadar küçük). Kapılar baskı tekniğini ölçüyordu, okunurluğu değil.
- Düzeltme: kavis yeniden kuruldu (orta satır yay uçlarının altından başlar, çakışma inşa gereği yok), ikincil satır alt sınırı,
  el yazısı bloğun alt kenarına alındı; yeni kapılar: en küçük yazı + OCR.
- OCR'ın iki tuzağı ölçüldü: 1600 px'de dev harfler algılanmıyor (iki ölçek birleşimi), yön sınıflandırıcısı el yazısını ters
  okuyor (kapatıldı). Kavisli yazıyı OCR okuyamıyor → kavisli satır OCR'dan muaf, geometrisi korur.
- İkinci tur: 16/20 geçti; düşen 4'ü el yazısının bloğa bindiği iki tasarım — göz kontrolüyle aynı yargı.
- `tests/test_kapilar.py`: 9 test (her biri tek kusurlu bozuk örnek). Mutasyon: altı eşiğin her biri tek tek etkisizleştirildi,
  **6/6 yakalandı**.

## Açık
- `el_yazisi_blok` zayıf: üretimde ya düzeltilir ya şablon havuzundan çıkar.
- Grafik öğe (ikon, illüstrasyon) gereken tasarımlar bu motorun dışında; AI görsel katmanı ayrı spike.
- Görsel çeşitlilik: 4 şablon × 11 font aynı mağazada tekrar eden görünüm yaratabilir → şablon havuzu büyümeli (finalizasyonda).
