"""Önceden yüklenmiş Shorts'lara kapak resmi üretir ve (UYGULA=1 ise) YouTube'da ayarlar.

Yeni Shorts'lar build.py'deki shorts_kapak ile aynı kapağı alır; bu araç eskileri aynı görünüme getirir.
- Başlık konu bankasıyla eşleşmeyen videoya dokunulmaz.
- UYGULA boşsa yalnızca kapaklar üretilir (out/analiz/kapaklar/), YouTube'a hiçbir şey gönderilmez.
- Ayarlanan videolar ve tarih out/analiz/kapak_guncelleme.json'a yazılır: sonraki analizde önce/sonra kıyası için.
Kullanım: UYGULA=1 python osmanli/araclar/eski_kapaklar.py
"""
import datetime, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OSM = os.path.dirname(HERE)
ROOT = os.path.dirname(OSM)
sys.path.insert(0, OSM)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "ortak"))
OUT = os.path.join(ROOT, "out", "analiz")


def kanca_sahnesi(konu, kategori, klasor):
    """build.py'deki kanca mantığı: kanca_anim > kanca_gorsel > kanca_sahne (varsayılan ilk sahne)."""
    import build as B
    import animasyon
    from gorsel import bul
    if konu.get("kanca_anim"):
        return {"anim": animasyon.hazirla(konu["kanca_anim"], 6.0), "anim_sure": 6.0, "anim_u": 0.85}
    if konu.get("kanca_gorsel"):
        g = bul(konu["kanca_gorsel"], kategori, klasor, set())
        if g:
            bg, fg = B.sahne_hazirla(g["yol"])
            return {"bg": bg, "fg": fg}
    sh = konu["sahneler"][konu.get("kanca_sahne", 0)]
    if sh.get("anim"):
        return {"anim": animasyon.hazirla(sh["anim"], 6.0), "anim_sure": 6.0, "anim_u": 0.85}
    g = bul(sh.get("gorsel", ["-"]), kategori, klasor, set())
    bg, fg = B.sahne_hazirla(g["yol"] if g else None)
    return {"bg": bg, "fg": fg}


def main():
    import build as B
    from upload import youtube
    from googleapiclient.http import MediaFileUpload
    from kanal_analizi import banka, norm, videolari_al
    uygula = os.environ.get("UYGULA", "").strip() in ("1", "true", "evet")
    yt = youtube()
    _, videolar = videolari_al(yt)
    eslesme = banka()
    klasor = os.path.join(OUT, "kapaklar")
    os.makedirs(klasor, exist_ok=True)
    kayit, sorunlu = [], []
    for v in videolar:
        bilgi = eslesme.get(norm(B.emojisiz(v["snippet"]["title"])))
        if not bilgi or bilgi[0] != "shorts":
            continue
        _, kat, konu = bilgi
        yol = os.path.join(klasor, f"{konu['id']}.jpg")
        try:
            B.shorts_kapak(kanca_sahnesi(konu, kat, os.path.join(ROOT, "out", "img")), kat,
                           konu.get("kapak") or B.emojisiz(v["snippet"]["title"]), yol)
        except Exception as e:
            sorunlu.append(f"{konu['id']}: kapak üretilemedi ({e})"); continue
        durum = "üretildi"
        if uygula:
            try:
                yt.thumbnails().set(videoId=v["id"], media_body=MediaFileUpload(yol, mimetype="image/jpeg")).execute()
                durum = "ayarlandı"
            except Exception as e:
                durum = f"HATA: {str(e)[:160]}"
                sorunlu.append(f"{konu['id']}: {durum}")
        kayit.append({"video": v["id"], "konu": konu["id"], "baslik": v["snippet"]["title"], "durum": durum})
        print(f"{konu['id']:<28} {durum}", flush=True)
    if uygula:
        yol = os.path.join(OUT, "kapak_guncelleme.json")
        with open(yol, "w", encoding="utf-8") as f:
            json.dump({"zaman": datetime.datetime.now(datetime.timezone.utc).isoformat(), "videolar": kayit},
                      f, ensure_ascii=False, indent=1)
    ozet = (f"\n## Eski Shorts kapakları\n\n{len(kayit)} Shorts · "
            f"{sum(1 for k in kayit if k['durum'] == 'ayarlandı')} ayarlandı · "
            f"{'uygulandı' if uygula else 'yalnızca önizleme (YouTube değişmedi)'}\n\n" +
            "".join(f"- {s}\n" for s in sorunlu))
    print(ozet)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(ozet)


if __name__ == "__main__":
    main()
