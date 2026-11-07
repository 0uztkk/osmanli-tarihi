"""Kodla çizilen animasyonlu sahneler (Shorts, 1080x1920).

Sahne JSON'unda "anim" alanı varsa görsel yerine bu modül çizer. Türler:

  harita   Akdeniz haritası (Natural Earth, kamu malı): şehir etiketleri, ilerleyen filo rotaları,
           çarpışma işareti, yanıp sönen bölge, mühür damgası, üst başlık, yavaş yakınlaşma.
  taraflar Tarafların armaları yukarıdan iner, ortada ittifak bandı, altta karşı taraf.
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


TURLER = {"harita": Harita, "taraflar": Taraflar, "takvim": Takvim, "plan": Plan, "basamak": Basamak}


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
    elif spec["tip"] == "takvim":
        spec.setdefault("arka", sec(["gunbatimi", "gece", "safak", "parsomen"], 0))
    elif spec["tip"] == "taraflar":
        spec.setdefault("arka", {"merkez": [18, 40], "genislik": 26})
        spec["arka"] = dict(spec["arka"])
        spec["arka"].setdefault("tema", sec(["parsomen", "gece", "antika", "kizil"], 0))
    return spec


def hazirla(spec, sure=6.0):
    spec = _cesit(dict(spec))
    spec["_sure"] = sure
    return TURLER[spec["tip"]](spec)
