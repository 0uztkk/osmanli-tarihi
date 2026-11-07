"""Osmanlı tarihi kanalı: günün Shorts videosunu üretir → out/video.mp4 ve out/meta.json

Ortam değişkenleri:
  KATEGORI   savaslar | saray | kisiler   (varsayılan: savaslar)
  SEED       YYYYMMDD; boşsa bugünün tarihi. Konu sırası bu tarihe göre ilerler.
  KONU       Belirli bir konunun id'si (ör. istanbul-fethi); verilirse sıra yok sayılır.
  GCP_TTS_KEY  Seslendirme anahtarı; yoksa sessiz video üretilir (deneme için).
"""
import datetime, json, math, os, random, re, subprocess, sys, wave

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
sys.path.insert(0, os.path.join(ROOT, "ortak"))
sys.path.insert(0, HERE)

# Erkek, belgesel tonunda sesler (ilk bulunan kullanılır). seslendirme modülü bunları okur.
os.environ.setdefault("TTS_SESLER", "Chirp3-HD-Charon,Chirp3-HD-Orus,Chirp3-HD-Fenrir,Wavenet-E,Wavenet-B")
os.environ.setdefault("TTS_HIZ", "1.0")

W, H, FPS = 1080, 1920, 30
SR = 44100
BASLANGIC = datetime.date(2026, 11, 1)    # konu sırasının ilk günü
MAKS_SURE = 58.0                           # Shorts sınırı 60 sn; pay bırakıyoruz
FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
ALTIN = (232, 190, 105)
KATEGORI_ADI = {"savaslar": "SAVAŞLAR VE İSYANLAR", "saray": "SARAY VE İSTANBUL", "kisiler": "TARİHTEN PORTRELER"}


def font(ad, boyut):
    for a in (ad, "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(FONT_DIR + a, boyut)
        except OSError:
            continue
    return ImageFont.load_default()


F_ALT = font("DejaVuSans-Bold.ttf", 66)
F_ETIKET = font("DejaVuSerif-Bold.ttf", 46)
F_BASLIK = font("DejaVuSerif-Bold.ttf", 74)
F_KUCUK = font("DejaVuSans-Bold.ttf", 34)
F_DEV = font("DejaVuSerif-Bold.ttf", 112)
F_KAPAK = font("DejaVuSerif-Bold.ttf", 96)


def tr_buyuk(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def emojisiz(s):
    return re.sub(r"[^\w\s.,:;!?'\"()\-–—’…%/&]", "", s, flags=re.UNICODE).strip()


# ---------------------------------------------------------------- konu seçimi
def konu_sec(kategori, seed, konu_id=""):
    with open(os.path.join(HERE, "konular", f"{kategori}.json"), encoding="utf-8") as f:
        konular = json.load(f)
    if konu_id:
        for k in konular:
            if k["id"] == konu_id:
                return k
        sys.exit(f"KONU bulunamadı: {konu_id}")
    konular = [k for k in konular if not k.get("yayinlandi")]   # elle yayınlanmış konular sıradan çıkar
    gun = datetime.datetime.strptime(str(seed), "%Y%m%d").date()
    sira = (gun - BASLANGIC).days % len(konular)
    return konular[sira]


def baslik_sec(seed, konu):
    """yt-package kuralları: her gün farklı kalıp, ≤60 karakter, konu ilk 40 karakterde, belirsiz sıfat yok
    ve kapak yazısıyla aynı kelimeleri kullanmayan başlık. Kurallara uyan yoksa en az sorunlu olan seçilir."""
    sys.path.insert(0, os.path.join(HERE, "araclar"))
    from title_tr import denetle, kelimeler
    konu_k = [w for e in konu.get("etiketler", []) for w in kelimeler(e)]
    sonuc = [(len(denetle(t, konu.get("kapak"), konu_k)["sorun"]), t) for t in konu["baslik"]]
    en_az = min(n for n, _ in sonuc)
    adaylar = [t for n, t in sonuc if n == en_az]
    return random.Random(seed * 31 + 7).choice(adaylar)


# ---------------------------------------------------------------- ses
BIRLER = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
ONLAR = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]


def sayi_yazi(n):
    """0-999999 arası sayıyı Türkçe yazıya çevirir: 1453 → bin dört yüz elli üç"""
    if n == 0:
        return "sıfır"
    parca = []
    binler, n = divmod(n, 1000)
    if binler:
        parca.append("bin" if binler == 1 else sayi_yazi(binler) + " bin")
    yuz, n = divmod(n, 100)
    if yuz:
        parca.append("yüz" if yuz == 1 else BIRLER[yuz] + " yüz")
    on, bir = divmod(n, 10)
    parca += [x for x in (ONLAR[on], BIRLER[bir]) if x]
    return " ".join(parca)


def tts_metni(metin):
    """Seslendirme için: kesme işaretleri ve sayılar duraksama yaratmasın.
    "Haliç'in" → "Haliçin", "1453'te" → "bin dört yüz elli üçte", "1550'lerde" → "bin beş yüz elllilerde"."""
    metin = re.sub(r"(\d+)['’](\w+)", lambda m: sayi_yazi(int(m.group(1))).replace(" ", "\u00a0") + m.group(2), metin)
    metin = re.sub(r"(?<=[^\W\d_])['’](?=[^\W\d_])", "", metin)
    metin = re.sub(r"\b\d{1,6}\b", lambda m: sayi_yazi(int(m.group())), metin)
    return metin.replace("\u00a0", " ")


def ses_uret(parcalar, cache):
    """Her parçayı seslendirir. Döner: (ses dizisi, [(başlangıç, bitiş), ...])"""
    from seslendirme import seslendir
    bosluk = np.zeros(int(SR * 0.35), dtype=np.float32)
    ses, zaman, t = [np.zeros(int(SR * 0.25), dtype=np.float32)], [], 0.25
    for metin in parcalar:
        a = seslendir(tts_metni(metin), cache)
        if a is None:   # anahtar yok: okuma süresini tahmin et, sessiz kal
            a = np.zeros(int(SR * max(2.5, len(metin) / 14.5)), dtype=np.float32)
        zaman.append((t, t + len(a) / SR))
        ses += [a, bosluk]
        t += len(a) / SR + len(bosluk) / SR
    ses.append(np.zeros(int(SR * 0.6), dtype=np.float32))
    return np.concatenate(ses), zaman


def wav_yaz(yol, a):
    a = np.clip(a, -1, 1)
    with wave.open(yol, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


def vuus_sesi(rng, sure=0.9):
    """Yumuşak geçiş sesi: süzgeci açılıp kapanan rüzgâr gibi bir 'vuuş'. Sert vuruş yok."""
    m = int(SR * sure)
    g = rng.normal(0, 1, m)
    x = np.linspace(0, 1, m)
    kesim = 250 + 2200 * np.sin(np.pi * np.clip(x / 0.85, 0, 1)) ** 2   # süzgeç 250 → 2450 → 250 Hz
    alfa = 1 - np.exp(-2 * np.pi * kesim / SR)
    y = np.zeros(m)
    acc = 0.0
    for k in range(m):   # zamanla değişen tek kutuplu alçak geçiren süzgeç (iki kez)
        acc += alfa[k] * (g[k] - acc)
        y[k] = acc
    acc = 0.0
    for k in range(m):
        acc += alfa[k] * (y[k] - acc)
        y[k] = acc
    zarf = np.sin(np.pi * np.clip(x, 0, 1)) ** 2 * np.where(x < 0.62, (x / 0.62) ** 0.6, 1)
    y *= zarf
    return (y / (np.abs(y).max() + 1e-9)).astype(np.float32)


def sinematik_yatak(yol, vuruslar):
    """Seslendirmenin altına alçak sesli, karanlık bir drone ve sahne geçişlerinde yumuşak bir vuuş ekler."""
    with wave.open(yol) as w:
        ses = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = len(ses)
    t = np.arange(n) / SR
    rng = np.random.default_rng(3)
    drone = np.zeros(n, dtype=np.float32)
    for f, g in ((55.0, 1.0), (82.41, 0.55), (110.0, 0.5), (164.81, 0.22)):
        for sap in (-0.25, 0.25):   # hafif akortsuz çiftler: koro etkisi
            for h, hg in ((1, 1.0), (2, 0.35), (3, 0.15)):
                drone += (g * hg * np.sin(2 * np.pi * (f + sap) * h * t + rng.uniform(0, 6.28))).astype(np.float32)
    drone *= (0.75 + 0.25 * np.sin(2 * np.pi * 0.07 * t)).astype(np.float32)
    drone /= np.max(np.abs(drone)) + 1e-9
    ruzgar = np.cumsum(rng.normal(0, 1, n)).astype(np.float32)
    cs = np.concatenate([[0.0], np.cumsum(ruzgar, dtype=np.float64)])   # hızlı hareketli ortalama (uzun seslerde de)
    k = 4410
    idx = np.arange(n)
    lo, hi = np.clip(idx - k // 2, 0, n), np.clip(idx + k // 2, 0, n)
    ruzgar -= ((cs[hi] - cs[lo]) / np.maximum(hi - lo, 1)).astype(np.float32)
    ruzgar /= np.max(np.abs(ruzgar)) + 1e-9
    yatak = 0.055 * drone + 0.018 * ruzgar
    zarf = np.minimum(1, np.minimum(t / 1.5, (t[-1] - t) / 2.0)).clip(0, 1).astype(np.float32)
    yatak *= zarf
    gecis = os.environ.get("GECIS_SESI", "vuus")   # vuus | yok
    if gecis == "vuus":
        vuus = vuus_sesi(rng)
        tepe = int(np.argmax(np.abs(vuus)))   # sesin en yüksek anı tam sahne değişimine denk gelsin
        for j, b in enumerate(vuruslar[1:], 1):   # vuruslar: geçiş anları (ilk eleman videonun başı)
            i0 = int(b * SR) - tepe
            if i0 < 0 or i0 >= n:
                continue
            parca = vuus[: n - i0]
            yatak[i0: i0 + len(parca)] += 0.07 * parca
    wav_yaz(yol, ses + yatak)


# ---------------------------------------------------------------- görsel hazırlığı
def parsomen():
    """Görsel bulunamazsa kullanılan koyu, eski kâğıt dokulu arka plan."""
    rng = np.random.default_rng(7)
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(-1, 1, W)[None, :]
    taban = np.array([62, 38, 24]) * (1 - 0.35 * (x ** 2 + (y - 0.45) ** 2))[..., None]
    gurultu = rng.normal(0, 6, (H, W, 1))
    img = np.clip(taban + gurultu, 0, 255).astype(np.uint8)
    return Image.fromarray(img)


def sahne_hazirla(yol):
    """Döner: (arka plan, kapak görseli). Görsel, ekranı tamamen kaplayacak ve üzerinde
    kamera gezebilecek kadar büyütülür. Görsel yoksa (parşömen, None)."""
    if not yol:
        return parsomen(), None
    try:
        im = Image.open(yol).convert("RGB")
    except Exception:
        return parsomen(), None
    if im.width / im.height > 2.4:   # aşırı geniş panoramaları ortadan kırp
        yeni = int(im.height * 2.4)
        im = im.crop(((im.width - yeni) // 2, 0, (im.width - yeni) // 2 + yeni, im.height))
    im = ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.10)).enhance(1.12)   # eski tabloları canlandır
    s = 1.10 * max(W / im.width, H / im.height)
    kapak = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    return None, kapak


def golge_katmani():
    """Altyazı ve üst etiketin okunması için üst/alt koyulaştırma."""
    a = np.zeros((H, W), dtype=np.float32)
    y = np.arange(H)
    a += np.clip((480 - y) / 480, 0, 1)[:, None] * 0.65
    a += np.clip((y - 1000) / 650, 0, 1)[:, None] * 0.80
    xx = np.linspace(-1, 1, W)[None, :]
    yy = np.linspace(-1, 1, H)[:, None]
    a += np.clip((xx ** 2 + yy ** 2) ** 1.5 * 0.35, 0, 0.4)   # kenar karartma (vinyet)
    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[..., 3] = (np.clip(a, 0, 0.85) * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


GOLGE = None


def yumusak(x):
    return x * x * (3 - 2 * x)


def sahne_kare(sahne, yerel, i):
    """Bir sahnenin metinsiz karesi (tam ekran). yerel: sahne içi ilerleme 0..1
    Kamera görselin uzun ekseni boyunca yavaşça kayar, aynı anda hafifçe yakınlaşır/uzaklaşır."""
    if sahne.get("anim"):
        u = sahne.get("anim_u", yerel)
        return sahne["anim"].kare(u, u * sahne.get("anim_sure", 6.0))
    bg, fg = sahne["bg"], sahne["fg"]
    if fg is None:
        return bg.copy()
    u = yumusak(yerel)
    z = 1.0 + 0.07 * (u if i % 2 == 0 else 1 - u)
    ww, wh = W * 1.05 / z, H * 1.05 / z
    bosx, bosy = fg.width - ww, fg.height - wh
    yon = 1 if i % 2 == 0 else -1
    if bosx > bosy:   # yatay görsel: soldan sağa (ya da tersi) gez
        cx = bosx * (0.5 + yon * 0.32 * (u - 0.5) * 2)
        cy = bosy * 0.45
    else:             # dikey görsel: yukarıdan aşağı hafif kayma
        cx = bosx * 0.5
        cy = bosy * (0.4 + yon * 0.12 * (u - 0.5) * 2)
    return fg.resize((W, H), Image.BILINEAR, box=(cx, cy, cx + ww, cy + wh))


def satirla(draw, metin, fnt, genislik):
    kelimeler, satirlar, s = metin.split(), [], ""
    for k in kelimeler:
        dene = (s + " " + k).strip()
        if draw.textlength(dene, font=fnt) <= genislik:
            s = dene
        else:
            if s:
                satirlar.append(s)
            s = k
    if s:
        satirlar.append(s)
    return satirlar


def ortala(draw, satirlar, fnt, y, renk, aralik=10, kontur=6):
    for s in satirlar:
        w = draw.textlength(s, font=fnt)
        draw.text(((W - w) / 2, y), s, font=fnt, fill=renk, stroke_width=kontur, stroke_fill=(0, 0, 0))
        y += fnt.size + aralik
    return y


def altyazi_parcalari(metin):
    """Metni 2 satırı geçmeyecek kısa parçalara böler; her parçanın süre payı karakter sayısıyla orantılı."""
    kelimeler, parcalar, p = metin.split(), [], []
    for k in kelimeler:
        p.append(k)
        if len(" ".join(p)) >= 26 or k.endswith((".", "?", "!", ",")) and len(" ".join(p)) >= 12:
            parcalar.append(" ".join(p)); p = []
    if p:
        parcalar.append(" ".join(p))
    toplam = sum(len(x) for x in parcalar) or 1
    sinirlar, b = [], 0.0
    for x in parcalar:
        sinirlar.append((b, b + len(x) / toplam, x)); b += len(x) / toplam
    return sinirlar


F_KUTU = font("DejaVuSans-Bold.ttf", 70)


def kutu_parcalari(metin, en_fazla=17, kelime=3):
    """Animasyonlu stil: 1-3 kelimelik kısa parçalar (tek satır). Uzun videoda daha uzun parçalar."""
    kelimeler, parcalar, p = metin.split(), [], []
    for k in kelimeler:
        if p and (len(" ".join(p + [k])) > en_fazla or len(p) >= kelime):
            parcalar.append(" ".join(p)); p = []
        p.append(k)
        if k.endswith((".", "?", "!", ",", ":", ";")):
            parcalar.append(" ".join(p)); p = []
    if p:
        parcalar.append(" ".join(p))
    toplam = sum(len(x) + 2 for x in parcalar) or 1
    sinirlar, b = [], 0.0
    for x in parcalar:
        sinirlar.append((b, b + (len(x) + 2) / toplam, x)); b += (len(x) + 2) / toplam
    return sinirlar


def altyazi_kutu(d, parca, ic, y=1400, vurgu_renk=(255, 200, 80), ekran_w=None):
    """Kanalın kendi stili: koyu mürekkep plaka, ince altın çerçeve, krem yazı;
    o an söylenen kelime altın renge döner ve altına kısa bir altın çizgi gelir."""
    kelimeler = parca.split()
    uz = [len(k) + 1 for k in kelimeler]
    hedef, n = ic * sum(uz), 0
    for i, l in enumerate(uz):
        n = i
        if hedef < l:
            break
        hedef -= l
    bosluk = d.textlength(" ", font=F_KUTU)
    gen = [d.textlength(k, font=F_KUTU) for k in kelimeler]
    tw = sum(gen) + bosluk * (len(kelimeler) - 1)
    W = ekran_w or globals()["W"]
    x0, x1 = (W - tw) / 2 - 38, (W + tw) / 2 + 38
    d.rectangle([x0 + 8, y + 10, x1 + 8, y + 112], fill=(8, 6, 4))
    d.rectangle([x0, y, x1, y + 102], fill=(28, 20, 14), outline=(232, 190, 105), width=3)
    for cx in (x0, x1):   # köşelerde küçük baklava süsü
        d.polygon([(cx, y + 37), (cx + 14, y + 51), (cx, y + 65), (cx - 14, y + 51)], fill=(232, 190, 105))
    x = (W - tw) / 2
    for i, k in enumerate(kelimeler):
        renk = vurgu_renk if i == n else (246, 234, 204)
        d.text((x, y + 10), k, font=F_KUTU, fill=renk)
        if i == n:
            d.line([(x, y + 90), (x + gen[i], y + 90)], fill=vurgu_renk, width=5)
        x += gen[i] + bosluk


def kapanis_karti(d, yazi, gecen):
    """Videonun sonunda altın çerçeveli küçük kart; yukarıdan yumuşakça iner."""
    iner = min(1.0, gecen / 0.4)
    y = int(1150 - 40 * (1 - iner) ** 2)
    tw = d.textlength(yazi, font=F_ETIKET)
    x0, x1 = (W - tw) / 2 - 44, (W + tw) / 2 + 44
    d.rounded_rectangle([x0, y, x1, y + 96], 18, fill=(25, 15, 10), outline=ALTIN, width=4)
    for x in (x0 + 20, x1 - 20):
        d.polygon([(x, y + 36), (x + 12, y + 48), (x, y + 60), (x - 12, y + 48)], fill=ALTIN)
    d.text(((W - tw) / 2, y + 22), yazi, font=F_ETIKET, fill=(255, 236, 160))


def render(sahneler, toplam, kategori, kapak, vid_yol):
    global GOLGE
    GOLGE = GOLGE or golge_katmani()
    n = int(toplam * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "21", "-pix_fmt", "yuv420p", vid_yol], stdin=subprocess.PIPE)
    GECIS = 0.35
    for fr in range(n):
        t = fr / FPS
        i = 0
        while i + 1 < len(sahneler) and t >= sahneler[i + 1]["bas"]:
            i += 1
        s = sahneler[i]
        bitis = sahneler[i + 1]["bas"] if i + 1 < len(sahneler) else toplam
        yerel = min(1.0, max(0.0, (t - s["bas"]) / max(0.1, bitis - s["bas"])))
        kare = sahne_kare(s, yerel, i)
        if i > 0 and t - s["bas"] < GECIS:   # yumuşak geçiş
            onceki = sahneler[i - 1]
            kare = Image.blend(sahne_kare(onceki, 1.0, i - 1), kare, (t - s["bas"]) / GECIS)
        if not s.get("anim"):
            kare.paste(GOLGE, (0, 0), GOLGE)
        d = ImageDraw.Draw(kare)

        # üstte kanal bandı ve ilerleme çizgisi
        d.rectangle([0, 0, int(W * t / toplam), 8], fill=ALTIN)
        ust = KATEGORI_ADI.get(kategori, "")
        d.text(((W - d.textlength(ust, font=F_KUCUK)) / 2, 150), ust, font=F_KUCUK, fill=ALTIN,
               stroke_width=4, stroke_fill=(20, 14, 10))

        if s["tur"] == "kanca":
            # kapak yazısı: başlığı tekrar etmeyen en fazla 3 kelime (yt-package)
            ortala(d, satirla(d, tr_buyuk(kapak), F_KAPAK, 980)[:2], F_KAPAK, 205, (255, 236, 160), 12, 8)
        elif s["tur"] == "kapanis":
            kapanis_karti(d, s["yazi"], t - s["bas"])
        elif s.get("anim"):
            pass
        elif s.get("yazi"):
            et = tr_buyuk(s["yazi"]) if len(s["yazi"]) < 18 else s["yazi"]
            tw = d.textlength(et, font=F_ETIKET)
            d.rounded_rectangle([(W - tw) / 2 - 30, 215, (W + tw) / 2 + 30, 215 + 78], 14,
                                fill=(25, 15, 10), outline=ALTIN, width=3)
            d.text(((W - tw) / 2, 228), et, font=F_ETIKET, fill=ALTIN)

        if s["fg"] is None and not s.get("anim"):   # görsel yoksa: ortada büyük süslü yazı
            merkez = s.get("yazi") or KATEGORI_ADI.get(kategori, "")
            satirlar = satirla(d, tr_buyuk(merkez), F_DEV, 920)[:3]
            y0 = 800 - len(satirlar) * (F_DEV.size + 16) / 2
            for yy in (y0 - 70, y0 + len(satirlar) * (F_DEV.size + 16) + 40):
                d.line([(W / 2 - 260, yy), (W / 2 - 30, yy)], fill=ALTIN, width=4)
                d.line([(W / 2 + 30, yy), (W / 2 + 260, yy)], fill=ALTIN, width=4)
                d.polygon([(W / 2, yy - 16), (W / 2 + 16, yy), (W / 2, yy + 16), (W / 2 - 16, yy)], fill=ALTIN)
            ortala(d, satirlar, F_DEV, y0, ALTIN, 16, 4)

        # altyazı: sesin konuşulan kısmıyla eşlenir
        if s["kon_bas"] <= t <= s["kon_bit"] + 0.3:
            ilerle = (t - s["kon_bas"]) / max(0.1, s["kon_bit"] - s["kon_bas"])
            for a, b, parca in s["altyazi"]:
                if a <= min(ilerle, 0.999) < b and s.get("kutu"):
                    altyazi_kutu(d, parca, (min(ilerle, 0.999) - a) / (b - a),
                                 vurgu_renk=(255, 200, 80) if s["tur"] == "sahne" else (255, 160, 110))
                    break
                if a <= min(ilerle, 0.999) < b:
                    satirlar = satirla(d, parca, F_ALT, 960)[:2]
                    ortala(d, satirlar, F_ALT, 1420 - (len(satirlar) - 1) * 38,
                           (255, 236, 160) if s["tur"] in ("kanca", "soru", "kapanis") else (255, 255, 255))
                    break
        ff.stdin.write(kare.tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg görüntü kodlaması başarısız")


# ---------------------------------------------------------------- video sonu (etkileşim)
SAAT = {"saray": "11:40", "kisiler": "17:25", "savaslar": "20:10"}
UZUN_BASI = datetime.date(2026, 11, 4)   # ilk uzun video
GUN_ASIRI_BASI = datetime.date(2026, 11, 8)   # buradan itibaren bir gün var, bir gün yok


def uzun_yayin_gunu(g):
    """Uzun video takvimi: 4 Kasım, sonra 8 Kasım'dan itibaren gün aşırı. uzun.py de bunu kullanır."""
    return g == UZUN_BASI or (g >= GUN_ASIRI_BASI and (g - GUN_ASIRI_BASI).days % 2 == 0)
# 8'lik döngü: art arda videolar aynı kapanışı almaz, kabaca 4 videodan 1'i yalnızca soruyla biter
DONGU = ["yarin", "bildin", "duz", "puan", "oneri", "yarin", "duz", "uzun"]
KATEGORI_KAYMA = {"saray": 0, "kisiler": 1, "savaslar": 2}


def yayinlanmis_uzunlar(bugun):
    """Bugünden önce yayınlanmış uzun videoların konuları (bugünkü Shorts uzun videodan önce çıkar)."""
    try:
        with open(os.path.join(HERE, "uzun", "sira.json"), encoding="utf-8") as f:
            sira = json.load(f)
    except OSError:
        return []
    cikan, g, n = [], UZUN_BASI, 0
    while g < bugun and n < len(sira):
        if uzun_yayin_gunu(g):
            try:
                with open(os.path.join(HERE, "uzun", f"{sira[n]}.json"), encoding="utf-8") as f:
                    cikan.append(json.load(f))
            except OSError:
                pass
            n += 1
        g += datetime.timedelta(days=1)
    return cikan


def kapanis_sec(konu, kategori, seed):
    """Videonun son cümleleri: [(metin, ekran kartı)], açıklamaya giden soru ve kapanış türü.
    Tek istek kuralı (voice.md): her videoda en fazla bir şey istenir, "sonuna kadar izle" yok."""
    gun = datetime.datetime.strptime(str(seed), "%Y%m%d").date()
    tur = os.environ.get("KAPANIS") or DONGU[((gun - BASLANGIC).days * 3 + KATEGORI_KAYMA.get(kategori, 0)) % len(DONGU)]
    soru = konu["soru"]
    kaotik = kategori == "savaslar" or konu.get("tur") == "az-bilinen"

    if tur == "puan" and not kaotik:
        tur = "bildin"
    if tur == "uzun":
        ozel = {e.casefold() for e in konu.get("etiketler", [])} - {"osmanlı tarihi", "osmanlı tarihi belgesel"}
        uzun = next((u for u in yayinlanmis_uzunlar(gun)
                     if ozel & {e.casefold() for e in u.get("etiketler", [])}), None)
        if not uzun:
            tur = "takip"

    if tur == "yarin":
        sonraki = konu_sec(kategori, int((gun + datetime.timedelta(days=1)).strftime("%Y%m%d")))
        if sonraki["id"] == konu["id"]:
            return [(soru, None)], soru, "duz"
        ad = emojisiz(baslik_sec(seed + 1, sonraki)).rstrip(" ?!.")
        return [(soru, None), (f"Yarın aynı saatte: {ad}.", f"YARIN {SAAT.get(kategori, '')}")], \
            soru + f"\n\nYarın aynı saatte: {ad}", tur
    if tur == "bildin":
        if konu.get("tur") == "az-bilinen":
            m = "Bunu daha önce duymuş muydun? Biliyorsan biliyordum, ilk kez duyduysan yeni öğrendim yaz."
        else:
            m = "Bu hikâyeyi böyle mi biliyordun? Yorumlara bir kelimeyle yaz: biliyordum ya da ilk kez duydum."
        return [(m, "BİLİYOR MUYDUN?")], m, tur
    if tur == "puan":
        m = "Sence bu olay ne kadar kaotikti? Birden ona kadar bir puan ver, yorumlara yaz."
        return [(m, "KAOS PUANIN: 1 – 10")], m.replace("Birden ona", "1'den 10'a"), tur
    if tur == "oneri":
        m = "Sıradaki Osmanlı hikâyesini sen seç: hangi olayı merak ediyorsan yorumlara yaz."
        return [(m, "SIRADAKİNİ SEN SEÇ")], m, tur
    if tur == "uzun":
        m = "Bu hikâyenin tamamını, perde arkasıyla birlikte kanaldaki uzun videoda anlattık."
        return [(soru, None), (m, "TAMAMI UZUN VİDEODA")], soru + "\n\nHikâyenin tamamı kanaldaki uzun videoda: " + \
            emojisiz(uzun["baslik"][0]), tur
    if tur == "takip":
        m = "Osmanlının az bilinen hikâyeleri için takipte kal."
        return [(soru, None), (m, "TAKİPTE KAL")], soru, tur
    return [(soru, None)], soru, "duz"


# ---------------------------------------------------------------- ana akış
def main():
    kategori = (os.environ.get("KATEGORI") or "savaslar").strip().lower()
    if kategori not in KATEGORI_ADI:
        sys.exit(f"Bilinmeyen KATEGORI: {kategori}")
    seed = int(os.environ.get("SEED") or datetime.date.today().strftime("%Y%m%d"))
    konu = konu_sec(kategori, seed, (os.environ.get("KONU") or "").strip())
    print(f"Kategori: {kategori}  Konu: {konu['id']}", flush=True)
    os.makedirs(OUT, exist_ok=True)

    # anlatım: kanca + 4 sahne + soru; kanca ilk sahnenin, soru son sahnenin görselini kullanır
    from gorsel import bul
    kullanilan, gorseller = set(), []
    for sh in konu["sahneler"]:
        gorseller.append(bul(sh.get("gorsel", ["-"]), kategori, os.path.join(OUT, "img"), kullanilan))
    kanca_gi = konu.get("kanca_sahne", 0)
    if konu.get("kanca_gorsel"):   # kanca için ayrı, en çarpıcı görsel
        ozel = bul(konu["kanca_gorsel"], kategori, os.path.join(OUT, "img"), kullanilan)
        if ozel:
            gorseller.append(ozel)
            kanca_gi = len(gorseller) - 1
    kapanis, aciklama_sorusu, kapanis_turu = kapanis_sec(konu, kategori, seed)
    print(f"Kapanış: {kapanis_turu}", flush=True)
    animler = {j: sh["anim"] for j, sh in enumerate(konu["sahneler"]) if sh.get("anim")}
    if konu.get("kanca_anim"):
        kanca_gi = "kanca_anim"
        animler[kanca_gi] = konu["kanca_anim"]
    parcalar = [("kanca", konu["kanca"], None, kanca_gi)] + \
               [("sahne", sh["metin"], sh.get("yazi"), j) for j, sh in enumerate(konu["sahneler"])] + \
               [("kapanis" if kart else "soru", m, kart, len(konu["sahneler"]) - 1) for m, kart in kapanis]

    ses, zaman = ses_uret([p[1] for p in parcalar], os.path.join(OUT, "tts"))
    toplam = len(ses) / SR
    oran = max(1.0, toplam / MAKS_SURE)   # Shorts sınırını aşmasın: gerekirse hafifçe hızlandır
    if oran > 1.0:
        print(f"Süre {toplam:.1f} sn, {oran:.2f}x hızlandırılıyor", flush=True)
    # Sesi kalınlaştır: perdeyi düşür (süre aynı kalır) ve alt frekansları biraz güçlendir
    perde = float(os.environ.get("SES_PERDE") or 0.92)
    wav_yaz(os.path.join(OUT, "ham.wav"), ses)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(OUT, "ham.wav"), "-filter:a",
                    f"asetrate={SR * perde:.0f},aresample={SR},atempo={oran / perde:.5f},"
                    f"bass=g=4:f=120:w=0.8,alimiter=limit=0.95",
                    "-ar", str(SR), "-ac", "1", os.path.join(OUT, "audio.wav")], check=True)
    zaman = [(a / oran, b / oran) for a, b in zaman]
    with wave.open(os.path.join(OUT, "audio.wav")) as w:
        toplam = w.getnframes() / w.getframerate()

    if os.environ.get("MUZIK", "1") != "0":
        sinematik_yatak(os.path.join(OUT, "audio.wav"), [a for a, _ in zaman])

    hazir = {}
    sahneler = []
    kutu = konu.get("stil", "animasyon") == "animasyon"   # yeni altyazı stili artık her videoda
    import animasyon
    anim_obj = {}
    for k, ((tur, metin, yazi, gi), (a, b)) in enumerate(zip(parcalar, zaman)):
        sahne = {"tur": tur, "yazi": yazi, "bas": max(0.0, a - 0.2), "kon_bas": a, "kon_bit": b, "kutu": kutu,
                 "altyazi": kutu_parcalari(metin) if kutu else altyazi_parcalari(metin)}
        if gi in animler:
            bitis = max(0.0, zaman[k + 1][0] - 0.2) if k + 1 < len(zaman) else toplam
            if gi in anim_obj:   # soru/kapanış: son animasyon son karesinde durur
                sahne.update(anim=anim_obj[gi][0], anim_u=1.0, anim_sure=anim_obj[gi][1])
            else:
                sure = bitis - sahne["bas"]
                anim_obj[gi] = (animasyon.hazirla(animler[gi], sure), sure)
                sahne.update(anim=anim_obj[gi][0], anim_sure=sure)
            sahne.update(bg=None, fg=None)
        else:
            if gi not in hazir:
                hazir[gi] = sahne_hazirla(gorseller[gi]["yol"] if gorseller[gi] else None)
            sahne["bg"], sahne["fg"] = hazir[gi]
        sahneler.append(sahne)
    sahneler[0]["bas"] = 0.0

    seed_baslik = baslik_sec(seed, konu)
    print(f"Süre: {toplam:.1f} sn, kare: {int(toplam * FPS)}", flush=True)
    render(sahneler, toplam, kategori, konu.get("kapak") or emojisiz(seed_baslik), os.path.join(OUT, "v.mp4"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(OUT, "v.mp4"),
                    "-i", os.path.join(OUT, "audio.wav"), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", os.path.join(OUT, "video.mp4")], check=True)

    meta = meta_olustur(konu, kategori, seed_baslik, gorseller, aciklama_sorusu)
    meta["kapanis"] = kapanis_turu
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


GENEL_ETIKET = ["osmanlı tarihi", "osmanlı", "tarih", "türk tarihi", "osmanlı imparatorluğu", "tarih shorts"]
HASHTAG = {"savaslar": "#osmanlısavaşları", "saray": "#sarayhayatı", "kisiler": "#osmanlıpadişahları"}


def tr_baslik_harf(s):
    return " ".join((w[:1].replace("i", "İ").replace("ı", "I").upper() + w[1:]) if w else w for w in s.split(" "))


def meta_olustur(konu, kategori, baslik, gorseller, soru=None):
    """yt-seo: açıklamanın ilk iki satırı arama kutusuna yazılan kelimeleri taşır ("...daha fazla"nın üstü),
    sonra kaynak, sonra uzun hâl. Etiketler en fazla 15 ve yalnızca ayırt edici yazımlar için."""
    sanatcilar = sorted({g["sanatci"] for g in gorseller if g and g.get("sanatci")})
    gorsel_satiri = "Görseller: Wikimedia Commons'taki kamu malı eserler"
    if sanatcilar:
        gorsel_satiri += " (" + ", ".join(sanatcilar[:4]) + ")"
    aramalar = [tr_baslik_harf(e) for e in konu.get("etiketler", [])[:3]]
    satir1 = konu["kanca"]
    satir2 = "Osmanlı tarihi: " + ", ".join(aramalar[:-1]) + (f" ve {aramalar[-1]}" if len(aramalar) > 1 else "".join(aramalar)) + \
             " hakkında kısa bir hikâye."
    uzun = " ".join(sh["metin"] for sh in konu["sahneler"])
    aciklama = (f"{satir1}\n{satir2}\n\n"
                f"{uzun}\n\n"
                f"{soru or konu['soru']}\n\n"
                f"Osmanlı tarihinden savaşlar, isyanlar, saray hayatı ve tarihe yön veren insanlar; her gün yeni bir hikâye. "
                f"Rivayetleri rivayet, bilgileri bilgi olarak anlatıyoruz. Abone olmayı unutma!\n\n"
                f"{gorsel_satiri}\n\n"
                f"#osmanlı #osmanlıtarihi #tarih {HASHTAG[kategori]} #shorts")
    etiketler = list(dict.fromkeys(konu.get("etiketler", []) + GENEL_ETIKET))[:15]
    return {"title": baslik[:100], "description": aciklama[:4900], "tags": etiketler,
            "categoryId": "27", "konu": konu["id"], "kategori": kategori,
            "sesli": bool(os.environ.get("GCP_TTS_KEY", "").strip())}


if __name__ == "__main__":
    main()
