"""Wikimedia Commons'tan YALNIZCA kamu malı (public domain / CC0) görsel bulur ve indirir.

Eski minyatürler ve tablolar (Levni, Matrakçı, Vanmour, Zonaro...) kamu malıdır; telif riski yoktur.
Lisansı kamu malı olmayan hiçbir görsel kabul edilmez. Bulunamazsa None döner,
video o sahnede yazılı/desenli arka plana geçer.
"""
import hashlib, html, json, os, re, sys, time, urllib.parse, urllib.request

API = "https://commons.wikimedia.org/w/api.php"
MET = "https://collectionapi.metmuseum.org/public/collection/v1"   # The Met Open Access: kamu malı eserler (CC0)
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


def met_eser(nesne_id):
    """The Met açık arşivinden tek eser: yalnızca isPublicDomain=true ve görseli olanlar kabul edilir."""
    try:
        time.sleep(0.5)   # The Met'in hız sınırına uy
        o = json.loads(_get(f"{MET}/objects/{int(nesne_id)}"))
    except Exception as e:
        print(f"  Met eseri alınamadı ({nesne_id}): {e}", file=sys.stderr)
        return None
    url = o.get("primaryImage") or o.get("primaryImageSmall")
    if not o.get("isPublicDomain") or not url:
        return None
    return {"baslik": f"Met:{o['objectID']}", "url": url, "w": 0, "h": 0,
            "sanatci": (o.get("artistDisplayName") or "").split(" (")[0][:40] or "The Met",
            "sayfa": o.get("objectURL", ""), "kaynak": "met", "eser": o.get("title", ""), "tarih": o.get("objectDate", "")}


def met_ara(sorgu, limit=40):
    """The Met'te arama: kamu malı ve görselli eserler (en alakalı önce)."""
    # /v1/search 1 Ekim 2026'da kaldırıldı; /v1.1/search sayfalı (offset, limit)
    try:
        r = json.loads(_get(MET.replace("/v1", "/v1.1") + "/search?" +
                            urllib.parse.urlencode({"q": sorgu, "hasImages": "true", "limit": limit * 2, "offset": 0})))
    except Exception as e:
        print(f"  Met araması başarısız ({sorgu}): {e}", file=sys.stderr)
        return []
    kimlikler = r.get("objectIDs") or [x.get("objectID") if isinstance(x, dict) else x
                                        for x in (r.get("results") or r.get("data") or r.get("objects") or [])]
    if not kimlikler:
        print(f"  Met araması boş ({sorgu}): {str(r)[:200]}", file=sys.stderr)
    sonuc = []
    for nid in [k for k in kimlikler if k][:limit * 2]:
        e = met_eser(nid)
        if e:
            sonuc.append(e)
        if len(sonuc) >= limit:
            break
    return sonuc


def ara(sorgu, limit=12, genislik=GENISLIK):
    """Sorgu için uygun adayları (en alakalı önce) döner: [{baslik, url, w, h, sanatci}]"""
    p = {
        "action": "query", "format": "json", "formatversion": "2", "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": str(genislik),
        "iiextmetadatafilter": "LicenseShortName|License|Artist",
    }
    if sorgu.startswith("Met:"):   # The Met açık arşivinden elle seçilmiş eser
        e = met_eser(sorgu[4:])
        return [e] if e else []
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
    elle = [q for q in sorgular if q.startswith(("File:", "Met:"))]
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
                veri = _get(aday["url"], timeout=60)
                from PIL import Image
                Image.open(__import__("io").BytesIO(veri)).verify()   # HTML/bozuk yanıt görsel sanılmasın
                with open(yol, "wb") as f:
                    f.write(veri)
                break
            except Exception as e:
                print(f"  İndirme hatası ({deneme + 1}/3): {e}", file=sys.stderr)
                if os.path.exists(yol):
                    os.remove(yol)
                time.sleep(2 * (deneme + 1))
        else:
            return None
    return {"yol": yol, "baslik": aday["baslik"], "sanatci": aday["sanatci"], "sayfa": aday.get("sayfa", ""),
            "kaynak": aday.get("kaynak", "commons")}


def kaynak_satiri(gorseller, uzun=False):
    """Açıklamadaki görsel teşekkür satırı: Commons ve/veya The Met."""
    g = [x for x in gorseller if x]
    sanatcilar = sorted({x["sanatci"] for x in g if x.get("sanatci") and x["sanatci"] != "The Met"})
    yerler = []
    if any(x.get("kaynak", "commons") == "commons" for x in g) or not g:
        yerler.append("Wikimedia Commons")
    if any(x.get("kaynak") == "met" for x in g):
        yerler.append("The Metropolitan Museum of Art (Open Access)")
    s = "Görseller: " + " ve ".join(yerler) + (" arşivlerindeki" if len(yerler) > 1 else "'taki" if yerler == ["Wikimedia Commons"] else " arşivindeki") + \
        " kamu malı " + ("tarihi " if uzun else "") + "eserler"
    if sanatcilar:
        s += " (" + ", ".join(sanatcilar[:6 if uzun else 4]) + ")"
    return s
