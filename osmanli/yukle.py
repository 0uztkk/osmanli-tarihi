"""Osmanlı kanalına yükler: out/video.mp4 + out/meta.json

Ortak mina/upload.py kodunu kullanır; farkları:
- Video çocuklara yönelik DEĞİL olarak işaretlenir.
- Token yanlışlıkla Mina ile Efe kanalına aitse yükleme iptal edilir.
- BEKLENEN_KANAL (GitHub değişkeni KANAL_ADI) verilmişse kanal adı onu içermelidir.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "ortak"))
os.environ["MADE_FOR_KIDS"] = "false"

from upload import kanal_kontrol, youtube, yukle, zaten_yuklendi  # noqa: E402

OUT = os.path.join(ROOT, "out")


def main():
    with open(os.path.join(OUT, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    if not meta.get("sesli"):
        sys.exit("HATA: Video seslendirmesiz üretilmiş (GCP_TTS_KEY yok). Sessiz video yüklenmez.")
    yt = youtube()
    ad = kanal_kontrol(yt)
    if "mina" in ad.casefold():
        sys.exit(f"HATA: Bu token '{ad}' kanalına ait. Osmanlı videosu çocuk kanalına yüklenmez; "
                 "YT_REFRESH_TOKEN secret'ını yeni kanalın hesabıyla alın.")
    if zaten_yuklendi(yt, meta["title"]):
        print("Bu video zaten yüklenmiş:", meta["title"], "– tekrar yüklenmedi.")
        return
    vid = yukle(os.path.join(OUT, "video.mp4"), meta, os.environ.get("PRIVACY", "public"), yt)
    kapak = os.path.join(OUT, "kapak.jpg")
    if vid and os.path.exists(kapak):
        try:   # YouTube rastgele bir ara kare (yarım altyazı) seçmesin
            from googleapiclient.http import MediaFileUpload
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(kapak, mimetype="image/jpeg")).execute()
            print("Kapak resmi ayarlandı.")
        except Exception as e:   # telefon doğrulaması yoksa ya da Shorts'ta izin verilmezse video yine yüklenmiş olur
            print("UYARI: Kapak resmi ayarlanamadı:", e)


if __name__ == "__main__":
    main()
