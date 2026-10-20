"""Çok platformlu paylaşım (K-38): kuyruk, takvim, kaçırılan saat, zamanlı/anında gönderme, hata ve elle paylaşılanlar.
Sahte istemciler; ağ yok."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from matbaa import db, paylasim, tiktok

SIMDI = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)  # ABD doğu 11:00 (EDT)
AYAR = {
    "tiktok": {"saatler": ["12:00", "19:00"], "ileri_gun": 7},
    "instagram": {"saatler": ["11:00", "20:00"], "ileri_gun": 0},
}


class Sahte:
    def __init__(self, hata: Exception | None = None):
        self.giden: list[tuple[paylasim.Is, bool]] = []
        self.hata = hata

    def gonder(self, is_, zamanli):
        if self.hata:
            raise self.hata
        self.giden.append((is_, zamanli))
        return paylasim.Sonuc("zamanlandi" if zamanli else "yayinda", f"d{is_.gonderi_id}", None)


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", tmp_path / "t.db")
    monkeypatch.setattr(paylasim, "KOK", tmp_path)
    c = db.baglan()
    # Üç tasarım: iki yazılı (biri TikTok'a elle yüklendi), bir çizimli; her birinin videosu.
    for n, (sablon, durum, plan) in enumerate(
        [("gunes", "paylasildi", "2026-10-19T23:00+00:00"), ("gunes", "hazir", None), ("cizim", "hazir", None)], start=1
    ):
        i = db.ifade_ekle(c, "fishing", [f"GONE FISHING {n}"])
        db.kapi_yaz(c, i, "temiz", [], [])
        tid = db.tasarim_ekle(c, i, sablon, [])
        for urun, lid in (("susleme", f"9{tid}"), ("tisort" if sablon != "cizim" else "tisort_cizim", f"1{tid}")):
            c.execute("INSERT INTO urun (tasarim_id, urun, durum, etsy_listing_id) VALUES (?, ?, 'aktif', ?)", (tid, urun, lid))
        (tmp_path / f"v{n}").mkdir()
        (tmp_path / f"v{n}" / "video.mp4").write_bytes(b"x")
        c.execute(
            """INSERT INTO tiktok_video (tasarim_id, tur, durum, klasor, hook, aciklama, etiketler, plan, olusturma)
               VALUES (?, 'urun', ?, ?, 'Hook', 'Find it at HobbyHeartPrints on Etsy.', ?, ?, ?)""",
            (tid, durum, f"v{n}", json.dumps(["fishinggifts", "giftsfordad"]), plan, f"2026-10-1{n}"),
        )
    c.commit()
    return c


def test_her_video_her_platforma_bir_kez_elle_yuklenen_tiktoka_gitmez(c):
    assert paylasim.kuyruga_ekle(c, ["tiktok", "instagram"]) == 6
    assert paylasim.kuyruga_ekle(c, ["tiktok", "instagram"]) == 0  # ikinci koşu yinelemez
    durum = {(r[0], r[1]): r[2] for r in c.execute("SELECT video_id, platform, durum FROM gonderi")}
    assert durum[(1, "tiktok")] == "elle" and durum[(1, "instagram")] == "bekliyor"


def test_ai_videosu_yalniz_tiktoka_yayindan_kalkan_tasarim_hic(c):
    c.execute("UPDATE tiktok_video SET ai = 1 WHERE id = 2")
    c.execute("UPDATE urun SET durum = 'kaldirildi' WHERE tasarim_id = 3")
    paylasim.kuyruga_ekle(c, ["tiktok", "instagram"])
    assert sorted(map(tuple, c.execute("SELECT video_id, platform FROM gonderi"))) == [
        (1, "instagram"), (1, "tiktok"), (2, "tiktok"),
    ]  # fmt: skip


def test_takvim_cizimli_once_dolu_saat_atlanir_kacirilan_kayar(c):
    paylasim.kuyruga_ekle(c, ["tiktok"])
    paylasim.planla(c, ["tiktok"], SIMDI, AYAR)
    plan = dict(c.execute("SELECT video_id, plan FROM gonderi WHERE platform = 'tiktok'").fetchall())
    # 1 elle (10-19 akşamı); bugün ABD 12:00 (16:00 UTC) çizimli #3'e, 19:00 yazılı #2'ye
    assert plan == {1: "2026-10-19T23:00+00:00", 3: "2026-10-20T16:00+00:00", 2: "2026-10-20T23:00+00:00"}
    gec = SIMDI + timedelta(hours=12)  # bilgisayar kapalıydı: ikisinin de saati 3 saatten fazla geçti
    paylasim.planla(c, ["tiktok"], gec, AYAR)
    yeni = dict(c.execute("SELECT video_id, plan FROM gonderi WHERE platform = 'tiktok' AND durum = 'bekliyor'").fetchall())
    assert yeni == {3: "2026-10-21T16:00+00:00", 2: "2026-10-21T23:00+00:00"}  # üst üste değil, sıradaki saatlere


def test_zamanlayan_platform_ufukta_zamanli_digeri_saati_gelince(c):
    tk, ig = Sahte(), Sahte()
    s = paylasim.paylas(c, {"tiktok": tk, "instagram": ig}, SIMDI, yazdir=lambda *_: None, ayarlar=AYAR)
    assert s["zamanlandi"] == 2 and s["yayinda"] == 0  # TikTok iki bekleyeni 7 gün ufkunda zamanlı; IG'nin saati gelmedi
    assert all(z for _, z in tk.giden) and not ig.giden
    assert c.execute("SELECT durum FROM tiktok_video WHERE id = 3").fetchone()[0] == "paylasildi"  # pano kartından düşer
    is_ = tk.giden[0][0]
    assert is_.video.name == "video.mp4" and is_.link == "https://www.etsy.com/listing/13" and "#fishinggifts" in is_.metin
    saat = datetime.fromisoformat(c.execute("SELECT min(plan) FROM gonderi WHERE platform = 'instagram'").fetchone()[0])
    paylasim.paylas(c, {"tiktok": tk, "instagram": ig}, saat + timedelta(minutes=5), yazdir=lambda *_: None, ayarlar=AYAR)
    assert len(ig.giden) == 1 and not ig.giden[0][1]  # saati gelen tek gönderi, hemen
    assert "link in bio" in ig.giden[0][0].metin and "etsy.com/listing" not in ig.giden[0][0].metin


def test_hata_yeniden_denenir_sonra_alarm(c):
    bozuk = Sahte(RuntimeError("401 token"))
    for _ in range(paylasim.MAKS_DENEME):
        s = paylasim.paylas(c, {"tiktok": bozuk}, SIMDI, yazdir=lambda *_: None, ayarlar=AYAR)
    assert s["alarm"] and "401 token" in s["alarm"][0]
    assert {r[0] for r in c.execute("SELECT durum FROM gonderi WHERE platform = 'tiktok' AND durum != 'elle'")} == {"hata"}


def test_pano_karti_otomatik_gidenleri_gostermez(c):
    assert {h["id"] for h in tiktok.ozet(c, SIMDI)["hazir"]} == {2, 3}
    paylasim.kuyruga_ekle(c, ["tiktok"])
    assert tiktok.ozet(c, SIMDI)["hazir"] == []


def test_metinler_platform_link_kurali():
    m = paylasim.metinler("Funny gift.", ["fishinggifts"], "https://www.etsy.com/listing/5")
    assert "etsy.com" not in m["tiktok"] and "etsy.com" not in m["instagram"]
    assert "https://www.etsy.com/listing/5" in m["facebook"] and m["youtube"].endswith("#shorts")


# --- Zernio istemcisi (sahte HTTP) ---


class ZernioSahte:
    """Zernio uç noktalarının sahte hali: istekleri kaydeder."""

    def __init__(self):
        self.istekler: list[httpx.Request] = []
        self.panolar = [{"id": "b1", "name": "Fishing Gifts"}]

    def __call__(self, r: httpx.Request) -> httpx.Response:
        self.istekler.append(r)
        yol = r.url.path
        if yol.endswith("/accounts"):
            return httpx.Response(200, json={"accounts": [
                {"_id": "tt1", "platform": "tiktok", "isActive": True},
                {"_id": "pn1", "platform": "pinterest", "isActive": True},
                {"_id": "x9", "platform": "threads", "isActive": True},
            ]})  # fmt: skip
        if yol.endswith("/media/presign"):
            return httpx.Response(200, json={"uploadUrl": "https://depo.test/yukle", "publicUrl": "https://depo.test/v.mp4"})
        if r.url.host == "depo.test":
            return httpx.Response(200)
        if yol.endswith("/pinterest-boards") and r.method == "GET":
            return httpx.Response(200, json={"boards": self.panolar})
        if yol.endswith("/pinterest-boards"):
            return httpx.Response(201, json={"board": {"id": "b2", "name": json.loads(r.content)["name"]}})
        if yol.endswith("/posts"):
            return httpx.Response(201, json={"post": {"_id": f"p{len(self.istekler)}"}})
        return httpx.Response(404)


@pytest.fixture
def zs():
    from matbaa.entegrasyon.zernio import Zernio

    s = ZernioSahte()
    return s, Zernio("sk_test", http=httpx.Client(transport=httpx.MockTransport(s)), bekle=lambda *_: None)


def _govdeler(s, yol="/posts"):
    return [json.loads(r.content) for r in s.istekler if r.url.path.endswith(yol)]


def test_zernio_yalniz_bagli_ve_bilinen_platformlar_tiktok_ayarlari_tam(c, zs):
    s, z = zs
    ist = paylasim.istemciler(z)
    assert sorted(ist) == ["pinterest", "tiktok"]  # threads bilinmiyor, IG bağlı değil
    paylasim.paylas(c, ist, SIMDI, yazdir=lambda *_: None, ayarlar=AYAR | {"pinterest": {"saatler": ["10:00"], "ileri_gun": 7}})
    tk = [g for g in _govdeler(s) if g["platforms"][0]["platform"] == "tiktok"]
    assert len(tk) == 2 and tk[0]["scheduledFor"].endswith("Z") and "publishNow" not in tk[0]
    ayar = tk[0]["tiktokSettings"]
    assert ayar["privacy_level"] == "PUBLIC_TO_EVERYONE" and ayar["express_consent_given"] and ayar["content_preview_confirmed"]
    assert ayar["commercialContentType"] == "brand_organic" and ayar["video_made_with_ai"] is False
    assert tk[0]["mediaItems"] == [{"type": "video", "url": "https://depo.test/v.mp4"}]
    put = [r for r in s.istekler if r.url.host == "depo.test"]
    assert put and "authorization" not in put[0].headers  # yükleme adresine anahtar gitmez
    posts = [r for r in s.istekler if r.url.path.endswith("/posts")]
    assert posts[0].headers["authorization"] == "Bearer sk_test" and posts[0].headers["idempotency-key"].startswith(
        "matbaa-gonderi-"
    )
    pn = [g for g in _govdeler(s) if g["platforms"][0]["platform"] == "pinterest"]
    assert pn[0]["platforms"][0]["platformSpecificData"]["boardId"] == "b1"  # "Fishing Gifts" panosu var
    assert pn[0]["platforms"][0]["platformSpecificData"]["link"].startswith("https://www.etsy.com/listing/")


def test_zernio_207_hata_sayilir(zs):
    from matbaa.entegrasyon import zernio

    s, z = zs
    z.http = httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"accounts": [{"_id": "a", "platform": "tiktok"}]}) if r.url.path.endswith("/accounts")
        else httpx.Response(207, json={"post": {"_id": "p"}})
    ))  # fmt: skip
    with pytest.raises(zernio.ApiHatasi):
        z.gonder("tiktok", "m", [], None, {}, "k")


def test_ilan_pinleri_zernioda_ayri_saatlerde_eksik_pano_acilir(c, zs):
    from matbaa import pinterest

    s, z = zs
    for n, (lid, pano) in enumerate([("13", "Fishing Gifts"), ("93", "Christmas Ornaments"), ("777", "Fishing Gifts")]):
        c.execute(
            """INSERT INTO pin (etsy_listing_id, gorsel_sira, tasarim_id, urun, gorsel_url, baslik, aciklama, pano, durum)
               VALUES (?, 0, 1, 'tisort', ?, 'Baslik', 'Aciklama', ?, 'bekliyor')""",
            (lid, f"https://i.etsystatic.com/{n}.jpg", pano),
        )
    c.commit()
    sonuc = pinterest.zernio_gonder(c, z, SIMDI, yazdir=lambda *_: None)
    assert sonuc == {"zamanlandi": 2, "hata": 0}  # 777 aktif ilan değil: atlandı
    assert c.execute("SELECT durum FROM pin WHERE etsy_listing_id = '777'").fetchone()[0] == "atlandi"
    g = _govdeler(s)
    assert [x["platforms"][0]["platformSpecificData"]["boardId"] for x in g] == ["b1", "b2"]  # süs panosu açıldı
    assert g[0]["mediaItems"] == [{"type": "image", "url": "https://i.etsystatic.com/0.jpg"}]
    yayin = [r[0] for r in c.execute("SELECT yayin FROM pin WHERE durum = 'verildi' ORDER BY yayin")]
    assert yayin == ["2026-10-20T17:00:00", "2026-10-20T21:00:00"]  # 15:00 UTC'den sonraki ilk iki Zernio saati
    assert pinterest.zernio_gonder(c, z, SIMDI, yazdir=lambda *_: None)["zamanlandi"] == 0  # ikinci koşu yinelemez


def test_gunluk_adim_anahtarsiz_atlar_bagliyken_video_ve_pin_yollar(c, zs, monkeypatch):
    monkeypatch.delenv("ZERNIO_API_KEY", raising=False)
    assert "atlandi" in paylasim.gunluk_adim(c, SIMDI, yazdir=lambda *_: None)
    s, z = zs
    r = paylasim.gunluk_adim(c, SIMDI, yazdir=lambda *_: None, z=z)
    assert r["platform"] == ["pinterest", "tiktok"] and r["alarm"] == [] and "ilan_pini" in r


def test_durum_yoklama_yayinlanan_adres_alir_reddedilen_alarm(c):
    paylasim.kuyruga_ekle(c, ["tiktok"])
    c.execute(
        "UPDATE gonderi SET durum = 'zamanlandi', dis_id = 'p' || video_id, plan = '2026-10-20T10:00+00:00' WHERE durum = 'bekliyor'"
    )

    class Z:
        def gonderi(self, pid):
            if pid == "p2":
                return {
                    "status": "published",
                    "platforms": [{"status": "published", "platformPostUrl": "https://tiktok.com/v/2"}],
                }
            return {"status": "failed", "platforms": [{"status": "failed", "errorMessage": "video too short"}]}

    y = paylasim.durum_yokla(c, Z(), SIMDI, yazdir=lambda *_: None)
    assert y["yayinda"] == 1 and y["hata"] == 1 and "too short" in y["alarm"][0]
    assert c.execute("SELECT url FROM gonderi WHERE video_id = 2").fetchone()[0] == "https://tiktok.com/v/2"
