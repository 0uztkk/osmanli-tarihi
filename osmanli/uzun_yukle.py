"""Uzun videoyu (out/uzun.mp4) normal video olarak yükler ve küçük resmi (out/kucuk_resim.jpg) ayarlar."""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "ortak"))
os.environ["MADE_FOR_KIDS"] = "false"

from googleapiclient.http import MediaFileUpload  # noqa: E402
from upload import kanal_kontrol, youtube, yukle, zaten_yuklendi  # noqa: E402

OUT = os.path.join(ROOT, "out")


def main():
    with open(os.path.join(OUT, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    if meta.get("atla"):
        print("Bugün için uzun video yok (banka bitti). Yükleme yapılmadı.")
        return
    if not meta.get("sesli"):
        sys.exit("HATA: Video seslendirmesiz üretilmiş (GCP_TTS_KEY yok). Sessiz video yüklenmez.")
    yt = youtube()
    ad = kanal_kontrol(yt)
    if "mina" in ad.casefold():
        sys.exit(f"HATA: Bu token '{ad}' kanalına ait; yükleme iptal.")
    if zaten_yuklendi(yt, meta["title"]):
        print("Bu video zaten yüklenmiş:", meta["title"], "– tekrar yüklenmedi.")
        return
    vid = yukle(os.path.join(OUT, "uzun.mp4"), meta, os.environ.get("PRIVACY", "public"), yt, shorts=False)
    try:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(os.path.join(OUT, "kucuk_resim.jpg"),
                                                                    mimetype="image/jpeg")).execute()
        print("Küçük resim ayarlandı.")
    except Exception as e:   # telefon doğrulaması yoksa YouTube özel küçük resme izin vermez
        print("UYARI: Küçük resim ayarlanamadı:", e)


if __name__ == "__main__":
    main()
