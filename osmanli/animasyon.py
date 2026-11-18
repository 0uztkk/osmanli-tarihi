"""Kodla çizilen animasyonlu sahneler (Shorts, 1080x1920).

Sahne JSON'unda "anim" alanı varsa görsel yerine bu modül çizer. Türler:

  harita   Akdeniz haritası (Natural Earth, kamu malı): şehir etiketleri, ilerleyen filo rotaları,
           çarpışma işareti, yanıp sönen bölge, mühür damgası, üst başlık, yavaş yakınlaşma.
  taraflar Tarafların armaları yukarıdan iner, ortada ittifak bandı, altta karşı taraf.
  sefer    Orduyu izleyen kamera: yürüyen asker birlikleri, arkalarında toz, yolda beliren şehir iğneleri,
           çarpışmada parlama/duman/sarsıntı, köşede ay plaketi; sonda genel görünüme açılır.
  mekan    Şehir içi yer (cami, saray, kule, meydan...): gök, uzak şehir silueti, binanın silueti ve suda yansıması,
           üstüne düşen iğne, ad plaketi, köşede bölge haritası madalyonu. Yakın (≤0.8°) harita sahneleri buna çevrilir.
  takvim   Gün batımı denizinde filo; ortada yaprakları çevrilen takvim ve "8 AY SONRA" bandı.

Her tür hazirla(spec) ile bir kez kurulur, sonra .kare(u, sn) ile her kare çizilir
(u: sahne içi ilerleme 0..1, sn: sahne başından beri geçen saniye).
"""
import json, math, os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920


def ayarla(w, h):
    """Ekran boyutu: Shorts 1080x1920 (varsayılan), uzun video 1920x1080."""
    global W, H
    W, H = w, h


def yatay():
    return W > H


YIL = None   # konunun en erken yılı (build.py / uzun.py ayarlar); Pixabay yapı fotoğrafında dönem denetimi için
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = "/usr/share/fonts/truetype/dejavu/"

DENIZ_UST, DENIZ_ALT = (38, 78, 90), (22, 46, 58)
SIG = (64, 112, 120)
KARA = (226, 206, 160)
KARA_KOYU = (196, 168, 120)
KIYI = (82, 58, 38)
KREM = (246, 234, 204)
MUREKKEP = (48, 32, 20)
ALTIN = (232, 190, 105)
KIRMIZI = (176, 34, 34)
OSMANLI = (178, 30, 36)
DUSMAN = (40, 60, 140)


def _f(ad, boy):
    try:
        return ImageFont.truetype(FONT_DIR + ad, boy)
    except OSError:
        return ImageFont.load_default()


F_SEHIR = _f("DejaVuSerif-Bold.ttf", 40)
F_BOLGE = _f("DejaVuSerif-Bold.ttf", 34)
F_UST = _f("DejaVuSerif-Bold.ttf", 120)
F_UST_ALT = _f("DejaVuSerif-Bold.ttf", 46)
F_BANT = _f("DejaVuSerif-Bold.ttf", 54)
F_ARMA = _f("DejaVuSerif-Bold.ttf", 32)
F_DAMGA = _f("DejaVuSerif-Bold.ttf", 38)
F_TAKVIM_YIL = _f("DejaVuSerif-Bold.ttf", 54)
F_TAKVIM_AY = _f("DejaVuSerif-Bold.ttf", 120)
F_ROZET = _f("DejaVuSerif-Bold.ttf", 52)


def tr_buyuk(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def yumusak(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def zipla(x):
    """0→1, sonunda hafif sekme (aşağı inen armalar, damga)."""
    x = min(1.0, max(0.0, x))
    if x < 0.7:
        return yumusak(x / 0.7) * 1.08
    return 1.08 - 0.08 * yumusak((x - 0.7) / 0.3)


def evre(sn, bas, sure=0.45):
    return min(1.0, max(0.0, (sn - bas) / sure))


def yazi(d, xy, metin, fnt, renk=KREM, kontur=5, kontur_renk=MUREKKEP, ortala=True, alfa=255):
    x, y = xy
    if ortala:
        x -= d.textlength(metin, font=fnt) / 2
    d.text((x, y), metin, font=fnt, fill=renk + (alfa,), stroke_width=kontur, stroke_fill=kontur_renk + (alfa,))


def kagit_dokusu(seed=3, guc=10):
    rng = np.random.default_rng(seed)
    g = rng.normal(0, 1, (H // 4, W // 4)).astype(np.float32)
    g = np.array(Image.fromarray(((g + 3) * 40).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC),
                 dtype=np.float32) / 255 - 0.6
    ince = rng.normal(0, 0.5, (H, W)).astype(np.float32)
    return (g * guc + ince * guc * 0.4)[..., None]


def vinyet(img, guc=0.55):
    a = np.asarray(img).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    r = ((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.45) / (H * 0.7)) ** 2
    m = 1 - np.clip(r, 0, 1) ** 1.6 * guc
    return Image.fromarray((a * m[..., None]).clip(0, 255).astype(np.uint8))


# ---------------------------------------------------------------- ikonlar
def kadirga(d, x, y, boy, yon=1, taraf="osmanli", sallan=0.0, alfa=255):
    """Yandan kadırga: gövde, kürekler, latin yelken, flama. yon=1 sağa bakar."""
    s = boy / 100.0
    y += math.sin(sallan) * 3 * s

    def p(px, py):
        return (x + yon * px * s, y + py * s)

    govde = KIYI if taraf == "osmanli" else (60, 44, 34)
    # kürekler
    for i in range(7):
        kx = -38 + i * 12
        aci = math.sin(sallan * 2 + i * 0.5) * 6
        d.line([p(kx, 8), p(kx - 6 + aci, 30)], fill=(70, 50, 34, alfa), width=max(2, int(3 * s)))
    d.polygon([p(-58, 0), p(52, 0), p(66, -10), p(48, 12), p(-48, 12), p(-64, -6)], fill=govde + (alfa,))
    d.line([p(-58, 0), p(52, 0)], fill=ALTIN + (alfa,), width=max(2, int(3 * s)))
    # direk ve yelken
    d.line([p(0, 0), p(0, -78)], fill=(60, 40, 26, alfa), width=max(2, int(4 * s)))
    yelken = KREM if taraf == "osmanli" else (236, 228, 210)
    d.polygon([p(-34, -6), p(10, -84), p(30, -10)], fill=yelken + (alfa,), outline=(90, 70, 50, alfa))
    d.line([p(-40, 0), p(14, -90)], fill=(60, 40, 26, alfa), width=max(2, int(3 * s)))
    cx, cy = p(4, -32)
    if taraf == "osmanli":
        r = 11 * s
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=OSMANLI + (alfa,))
        d.ellipse([cx - r * 0.55 + yon * r * 0.45, cy - r * 0.8, cx + r * 0.95 + yon * r * 0.45, cy + r * 0.8],
                  fill=yelken + (alfa,))
    else:
        d.line([(cx, cy - 12 * s), (cx, cy + 12 * s)], fill=KIRMIZI + (alfa,), width=max(2, int(5 * s)))
        d.line([(cx - 9 * s, cy - 3 * s), (cx + 9 * s, cy - 3 * s)], fill=KIRMIZI + (alfa,), width=max(2, int(5 * s)))
    renk = OSMANLI if taraf == "osmanli" else DUSMAN
    d.polygon([p(0, -78), p(0, -66), p(-22 + math.sin(sallan * 3) * 3, -72)], fill=renk + (alfa,))


def sancak(d, x, y, boy, taraf="osmanli", sallan=0.0, alfa=255):
    """Kara ordusu işareti: dalgalanan sancak ve altında asker sırası."""
    s = boy / 100.0
    renk = OSMANLI if taraf == "osmanli" else DUSMAN
    for sira in range(2):
        for i in range(4):
            px = x + (i - 1.5) * 20 * s + sira * 10 * s
            py = y + 8 * s + sira * 18 * s
            d.ellipse([px - 7 * s, py - 7 * s, px + 7 * s, py + 7 * s], fill=MUREKKEP + (alfa,))
            d.rectangle([px - 6 * s, py + 5 * s, px + 6 * s, py + 14 * s], fill=renk + (alfa,))
    d.line([(x, y + 6 * s), (x, y - 80 * s)], fill=(60, 40, 26, alfa), width=max(2, int(4 * s)))
    nok = []
    for i in range(9):
        t = i / 8
        nok.append((x + t * 58 * s, y - 78 * s + math.sin(sallan * 3 + t * 4) * 5 * s * t))
    for i in range(8, -1, -1):
        t = i / 8
        nok.append((x + t * 58 * s, y - 44 * s + math.sin(sallan * 3 + t * 4) * 5 * s * t))
    d.polygon(nok, fill=renk + (alfa,), outline=MUREKKEP + (alfa,))
    if taraf == "osmanli":
        cx, cy, r = x + 26 * s, y - 61 * s, 9 * s
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(250, 248, 240, alfa))
        d.ellipse([cx - r * 0.5, cy - r * 0.8, cx + r * 1.1, cy + r * 0.8], fill=renk + (alfa,))
    else:
        cx, cy = x + 28 * s, y - 61 * s
        d.line([(cx, cy - 11 * s), (cx, cy + 11 * s)], fill=(250, 248, 240, alfa), width=max(2, int(4 * s)))
        d.line([(cx - 9 * s, cy - 3 * s), (cx + 9 * s, cy - 3 * s)], fill=(250, 248, 240, alfa), width=max(2, int(4 * s)))


def capraz_kilic(d, x, y, s, alfa=255):
    if s < 0.05:
        return
    for yon in (1, -1):
        uc = (x + yon * 70 * s, y - 70 * s)
        kabza = (x - yon * 52 * s, y + 52 * s)
        d.line([kabza, uc], fill=(235, 235, 240, alfa), width=int(14 * s))
        d.line([kabza, uc], fill=(150, 150, 160, alfa), width=int(4 * s))
        gx, gy = x - yon * 34 * s, y + 34 * s
        d.line([(gx - 20 * s, gy - 20 * s * yon * -1), (gx + 20 * s, gy + 20 * s * yon * -1)],
               fill=ALTIN + (alfa,), width=int(10 * s))
        d.ellipse([kabza[0] - 9 * s, kabza[1] - 9 * s, kabza[0] + 9 * s, kabza[1] + 9 * s], fill=ALTIN + (alfa,))


def kalkan_noktalari(cx, cy, w, h):
    nok = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2)]
    for i in range(13):
        a = i / 12
        x = cx + w / 2 - a * w
        yy = cy - h / 2 + h * 0.45 + math.sin(a * math.pi) * h * 0.55
        nok.append((x, yy if 0 < a < 1 else cy - h / 2 + h * 0.45))
    return nok


def arma(d, cx, cy, s, desen, ad, alfa=255):
    w, h = 150 * s, 180 * s
    nok = kalkan_noktalari(cx, cy, w, h)
    golge = [(x + 8 * s, y + 10 * s) for x, y in nok]
    d.polygon(golge, fill=(0, 0, 0, int(alfa * 0.35)))
    zemin = {"carpi": (238, 196, 70), "kanat": (168, 30, 40), "anahtar": (240, 232, 214),
             "hilal": (178, 30, 36), "kartal": (238, 196, 70), "halka": (40, 40, 52), "kazan": (120, 30, 34),
             "bizans": (96, 30, 90), "defne": (150, 24, 30), "selcuklu": (40, 70, 110)}.get(desen, (200, 200, 200))
    d.polygon(nok, fill=zemin + (alfa,), outline=ALTIN + (alfa,), width=int(7 * s))
    a = alfa
    if desen == "carpi":
        for yon in (1, -1):
            d.line([(cx - 46 * s * yon, cy - 58 * s), (cx + 46 * s * yon, cy + 52 * s)], fill=(170, 30, 30, a),
                   width=int(20 * s))
    elif desen == "kanat":   # Venedik: hale içinde açık kitap
        d.ellipse([cx - 54 * s, cy - 62 * s, cx + 54 * s, cy + 46 * s], outline=ALTIN + (a,), width=int(6 * s))
        for yon in (1, -1):
            d.polygon([(cx, cy - 22 * s), (cx + yon * 44 * s, cy - 34 * s), (cx + yon * 44 * s, cy + 24 * s),
                       (cx, cy + 34 * s)], fill=ALTIN + (a,), outline=(120, 80, 30, a))
            for k in range(3):
                yy = cy - 14 * s + k * 14 * s
                d.line([(cx + yon * 8 * s, yy), (cx + yon * 36 * s, yy - 9 * s)], fill=(140, 30, 34, a), width=max(2, int(3 * s)))
    elif desen == "anahtar":
        for yon, renk in ((1, (220, 170, 40)), (-1, (170, 170, 180))):
            bas, uc = (cx - yon * 40 * s, cy + 44 * s), (cx + yon * 38 * s, cy - 50 * s)
            d.line([bas, uc], fill=renk + (a,), width=int(11 * s))
            d.ellipse([bas[0] - 17 * s, bas[1] - 17 * s, bas[0] + 17 * s, bas[1] + 17 * s], outline=renk + (a,),
                      width=int(8 * s))
            d.line([uc, (uc[0] + yon * 16 * s, uc[1] + 10 * s)], fill=renk + (a,), width=int(9 * s))
    elif desen in ("kartal", "selcuklu"):   # çift başlı kartal (Bizans, Selçuklu)
        renk = (60, 30, 20, a) if desen == "kartal" else ALTIN + (a,)
        d.ellipse([cx - 18 * s, cy - 30 * s, cx + 18 * s, cy + 34 * s], fill=renk)
        for yon in (1, -1):
            d.polygon([(cx + yon * 10 * s, cy - 20 * s), (cx + yon * 62 * s, cy - 54 * s), (cx + yon * 56 * s, cy - 20 * s),
                       (cx + yon * 66 * s, cy - 16 * s), (cx + yon * 50 * s, cy + 8 * s), (cx + yon * 58 * s, cy + 14 * s),
                       (cx + yon * 14 * s, cy + 20 * s)], fill=renk)
            hx, hy = cx + yon * 20 * s, cy - 52 * s
            d.line([(cx + yon * 6 * s, cy - 26 * s), (hx, hy)], fill=renk, width=int(9 * s))
            d.ellipse([hx - 10 * s, hy - 10 * s, hx + 10 * s, hy + 10 * s], fill=renk)
            d.polygon([(hx + yon * 8 * s, hy - 2 * s), (hx + yon * 22 * s, hy + 4 * s), (hx + yon * 8 * s, hy + 8 * s)], fill=(220, 120, 40, a))
        d.line([(cx - 14 * s, cy + 34 * s), (cx - 24 * s, cy + 56 * s)], fill=renk, width=int(6 * s))
        d.line([(cx + 14 * s, cy + 34 * s), (cx + 24 * s, cy + 56 * s)], fill=renk, width=int(6 * s))
    elif desen == "bizans":   # mor zemin, altın haç ve dört köşede B harfi
        d.rectangle([cx - 7 * s, cy - 60 * s, cx + 7 * s, cy + 50 * s], fill=ALTIN + (a,))
        d.rectangle([cx - 50 * s, cy - 14 * s, cx + 50 * s, cy], fill=ALTIN + (a,))
        fb = _f("DejaVuSerif-Bold.ttf", max(8, int(30 * s)))
        for bx, by in ((-30, -44), (16, -44), (-30, 10), (16, 10)):
            d.text((cx + bx * s, cy + by * s), "B", font=fb, fill=ALTIN + (a,))
    elif desen == "defne":   # Roma: defne çelengi ve kartal başı yerine SPQR
        for bas_aci in (110, -70):
            for k in range(7):
                aa = math.radians(bas_aci + k * 23)
                x, y = cx + math.cos(aa) * 50 * s, cy + math.sin(aa) * 50 * s
                d.ellipse([x - 11 * s, y - 6 * s, x + 11 * s, y + 6 * s], fill=ALTIN + (a,))
        fb = _f("DejaVuSerif-Bold.ttf", max(8, int(26 * s)))
        d.text((cx - d.textlength("SPQR", font=fb) / 2, cy - 16 * s), "SPQR", font=fb, fill=ALTIN + (a,))
    elif desen == "kazan":   # yeniçeri kazanı ve kaşığı
        d.chord([cx - 50 * s, cy - 40 * s, cx + 50 * s, cy + 50 * s], 0, 180, fill=(40, 34, 30, a), outline=ALTIN + (a,), width=int(5 * s))
        d.rectangle([cx - 56 * s, cy - 2 * s, cx + 56 * s, cy + 8 * s], fill=ALTIN + (a,))
        d.arc([cx - 40 * s, cy - 50 * s, cx + 40 * s, cy + 20 * s], 200, 340, fill=ALTIN + (a,), width=int(5 * s))
        d.line([(cx + 20 * s, cy - 60 * s), (cx + 44 * s, cy + 4 * s)], fill=(220, 220, 225, a), width=int(7 * s))
        d.ellipse([cx + 12 * s, cy - 70 * s, cx + 30 * s, cy - 54 * s], fill=(220, 220, 225, a))
    elif desen == "halka":   # Timur'un üç halkası
        for hx, hy in ((0, -30), (-30, 22), (30, 22)):
            d.ellipse([cx + hx * s - 22 * s, cy + hy * s - 22 * s, cx + hx * s + 22 * s, cy + hy * s + 22 * s],
                      outline=ALTIN + (a,), width=int(8 * s))
    elif desen == "hilal":
        r = 48 * s
        d.ellipse([cx - r - 10 * s, cy - r, cx + r - 10 * s, cy + r], fill=(250, 248, 240, a))
        d.ellipse([cx - r + 12 * s, cy - r * 0.82, cx + r * 0.82 + 12 * s, cy + r * 0.82], fill=zemin + (a,))
        yildiz(d, cx + 40 * s, cy, 18 * s, (250, 248, 240, a))
    # isim şeridi
    tw = d.textlength(ad, font=F_ARMA)
    y0 = cy + h / 2 + 18 * s
    d.rounded_rectangle([cx - tw / 2 - 22, y0, cx + tw / 2 + 22, y0 + 54], 10, fill=KREM + (a,),
                        outline=MUREKKEP + (a,), width=3)
    d.text((cx - tw / 2, y0 + 9), ad, font=F_ARMA, fill=MUREKKEP + (a,))


def yildiz(d, cx, cy, r, renk):
    nok = []
    for i in range(10):
        aa = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        nok.append((cx + rr * math.cos(aa), cy + rr * math.sin(aa)))
    d.polygon(nok, fill=renk)


def damga(d, cx, cy, metin, olcek, alfa=255):
    """Kırmızı mum mühür."""
    r = 160 * olcek
    nok = []
    for i in range(40):
        aa = i / 40 * math.tau
        rr = r * (1 + 0.06 * math.sin(i * 2.7) + 0.04 * math.cos(i * 5.1))
        nok.append((cx + rr * math.cos(aa), cy + rr * math.sin(aa)))
    d.polygon([(x + 6, y + 8) for x, y in nok], fill=(0, 0, 0, int(alfa * 0.3)))
    d.polygon(nok, fill=(160, 26, 30, alfa))
    d.ellipse([cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78], outline=(120, 14, 18, alfa), width=int(6 * olcek) + 1)
    satirlar = metin.split("\n")
    fnt = F_DAMGA if olcek > 0.2 else F_ARMA
    y = cy - len(satirlar) * 24 * olcek
    for s in satirlar:
        tw = d.textlength(s, font=fnt)
        if olcek >= 0.99:
            d.text((cx - tw / 2, y), s, font=fnt, fill=(250, 226, 200, alfa))
        y += 48 * olcek


def murekkep_damga(d, cx, cy, metin, olcek, alfa=255):
    """Eğik basılmış kırmızı lastik damga: çift çerçeve, aşınmış mürekkep."""
    satirlar = metin.split("\n")
    gen = max(d.textlength(x, font=F_DAMGA) for x in satirlar) + 70
    yuk = 56 * len(satirlar) + 40
    katman = Image.new("RGBA", (int(gen) + 40, int(yuk) + 40), (0, 0, 0, 0))
    k = ImageDraw.Draw(katman)
    renk = (176, 28, 32, alfa)
    k.rectangle([20, 20, 20 + gen, 20 + yuk], outline=renk, width=8)
    k.rectangle([32, 32, 8 + gen, 8 + yuk], outline=renk, width=3)
    y = 40
    for x in satirlar:
        k.text((20 + (gen - k.textlength(x, font=F_DAMGA)) / 2, y), x, font=F_DAMGA, fill=renk)
        y += 56
    rng = np.random.default_rng(len(metin))
    a = np.asarray(katman).copy()
    delik = rng.random(a.shape[:2]) < 0.18   # aşınmış mürekkep
    a[..., 3][delik] = (a[..., 3][delik] * 0.25).astype(np.uint8)
    katman = Image.fromarray(a).rotate(-9, expand=True, resample=Image.BICUBIC)
    if olcek != 1:
        katman = katman.resize((max(1, int(katman.width * olcek)), max(1, int(katman.height * olcek))))
    d._image.paste(katman, (int(cx - katman.width / 2), int(cy - katman.height / 2)), katman)


def ferman(d, cx, cy, metin, ilerle, alfa=255):
    """Açılan ferman tomarı: iki rulo arasından yazı görünür."""
    satirlar = tr_buyuk(metin).split("\n")
    gen = max(d.textlength(x, font=F_DAMGA) for x in satirlar) + 90
    yuk = 56 * len(satirlar) + 50
    acik = yuk * yumusak(ilerle)
    x0, x1 = cx - gen / 2, cx + gen / 2
    d.rectangle([x0 + 8, cy - acik / 2 + 10, x1 + 8, cy + acik / 2 + 10], fill=(0, 0, 0, 70))
    d.rectangle([x0, cy - acik / 2, x1, cy + acik / 2], fill=(244, 230, 196, alfa), outline=(150, 110, 60, alfa), width=3)
    if ilerle > 0.6:
        y = cy - 28 * len(satirlar)
        for x in satirlar:
            d.text((cx - d.textlength(x, font=F_DAMGA) / 2, y), x, font=F_DAMGA, fill=MUREKKEP + (int(alfa * min(1, (ilerle - 0.6) / 0.4)),))
            y += 56
    for yy in (cy - acik / 2, cy + acik / 2):
        d.rounded_rectangle([x0 - 22, yy - 16, x1 + 22, yy + 16], 14, fill=(196, 150, 90, alfa), outline=(110, 74, 40, alfa), width=3)
        for xx in (x0 - 22, x1 + 22):
            d.ellipse([xx - 12, yy - 12, xx + 12, yy + 12], fill=ALTIN + (alfa,))


def rozet(d, cx, cy, metin, alfa=255, fnt=F_ROZET, zemin=KREM, renk=MUREKKEP):
    tw = d.textlength(metin, font=fnt)
    d.rounded_rectangle([cx - tw / 2 - 34 + 6, cy - 44 + 8, cx + tw / 2 + 34 + 6, cy + 44 + 8], 44,
                        fill=(0, 0, 0, int(alfa * 0.35)))
    d.rounded_rectangle([cx - tw / 2 - 34, cy - 44, cx + tw / 2 + 34, cy + 44], 44, fill=zemin + (alfa,),
                        outline=MUREKKEP + (alfa,), width=5)
    d.text((cx - tw / 2, cy - fnt.size * 0.62), metin, font=fnt, fill=renk + (alfa,))


def bant(d, cx, cy, metin, ilerle, alfa=255):
    """Uçları kıvrık kurdele; soldan sağa açılır."""
    tw = d.textlength(metin, font=F_BANT)
    yarim = (tw / 2 + 60) * yumusak(ilerle)
    if yarim < 4:
        return
    for yon in (1, -1):
        ux = cx + yon * yarim
        d.polygon([(ux - yon * 10, cy - 30), (ux + yon * 60, cy - 30), (ux + yon * 34, cy + 6), (ux + yon * 60, cy + 42),
                   (ux - yon * 10, cy + 42)], fill=(130, 24, 28, alfa))
    d.rectangle([cx - yarim, cy - 46, cx + yarim, cy + 46], fill=(176, 34, 34, alfa))
    d.line([(cx - yarim, cy - 36), (cx + yarim, cy - 36)], fill=ALTIN + (alfa,), width=3)
    d.line([(cx - yarim, cy + 36), (cx + yarim, cy + 36)], fill=ALTIN + (alfa,), width=3)
    if ilerle > 0.6:
        a = int(alfa * min(1, (ilerle - 0.6) / 0.4))
        d.text((cx - tw / 2, cy - 33), metin, font=F_BANT, fill=(255, 240, 210, a))


# ---------------------------------------------------------------- harita
KARA_VERI = None


def kara_verisi():
    global KARA_VERI
    if KARA_VERI is None:
        with open(os.path.join(HERE, "assets", "harita_kara.json")) as f:
            KARA_VERI = json.load(f)
    return KARA_VERI


HARITA_TEMA = {
    # deniz üst/alt, sığ su, kara, kara gölgesi, kıyı çizgisi, ağ rengi
    "parsomen": dict(du=(38, 78, 90), da=(22, 46, 58), sig=(64, 112, 120), kara=(226, 206, 160), kk=(196, 168, 120),
                     kiyi=(82, 58, 38), ag=(255, 255, 255), dalga=(255, 255, 255)),
    "gece": dict(du=(16, 26, 48), da=(8, 12, 28), sig=(30, 54, 88), kara=(96, 88, 100), kk=(62, 56, 70),
                 kiyi=(232, 190, 105), ag=(232, 190, 105), dalga=(140, 170, 220)),
    "antika": dict(du=(170, 186, 172), da=(146, 166, 156), sig=(196, 206, 188), kara=(236, 220, 180), kk=(208, 184, 140),
                   kiyi=(92, 62, 40), ag=(92, 62, 40), dalga=(92, 62, 40)),
    "kizil": dict(du=(112, 50, 40), da=(64, 26, 24), sig=(150, 80, 62), kara=(232, 210, 168), kk=(196, 160, 116),
                  kiyi=(40, 20, 16), ag=(255, 220, 180), dalga=(255, 200, 170)),
}


class Harita:
    def __init__(self, spec):
        self.spec = spec
        self.t = HARITA_TEMA.get(spec.get("tema", "parsomen"), HARITA_TEMA["parsomen"])
        self.lonc, self.latc = spec["merkez"]
        self.cos = math.cos(math.radians(self.latc))
        self.k = W / (spec.get("genislik", 20) * self.cos)
        self.taban = self._taban()

    def xy(self, lon, lat):
        return (W / 2 + (lon - self.lonc) * self.cos * self.k, H / 2 - (lat - self.latc) * self.k)

    def _taban(self):
        y = np.linspace(0, 1, H)[:, None, None]
        T = self.t
        deniz = np.array(T["du"]) * (1 - y) + np.array(T["da"]) * y
        deniz = np.broadcast_to(deniz, (H, W, 3)).astype(np.float32).copy()
        maske = Image.new("L", (W, H), 0)
        md = ImageDraw.Draw(maske)
        for halka in kara_verisi():
            nok = [self.xy(lon, lat) for lon, lat in halka]
            xs = [p[0] for p in nok]
            ys = [p[1] for p in nok]
            if max(xs) < -50 or min(xs) > W + 50 or max(ys) < -50 or min(ys) > H + 50:
                continue
            md.polygon(nok, fill=255)
        m = np.asarray(maske).astype(np.float32)[..., None] / 255
        sig = np.asarray(maske.filter(ImageFilter.MaxFilter(25)).filter(ImageFilter.GaussianBlur(14))).astype(np.float32)[..., None] / 255
        deniz = deniz * (1 - sig * 0.55) + np.array(T["sig"]) * sig * 0.55
        ic = np.asarray(maske.filter(ImageFilter.MinFilter(15)).filter(ImageFilter.GaussianBlur(18))).astype(np.float32)[..., None] / 255
        kara = np.array(T["kk"]) * (1 - ic) + np.array(T["kara"]) * ic
        img = deniz * (1 - m) + kara * m
        img += kagit_dokusu(5, 9)
        taban = Image.fromarray(img.clip(0, 255).astype(np.uint8))
        d = ImageDraw.Draw(taban)
        # boylam/enlem ağı
        for lon in range(-20, 70, 5 if self.spec.get("genislik", 20) > 8 else 1):
            x, _ = self.xy(lon, self.latc)
            d.line([(x, 0), (x, H)], fill=T["ag"], width=1)
        for lat in range(20, 60, 5 if self.spec.get("genislik", 20) > 8 else 1):
            _, yy = self.xy(self.lonc, lat)
            d.line([(0, yy), (W, yy)], fill=T["ag"], width=1)
        taban = Image.blend(Image.fromarray(img.clip(0, 255).astype(np.uint8)), taban, 0.12)
        kenar = maske.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
        if self.spec.get("tema") == "antika":   # eski haritalardaki kıyıya paralel dalga çizgileri
            for k, a in ((10, 150), (20, 100), (32, 60), (46, 35)):
                halka = maske.filter(ImageFilter.MaxFilter(k * 2 + 1)).filter(ImageFilter.FIND_EDGES)
                taban.paste(Image.new("RGB", (W, H), T["kiyi"]), (0, 0), halka.point(lambda v, a=a: a if v else 0))
        koyu = Image.new("RGB", (W, H), T["kiyi"])
        taban.paste(koyu, (0, 0), kenar)
        if self.spec.get("tema") == "gece":   # kıyıda altın ışıltı
            parilti = kenar.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(6))
            taban.paste(Image.new("RGB", (W, H), (255, 210, 120)), (0, 0), parilti.point(lambda v: v // 2))
        # dalga çizgileri
        d = ImageDraw.Draw(taban, "RGBA")
        rng = np.random.default_rng(11)
        mm = np.asarray(maske)
        for _ in range(70):
            x, y = int(rng.integers(30, W - 60)), int(rng.integers(int(H * 0.1), int(H * 0.9)))
            if mm[y, x] or mm[y, min(W - 1, x + 40)]:
                continue
            d.arc([x, y, x + 22, y + 12], 200, 340, fill=T["dalga"] + (60,), width=2)
            d.arc([x + 20, y, x + 42, y + 12], 200, 340, fill=T["dalga"] + (60,), width=2)
        self._pusula(d)
        taban = vinyet(taban, 0.5 if self.spec.get("tema") != "gece" else 0.7)
        if self.spec.get("tema") == "antika":   # süslü çift çerçeve
            d = ImageDraw.Draw(taban)
            for k, w in ((26, 6), (40, 2)):
                d.rectangle([k, k, W - k, H - k], outline=T["kiyi"], width=w)
            for cx, cy in ((26, 26), (W - 26, 26), (26, H - 26), (W - 26, H - 26)):
                d.rectangle([cx - 12, cy - 12, cx + 12, cy + 12], fill=T["kiyi"])
        return taban

    def _bulutlar(self):
        """Haritanın üstünden yavaşça geçen yarı saydam bulut/sis katmanı (bir kez üretilir)."""
        rng = np.random.default_rng(int(abs(self.lonc * 100 + self.latc * 10)) % 1000)
        kat = Image.new("L", (W * 2, H), 0)
        d = ImageDraw.Draw(kat)
        for _ in range(26):
            x, y = int(rng.integers(0, W * 2)), int(rng.integers(0, H))
            r = int(rng.integers(H // 14, H // 6))
            d.ellipse([x - r * 1.8, y - r * 0.6, x + r * 1.8, y + r * 0.6], fill=int(rng.integers(40, 90)))
        return kat.filter(ImageFilter.GaussianBlur(H // 30))

    def _pusula(self, d):
        cx, cy, r = (W - 150, H * 0.73, 70) if not yatay() else (W - 130, H * 0.62, 60)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=KREM + (150,), width=3)
        for i in range(8):
            aa = i * math.pi / 4 - math.pi / 2
            rr = r if i % 2 == 0 else r * 0.55
            uc = (cx + rr * math.cos(aa), cy + rr * math.sin(aa))
            y1 = (cx + 12 * math.cos(aa + math.pi / 2), cy + 12 * math.sin(aa + math.pi / 2))
            y2 = (cx + 12 * math.cos(aa - math.pi / 2), cy + 12 * math.sin(aa - math.pi / 2))
            d.polygon([uc, y1, (cx, cy), ], fill=KREM + (170,))
            d.polygon([uc, y2, (cx, cy)], fill=(120, 90, 60, 170))
        yazi(d, (cx, cy - r - 46), "K", F_BOLGE, KREM, 3, alfa=200)

    def kare(self, u, sn):
        sp = self.spec
        img = self.taban.copy()
        d = ImageDraw.Draw(img, "RGBA")
        # rotalar
        for r in sp.get("rotalar", []):
            p = yumusak((u - r.get("bas", 0.05)) / max(0.05, r.get("bit", 0.6) - r.get("bas", 0.05)))
            if p <= 0:
                continue
            nok = [self.xy(*q) for q in r["yol"]]
            parca = self._kes(nok, p)
            renk = OSMANLI if r.get("taraf") == "osmanli" else DUSMAN
            cizgi = r.get("cizgi", sp.get("cizgi", "kesikli"))
            if cizgi == "akan":     # düz parlak hat, üstünde akan ışık
                d.line(parca, fill=(255, 250, 235, 200), width=14, joint="curve")
                d.line(parca, fill=renk + (255,), width=8, joint="curve")
                for i in range(len(parca) - 1):
                    self._kesikli(d, parca[i], parca[i + 1], (255, 230, 160), faz=sn * 1.5, ince=True)
            elif cizgi == "kalin":  # kalın ok gövdesi, ucunda ok başı
                d.line(parca, fill=(20, 14, 10, 120), width=30, joint="curve")
                d.line(parca, fill=renk + (230,), width=22, joint="curve")
                if len(parca) > 1 and r.get("ikon") == "yok":
                    (x0, y0), (x1, y1) = parca[-2], parca[-1]
                    aa = math.atan2(y1 - y0, x1 - x0)
                    d.polygon([(x1 + 38 * math.cos(aa), y1 + 38 * math.sin(aa)),
                               (x1 + 34 * math.cos(aa + 2.4), y1 + 34 * math.sin(aa + 2.4)),
                               (x1 + 34 * math.cos(aa - 2.4), y1 + 34 * math.sin(aa - 2.4))], fill=renk + (240,))
            else:
                for i in range(len(parca) - 1):
                    self._kesikli(d, parca[i], parca[i + 1], renk)
            bas = parca[-1]
            onceki = parca[-2] if len(parca) > 1 else parca[-1]
            yon = 1 if bas[0] >= onceki[0] else -1
            boy = r.get("boy", 70)
            if r.get("ikon") == "yok":
                continue
            if r.get("ikon") == "ordu":
                sancak(d, bas[0], bas[1], boy, r.get("taraf", "osmanli"), sn * 2)
                continue
            for g in range(r.get("gemi", 3)):
                ox, oy = (-yon * 46 * g, 34 * (g % 2) * (1 if g % 4 < 2 else -1)) if g else (0, 0)
                kadirga(d, bas[0] + ox, bas[1] + oy, boy, yon, r.get("taraf", "osmanli"), sn * 3 + g)
        # etiketler
        for e in sp.get("etiketler", []):
            a = int(255 * evre(u, e.get("bas", 0.0), 0.12))
            if not a:
                continue
            x, y = self.xy(e["lon"], e["lat"])
            y += e.get("dy", 0)
            if e.get("tip") == "bolge":
                yazi(d, (x, y), tr_buyuk(e["ad"]), F_BOLGE, (250, 240, 215), 4, alfa=a)
            else:
                d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=MUREKKEP + (a,))
                d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=ALTIN + (a,))
                ad = tr_buyuk(e["ad"])
                tw = d.textlength(ad, font=F_SEHIR)
                ex = x + 22 if e.get("yan", "sag") == "sag" else x - 22 - tw
                if ex + tw > W - 60 or e.get("yan") == "sol":
                    ex = x - 22 - tw
                ex = max(50, ex)
                d.rounded_rectangle([ex - 14, y - 30, ex + tw + 14, y + 26], 10, fill=KREM + (int(a * 0.92),),
                                    outline=MUREKKEP + (a,), width=3)
                d.text((ex, y - 26), ad, font=F_SEHIR, fill=MUREKKEP + (a,))
        # bölge vurgusu
        v = sp.get("vurgu")
        if v and u >= v.get("bas", 0.2):
            x, y = self.xy(v["lon"], v["lat"])
            t = sn - v.get("bas", 0.2) * sp.get("_sure", 6)
            for k in range(3):
                faz = (t * 0.9 + k / 3) % 1
                r = 40 + faz * 170
                d.ellipse([x - r, y - r * 0.7, x + r, y + r * 0.7], outline=tuple(v.get("renk", (255, 214, 90))) + (int(230 * (1 - faz)),), width=7)
        # çarpışma
        c = sp.get("carpisma")
        if c and u >= c.get("bas", 0.6):
            x, y = self.xy(c["lon"], c["lat"])
            e = evre(u, c["bas"], 0.08)
            for k in range(6):   # duman
                aa = k * 1.05 + sn * 0.3
                rr = 60 + 40 * e + 20 * math.sin(sn * 2 + k)
                d.ellipse([x + math.cos(aa) * rr - 46, y + math.sin(aa) * rr * 0.6 - 36, x + math.cos(aa) * rr + 46,
                           y + math.sin(aa) * rr * 0.6 + 36], fill=(70, 66, 62, int(110 * e)))
            capraz_kilic(d, x, y, 0.9 * zipla(e) + 0.02 * math.sin(sn * 8))
        # damga
        dm = sp.get("damga")
        if dm and u >= dm.get("bas", 0.5):
            e = evre(u, dm["bas"], 0.06)
            olcek = 1.8 - 0.8 * yumusak(e)
            x, y = (self.xy(dm["lon"], dm["lat"]) if "lon" in dm else (W / 2, 700))
            dx, dy = x + dm.get("dx", 0 if not yatay() else 300), y + dm.get("dy", -230 if not yatay() else -60)
            tip = dm.get("tip", sp.get("damga_tip", "muhur"))
            if tip == "murekkep":
                murekkep_damga(d, dx, dy, tr_buyuk(dm["yazi"]), olcek, int(255 * min(1, e * 2)))
            elif tip == "ferman":
                ferman(d, dx, dy, dm["yazi"], evre(u, dm["bas"], 0.15), 255)
            else:
                damga(d, dx, dy, tr_buyuk(dm["yazi"]), olcek, int(255 * min(1, e * 2)))
        # sayaç rozeti (ör. "≈230 GEMİ")
        for rz in sp.get("rozetler", []):
            if u >= rz.get("bas", 0):
                a = int(255 * evre(u, rz["bas"], 0.1))
                rozet(d, rz.get("x", W / 2), rz.get("y", 1200), tr_buyuk(rz["yazi"]), a)
        # bulut/sis geçişi
        if sp.get("bulut"):
            if not hasattr(self, "_bulut"):
                self._bulut = self._bulutlar()
            kx = int((sn * 28) % W)
            maske = self._bulut.crop((kx, 0, kx + W, H))
            renk = (255, 250, 240) if sp.get("tema") != "gece" else (120, 130, 160)
            img.paste(Image.new("RGB", (W, H), renk), (0, 0), maske)
        # kamera: yaklaş (varsayılan), uzaklaş ya da kaydır
        kamera = sp.get("kamera", "yaklas")
        zmax = sp.get("zoom", 1.10)
        ox, oy = self.xy(*sp["odak"]) if "odak" in sp else (W / 2, H / 2)
        if kamera == "uzaklas":
            z = zmax + 0.08 - (zmax + 0.08 - 1) * yumusak(u)
        elif kamera == "kaydir":
            z = max(zmax, 1.12)
            ox = ox + (0.5 - yumusak(u)) * W * 0.16
        else:
            z = 1 + (zmax - 1) * yumusak(u)
        if z > 1.001:
            ww, hh = W / z, H / z
            x0 = min(max(ox - ww / 2, 0), W - ww)
            y0 = min(max(oy - hh / 2, 0), H - hh)
            img = img.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + ww, y0 + hh))
        d = ImageDraw.Draw(img, "RGBA")
        # üst başlık
        b = sp.get("baslik")
        if b:
            a = int(255 * evre(sn, 0.1, 0.5))
            if yatay():   # uzun videoda köşede plaket: haritanın ortası açık kalsın
                alt = tr_buyuk(b.get("alt", ""))
                gen = max(d.textlength(b.get("ust", ""), font=F_UST), d.textlength(alt, font=F_UST_ALT)) + 80
                x0 = 60 if b.get("yer", "sol") == "sol" else W - 60 - gen
                d.rounded_rectangle([x0 + 8, 108, x0 + gen + 8, 388], 18, fill=(0, 0, 0, int(a * 0.3)))
                d.rounded_rectangle([x0, 100, x0 + gen, 380], 18, fill=(22, 30, 34, int(a * 0.82)), outline=ALTIN + (a,), width=3)
                yazi(d, (x0 + gen / 2, 118), b.get("ust", ""), F_UST, (255, 236, 190), 6, alfa=a)
                if alt:
                    yazi(d, (x0 + gen / 2, 275), alt, F_UST_ALT, ALTIN, 4, alfa=a)
            else:
                y0 = 230
                d.rectangle([0, y0, W, y0 + 290], fill=(16, 26, 30, int(a * 0.55)))
                f = F_UST
                while d.textlength(b.get("ust", ""), font=f) > W - 100 and f.size > 60:
                    f = _f("DejaVuSerif-Bold.ttf", f.size - 10)
                yazi(d, (W / 2, y0 + 20 + (F_UST.size - f.size) * 0.6), b.get("ust", ""), f, (255, 236, 190), 6, alfa=a)
                if b.get("alt"):
                    yazi(d, (W / 2, y0 + 170), tr_buyuk(b["alt"]), F_UST_ALT, ALTIN, 4, alfa=a)
        return img

    @staticmethod
    def _kes(nok, p):
        uz = [math.dist(nok[i], nok[i + 1]) for i in range(len(nok) - 1)]
        hedef = sum(uz) * p
        cikti = [nok[0]]
        for i, l in enumerate(uz):
            if hedef >= l:
                cikti.append(nok[i + 1]); hedef -= l
            else:
                a = hedef / l if l else 0
                cikti.append((nok[i][0] + (nok[i + 1][0] - nok[i][0]) * a, nok[i][1] + (nok[i + 1][1] - nok[i][1]) * a))
                break
        return cikti

    @staticmethod
    def _kesikli(d, a, b, renk, faz=0.0, ince=False):
        l = math.dist(a, b)
        n = int(l // 30) + 1
        for i in range(n):
            t0, t1 = (i + faz % 1) / n, min(1, (i + faz % 1 + (0.25 if ince else 0.6)) / n)
            if ince:
                d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                        (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=renk + (230,), width=4)
                continue
            d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                    (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=(255, 250, 235, 230), width=10)
            d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                    (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=renk + (255,), width=6)


# ---------------------------------------------------------------- sefer (orduyu izleyen kamera)
def _yumusat(noktalar, adim=10):
    """Catmull-Rom: köşeleri yuvarlatılmış yoğun nokta dizisi (ordu, çizgi ve toz aynı yolu izler)."""
    if len(noktalar) < 3:
        a, b = noktalar[0], noktalar[-1]
        return [(a[0] + (b[0] - a[0]) * i / adim, a[1] + (b[1] - a[1]) * i / adim) for i in range(adim + 1)]
    p = [noktalar[0]] + list(noktalar) + [noktalar[-1]]
    cikti = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for s in range(adim):
            t = s / adim
            t2, t3 = t * t, t * t * t
            cikti.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 +
                                      (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    cikti.append(tuple(p[-2]))
    return cikti


def _yol_noktasi(yol, f):
    """Yolun toplam uzunluğunun f oranındaki nokta ve oradaki yön açısı."""
    uz = [math.dist(yol[i], yol[i + 1]) for i in range(len(yol) - 1)]
    hedef = sum(uz) * min(1.0, max(0.0, f))
    for i, l in enumerate(uz):
        if hedef <= l and l > 0:
            a = hedef / l
            return ((yol[i][0] + (yol[i + 1][0] - yol[i][0]) * a, yol[i][1] + (yol[i + 1][1] - yol[i][1]) * a),
                    math.atan2(yol[i + 1][1] - yol[i][1], yol[i + 1][0] - yol[i][0]))
        hedef -= l
    return yol[-1], math.atan2(yol[-1][1] - yol[-2][1], yol[-1][0] - yol[-2][0]) if len(yol) > 1 else 0.0


def _yol_orani(yol, nokta):
    """Bir noktanın (ör. şehir) yol üzerindeki en yakın yerinin uzunluk oranı ve uzaklığı."""
    i = min(range(len(yol)), key=lambda j: math.dist(yol[j], nokta))
    toplam = sum(math.dist(yol[j], yol[j + 1]) for j in range(len(yol) - 1)) or 1
    return sum(math.dist(yol[j], yol[j + 1]) for j in range(i)) / toplam, math.dist(yol[i], nokta)


def ordu_birligi(d, x, y, aci, s, taraf, sn, alfa=255, sira=3, kol=5):
    """Yürüyen asker birliği: sancağın arkasında sıra sıra miğferli, mızraklı askerler (adım adım sallanır)."""
    renk = OSMANLI if taraf == "osmanli" else DUSMAN
    koyu = tuple(int(c * 0.55) for c in renk)
    ux, uy = math.cos(aci), math.sin(aci)          # yürüyüş yönü
    nx, ny = -uy, ux                               # yana doğru
    askerler = []
    for j in range(kol):
        for i in range(sira):
            geri = (j + 1) * 17 * s + (i % 2) * 8 * s
            yan = (i - (sira - 1) / 2) * 15 * s
            px, py = x - ux * geri + nx * yan, y - uy * geri + ny * yan
            askerler.append((py, px, j, i))
    for py, px, j, i in sorted(askerler):          # arkadakiler (yukarıdakiler) önce
        zip_ = abs(math.sin(sn * 7 + j * 1.3 + i * 0.7)) * 3 * s
        py -= zip_
        d.line([(px + 5 * s, py - 4 * s), (px + 8 * s, py - 30 * s)], fill=(70, 50, 32, alfa), width=max(1, int(2 * s)))
        d.polygon([(px + 8 * s, py - 30 * s), (px + 6 * s, py - 36 * s), (px + 10 * s, py - 35 * s)], fill=(200, 200, 205, alfa))
        d.rounded_rectangle([px - 5 * s, py - 6 * s, px + 5 * s, py + 7 * s], max(1, int(2 * s)), fill=renk + (alfa,),
                            outline=koyu + (alfa,))
        d.ellipse([px - 4 * s, py - 13 * s, px + 4 * s, py - 5 * s], fill=(222, 190, 150, alfa))
        if taraf == "osmanli":   # sivri miğfer / börk
            d.polygon([(px - 5 * s, py - 10 * s), (px + 5 * s, py - 10 * s), (px, py - 19 * s)], fill=(236, 232, 220, alfa))
        else:
            d.chord([px - 5 * s, py - 16 * s, px + 5 * s, py - 6 * s], 180, 360, fill=(150, 150, 160, alfa))
    sancak(d, x, y + 6 * s, 62 * s, taraf, sn * 2, alfa)


class Sefer:
    """Orduyu izleyen kamera: harita büyük çözünürlükte bir kez çizilir; kamera genel görünümden
    yürüyen birliğin üstüne iner, onunla birlikte ilerler, geçtiği şehirlerin iğneleri belirir,
    arkasında toz kalkar; çarpışmada parlama, duman ve sarsıntı olur, sonda genel görünüme açılır.

    spec: rotalar [{yol, taraf, bas, bit, takip?}], etiketler [{ad, lon, lat, yan?}], carpisma {lon, lat, bas},
          zaman [{yazi, bas}] (köşede çevrilen ay/yıl plaketi), baslik {ust, alt}, tema, cizgi,
          yakinlik (takip yakınlaşması, 1.4-2.2), son ("genel" | "carpisma"), merkez/genislik (yoksa rotadan hesaplanır)."""
    OLCEK = 2.0

    def __init__(self, spec):
        global W, H
        self.spec = spec
        noktalar = [q for r in spec["rotalar"] for q in r["yol"]] + \
                   [(e["lon"], e["lat"]) for e in spec.get("etiketler", [])]
        if "merkez" in spec:
            lonc, latc = spec["merkez"]
            gen = spec.get("genislik", 12)
        else:
            lons, lats = [p[0] for p in noktalar], [p[1] for p in noktalar]
            lonc, latc = (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2
            cos = math.cos(math.radians(latc))
            gen_lon = (max(lons) - min(lons)) * 1.35 + 0.6
            gen_lat = ((max(lats) - min(lats)) * 1.35 + 0.6) * W / H / cos
            gen = max(gen_lon, gen_lat, 1.2)
        self.ekran = (W, H)
        S = self.OLCEK
        W, H = int(self.ekran[0] * S), int(self.ekran[1] * S)
        try:
            h = Harita({"merkez": [lonc, latc], "genislik": gen, "tema": spec.get("tema", "parsomen"), "zoom": 1.0})
        finally:
            W, H = self.ekran
        self.taban, self.lonc, self.latc, self.cos, self.k = h.taban, lonc, latc, h.cos, h.k
        self.BW, self.BH = self.taban.size
        self.yollar = [_yumusat([self.bxy(*q) for q in r["yol"]]) for r in spec["rotalar"]]
        ti = next((i for i, r in enumerate(spec["rotalar"]) if r.get("takip")), 0)
        self.takip = ti
        # şehir iğneleri: verilmemişse ordu yanından geçerken belirir
        self.igneler = []
        for e in spec.get("etiketler", []):
            p = self.bxy(e["lon"], e["lat"])
            bas = e.get("bas")
            if bas is None:
                en_iyi = None
                for i, r in enumerate(spec["rotalar"]):
                    f, uz = _yol_orani(self.yollar[i], p)
                    t = r.get("bas", 0.08) + (r.get("bit", 0.7) - r.get("bas", 0.08)) * f - 0.04
                    if en_iyi is None or uz < en_iyi[1]:
                        en_iyi = (t, uz)
                bas = max(0.0, en_iyi[0])
            self.igneler.append((e, p, bas))

    def bxy(self, lon, lat):
        return (self.BW / 2 + (lon - self.lonc) * self.cos * self.k, self.BH / 2 - (lat - self.latc) * self.k)

    def _ilerleme(self, r, u):
        return yumusak((u - r.get("bas", 0.08)) / max(0.05, r.get("bit", 0.7) - r.get("bas", 0.08)))

    def _kamera(self, u, sn):
        """(merkez_x, merkez_y, yakınlaşma) – büyük tuval koordinatında."""
        sp = self.spec
        S = self.OLCEK
        zt = sp.get("yakinlik", 1.8)
        genel = (self.BW / 2, self.BH / 2, 1.0)
        r = sp["rotalar"][self.takip]
        p = self._ilerleme(r, u)
        bas, _ = _yol_noktasi(self.yollar[self.takip], p)
        c = sp.get("carpisma")
        if c and u >= c.get("bas", 0.75) - 0.06:
            cx, cy = self.bxy(c["lon"], c["lat"])
            a = yumusak((u - c.get("bas", 0.75) + 0.06) / 0.08)
            bas = (bas[0] + (cx - bas[0]) * a, bas[1] + (cy - bas[1]) * a)
        giris = yumusak((u - 0.0) / max(0.05, r.get("bas", 0.08) + 0.06))
        cik = sp.get("son", "genel") == "genel" and u > 0.88
        a = giris * (1 - (yumusak((u - 0.88) / 0.12) if cik else 0))
        z = 1 + (zt - 1) * a
        x = genel[0] + (bas[0] - genel[0]) * a
        y = genel[1] + (bas[1] - genel[1]) * a
        if c and u >= c.get("bas", 0.75):   # çarpışma sarsıntısı
            t = (u - c["bas"]) * sp.get("_sure", 8)
            g = max(0.0, 1 - t / 0.7) * 14 * S
            x += math.sin(sn * 53) * g
            y += math.cos(sn * 47) * g
        return x, y, min(z, S)

    def kare(self, u, sn):
        sp = self.spec
        EW, EH = self.ekran
        cx, cy, z = self._kamera(u, sn)
        ww, hh = self.BW / z, self.BH / z
        x0 = min(max(cx - ww / 2, 0), self.BW - ww)
        y0 = min(max(cy - hh / 2, 0), self.BH - hh)
        img = self.taban.resize((EW, EH), Image.BILINEAR, box=(x0, y0, x0 + ww, y0 + hh))
        d = ImageDraw.Draw(img, "RGBA")
        oran = EW / ww
        olc = max(0.8, min(1.7, oran * 1.5))       # ikon ölçeği yakınlaşmayla büyür

        def ex(p):
            return ((p[0] - x0) * oran, (p[1] - y0) * oran)

        # rotalar ve ordular
        ordular = []
        for i, r in enumerate(sp["rotalar"]):
            p = self._ilerleme(r, u)
            if p <= 0:
                continue
            yol = [ex(q) for q in self.yollar[i]]
            parca = Harita._kes(yol, p)
            renk = OSMANLI if r.get("taraf") == "osmanli" else DUSMAN
            cizgi = r.get("cizgi", sp.get("cizgi", "kesikli"))
            if cizgi == "kalin":
                d.line(parca, fill=(20, 14, 10, 110), width=int(24 * olc), joint="curve")
                d.line(parca, fill=renk + (220,), width=int(16 * olc), joint="curve")
            elif cizgi == "akan":
                d.line(parca, fill=(255, 250, 235, 200), width=int(12 * olc), joint="curve")
                d.line(parca, fill=renk + (255,), width=int(7 * olc), joint="curve")
                for k in range(len(parca) - 1):
                    Harita._kesikli(d, parca[k], parca[k + 1], (255, 230, 160), faz=sn * 1.5, ince=True)
            else:
                for k in range(len(parca) - 1):
                    Harita._kesikli(d, parca[k], parca[k + 1], renk)
            (hx, hy), aci = _yol_noktasi(yol, p)
            # toz: ordunun geçtiği yerde kalkıp sönen bulutçuklar
            rng = np.random.default_rng(i * 97 + 5)
            ofs = rng.random((18, 3))
            yuruyor = p < 0.999
            for k in range(18):
                gp = p - (k + 1) * 0.012
                if gp <= 0:
                    break
                (tx, ty), _ = _yol_noktasi(yol, gp)
                yas = k / 18
                rr = (10 + 26 * yas) * olc
                al = int((70 if yuruyor else 30) * (1 - yas))
                tx += (ofs[k, 0] - 0.5) * 30 * olc
                ty += (ofs[k, 1] - 0.5) * 18 * olc - yas * 14 * olc
                d.ellipse([tx - rr, ty - rr * 0.6, tx + rr, ty + rr * 0.6], fill=(214, 196, 160, al))
            ordular.append((hy, hx, aci, r, p))
        for hy, hx, aci, r, p in sorted(ordular, key=lambda o: o[0]):
            if r.get("ikon", "ordu") == "gemi":
                for g in range(r.get("gemi", 3)):
                    kadirga(d, hx - math.cos(aci) * 50 * g * olc, hy - math.sin(aci) * 50 * g * olc + 26 * (g % 2) * olc,
                            70 * olc, 1 if math.cos(aci) >= 0 else -1, r.get("taraf", "osmanli"), sn * 3 + g)
            else:
                ordu_birligi(d, hx, hy, aci, olc * 1.3, r.get("taraf", "osmanli"), sn if p < 0.999 else 0)
        # çarpışma: parlama, duman, kılıçlar
        c = sp.get("carpisma")
        if c and u >= c.get("bas", 0.75):
            x, y = ex(self.bxy(c["lon"], c["lat"]))
            t = (u - c["bas"]) * sp.get("_sure", 8)
            e_ = min(1.0, t / 0.4)
            rng = np.random.default_rng(7)
            for k in range(12):
                aa = rng.random() * math.tau
                hiz = 60 + rng.random() * 120
                rr = (46 + t * 34) * olc
                px = x + math.cos(aa) * hiz * min(1.0, t) * olc
                py = y + math.sin(aa) * hiz * 0.6 * min(1.0, t) * olc - t * 18 * olc
                d.ellipse([px - rr, py - rr * 0.7, px + rr, py + rr * 0.7], fill=(78, 72, 66, int(120 * max(0.25, 1 - t / 4))))
            capraz_kilic(d, x, y - 10 * olc, 0.8 * olc * zipla(e_) + 0.02 * math.sin(sn * 8))
        # şehir iğneleri
        for e, p, bas in self.igneler:
            e_ = evre(u, bas, 0.06)
            if e_ <= 0:
                continue
            x, y = ex(p)
            a = int(255 * min(1, e_ * 2))
            yuk = 46 * olc * zipla(e_)
            d.line([(x, y), (x, y - yuk)], fill=MUREKKEP + (a,), width=max(2, int(4 * olc)))
            d.ellipse([x - 7, y - 4, x + 7, y + 4], fill=(0, 0, 0, a // 3))
            d.ellipse([x - 12 * olc, y - yuk - 12 * olc, x + 12 * olc, y - yuk + 12 * olc], fill=KIRMIZI + (a,),
                      outline=MUREKKEP + (a,), width=2)
            ad = tr_buyuk(e["ad"])
            tw = d.textlength(ad, font=F_SEHIR)
            sag = e.get("yan", "sag") == "sag"
            lx = x + 24 * olc if sag else x - 24 * olc - tw
            if lx + tw > EW - 40:
                lx = x - 24 * olc - tw
            lx = max(40, lx)
            ly = y - yuk + e.get("dy", 0)
            d.rounded_rectangle([lx - 12, ly - 28, lx + tw + 12, ly + 26], 10, fill=KREM + (int(a * 0.93),),
                                outline=MUREKKEP + (a,), width=3)
            d.text((lx, ly - 25), ad, font=F_SEHIR, fill=MUREKKEP + (a,))
        if c and u >= c.get("bas", 0.75):
            t = (u - c["bas"]) * sp.get("_sure", 8)
            parla = max(0.0, 1 - t / 0.35)
            if parla > 0:
                img.paste(Image.new("RGB", (EW, EH), (255, 244, 214)), (0, 0),
                          Image.new("L", (EW, EH), int(150 * parla)))
                d = ImageDraw.Draw(img, "RGBA")
        # zaman plaketi (köşede çevrilen ay/yıl)
        zaman = [zz for zz in sp.get("zaman", []) if u >= zz.get("bas", 0)]
        if zaman:
            zz = zaman[-1]
            e_ = evre(u, zz.get("bas", 0), 0.05)
            metin = tr_buyuk(zz["yazi"])
            tw = d.textlength(metin, font=F_UST_ALT)
            px, py = (60, 60) if yatay() else (60, 150)
            d.rounded_rectangle([px + 6, py + 8, px + tw + 66, py + 96], 14, fill=(0, 0, 0, 80))
            d.rounded_rectangle([px, py, px + tw + 60, py + 88], 14, fill=(22, 30, 34, 225), outline=ALTIN + (255,), width=3)
            d.text((px + 30, py + 44 - F_UST_ALT.size * 0.62 + (1 - yumusak(e_)) * 24), metin, font=F_UST_ALT,
                   fill=(255, 236, 190, int(255 * e_)))
        # başlık plaketi (sağ üst / dikeyde üst bant)
        b = sp.get("baslik")
        if b:
            a = int(255 * evre(sn, 0.1, 0.5))
            alt = tr_buyuk(b.get("alt", ""))
            gen = max(d.textlength(b.get("ust", ""), font=F_UST), d.textlength(alt, font=F_UST_ALT)) + 80
            if yatay():
                bx0, by0 = EW - 60 - gen, 60
            else:
                bx0, by0 = (EW - gen) / 2, 300
            d.rounded_rectangle([bx0 + 8, by0 + 8, bx0 + gen + 8, by0 + 288], 18, fill=(0, 0, 0, int(a * 0.3)))
            d.rounded_rectangle([bx0, by0, bx0 + gen, by0 + 280], 18, fill=(22, 30, 34, int(a * 0.82)), outline=ALTIN + (a,), width=3)
            yazi(d, (bx0 + gen / 2, by0 + 18), b.get("ust", ""), F_UST, (255, 236, 190), 6, alfa=a)
            if alt:
                yazi(d, (bx0 + gen / 2, by0 + 175), alt, F_UST_ALT, ALTIN, 4, alfa=a)
        return img


# ---------------------------------------------------------------- mekan (şehir içi yer: bina silueti)
BINA_TURU = [   # ad içinde geçen kelime → bina türü (sıra önemli: "Yıldız Camii" saray değil cami)
    ("cami", ("cami", "ayasofya", "süleymaniye", "külliye", "eyüp sultan", "mescit")),
    ("kule", ("kule",)),
    ("carsi", ("çarşı", "bedesten", "tahtakale")),
    ("kale", ("kale", "hisar", "kavağı", "seddülbahir", "kumkale", "surlar")),
    ("meydan", ("meydan", "hipodrom")),
    ("konak", ("konağı", "konak", "köşk", "babıali", "yalı")),
    ("manastir", ("manastır", "kilise")),
    ("saray", ("saray", "topkapı", "dolmabahçe", "çırağan", "yıldız", "harem", "sadabad")),
    ("kiyi", ("boğaz", "üsküdar", "tophane", "karaköy", "galata", "liman", "haliç")),
]
SEHIRLER = [("İstanbul", 28.98, 41.01), ("Edirne", 26.56, 41.68), ("Bursa", 29.06, 40.19), ("Yanya", 20.85, 39.67),
            ("Konya", 32.48, 37.87), ("Kahire", 31.24, 30.04), ("Şam", 36.29, 33.51), ("Bağdat", 44.36, 33.31),
            ("Selanik", 22.94, 40.64), ("Amasya", 35.83, 40.65), ("Manisa", 27.43, 38.61), ("Akka", 35.07, 32.92),
            ("Belgrad", 20.46, 44.82), ("Budin", 19.04, 47.5), ("Taberiye", 35.53, 32.79), ("Çanakkale", 26.4, 40.15)]
MEKAN_RENK = {   # gök üst, gök alt, deniz üst, deniz alt, siluet, uzak siluet, pencere ışığı
    "gunbatimi": ((58, 40, 72), (246, 168, 104), (96, 62, 78), (28, 20, 34), (34, 22, 30), (128, 78, 84), (255, 206, 120)),
    "gece": ((6, 10, 28), (42, 50, 96), (22, 30, 60), (6, 8, 20), (12, 14, 28), (40, 46, 80), (255, 204, 110)),
    "safak": ((70, 96, 150), (246, 204, 170), (120, 140, 168), (46, 62, 90), (48, 46, 68), (140, 132, 156), (255, 226, 170)),
    "parsomen": ((226, 206, 164), (214, 190, 146), (200, 178, 136), (186, 160, 118), (184, 156, 112), (196, 174, 134), (150, 40, 34)),
}


def bina_turu(ad):
    a = ad.lower().replace("I", "ı").replace("İ", "i")
    for tur, kelimeler in BINA_TURU:
        if any(k in a for k in kelimeler):
            return tur
    return "sehir"


def _kubbe(d, cx, ty, r, renk, cizgi=None, alem=False, cz=2):
    """ty: kubbenin oturduğu çizgi; yarım elips kubbe, tepede alem."""
    d.chord([cx - r, ty - r * 0.95, cx + r, ty + r * 0.95], 180, 360, fill=renk, outline=cizgi, width=cz)
    d.line([(cx, ty - r * 0.95), (cx, ty - r * 0.95 - r * 0.28)], fill=cizgi or renk, width=max(2, int(r * 0.08)))
    if alem:   # hilal
        rr = r * 0.12
        y0 = ty - r * 0.95 - r * 0.28 - rr
        d.arc([cx - rr, y0 - rr, cx + rr, y0 + rr], 300, 240, fill=cizgi or renk, width=max(2, int(rr * 0.5)))


def _minare(d, x, by, s, boy, renk, cizgi=None, cz=2):
    w = 3.4 * s
    d.rectangle([x - w / 2, by - boy * s, x + w / 2, by], fill=renk, outline=cizgi, width=cz)
    for k in (0.62, 0.8):
        yy = by - boy * s * k
        d.rectangle([x - w * 0.95, yy - 1.4 * s, x + w * 0.95, yy + 0.6 * s], fill=renk, outline=cizgi, width=cz)
    d.polygon([(x - w / 2, by - boy * s), (x + w / 2, by - boy * s), (x, by - boy * s - 11 * s)], fill=renk, outline=cizgi)


def _pencereler(d, x0, x1, y, s, isik, rng, yogun=0.6):
    if isik is None:
        return
    x = x0 + 3 * s
    while x < x1 - 3 * s:
        if rng.random() < yogun:
            d.rounded_rectangle([x, y - 3.2 * s, x + 1.8 * s, y], max(1, int(s * 0.8)), fill=isik)
        x += 4.6 * s


def bina_ciz(d, tur, cx, by, s, renk, cizgi=None, isik=None, minare=4, seed=1):
    """by: zemin çizgisi, s: birim (bina ~100 birim genişliğinde)."""
    rng = np.random.default_rng(seed)
    cz = max(2, int(s * 0.5))
    if tur == "cami":
        d.rectangle([cx - 40 * s, by - 16 * s, cx + 40 * s, by], fill=renk, outline=cizgi, width=cz)
        for k in (-30, -16, 16, 30):
            _kubbe(d, cx + k * s, by - 16 * s, 6 * s, renk, cizgi, cz=cz)
        d.rectangle([cx - 24 * s, by - 24 * s, cx + 24 * s, by - 16 * s], fill=renk, outline=cizgi, width=cz)
        for k in (-17, 17):
            _kubbe(d, cx + k * s, by - 24 * s, 11 * s, renk, cizgi, cz=cz)
        d.rectangle([cx - 17 * s, by - 31 * s, cx + 17 * s, by - 24 * s], fill=renk, outline=cizgi, width=cz)
        _kubbe(d, cx, by - 31 * s, 19 * s, renk, cizgi, alem=True, cz=cz)
        xs = {2: (-46, 46), 4: (-48, -36, 36, 48), 6: (-50, -42, -34, 34, 42, 50)}.get(minare, (-48, 48))
        for k in xs:
            _minare(d, cx + k * s, by, s, 62 if abs(k) > 40 else 52, renk, cizgi, cz)
        _pencereler(d, cx - 38 * s, cx + 38 * s, by - 5 * s, s, isik, rng, 0.5)
    elif tur == "saray":
        d.rectangle([cx - 52 * s, by - 13 * s, cx + 52 * s, by], fill=renk, outline=cizgi, width=cz)
        for i in range(-52, 52, 5):   # mazgallar
            d.rectangle([cx + i * s, by - 15.5 * s, cx + (i + 2.6) * s, by - 13 * s], fill=renk, outline=cizgi, width=1)
        d.rectangle([cx - 40 * s, by - 22 * s, cx - 4 * s, by - 13 * s], fill=renk, outline=cizgi, width=cz)
        for k in (-34, -24, -14):
            _kubbe(d, cx + k * s, by - 22 * s, 4 * s, renk, cizgi, cz=cz)
        d.rectangle([cx + 14 * s, by - 46 * s, cx + 22 * s, by - 13 * s], fill=renk, outline=cizgi, width=cz)   # Adalet Kulesi
        d.polygon([(cx + 13 * s, by - 46 * s), (cx + 23 * s, by - 46 * s), (cx + 18 * s, by - 62 * s)], fill=renk, outline=cizgi)
        for k in (-8, 8):   # kapı kuleleri
            d.rectangle([cx + (k - 3.5) * s, by - 28 * s, cx + (k + 3.5) * s, by], fill=renk, outline=cizgi, width=cz)
            d.polygon([(cx + (k - 4.5) * s, by - 28 * s), (cx + (k + 4.5) * s, by - 28 * s), (cx + k * s, by - 40 * s)],
                      fill=renk, outline=cizgi)
        d.chord([cx - 4 * s, by - 14 * s, cx + 4 * s, by - 2 * s], 180, 360, fill=isik or (20, 14, 10))
        d.rectangle([cx - 4 * s, by - 8 * s, cx + 4 * s, by], fill=isik or (20, 14, 10))
        for k in (-58, -48, 30, 40, 50):   # selviler
            d.ellipse([cx + (k - 2.2) * s, by - 30 * s, cx + (k + 2.2) * s, by + 1 * s], fill=renk, outline=cizgi, width=1)
        _pencereler(d, cx + 26 * s, cx + 52 * s, by - 5 * s, s, isik, rng)
        _pencereler(d, cx - 40 * s, cx - 12 * s, by - 16 * s, s, isik, rng)
    elif tur == "kule":
        d.rectangle([cx - 30 * s, by - 8 * s, cx + 30 * s, by], fill=renk, outline=cizgi, width=cz)
        d.rectangle([cx - 9 * s, by - 62 * s, cx + 9 * s, by - 8 * s], fill=renk, outline=cizgi, width=cz)
        d.rectangle([cx - 11 * s, by - 68 * s, cx + 11 * s, by - 62 * s], fill=renk, outline=cizgi, width=cz)
        d.polygon([(cx - 11 * s, by - 68 * s), (cx + 11 * s, by - 68 * s), (cx, by - 92 * s)], fill=renk, outline=cizgi)
        if isik:
            for yy in (by - 66 * s, by - 50 * s, by - 34 * s, by - 20 * s):
                d.rectangle([cx - 1.2 * s, yy - 3 * s, cx + 1.2 * s, yy], fill=isik)
        for k in (-26, -18, 18, 26):
            d.rectangle([cx + (k - 4) * s, by - 16 * s, cx + (k + 4) * s, by - 8 * s], fill=renk, outline=cizgi, width=cz)
            d.polygon([(cx + (k - 5) * s, by - 16 * s), (cx + (k + 5) * s, by - 16 * s), (cx + k * s, by - 22 * s)], fill=renk, outline=cizgi)
    elif tur in ("kale", "manastir") and tur == "kale":
        d.rectangle([cx - 50 * s, by - 18 * s, cx + 50 * s, by], fill=renk, outline=cizgi, width=cz)
        for i in range(-50, 50, 6):
            d.rectangle([cx + i * s, by - 22 * s, cx + (i + 3) * s, by - 18 * s], fill=renk, outline=cizgi, width=1)
        for k in (-46, -16, 16, 46):
            d.rectangle([cx + (k - 6) * s, by - 32 * s, cx + (k + 6) * s, by], fill=renk, outline=cizgi, width=cz)
            for j in (-6, -2, 2):
                d.rectangle([cx + (k + j) * s, by - 36 * s, cx + (k + j + 2.4) * s, by - 32 * s], fill=renk, outline=cizgi, width=1)
        d.rectangle([cx - 8 * s, by - 46 * s, cx + 8 * s, by - 18 * s], fill=renk, outline=cizgi, width=cz)
        for j in (-8, -3.5, 1, 5.5):
            d.rectangle([cx + j * s, by - 50 * s, cx + (j + 2.5) * s, by - 46 * s], fill=renk, outline=cizgi, width=1)
        d.chord([cx - 5 * s, by - 12 * s, cx + 5 * s, by + 2 * s], 180, 360, fill=isik or (20, 14, 10))
    elif tur == "manastir":
        d.rectangle([cx - 30 * s, by - 18 * s, cx + 30 * s, by], fill=renk, outline=cizgi, width=cz)
        d.rectangle([cx - 10 * s, by - 26 * s, cx + 10 * s, by - 18 * s], fill=renk, outline=cizgi, width=cz)
        _kubbe(d, cx, by - 26 * s, 10 * s, renk, cizgi, cz=cz)
        for k in (-22, 22):
            _kubbe(d, cx + k * s, by - 18 * s, 6 * s, renk, cizgi, cz=cz)
        for k in (-46, -40, 40, 48):
            d.ellipse([cx + (k - 2.4) * s, by - 30 * s, cx + (k + 2.4) * s, by + 1 * s], fill=renk, outline=cizgi, width=1)
        _pencereler(d, cx - 28 * s, cx + 28 * s, by - 6 * s, s, isik, rng)
    elif tur == "meydan":
        bina_ciz(d, "cami", cx + 18 * s, by - 2 * s, s * 0.62, renk, cizgi, isik, 6, seed)
        d.polygon([(cx - 36 * s, by), (cx - 30 * s, by), (cx - 31.5 * s, by - 44 * s), (cx - 33 * s, by - 50 * s),
                   (cx - 34.5 * s, by - 44 * s)], fill=renk, outline=cizgi)   # dikilitaş
        d.polygon([(cx - 14 * s, by), (cx - 8 * s, by), (cx - 9.5 * s, by - 40 * s), (cx - 12.5 * s, by - 40 * s)],
                  fill=renk, outline=cizgi)   # örme dikilitaş
        for i in range(-56, 56, 3):   # kalabalık
            hh = 2.4 + rng.random() * 1.4
            d.ellipse([cx + i * s, by - hh * s - 2 * s, cx + (i + 2) * s, by - hh * s], fill=renk, outline=cizgi, width=1)
            d.rectangle([cx + (i + 0.2) * s, by - hh * s - 0.5 * s, cx + (i + 1.8) * s, by], fill=renk)
    elif tur == "konak":
        d.rectangle([cx - 36 * s, by - 6 * s, cx + 36 * s, by], fill=renk, outline=cizgi, width=cz)
        d.rectangle([cx - 32 * s, by - 20 * s, cx + 32 * s, by - 6 * s], fill=renk, outline=cizgi, width=cz)
        d.rectangle([cx - 36 * s, by - 34 * s, cx + 36 * s, by - 20 * s], fill=renk, outline=cizgi, width=cz)   # cumbalı üst kat
        d.polygon([(cx - 42 * s, by - 34 * s), (cx + 42 * s, by - 34 * s), (cx + 28 * s, by - 46 * s), (cx - 28 * s, by - 46 * s)],
                  fill=renk, outline=cizgi)
        d.rectangle([cx + 12 * s, by - 52 * s, cx + 16 * s, by - 42 * s], fill=renk, outline=cizgi, width=1)
        _pencereler(d, cx - 32 * s, cx + 32 * s, by - 24 * s, s, isik, rng, 0.7)
        _pencereler(d, cx - 28 * s, cx + 28 * s, by - 10 * s, s, isik, rng, 0.5)
    elif tur == "carsi":
        d.rectangle([cx - 46 * s, by - 16 * s, cx + 46 * s, by], fill=renk, outline=cizgi, width=cz)
        for k in range(-40, 41, 16):
            _kubbe(d, cx + k * s, by - 16 * s, 7 * s, renk, cizgi, cz=cz)
        for k in range(-40, 41, 10):
            d.chord([cx + (k - 2.5) * s, by - 9 * s, cx + (k + 2.5) * s, by - 3 * s], 180, 360, fill=isik or (20, 14, 10))
            d.rectangle([cx + (k - 2.5) * s, by - 6 * s, cx + (k + 2.5) * s, by], fill=isik or (20, 14, 10))
    else:   # sehir / kiyi: iki cami ve evler
        for i in range(-56, 56, 9):
            hh = 8 + rng.random() * 10
            d.rectangle([cx + i * s, by - hh * s, cx + (i + 8) * s, by], fill=renk, outline=cizgi, width=1)
            d.polygon([(cx + (i - 1) * s, by - hh * s), (cx + (i + 9) * s, by - hh * s), (cx + (i + 4) * s, by - (hh + 4) * s)],
                      fill=renk, outline=cizgi)
            if isik and rng.random() < 0.6:
                d.rectangle([cx + (i + 3) * s, by - (hh - 3) * s, cx + (i + 5) * s, by - (hh - 6) * s], fill=isik)
        bina_ciz(d, "cami", cx - 22 * s, by - 6 * s, s * 0.55, renk, cizgi, isik, 2, seed + 1)
        bina_ciz(d, "cami", cx + 26 * s, by - 4 * s, s * 0.7, renk, cizgi, isik, 4, seed + 2)


class Mekan:
    """Şehir içindeki bir yer: düz harita yerine gök, uzak şehir silueti, ortada binanın silueti ve suda yansıması.
    Binanın üstüne iğne düşer, adı plakette çıkar; köşede madalyonda bölge haritası ve konum noktası.
    spec: yer (ad), bina (cami|saray|kule|kale|meydan|konak|carsi|manastir|sehir; yoksa addan tahmin), alt (ikinci satır;
          yoksa en yakın şehir), lon/lat (madalyon için), arka (gunbatimi|gece|safak|parsomen), minare (2|4|6), damga."""
    OLCEK = 2

    def __init__(self, spec):
        self.spec = spec
        S = self.OLCEK
        self.BW, self.BH = W * S, H * S
        BW, BH = self.BW, self.BH
        arka = spec.get("arka", "gunbatimi")
        gu, ga, du, da, sil, uzak, isik = MEKAN_RENK.get(arka, MEKAN_RENK["gunbatimi"])
        parsomen = arka == "parsomen"
        self.ufuk = ufuk = int(BH * (0.66 if yatay() else 0.6))
        y = np.linspace(0, 1, ufuk)[:, None, None]
        gok = np.array(gu) * (1 - y) + np.array(ga) * y
        img = np.zeros((BH, BW, 3), np.float32)
        img[:ufuk] = gok
        yy = np.linspace(0, 1, BH - ufuk)[:, None, None]
        img[ufuk:] = np.array(du) * (1 - yy) + np.array(da) * yy
        gx = BW * (0.72 if yatay() else 0.7)
        if not parsomen:   # güneş/ay ışığı
            g = np.mgrid[0:BH:4, 0:BW:4]
            r = np.sqrt((g[1] - gx) ** 2 + (g[0] - (ufuk - BH * 0.06)) ** 2)
            hale = np.clip(1 - r / (BH * 0.42), 0, 1) ** 2 * (55 if arka != "gece" else 25)
            hale = np.asarray(Image.fromarray(hale.astype(np.float32)).resize((BW, BH), Image.BILINEAR))
            img += hale[..., None] * (np.array([1, 0.8, 0.45]) if arka != "gece" else np.array([0.6, 0.65, 0.9]))
        taban = Image.fromarray(img.clip(0, 255).astype(np.uint8))
        d = ImageDraw.Draw(taban, "RGBA")
        rng = np.random.default_rng(len(spec.get("yer", "")) * 7 + 3)
        if arka == "gece":
            for _ in range(260):
                x, yy3 = int(rng.integers(0, BW)), int(rng.integers(0, int(ufuk * 0.85)))
                rr = float(rng.uniform(1.5, 4.5))
                d.ellipse([x - rr, yy3 - rr, x + rr, yy3 + rr], fill=(255, 250, 230, int(rng.integers(110, 255))))
            my = ufuk - BH * 0.36
            d.ellipse([gx - 70, my - 70, gx + 70, my + 70], fill=(250, 244, 220, 240))
            d.ellipse([gx - 34, my - 82, gx + 96, my + 52], fill=gu + (255,))
        elif not parsomen:
            d.ellipse([gx - 110, ufuk - BH * 0.06 - 110, gx + 110, ufuk - BH * 0.06 + 110], fill=(255, 236, 190, 210))
        # uzak şehir silueti
        cz = None if not parsomen else MUREKKEP + (150,)
        x = -BW * 0.05
        s_uzak = BW / (900 if yatay() else 520)
        bizans = YIL is not None and YIL < 1453 and "lon" in spec and \
            min(math.dist((spec["lon"], spec["lat"]), c) for c in ((28.98, 41.01), (22.94, 40.64))) < 0.6
        while x < BW * 1.05:   # fetihten önceki Konstantinopolis/Selanik'te minare yok
            tur = (["manastir", "kale", "manastir", "kule"] if bizans else ["cami", "sehir", "kule", "cami", "sehir"])[int(rng.integers(0, 4 if bizans else 5))]
            sc = s_uzak * float(rng.uniform(0.5, 0.85))
            if tur == "kule":
                sc *= 0.7
            bina_ciz(d, tur, x, ufuk + 2, sc, uzak + (255,), cz, None, int(rng.choice([2, 4])), int(rng.integers(0, 99)))
            x += sc * float(rng.uniform(70, 120))
        if not parsomen:   # pus
            pus = Image.new("L", (BW, BH), 0)
            ImageDraw.Draw(pus).rectangle([0, ufuk - BH * 0.12, BW, ufuk], fill=70)
            pus = pus.filter(ImageFilter.GaussianBlur(BH * 0.03))
            taban.paste(Image.new("RGB", (BW, BH), ga), (0, 0), pus)
            d = ImageDraw.Draw(taban, "RGBA")
        # ana bina
        self.tur = spec.get("bina") or bina_turu(spec.get("yer", ""))
        if bizans and self.tur in ("cami", "sehir", "meydan"):
            self.tur = "manastir"   # fetihten önce minaresiz kilise
        s = BW / (290 if yatay() else 150)
        if self.tur == "kule":
            s *= 0.85 if not yatay() else 1.0
        self.bx, self.by, self.s = BW * (0.5 if not yatay() else 0.5), ufuk + 4 * s, s
        isik_r = isik + (255,) if arka in ("gece", "gunbatimi") else None
        renk = sil + (255,)
        cizgi = MUREKKEP + (255,) if parsomen else None
        katman = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
        kd = ImageDraw.Draw(katman)
        bina_ciz(kd, self.tur, self.bx, self.by, s, renk, cizgi, isik_r, spec.get("minare", 4), len(spec.get("yer", "")))
        # suda yansıma
        kutu = katman.crop((0, 0, BW, int(self.by)))
        yans = kutu.transpose(Image.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(6))
        a = np.asarray(yans).copy()
        sol = np.linspace(0.55, 0.0, a.shape[0])[:, None]
        a[..., 3] = (a[..., 3] * sol).astype(np.uint8)
        if not parsomen:
            taban.paste(Image.fromarray(a), (0, int(self.by)), Image.fromarray(a))
        taban.paste(katman, (0, 0), katman)
        d = ImageDraw.Draw(taban, "RGBA")
        if not parsomen:
            for _ in range(140):
                x, y2 = int(rng.integers(0, BW)), int(rng.integers(int(self.by) + 10, BH))
                d.line([(x, y2), (x + int(rng.integers(30, 120)), y2)], fill=(255, 240, 210, int(rng.integers(20, 60))), width=3)
        else:
            for y2 in range(int(self.by) + 30, BH, 46):
                for x in range(int(rng.integers(0, 80)), BW, 160):
                    d.arc([x, y2, x + 60, y2 + 20], 200, 340, fill=MUREKKEP + (90,), width=3)
        taban = taban.filter(ImageFilter.GaussianBlur(0.6))
        self.taban = vinyet_buyuk(taban, 0.45)
        self.foto = False
        try:   # dönemine uygun gerçek yapı fotoğrafı varsa çizim yerine o (pin yok, plaket ve madalyon kalır)
            import pixabay
            yol = pixabay.yapi_fotografi(spec.get("yer", ""), YIL)
            if yol:
                im = pixabay.kapla(Image.open(yol).convert("RGB"), BW, BH)
                self.taban = vinyet_buyuk(pixabay.eskit(im, 0.88, 0.35), 0.55)
                self.foto = True
        except Exception as e:  # noqa: BLE001
            print("Mekan fotoğrafı atlandı:", e, flush=True)
        self.tepe = self._tepe()
        self.madalyon = self._madalyon()

    def _tepe(self):
        """İğnenin düşeceği nokta: binanın en yüksek yerinin biraz altı (büyük tuvalde)."""
        boy = {"cami": 62, "saray": 48, "kule": 88, "kale": 44, "meydan": 46, "konak": 46, "carsi": 22, "manastir": 34}.get(self.tur, 36)
        return self.bx, self.by - boy * self.s

    def _madalyon(self):
        sp = self.spec
        if "lon" not in sp:
            return None
        R = 120 if not yatay() else 110
        n = R * 2
        lon, lat = sp["lon"], sp["lat"]
        gen = sp.get("madalyon_genislik", 5.0)
        cos = math.cos(math.radians(lat))
        k = n / (gen * cos)
        img = Image.new("RGB", (n, n), (52, 92, 104))
        d = ImageDraw.Draw(img)
        for halka in kara_verisi():
            nok = [(n / 2 + (a - lon) * cos * k, n / 2 - (b - lat) * k) for a, b in halka]
            xs = [p[0] for p in nok]
            ys = [p[1] for p in nok]
            if max(xs) < 0 or min(xs) > n or max(ys) < 0 or min(ys) > n:
                continue
            d.polygon(nok, fill=(232, 214, 170), outline=(90, 64, 40))
        maske = Image.new("L", (n, n), 0)
        ImageDraw.Draw(maske).ellipse([0, 0, n - 1, n - 1], fill=255)
        return img, maske, R

    def kare(self, u, sn):
        sp = self.spec
        S = self.OLCEK
        z = 1.0 + 0.07 * yumusak(u)
        ww, hh = self.BW / z, self.BH / z
        tx, ty = self._tepe()
        ox = self.BW / 2 + (tx - self.BW / 2) * 0.3 * yumusak(u)
        oy = self.BH / 2 + (ty - self.BH / 2) * 0.15 * yumusak(u)
        x0 = min(max(ox - ww / 2, 0), self.BW - ww)
        y0 = min(max(oy - hh / 2, 0), self.BH - hh)
        img = self.taban.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + ww, y0 + hh))
        d = ImageDraw.Draw(img, "RGBA")
        oran = W / ww

        def ex(px, py):
            return ((px - x0) * oran, (py - y0) * oran)

        # kuşlar
        if sp.get("arka", "gunbatimi") != "parsomen" and not self.foto:
            renk_k = (30, 24, 30, 200) if sp.get("arka") != "gece" else (200, 200, 220, 150)
            for k in range(5):
                bx = (W * (0.1 + k * 0.13) + sn * (38 + k * 6)) % (W * 1.2) - W * 0.1
                by = H * (0.14 + 0.05 * math.sin(k * 2.1)) + math.sin(sn * 1.3 + k) * 8
                kan = 9 + 3 * math.sin(sn * 9 + k * 1.7)
                d.line([(bx - 14, by - kan), (bx, by), (bx + 14, by - kan)], fill=renk_k, width=3)
        # iğne (fotoğrafta binanın yeri bilinmediği için yok)
        px, py = ex(tx, ty)
        e = evre(u, 0.12, 0.12) if not self.foto else 0
        if e > 0:
            yuk = 80 + (1 - zipla(e)) * H * 0.25
            if e >= 1:
                for k in range(2):
                    faz = (sn * 0.7 + k / 2) % 1
                    r = 30 + faz * 120
                    d.ellipse([px - r, py - r * 0.4, px + r, py + r * 0.4], outline=(255, 214, 90, int(200 * (1 - faz))), width=5)
            d.line([(px, py), (px, py - yuk + 20)], fill=MUREKKEP + (255,), width=6)
            d.ellipse([px - 26, py - yuk - 26, px + 26, py - yuk + 26], fill=KIRMIZI + (255,), outline=MUREKKEP + (255,), width=4)
            d.ellipse([px - 9, py - yuk - 9, px + 9, py - yuk + 9], fill=(250, 236, 210, 255))
        # ad plaketi
        e2 = evre(u, 0.2, 0.1)
        if e2 > 0:
            a = int(255 * e2)
            ad = tr_buyuk(sp.get("yer", ""))
            alt = sp.get("alt")
            if alt is None and "lon" in sp:
                en = min(SEHIRLER, key=lambda c: math.dist((c[1], c[2]), (sp["lon"], sp["lat"])))
                alt = en[0] if math.dist((en[1], en[2]), (sp["lon"], sp["lat"])) < 0.6 else ""
            alt = tr_buyuk(alt or "")
            sinir = W * 0.55 if yatay() else W - 160
            f = F_UST
            while d.textlength(ad, font=f) > sinir and f.size > 60:
                f = _f("DejaVuSerif-Bold.ttf", f.size - 8)
            gen = max(d.textlength(ad, font=f), d.textlength(alt, font=F_UST_ALT)) + 90
            yuk = f.size + (94 if alt else 40)
            if yatay():
                bx0, by0 = 70, 70
            else:
                bx0, by0 = (W - gen) / 2, H * 0.115
            by0 += (1 - yumusak(e2)) * 30
            d.rounded_rectangle([bx0 + 8, by0 + 8, bx0 + gen + 8, by0 + yuk + 8], 18, fill=(0, 0, 0, int(a * 0.3)))
            d.rounded_rectangle([bx0, by0, bx0 + gen, by0 + yuk], 18, fill=(22, 30, 34, int(a * 0.84)), outline=ALTIN + (a,), width=3)
            yazi(d, (bx0 + gen / 2, by0 + 14), ad, f, (255, 236, 190), 6, alfa=a)
            if alt:
                yazi(d, (bx0 + gen / 2, by0 + f.size + 22), alt, F_UST_ALT, ALTIN, 4, alfa=a)
        # madalyon: bölge haritası ve konum
        if self.madalyon:
            e3 = evre(u, 0.3, 0.12)
            if e3 > 0:
                harita, maske, R = self.madalyon
                cx, cy = (W - R - 70, R + 70) if yatay() else (W - R - 60, H * 0.31)
                a = int(255 * e3)
                d.ellipse([cx - R - 10 + 6, cy - R - 10 + 8, cx + R + 10 + 6, cy + R + 10 + 8], fill=(0, 0, 0, a // 3))
                d.ellipse([cx - R - 10, cy - R - 10, cx + R + 10, cy + R + 10], fill=ALTIN + (a,))
                m = maske.point(lambda v: v * a // 255)
                img.paste(harita, (int(cx - R), int(cy - R)), m)
                d = ImageDraw.Draw(img, "RGBA")
                faz = (sn * 0.9) % 1
                r = 8 + faz * 30
                d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=KIRMIZI + (int(a * (1 - faz)),), width=4)
                d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=KIRMIZI + (a,), outline=(255, 255, 255, a), width=3)
        # damga (eski harita sahnelerinden gelebilir)
        dm = sp.get("damga")
        if dm and u >= dm.get("bas", 0.5):
            e4 = evre(u, dm["bas"], 0.06)
            olcek = 1.8 - 0.8 * yumusak(e4)
            dx, dy = (W * 0.5, H * 0.8) if not yatay() else (W * 0.78, H * 0.78)
            tip = dm.get("tip", sp.get("damga_tip", "muhur"))
            if tip == "murekkep":
                murekkep_damga(d, dx, dy, tr_buyuk(dm["yazi"]), olcek, int(255 * min(1, e4 * 2)))
            elif tip == "ferman":
                ferman(d, dx, dy, dm["yazi"], evre(u, dm["bas"], 0.15), 255)
            else:
                damga(d, dx, dy, tr_buyuk(dm["yazi"]), olcek * 0.8, int(255 * min(1, e4 * 2)))
        return img


def vinyet_buyuk(img, guc=0.5):
    w, h = img.size
    a = np.asarray(img).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    r = ((xx - w / 2) / (w * 0.75)) ** 2 + ((yy - h * 0.45) / (h * 0.7)) ** 2
    m = 1 - np.clip(r, 0, 1) ** 1.6 * guc
    return Image.fromarray((a * m[..., None]).clip(0, 255).astype(np.uint8))


def harita_mekan_mi(spec):
    """Şehir içi (yakın) harita sahnesi mi: ≤0.8 derece genişlik, rota yok. Bunlar Mekan olarak çizilir."""
    return spec.get("tip") == "harita" and spec.get("genislik", 20) <= 0.8 and not spec.get("rotalar") \
        and spec.get("etiketler")


def haritadan_mekan(spec):
    e = spec["etiketler"][0]
    m = {"tip": "mekan", "yer": e["ad"], "lon": e["lon"], "lat": e["lat"]}
    b = spec.get("baslik") or {}
    if b.get("alt") and tr_buyuk(b["alt"]) != tr_buyuk(e["ad"]):
        m["alt"] = b["alt"]
    for k in ("damga", "damga_tip"):
        if k in spec:
            m[k] = spec[k]
    if "tema" in spec:
        m["arka"] = {"gece": "gece", "kizil": "gunbatimi", "antika": "parsomen", "parsomen": "safak"}.get(spec["tema"], "gunbatimi")
    return m


# ---------------------------------------------------------------- taraflar
class Taraflar:
    def __init__(self, spec):
        self.spec = spec
        arka = spec.get("arka", {"merkez": [18, 40], "genislik": 26, "zoom": 1.0})
        h = Harita(dict(arka, zoom=1.0))
        img = h.taban.filter(ImageFilter.GaussianBlur(3))
        self.taban = Image.blend(img, Image.new("RGB", (W, H), (20, 18, 16)), 0.45)

    def kare(self, u, sn):
        sp = self.spec
        img = self.taban.copy()
        d = ImageDraw.Draw(img, "RGBA")
        taraflar = sp["taraflar"]
        n = len(taraflar)
        for i, t in enumerate(taraflar):
            e = evre(sn, 0.15 + i * 0.35, 0.5)
            if e <= 0:
                continue
            if yatay():   # ittifak solda, karşı taraf sağda
                cx = W * 0.32 + (i - (n - 1) / 2) * 300
                hedef = 330
            else:
                cx = W / 2 + (i - (n - 1) / 2) * 320
                hedef = 560
            cy = -200 + (hedef + 200) * zipla(e)
            arma(d, cx, cy, 1.25, t["desen"], tr_buyuk(t["ad"]))
        bt = sp.get("bant")
        if bt:
            bant(d, W * 0.32 if yatay() else W / 2, 640 if yatay() else 860, tr_buyuk(bt), evre(sn, 0.25 + n * 0.35, 0.6))
        k = sp.get("karsi")
        if k:
            e = evre(sn, 0.6 + n * 0.35, 0.5)
            if e > 0:
                if yatay():
                    capraz_kilic(d, W * 0.62, 420, 0.7 * zipla(e))
                    arma(d, W * 0.8, -200 + 530 * zipla(e) if e < 1 else 330, 1.25, k["desen"], tr_buyuk(k["ad"]),
                         int(255 * min(1, e * 2)))
                else:
                    capraz_kilic(d, W / 2, 1010, 0.55 * zipla(e))
                    arma(d, W / 2, 1450 - 260 * zipla(e) if e < 1 else 1190, 1.15, k["desen"], tr_buyuk(k["ad"]),
                         int(255 * min(1, e * 2)))
        return img


# ---------------------------------------------------------------- takvim
class Takvim:
    def __init__(self, spec):
        self.spec = spec
        arka = spec.get("arka", "gunbatimi")
        self.arka = arka
        y = np.linspace(0, 1, H)[:, None, None]
        if arka == "gece":
            gok = np.array([10, 16, 40]) * (1 - y) + np.array([40, 46, 90]) * y
            deniz_u, deniz_a = [24, 34, 64], [8, 12, 26]
        elif arka == "safak":
            gok = np.array([150, 176, 210]) * (1 - y) + np.array([250, 200, 170]) * y
            deniz_u, deniz_a = [120, 150, 170], [50, 80, 100]
        else:
            gok = np.array([248, 214, 160]) * (1 - y) + np.array([226, 140, 92]) * y
            deniz_u, deniz_a = [70, 110, 130], [30, 56, 72]
        img = np.broadcast_to(gok, (H, W, 3)).astype(np.float32).copy()
        ufuk = int(H * 0.62)
        yy = np.linspace(0, 1, H - ufuk)[:, None, None]
        img[ufuk:] = np.array(deniz_u) * (1 - yy) + np.array(deniz_a) * yy
        # güneş
        cy, cx = ufuk - 60, W * 0.7
        g = np.mgrid[0:H, 0:W]
        r = np.sqrt((g[1] - cx) ** 2 + (g[0] - cy) ** 2)
        isik = np.array([1, 0.8, 0.4]) if arka != "gece" else np.array([0.5, 0.55, 0.8])
        img += (np.clip(1 - r / 520, 0, 1) ** 2 * 60)[..., None] * isik
        img += kagit_dokusu(9, 7)
        if arka == "parsomen":   # masa üstünde eski kâğıt: ufuk yok
            img = np.broadcast_to(np.array([214, 190, 146], np.float32), (H, W, 3)).copy() + kagit_dokusu(9, 16)
        self.taban = vinyet(Image.fromarray(img.clip(0, 255).astype(np.uint8)), 0.45 if arka != "parsomen" else 0.6)
        d = ImageDraw.Draw(self.taban, "RGBA")
        if arka == "gece":
            rng0 = np.random.default_rng(17)
            for _ in range(160):
                x, yy3 = int(rng0.integers(0, W)), int(rng0.integers(0, ufuk - 20))
                rr = float(rng0.uniform(1, 3.2))
                d.ellipse([x - rr, yy3 - rr, x + rr, yy3 + rr], fill=(255, 250, 230, int(rng0.integers(120, 255))))
            d.ellipse([cx - 70, cy - 300, cx + 70, cy - 160], fill=(250, 244, 220, 235))
            d.ellipse([cx - 40, cy - 310, cx + 90, cy - 170], fill=(18, 24, 54, 255))
        elif arka == "parsomen":
            for i in range(0, W, 120):   # silik satır çizgileri, köşede mürekkep lekesi
                d.line([(0, i * H / W + 80), (W, i * H / W + 80)], fill=(120, 90, 50, 30), width=2)
            d.ellipse([W * 0.75, H * 0.78, W * 0.75 + 140, H * 0.78 + 90], fill=(60, 40, 30, 60))
        else:
            d.ellipse([cx - 90, cy - 90, cx + 90, cy + 90], fill=(255, 236, 190, 200))
        rng = np.random.default_rng(4)
        for _ in range(60 if arka != "parsomen" else 0):
            x, yy2 = int(rng.integers(0, W)), int(rng.integers(ufuk + 20, H))
            d.line([(x, yy2), (x + int(rng.integers(20, 70)), yy2)], fill=(255, 255, 255, 50), width=3)
        self.ufuk = ufuk

    def kare(self, u, sn):
        sp = self.spec
        img = self.taban.copy()
        d = ImageDraw.Draw(img, "RGBA")
        if sp.get("filo", True) and self.arka != "parsomen":
            ilerle = yumusak(u * 1.2)
            o = H / 1920 if not yatay() else 0.62
            sirlar = ((self.ufuk + 40 * o, 110 * o, 6), (self.ufuk + 170 * o, 170 * o, 4), (self.ufuk + 340 * o, 250 * o, 3))
            if yatay():
                sirlar = ((self.ufuk + 25, 80, 9), (self.ufuk + 110, 120, 7), (self.ufuk + 230, 170, 5))
            for sira, (yb, boy, n) in enumerate(sirlar):
                for i in range(n):
                    x = -300 + (W + 300) * (i + 0.5) / n + ilerle * 220 * (sira + 1) - 140 * (sira + 1)
                    kadirga(d, x, yb, boy, 1, "osmanli", sn * 2.5 + i + sira)
        # takvim kartı
        e = evre(sn, 0.1, 0.5)
        cy = (520 if not yatay() else 330) - 600 * (1 - zipla(e))
        x0, x1, y0, y1 = W / 2 - 290, W / 2 + 290, cy - 250, cy + 250
        d.rounded_rectangle([x0 + 10, y0 + 14, x1 + 10, y1 + 14], 30, fill=(0, 0, 0, 80))
        d.rounded_rectangle([x0, y0, x1, y1], 30, fill=(250, 244, 228), outline=MUREKKEP, width=6)
        d.rounded_rectangle([x0, y0, x1, y0 + 110], 30, fill=(176, 34, 34), outline=MUREKKEP, width=6)
        d.rectangle([x0 + 3, y0 + 70, x1 - 3, y0 + 107], fill=(176, 34, 34))
        for hx in (x0 + 130, x1 - 130):
            d.rounded_rectangle([hx - 12, y0 - 34, hx + 12, y0 + 30], 10, fill=(90, 90, 96), outline=MUREKKEP, width=3)
        aylar = sp.get("aylar") or [sp.get("ay", "")]
        cevir = sp.get("cevir_bit", 0.55)
        idx = min(len(aylar) - 1, int(yumusak(min(1, max(0, (u - 0.08) / max(0.05, cevir - 0.08)))) * (len(aylar) - 1) + 0.0001))
        yil = sp.get("yil", "")
        if isinstance(yil, list):
            yil = yil[0] if idx < len(aylar) - 1 else yil[-1]
        yazi(d, (W / 2, y0 + 22), str(yil), F_TAKVIM_YIL, (255, 240, 220), 0)
        ay = tr_buyuk(aylar[idx])
        f = F_TAKVIM_AY
        while d.textlength(ay, font=f) > 520 and f.size > 50:
            f = _f("DejaVuSerif-Bold.ttf", f.size - 8)
        yazi(d, (W / 2, cy - 10), ay, f, MUREKKEP, 0)
        # çevrilen yaprak efekti
        faz = (u - 0.08) / max(0.05, cevir - 0.08) * (len(aylar) - 1)
        if 0 < faz < len(aylar) - 1:
            k = faz % 1
            yy = y0 + 110 + (y1 - y0 - 110) * (1 - k)
            d.polygon([(x0 + 6, y0 + 110), (x1 - 6, y0 + 110), (x1 - 6, yy), (x0 + 6, yy)], fill=(236, 226, 204, 200))
        rz = sp.get("rozet")
        if rz and u >= cevir:
            rozet(d, W / 2 if not yatay() else x1 + 80 + d.textlength(tr_buyuk(rz), font=F_ROZET) / 2, cy + 340 if not yatay() else cy, tr_buyuk(rz), int(255 * evre(u, cevir, 0.08)))
        return img


# ---------------------------------------------------------------- savaş planı
class Plan:
    """Kuşbakışı savaş alanı: birlik blokları hedefe kayar, oklar çizilir, toplar ateş eder.
    Koordinatlar ekran pikselidir (1080x1920)."""

    def __init__(self, spec):
        self.spec = spec
        y = np.linspace(0, 1, H)[:, None, None]
        zemin = np.array([196, 186, 132]) * (1 - y) + np.array([150, 150, 96]) * y
        img = np.broadcast_to(zemin, (H, W, 3)).astype(np.float32).copy()
        img += kagit_dokusu(21, 12)
        taban = Image.fromarray(img.clip(0, 255).astype(np.uint8))
        d = ImageDraw.Draw(taban, "RGBA")
        rng = np.random.default_rng(8)
        for _ in range(140):   # çimen tutamları
            x, yy = int(rng.integers(0, W)), int(rng.integers(int(H * 0.15), H))
            for k in (-6, 0, 6):
                d.line([(x, yy), (x + k, yy - 14)], fill=(96, 104, 60, 120), width=2)
        if spec.get("nehir"):   # yanda kıvrılan nehir (ör. Tuna)
            nok = [(W - 140 + 60 * math.sin(i / 6), i * 40) for i in range(0, H // 40 + 2)]
            d.line(nok, fill=(70, 110, 130, 255), width=90, joint="curve")
            d.line(nok, fill=(110, 150, 165, 160), width=40, joint="curve")
            yazi(d, (W - 150, H * 0.86), tr_buyuk(spec["nehir"]), F_BOLGE, KREM, 4)
        if spec.get("bataklik"):
            bx, by = spec["bataklik"]
            for k in range(9):
                r = 40 + k * 9
                d.ellipse([bx - r * 1.6 + k * 5, by - r * 0.5, bx + r * 1.6 + k * 5, by + r * 0.5], outline=(80, 110, 110, 110), width=3)
        self.taban = vinyet(taban, 0.5)

    def kare(self, u, sn):
        sp = self.spec
        img = self.taban.copy()
        d = ImageDraw.Draw(img, "RGBA")
        for o in sp.get("oklar", []):
            p = yumusak((u - o.get("bas", 0.3)) / 0.25)
            if p <= 0:
                continue
            (x0, y0), (x1, y1) = o["bas_xy"], o["son_xy"]
            x, y = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
            renk = OSMANLI if o.get("taraf") == "osmanli" else DUSMAN
            d.line([(x0, y0), (x, y)], fill=renk + (235,), width=22)
            aa = math.atan2(y1 - y0, x1 - x0)
            d.polygon([(x + 34 * math.cos(aa), y + 34 * math.sin(aa)),
                       (x + 30 * math.cos(aa + 2.3), y + 30 * math.sin(aa + 2.3)),
                       (x + 30 * math.cos(aa - 2.3), y + 30 * math.sin(aa - 2.3))], fill=renk + (235,))
        for t in sp.get("toplar", []):
            if u < t.get("bas", 0.5):
                continue
            x, y = t["xy"]
            d.rectangle([x - 30, y - 10, x + 26, y + 10], fill=(50, 44, 40))
            d.ellipse([x - 22, y + 2, x - 2, y + 22], fill=(110, 80, 50))
            faz = ((sn * 1.6 + x * 0.01) % 1)
            if faz < 0.35:
                r = 18 + faz * 120
                d.ellipse([x + 30 - r * 0.2, y - 20 - r * 0.5, x + 30 + r, y - 20 + r * 0.5], fill=(240, 236, 226, int(200 * (1 - faz / 0.35))))
                d.ellipse([x + 26, y - 8, x + 46, y + 8], fill=(255, 200, 80, int(255 * (1 - faz / 0.35))))
        for b in sp.get("birlikler", []):
            a = int(255 * evre(u, b.get("gor", 0.0), 0.08))
            if not a:
                continue
            x, y = b["xy"]
            if "hedef" in b:
                p = yumusak((u - b.get("bas", 0.2)) / max(0.05, b.get("bit", 0.6) - b.get("bas", 0.2)))
                x, y = x + (b["hedef"][0] - x) * p, y + (b["hedef"][1] - y) * p
            w, h = b.get("wh", (300, 120))
            renk = OSMANLI if b.get("taraf") == "osmanli" else DUSMAN
            d.rectangle([x - w / 2 + 8, y - h / 2 + 10, x + w / 2 + 8, y + h / 2 + 10], fill=(0, 0, 0, int(a * 0.25)))
            d.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=renk + (int(a * 0.85),), outline=MUREKKEP + (a,), width=4)
            sutun, satir = max(2, int(w // 34)), max(1, int(h // 34))
            for i in range(sutun):
                for j in range(satir):
                    px = x - w / 2 + (i + 0.5) * w / sutun
                    py = y - h / 2 + (j + 0.5) * h / satir + (math.sin(sn * 6 + i) * 2 if "hedef" in b else 0)
                    d.ellipse([px - 7, py - 7, px + 7, py + 7], fill=(240, 228, 200, a))
            if b.get("etiket"):
                et = tr_buyuk(b["etiket"])
                tw = d.textlength(et, font=F_ARMA)
                ey = y - h / 2 - 58 if b.get("etiket_ust", True) else y + h / 2 + 12
                d.rounded_rectangle([x - tw / 2 - 16, ey, x + tw / 2 + 16, ey + 48], 10, fill=KREM + (a,), outline=MUREKKEP + (a,), width=3)
                d.text((x - tw / 2, ey + 6), et, font=F_ARMA, fill=MUREKKEP + (a,))
        c = sp.get("carpisma")
        if c and u >= c.get("bas", 0.7):
            e = evre(u, c["bas"], 0.08)
            capraz_kilic(d, c["xy"][0], c["xy"][1], 0.9 * zipla(e) + 0.02 * math.sin(sn * 8))
        b = sp.get("baslik")
        if b:
            a = int(255 * evre(sn, 0.1, 0.5))
            y0 = 230 if not yatay() else 100
            d.rectangle([0, y0, W, y0 + 110], fill=(30, 24, 16, int(a * 0.6)))
            yazi(d, (W / 2, y0 + 28), tr_buyuk(b), F_UST_ALT, (255, 236, 190), 4, alfa=a)
        return img


# ---------------------------------------------------------------- basamak (hiyerarşi)
class Basamak:
    """Alttan üste dizilen basamaklar: rütbeler, odalar, makamlar. En üstteki altın renkte parlar."""

    def __init__(self, spec):
        self.spec = spec
        y = np.linspace(0, 1, H)[:, None, None]
        zemin = np.array([70, 44, 30]) * (1 - y) + np.array([34, 22, 16]) * y
        img = np.broadcast_to(zemin, (H, W, 3)).astype(np.float32).copy() + kagit_dokusu(13, 8)
        taban = vinyet(Image.fromarray(img.clip(0, 255).astype(np.uint8)), 0.5)
        d = ImageDraw.Draw(taban, "RGBA")
        for i in range(-2, W // 90 + 2):   # arka planda geometrik desen (çini motifi)
            for j in range(-2, H // 80 + 2):
                cx, cy = i * 90 + (45 if j % 2 else 0), j * 80
                d.polygon([(cx, cy - 30), (cx + 30, cy), (cx, cy + 30), (cx - 30, cy)], outline=(232, 190, 105, 22), width=2)
        self.taban = taban

    def kare(self, u, sn):
        sp = self.spec
        img = self.taban.copy()
        d = ImageDraw.Draw(img, "RGBA")
        b = sp.get("baslik")
        if b:
            a = int(255 * evre(sn, 0.05, 0.4))
            yazi(d, (W / 2, 260 if not yatay() else 110), tr_buyuk(b), F_UST_ALT, ALTIN, 4, alfa=a)
        ogeler = sp["ogeler"]   # alttan üste
        n = len(ogeler)
        alt, ust = (1260, 380) if not yatay() else (800, 230)
        adim = (alt - ust) / max(1, n - 1) if n > 1 else 0
        for i, o in enumerate(ogeler):
            bas = 0.05 + i * (0.7 / n)
            e = evre(u, bas, 0.09)
            if e <= 0:
                continue
            y = alt - i * adim
            gen = 860 - i * (280 / max(1, n - 1)) if n > 1 else 640
            x0, x1 = W / 2 - gen / 2, W / 2 + gen / 2
            ofs = (1 - zipla(e)) * 60
            son = i == n - 1
            zemin = (176, 34, 34) if son else KREM
            renk = (255, 236, 190) if son else MUREKKEP
            d.rectangle([x0 + 8, y - 44 + 10 + ofs, x1 + 8, y + 44 + 10 + ofs], fill=(0, 0, 0, int(110 * e)))
            d.rectangle([x0, y - 44 + ofs, x1, y + 44 + ofs], fill=zemin + (int(255 * e),), outline=ALTIN + (int(255 * e),), width=4)
            et = tr_buyuk(o)
            f = F_ARMA if d.textlength(et, font=F_BANT) > gen - 40 else F_BANT
            yazi(d, (W / 2, y - f.size * 0.6 + ofs), et, f, renk, 0, alfa=int(255 * e))
            if son and e >= 1:
                for k in range(2):
                    faz = (sn * 0.8 + k / 2) % 1
                    r = gen / 2 + 20 + faz * 60
                    d.rectangle([W / 2 - r, y - 44 - faz * 30, W / 2 + r, y + 44 + faz * 30], outline=ALTIN + (int(180 * (1 - faz)),), width=4)
        return img


TURLER = {"harita": Harita, "sefer": Sefer, "mekan": Mekan, "taraflar": Taraflar, "takvim": Takvim, "plan": Plan, "basamak": Basamak}


def _cesit(spec):
    """Spec'te belirtilmemiş görünüş seçeneklerini spec'in kendisinden türetilen tohumla seçer:
    her sahne farklı tema, kamera, rota çizgisi, mühür ve takvim arka planı alır (her üretimde aynı)."""
    import hashlib
    h = int(hashlib.md5(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest(), 16)

    def sec(secenekler, kaydir):
        return secenekler[(h >> kaydir) % len(secenekler)]
    if spec["tip"] == "harita":
        spec.setdefault("tema", sec(["parsomen", "parsomen", "antika", "gece", "kizil", "antika"], 0))
        spec.setdefault("kamera", sec(["yaklas", "yaklas", "uzaklas", "kaydir"], 4))
        spec.setdefault("cizgi", sec(["kesikli", "akan", "kalin"], 8))
        spec.setdefault("damga_tip", sec(["muhur", "murekkep", "ferman"], 12))
        spec.setdefault("bulut", sec([True, False, False], 16))
    elif spec["tip"] == "mekan":
        spec.setdefault("arka", sec(["gunbatimi", "gece", "safak", "gunbatimi", "parsomen"], 0))
    elif spec["tip"] == "sefer":
        spec.setdefault("tema", sec(["parsomen", "antika", "parsomen", "kizil"], 0))
        spec.setdefault("cizgi", sec(["kesikli", "akan", "kalin"], 8))
    elif spec["tip"] == "takvim":
        spec.setdefault("arka", sec(["gunbatimi", "gece", "safak", "parsomen"], 0))
    elif spec["tip"] == "taraflar":
        spec.setdefault("arka", {"merkez": [18, 40], "genislik": 26})
        spec["arka"] = dict(spec["arka"])
        spec["arka"].setdefault("tema", sec(["parsomen", "gece", "antika", "kizil"], 0))
    return spec


def hazirla(spec, sure=6.0):
    if harita_mekan_mi(spec):   # şehir içi düz harita yerine bina silueti
        spec = haritadan_mekan(spec)
    spec = _cesit(dict(spec))
    spec["_sure"] = sure
    return TURLER[spec["tip"]](spec)
