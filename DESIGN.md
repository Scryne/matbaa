---
version: alpha
name: Matbaa
description: Etsy print-on-demand hattının yerel onay paneli — tasarım provası, ilan metni ve marka kapısı kanıtını tek bakışta gösterip onay/ret alır.
colors:
  masa: "#17171a"
  masa-yukseltilmis: "#212125"
  cizgi: "#34343a"
  metin: "#ecebe6"
  metin-ikincil: "#a3a19a"
  primary: "#e0483e"
  onay-yesil: "#3fb46b"
  uyari-sari: "#e2b23c"
  odak: "#8fb3ff"
  kagit: "#f3efe6"
  kagit-koyu: "#ebe5d8"
  kagit-yuzey: "#fbf9f4"
  kagit-cizgi: "#e0d9ca"
  murekkep: "#1f1d1a"
  murekkep-ikincil: "#605b52"
  kagit-kirmizi: "#c2392a"
  kagit-yesil: "#2a7f51"
typography:
  pano-baslik:
    fontFamily: "'DM Serif Display', Georgia, serif"
    fontSize: 54px
    lineHeight: 1.06
  govde:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: 15px
    lineHeight: 1.5
  etiket:
    fontFamily: "ui-monospace, 'Cascadia Mono', Consolas, monospace"
    fontSize: 12px
    letterSpacing: 0.04em
  baslik:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"
    fontSize: 20px
    fontWeight: 650
rounded:
  kart: 10px
  dugme: 8px
spacing:
  birim: 8px
  kart-ic: 20px
---

# Matbaa

## Overview

Tek kullanıcı (Scryne), haftada bir, yerelde (`127.0.0.1`) açılan bir onay paneli. İş: 30 tasarımlık kuyruğu 10 dakikada bitirmek.
Bu yüzden ekran tek tasarıma odaklanır, klavye birinci sınıf yoldur (A onay, R ret, ← → gezinme).

- **Mood:** baskı atölyesinin prova masası — nötr koyu zemin, kâğıt gibi duran prova kartları, düzeltme kalemi kırmızısı.
- **Farklılaştırıcı detay:** tasarım her zaman gerçek kumaş renkleri üzerinde, yan yana prova olarak görünür (açık ve koyu tişört);
  kullanıcı tasarımı değil, satılacak ürünü onaylar.
- **Global estetikten bilinçli sapma:** dark glassmorphism burada kullanılmaz. Gradient mesh ve `backdrop-filter`, kumaş rengi
  değerlendirmesini bozar; zemin nötr (`masa`) ve düz kalır.

## Colors

`masa` hafif sıcak nötr koyu: kumaş renklerini (siyah, lacivert, krem) yanıltmayacak kadar renksiz. `primary` (prova kırmızısı) yalnız ret ve
marka-kapısı uyarılarında; `onay-yesil` yalnız onay aksiyonunda. Kumaş renkleri tasarım değil veridir (`config/urunler.toml`).

## Typography

Sistem fontu: panel çevrimdışı ve yerel, dış font yüklemesi yok. Kanıt ve sayılar (marka seri numarası, Jev olasılıkları, net kâr)
`etiket` (monospace) ile; okunan metin `govde` ile.

## Components

- **Prova kartı:** tasarım PNG'si, kumaş renginde dolu bir tişört silüetinin göğsüne bindirilir; açık ve koyu prova yan yana.
- **Kanıt şeridi:** IP kapısı sonucu (USPTO adayları, benzer markalar, Jev olasılıkları) — onay kararından önce görünür, gizlenmez.
- **Aksiyon çubuğu:** ekranın altında sabit; Onayla / Reddet; ret nedeni hızlı seçimle (okunmuyor, espri zayıf, marka şüphesi, tekrar).

## Do's and Don'ts

- Kumaş provasını küçültüp kenara itme; ekranın en büyük öğesi odur.
- Onay butonu klavye kısayolu olmadan eklenmez.
- Toplu "hepsini onayla" yok: her tasarım tek tek görülür (marka kapısı insan gözünü de ister, K-13).

## Pano (takip sayfası, 2026-10-15)

Açılış sayfası (`/`) Scryne'ın her sabah oturum açınca gördüğü dükkân panosu; onay masası `/onay`'da kalır.

- **Mood:** matbaa kâğıdı. Açık temada sıcak kâğıt zemin (`kagit`), mürekkep siyahı metin (`murekkep`), tek vurgu `kagit-kirmizi`
  (prova kırmızısının kâğıt üstünde 4.5:1 sağlayan tonu). Koyu temada (`prefers-color-scheme: dark`) onay masasının `masa` paleti.
  Onay masasındaki "nötr zemin" gerekçesi (kumaş rengi yargısı) panoda yok; burada ürün fotoğrafı Etsy'nin beyaz zeminiyle gelir.
- **Tipografi:** manşet ve bölüm başlıkları DM Serif Display (projede OFL, `/font/serif` yerelden), sayılar monospace tabular.
- **Farklılaştırıcı detay:** "Sıradaki" kartının köşelerinde baskı kesim işaretleri, tarih satırında kayıt işareti (crosshair).
- **Düzen sırası:** asimetrik giriş (tek cümlelik durum manşeti + sıradaki iş/senden beklenenler) → tam genişlik vitrin bandı
  (gerçek ürün fotoğrafları) → bento (para ve görüntülenme geniş, hat/Pinterest/koşu dar) → siparişler + yol haritası / etkinlik.
- **Yapma:** emoji, renkli sol kenar şeridi, her kutuya gölge; olay akışına eşitleme kayıtlarını (öznitelik, vitrin, galeri) dökme.

