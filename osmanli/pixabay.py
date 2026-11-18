"""Pixabay'den döneme aykırı olmayan görüntüler (PIXABAY_API_KEY yoksa hiçbir şey yapmaz).

Kural: tarih farkı olmasın. Bu yüzden yalnızca iki tür görüntü alınır:
  1) Atmosfer: zamansız doğa/doku görüntüleri (sis, deniz dalgası, alev, duman, mum, yıldızlar, bulut, kar,
     çöl, eski kâğıt). İnsan, araç, gemi, şehir, ışıklı tabela gibi etiketi olan her sonuç elenir.
     Görselsiz (yalnızca başlık yazılı) sahnelerin arka planı olur.
  2) Yapı: o yapının bugünkü hâliyle olayın yılında da ayakta olduğu (ve görünüşünün büyük ölçüde aynı kaldığı)
     birkaç anıt. Konunun en erken yılı yapının "since" yılından önceyse kullanılmaz; yıl bilinmiyorsa da kullanılmaz.
     Mekan sahnesinin arka planı olur.
İndirilenler out/pixabay/ altında saklanır; aynı video içinde aynı klip iki kez kullanılmaz.
"""
import hashlib, io, json, os, re, subprocess, time, urllib.error, urllib.parse, urllib.request

from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
KLASOR = os.path.join(os.path.dirname(HERE), "out", "pixabay")
KEY = (os.environ.get("PIXABAY_API_KEY") or "").strip()
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) SarayinGolgesiBot/1.0", "Accept": "*/*"}
KULLANILAN = set()

# Etiketinde bunlardan biri geçen sonuç asla kullanılmaz (modern hayat, insan, araç)
YASAK = {"person", "people", "man", "woman", "men", "women", "girl", "boy", "child", "children", "kid", "baby", "tourist",
         "tourists", "crowd", "human", "face", "portrait", "model", "couple", "family", "selfie", "hand", "hands",
         "car", "cars", "traffic", "road", "street", "highway", "bus", "tram", "train", "taxi", "bike", "bicycle",
         "motorcycle", "truck", "vehicle", "airplane", "plane", "aircraft", "jet", "helicopter", "drone",
         "boat", "boats", "ship", "ships", "yacht", "ferry", "sailboat", "cruise", "port", "harbor", "harbour",
         "city", "cityscape", "skyline", "skyscraper", "skyscrapers", "building", "buildings", "bridge", "modern",
         "neon", "lamp", "lamps", "light bulb", "bulb", "electricity", "power line", "pylon", "wind turbine",
         "sign", "text", "logo", "phone", "smartphone", "laptop", "computer", "technology", "flag", "flags",
         "christmas", "halloween", "santa", "party", "concert", "festival", "fireworks", "glass", "plastic",
         "surfer", "surfing", "beach", "swimming", "pool", "sunglasses", "graffiti", "construction", "crane",
         "3d", "render", "illustration", "cartoon", "vector", "abstract", "digital", "fantasy", "ai generated",
         "generated", "game", "sci-fi", "space", "planet", "galaxy", "nebula", "earth"}

# Atmosfer: metindeki kelime -> İngilizce arama (sıra önemli: ilk eşleşen)
ATMOSFER = [
    (r"yang[ıi]n|alev|yak[tm]|yand[ıi]|ate[şs]|barut|patla", ["fire flames", "burning embers", "campfire flames dark"]),
    (r"deniz|donanma|gemi|filo|kad[ıi]rga|liman|k[ıi]y[ıi]|ada\b|bo[ğg]az", ["ocean waves", "stormy sea", "sea waves dark"]),
    (r"f[ıi]rt[ıi]na|ya[ğg]mur|sel\b|y[ıi]ld[ıi]r[ıi]m", ["storm clouds", "rain drops", "lightning storm"]),
    (r"k[ıi][şs]\b|kar\b|so[ğg]uk|don\b|buz", ["snowfall", "snow falling", "frost"]),
    (r"[çc][öo]l|kum\b|susuz|s[ıi]cak", ["desert dunes", "sand dunes wind"]),
    (r"gece|karanl[ıi]k|ay ı[şs][ıi][ğg][ıi]|y[ıi]ld[ıi]z", ["night sky stars", "moon clouds night", "starry sky"]),
    (r"kale|sur\b|surlar|ku[şs]at|top\b|toplar|h[üu]cum|sava[şs]|ordu|asker|duman", ["smoke dark", "fog smoke", "dust smoke"]),
    (r"mektup|ferman|yazd|kitap|kronik|kaynak|tarih[çc]i|kay[ıi]t|belge|defter", ["old paper texture", "parchment", "candle flame"]),
    (r"[öo]ld[üu]|[öo]l[üu]m|idam|bo[ğg]dur|cenaze|mezar|yas\b|veba|hastal", ["candle flame dark", "candle light", "smoke dark"]),
    (r"sabah|[şs]afak|g[üu]ne[şs]", ["sunrise clouds", "sunrise sky", "morning fog"]),
]
VARSAYILAN = ["fog", "clouds timelapse", "mist forest dark", "candle flame"]

# Yapı: yer adında geçen kelime -> (arama, en erken yıl). Ayrı tutulanlar (Galata, Boğaz, Çırağan...) bilerek yok:
# bugünkü görünüşleri olay zamanındakinden farklı ya da çevreleri tamamen modern.
YAPILAR = [   # (yer adında geçen, arama, en erken yıl, etiketlerde mutlaka olması gereken)
    ("ayasofya", "hagia sophia", 1580, "hagia"),
    ("süleymaniye", "suleymaniye mosque", 1560, "suleymaniye"),
    ("sultanahmet", "blue mosque istanbul", 1620, "mosque"),
    ("yeni cami", "new mosque eminonu", 1665, "mosque"),
    ("selimiye", "selimiye mosque edirne", 1575, "selimiye"),
    ("topkapı", "topkapi palace", 1480, "topkapi"),
    ("dolmabahçe", "dolmabahce palace", 1856, "dolmabahce"),
    ("rumeli hisar", "rumeli fortress", 1452, "fortress"),
    ("atmeydanı", "obelisk of theodosius", 390, "obelisk"),
    ("hipodrom", "obelisk of theodosius", 390, "obelisk"),
]
YAPI_YASAK = {"night", "illuminated", "illumination", "lights", "lighting", "interior", "inside", "museum", "tiles",
              "flower", "flowers", "tulip", "tulips", "garden", "park", "tree", "trees", "spring", "cat", "bird", "food"}


def var():
    return bool(KEY)


def _get(url, tekrar=3):
    for i in range(tekrar):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if i == tekrar - 1:
                print("Pixabay: istek başarısız:", type(e).__name__, getattr(e, "code", ""), flush=True)
                return None
            time.sleep(2 + i * 2)


def _ara(sorgu, tur):
    os.makedirs(KLASOR, exist_ok=True)
    onb = os.path.join(KLASOR, hashlib.md5(f"{tur}:{sorgu}".encode()).hexdigest() + ".json")
    if os.path.exists(onb):
        return json.load(open(onb))
    if tur == "video":
        url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
            {"key": KEY, "q": sorgu, "per_page": 30, "safesearch": "true", "video_type": "film"})
    else:
        url = "https://pixabay.com/api/?" + urllib.parse.urlencode(
            {"key": KEY, "q": sorgu, "per_page": 30, "safesearch": "true", "image_type": "photo",
             "orientation": "horizontal", "min_width": 1600})
    ham = _get(url)
    if not ham:
        return {"hits": []}
    veri = json.loads(ham)
    json.dump(veri, open(onb, "w"))
    return veri


def _temiz(hit, gerekli=(), ek_yasak=frozenset()):
    etiketler = {t.strip().lower() for t in hit.get("tags", "").split(",")}
    kelimeler = {w for t in etiketler for w in t.split()}
    yasak = YASAK | ek_yasak
    if etiketler & yasak or kelimeler & yasak:
        return False
    return all(any(g in t for t in etiketler) for g in gerekli)


def _indir(url, uzanti):
    yol = os.path.join(KLASOR, hashlib.md5(url.encode()).hexdigest() + uzanti)
    if not os.path.exists(yol):
        ham = _get(url)
        if not ham:
            return None
        with open(yol, "wb") as f:
            f.write(ham)
    return yol


def atmosfer_video(metin, tohum=0):
    """Metne uygun zamansız atmosfer videosu (yerel mp4 yolu) ya da None."""
    if not var():
        return None
    m = metin.lower()
    sorgular = next((q for desen, q in ATMOSFER if re.search(desen, m)), VARSAYILAN)
    sorgular = sorgular[tohum % len(sorgular):] + sorgular[:tohum % len(sorgular)]
    for sorgu in sorgular:
        for hit in _ara(sorgu, "video").get("hits", []):
            if hit["id"] in KULLANILAN or not _temiz(hit) or hit.get("duration", 0) < 6:
                continue
            v = hit.get("videos", {})
            secim = next((v[k] for k in ("medium", "small", "large") if v.get(k, {}).get("url") and v[k].get("width", 0) >= 960), None)
            if not secim:
                continue
            yol = _indir(secim["url"], ".mp4")
            if yol:
                KULLANILAN.add(hit["id"])
                print(f"Pixabay atmosfer: '{sorgu}' -> {hit['id']} ({hit.get('tags')})", flush=True)
                return yol
    return None


YAPI_FOTO = os.environ.get("PIXABAY_YAPI", "0") == "1"   # varsayılan kapalı: bkz. aşağıdaki not


def yapi_fotografi(yer, yil):
    """Yapının fotoğrafı (yerel jpg yolu) ya da None. yil: konunun en erken yılı (bilinmiyorsa None -> kullanılmaz).
    NOT: Denemede (Kösem, Topkapı) gelen fotoğraf lale bahçesi ve arkada bulanık turistlerdi; etiketler modern
    ayrıntıları (turist, lamba, iskele) güvenilir biçimde göstermiyor. Tarih farkı riski yüzünden kapalı;
    yer sahneleri çizim silueti kullanır. Açmak için PIXABAY_YAPI=1."""
    if not var() or yil is None or not YAPI_FOTO:
        return None
    ad = yer.lower().replace("I", "ı").replace("İ", "i")
    eslesen = next(((q, since, g) for anahtar, q, since, g in YAPILAR if anahtar in ad), None)
    if not eslesen or yil < eslesen[1]:
        return None
    sorgu, _, zorunlu = eslesen
    # yapı fotoğrafında "building/city" etiketi olağan; onları değil, insan/araç/gece ışığını ele
    for hit in _ara(sorgu, "foto").get("hits", []):
        etiket = hit.get("tags", "").lower()
        if hit["id"] in KULLANILAN or zorunlu not in etiket:
            continue
        kopya = dict(hit, tags=",".join(t for t in etiket.split(",") if t.strip() not in
                                       ("building", "buildings", "city", "cityscape", "skyline")))
        if not _temiz(kopya, (), frozenset(YAPI_YASAK)):
            continue
        url = hit.get("largeImageURL") or hit.get("webformatURL")
        yol = _indir(url, ".jpg") if url else None
        if yol:
            KULLANILAN.add(hit["id"])
            print(f"Pixabay yapı: '{sorgu}' -> {hit['id']} ({hit.get('tags')})", flush=True)
            return yol
    return None


def eskit(im, karart=0.62, sepya=0.45):
    """Modern fotoğraf/videoyu eski belgesel havasına çek: renk azalt, sıcak ton, karart."""
    im = ImageEnhance.Color(im).enhance(1 - sepya)
    a = np.asarray(im).astype(np.float32)
    ton = np.array([1.06, 0.97, 0.84])
    a = a * ton * karart
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def kapla(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((max(w, int(im.width * s + 1)), max(h, int(im.height * s + 1))), Image.BILINEAR)
    x0, y0 = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x0, y0, x0 + w, y0 + h))


class Klip:
    """Görselsiz sahnenin arka planı: atmosfer videosundan kareler (bellekte JPEG olarak, en çok ~9 sn).
    kare(yerel) sahne ilerlemesine göre kare döndürür (sahne uzunsa yavaşlatılmış oynar)."""
    FPS = 12

    def __init__(self, yol, w, h):
        self.w, self.h = w, h
        pw, ph = (w // 2, h // 2)
        vf = f"fps={self.FPS},scale={pw}:{ph}:force_original_aspect_ratio=increase,crop={pw}:{ph}"
        p = subprocess.run(["ffmpeg", "-loglevel", "error", "-t", "9", "-i", yol, "-vf", vf, "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
        n = len(p.stdout) // (pw * ph * 3)
        self.kareler = []
        for i in range(n):
            a = np.frombuffer(p.stdout, np.uint8, pw * ph * 3, i * pw * ph * 3).reshape(ph, pw, 3)
            im = eskit(Image.fromarray(a))
            b = io.BytesIO()
            im.save(b, "JPEG", quality=85)
            self.kareler.append(b.getvalue())
        if not self.kareler:
            raise ValueError("klip boş")

    def kare(self, yerel):
        n = len(self.kareler)
        i = int(min(1.0, max(0.0, yerel)) * (n - 1))
        im = Image.open(io.BytesIO(self.kareler[i])).convert("RGB")
        return im.resize((self.w, self.h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.2))


def klip_hazirla(metin, w, h, tohum=0):
    """Görselsiz sahne için Klip ya da None (anahtar yoksa, bulunamazsa ya da hata olursa)."""
    try:
        yol = atmosfer_video(metin, tohum)
        return Klip(yol, w, h) if yol else None
    except Exception as e:  # noqa: BLE001
        print("Pixabay klip atlandı:", e, flush=True)
        return None


def konu_yili(konu):
    """Konudaki en erken yıl (300-1950 arası sayılar; id, kanca, sahne yazı ve metinleri). Bulunmazsa None."""
    parcalar = [konu.get("id", ""), konu.get("kanca", "")]
    for s in konu.get("sahneler", []) + [s for b in konu.get("bolumler", []) for s in b["sahneler"]]:
        parcalar += [s.get("yazi") or "", s.get("metin") or ""]
    yillar = [int(x) for x in re.findall(r"(?<!\d)(\d{3,4})(?!\d)", " ".join(parcalar)) if 300 <= int(x) <= 1950]
    return min(yillar) if yillar else None
