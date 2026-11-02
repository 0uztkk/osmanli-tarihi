"""out/video.mp4 dosyasını YouTube'a yükler. Anahtarlar GitHub Secrets'tan ortam değişkeni olarak gelir."""
import json, os, sys, time

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")


def youtube():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube.readonly"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def cocuklara_yonelik():
    """Bu kanalda varsayılan: çocuklara yönelik DEĞİL."""
    return os.environ.get("MADE_FOR_KIDS", "false").strip().lower() not in ("false", "0", "hayir", "hayır", "no")


def kanal_kontrol(yt):
    """Yanlış kanala yüklemeyi engeller: BEKLENEN_KANAL verilmişse kanal adı onu içermeli."""
    ch = yt.channels().list(part="snippet", mine=True).execute()
    ad = ch["items"][0]["snippet"]["title"] if ch.get("items") else ""
    print("Kanal:", ad or "bulunamadı")
    beklenen = os.environ.get("BEKLENEN_KANAL", "").strip()
    if beklenen and beklenen.casefold() not in ad.casefold():
        sys.exit(f"HATA: token '{ad}' kanalına ait, beklenen '{beklenen}'. Yükleme iptal edildi.")
    return ad


def zaten_yuklendi(yt, baslik, adet=15):
    """Kanalın son yüklemelerinde aynı başlık varsa True. Gecikmeli zamanlanmış görevle elle başlatılan
    görev üst üste gelirse aynı videonun iki kez yüklenmesini engeller."""
    try:
        ch = yt.channels().list(part="contentDetails", mine=True).execute()
        pl = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        items = yt.playlistItems().list(part="snippet", playlistId=pl, maxResults=adet).execute().get("items", [])
        return any(i["snippet"]["title"].strip() == baslik.strip() for i in items)
    except Exception as e:
        print("UYARI: Önceki yüklemeler kontrol edilemedi:", e)
        return False


def yukle(path, meta, privacy="public", yt=None, shorts=True):
    """Videoyu yükler (çocuklara yönelik işareti MADE_FOR_KIDS'e göre), video kimliğini döner."""
    yt = yt or youtube()

    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta["tags"],
            "categoryId": meta["categoryId"],
            "defaultLanguage": "tr",
            "defaultAudioLanguage": "tr",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": cocuklara_yonelik(),
        },
    }
    media = MediaFileUpload(path, mimetype="video/mp4",
                            chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"Yükleniyor: %{int(status.progress() * 100)}", flush=True)
    vid = resp["id"]
    url = ("https://youtube.com/shorts/" if shorts else "https://youtu.be/") + vid
    print("Yüklendi:", url)
    print("Durum:", resp.get("status", {}).get("privacyStatus"))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"### Yüklendi\n\n[{meta['title']}]({url})\n\n")
    return vid


def main():
    with open(os.path.join(OUT, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    yt = youtube()
    kanal_kontrol(yt)
    yukle(os.path.join(OUT, "video.mp4"), meta, os.environ.get("PRIVACY", "public"), yt)


if __name__ == "__main__":
    main()
