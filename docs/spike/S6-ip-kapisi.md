---
title: S6 — IP kapısı (USPTO + TypeSafe/Jev)
created: 2026-10-13
type: spike
status: tamamlandi
---
# S6 — Marka/eser/ünlü gönderme kapısı

**Soru:** Bir tişört ifadesi yayından önce otomatik olarak "markaya, esere, ünlüye, takıma, şarkıya çarpıyor mu" diye elenebilir mi?
**Neden önemli:** Etsy marka/telif bildiriminde ilanı kaldırır, tekrarında mağazayı kapatır, yeni mağaza "ilişkili hesap" diye reddedilebilir
(araştırma 01, 06). Hukuki değerlendirme değil, platform riskini düşüren filtre.

## Kurulan
1. **USPTO verisi:** `scripts/uspto_guncelle.py` → `veri/uspto_25_canli.parquet`: ABD giyim sınıfında (25) canlı **402.746** marka
   (357.187 benzersiz normal biçim), 7 MB, ~2 dk. Kaynak: HF `illeatmyhat/uspto-trademarks` (USPTO TRTYRAP + TRTDXFAP'tan, kamu malı,
   30.09.2026'ya kadar). Resmî ODP API'si ve TSDR anahtar istiyor (canlı 401) → anahtar USPTO hesabıyla Scryne'da; alınınca kaynak değişir.
2. **Kod katmanı** (`src/matbaa/ip/marka.py`): kesin ret — ifadenin tamamı marka; bitişik yazılınca marka (BOY MOM ↔ BOYMOM);
   çok kelimeli marka ifadenin en az yarısı; uydurma tek kelime marka (zipf < 1). Gündelik kelime markaları ret değil "aday".
   Tek kelimesi değiştirilmiş markaları (`JUST * IT`) "benzer" olarak döner; iki kelimede yalnız sesteş takas (PEARL → PURL).
3. **Anlamsal katman** (`src/matbaa/ip/anlam.py`, Jev): tek istekte "kaynak" Choice'u (özgün / deyim kelime oyunu / şarkı / ekran-kitap /
   marka-slogan / ünlü / takım) + 4 Noul (marka, karakter, kişi, takım). Benzer marka varsa ikinci istek: kanıt olarak benzer markalar
   verilir, "ünlü olanın parodisi mi" sorulur. Kod ünlülüğü bilemez, Jev kanıtın ne dediğine bakar.
4. **Kapı** (`src/matbaa/ip/kapi.py`): satırlar + tüm ifade → önce USPTO, sonra Jev; sonuç `temiz` / `ret` / `insan`, ham sinyaller kayıtta.

## Ölçülen (jev-1.13.0)
| Deneme | Kaçan riskli (25) | Yanlış ret (25) |
|---|---|---|
| 5 Noul, eşik 0,5 | 0 | 9 — "şarkı" sorusu deyim kelime oyunlarını gönderme sanıyor |
| Tek "kaynak" Choice | 8 | 1 — kelimesi değiştirilmiş parodileri kaçırıyor (Just Dink It, Dink Different, Netflix And Knit, Purl Jam) |
| Choice ∨ 4 Noul | 3 | 2 |
| "Parodi mi" Noul'u | 0 | 17 — ayırt edici değil, bırakıldı |
| Benzer marka + "ünlü mü" (yalnız takas eşleşenler) | gerçek parodiler 0,73–0,95 | sıradan kalıplar ≤ 0,39 (bir ara değer 0,57 → insan) |
| **Uçtan uca kapı (USPTO + Jev)** | **0** | 7 → ama 5'i gerçekten canlı marka: etiketim yanlıştı |

- **Asıl bulgu:** POD'un en yaygın kalıp ifadeleri giyim sınıfında başkalarına tescilli: BORN TO FISH FORCED TO WORK, I CANT I HAVE
  PICKLEBALL, LIFE IS BETTER, HOOK LINE AND SINKER, DINK DIFFERENT, JUST KEEP SWIMMING, SHAKE IT OFF, HAKUNA MATATA, IN MY TEACHER ERA
  (S5'teki 09 tasarımı!), REEL COOL, BASKETBALL IS MY THERAPY. Kapı olmasa "trend ifade" üreten bir hat ilk haftada şikâyet toplardı.
- Gerçek yanlış ret 1–3: "Paddle Battle Royale" (Jev, ekran-kitap 0,65), "One More Cast" / "Hooked On Grandkids" (iki kelimelik gündelik
  marka ifadenin 2/3'ü). Yanlış ret ucuz: yerine yeni ifade üretilir.
- Süre: 50 ifade 15 sn (~0,3 sn/ifade); maliyet ifade başı < $0,0001.
- **Sınır:** eşikler bu 50 ifadeye bakılarak seçildi; canlıda her kararın ham sinyali kaydedilir, ilk 200 kararda yeniden kalibre edilir.
  Jev'in "ünlü" bilgisi eğitim verisiyle sınırlı; çok yeni bir şarkı/dizi kaçabilir.

## Testler
`tests/test_marka.py` (11): elle kurulmuş küçük dizinle her ret yolu, aday, sesteş takas, noktalama.
