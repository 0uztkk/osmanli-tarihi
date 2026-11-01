"""Wikimedia Commons'tan YALNIZCA kamu malı (public domain / CC0) görsel bulur ve indirir.

Eski minyatürler ve tablolar (Levni, Matrakçı, Vanmour, Zonaro...) kamu malıdır; telif riski yoktur.
Lisansı kamu malı olmayan hiçbir görsel kabul edilmez. Bulunamazsa None döner,
video o sahnede yazılı/desenli arka plana geçer.
"""
import hashlib, html, json, os, re, sys, time, urllib.parse, urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = "OsmanliShortsBot/1.0 (https://github.com/efeeminaa1/mina-ile-efe; otomatik egitim videolari)"
GENISLIK = 1280   # Wikimedia'nın standart küçük resim genişliklerinden biri

# Kategoriye göre son çare aramaları
YEDEK = {
    "savaslar": ["Ottoman army miniature", "Janissaries miniature", "Ottoman cavalry miniature", "Ottoman siege miniature"],
    "saray": ["Topkapi Palace painting", "Levni miniature", "Ottoman court miniature", "Topkapi Palace interior"],
    "kisiler": ["Ottoman sultan miniature", "Ottoman manuscript", "Istanbul old painting", "Ottoman calligraphy"],
}


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def kamu_mali(meta):
    """extmetadata'ya göre kamu malı mı? Emin olunamayan her şey reddedilir."""
    meta = {k: v if isinstance(v, dict) else {} for k, v in meta.items()} if isinstance(meta, dict) else {}
    lic = (meta.get("LicenseShortName", {}).get("value") or "").lower()
    lic2 = (meta.get("License", {}).get("value") or "").lower()
    if "public domain" in lic or lic.startswith("pd") or "cc0" in lic or lic2.startswith("pd") or lic2 == "cc0":
        return True
    return False


def sanatci(meta):
    meta = meta if isinstance(meta, dict) else {}
    if not isinstance(meta.get("Artist"), dict):
        return ""
    a = meta.get("Artist", {}).get("value") or ""
    a = html.unescape(re.sub(r"<[^>]+>", "", a)).strip()
    a = re.sub(r"\s+", " ", a).split(":")[0].split(" (")[0].strip(" ,;")
    return a[:40] if a and "unknown" not in a.lower() and "bilinmiyor" not in a.lower() else ""


def ara(sorgu, limit=12, genislik=GENISLIK):
    """Sorgu için uygun adayları (en alakalı önce) döner: [{baslik, url, w, h, sanatci}]"""
    p = {
        "action": "query", "format": "json", "formatversion": "2", "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": str(genislik),
        "iiextmetadatafilter": "LicenseShortName|License|Artist",
    }
    if sorgu.startswith("File:"):   # elle seçilmiş belirli bir dosya
        p["titles"] = sorgu
    else:
        p.update({"generator": "search", "gsrsearch": f"{sorgu} filetype:bitmap",
                  "gsrnamespace": "6", "gsrlimit": str(limit)})
    try:
        veri = json.loads(_get(API + "?" + urllib.parse.urlencode(p)))
    except Exception as e:
        print(f"  Commons araması başarısız ({sorgu}): {e}", file=sys.stderr)
        return []
    sayfalar = sorted(veri.get("query", {}).get("pages", []), key=lambda x: x.get("index", 99))
    sonuc = []
    for s in sayfalar:
        ii = (s.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata")
        if not isinstance(meta, dict):   # Commons bazen boş liste döndürüyor
            meta = {}
        if ii.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if ii.get("width", 0) < 600 or ii.get("height", 0) < 450:
            continue
        if not kamu_mali(meta):
            continue
        sonuc.append({"baslik": s["title"], "url": ii.get("thumburl") or ii.get("url"),
                      "w": ii["width"], "h": ii["height"], "sanatci": sanatci(meta),
                      "sayfa": ii.get("descriptionurl", "")})
    return sonuc


def bul(sorgular, kategori, klasor, kullanilan=None):
    """Sorgular sırayla denenir; kullanılmamış ilk kamu malı görsel indirilir.
    Döner: {"yol", "baslik", "sanatci", "sayfa"} ya da None."""
    kullanilan = kullanilan if kullanilan is not None else set()
    os.makedirs(klasor, exist_ok=True)
    sorgular = list(sorgular)
    if not sorgular or sorgular == ["-"]:
        return None   # bu sahne bilerek yazılı sahne
    elle = [q for q in sorgular if q.startswith("File:")]
    # Elle seçilmiş dosya varsa yalnızca o denenir: bulunamazsa rastgele bir tablo yerine yazılı sahne
    # gösterilir; çünkü genel aramalar başka bir olayın görselini getirebilir.
    deneme = elle if elle else sorgular + YEDEK.get(kategori, [])
    yedek_aday = None
    for sorgu in deneme:
        for aday in ara(sorgu):
            if aday["baslik"] in kullanilan:
                yedek_aday = yedek_aday or aday   # tekrar kullanmak, hiç görsel olmamasından iyidir
                continue
            sonuc = indir(aday, klasor)
            if sonuc:
                kullanilan.add(aday["baslik"])
                print(f"  Görsel: {aday['baslik']}  ← '{sorgu}'", file=sys.stderr)
                return sonuc
        time.sleep(0.2)
    if yedek_aday:
        return indir(yedek_aday, klasor)
    return None


def indir(aday, klasor):
    ad = hashlib.md5(aday["url"].encode()).hexdigest() + (".png" if aday["url"].lower().endswith(".png") else ".jpg")
    yol = os.path.join(klasor, ad)
    if not os.path.exists(yol):
        for deneme in range(3):
            try:
                with open(yol, "wb") as f:
                    f.write(_get(aday["url"], timeout=60))
                break
            except Exception as e:
                print(f"  İndirme hatası ({deneme + 1}/3): {e}", file=sys.stderr)
                if os.path.exists(yol):
                    os.remove(yol)
                time.sleep(2 * (deneme + 1))
        else:
            return None
    return {"yol": yol, "baslik": aday["baslik"], "sanatci": aday["sanatci"], "sayfa": aday.get("sayfa", "")}
