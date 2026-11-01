#!/usr/bin/env python3
"""Kanal profil resmi (800x800) ve kapak görseli (2560x1440) üretir. Tamamen özgün çizim, telif yok.

Tema: "Sarayın Gölgesi" – gün batımına karşı kubbe ve minare siluetleri, altın çizgiler.
Kullanım: python osmanli/araclar/kanal_gorselleri.py <çıkış klasörü>
"""
import math, os, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ALTIN = (226, 184, 104)
ALTIN_ACIK = (246, 214, 150)
GOLGE = (14, 9, 12)
BASLIK_FONT = "/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf"
ALT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SS = 2   # süper örnekleme: kenarlar yumuşak olsun


def gok(w, h, ufuk):
    """Koyu bordo üstten, ufka doğru turuncu-altın parlayan gün batımı."""
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(-1, 1, w)[None, :]
    ust, orta, alt = np.array([22, 10, 20]), np.array([96, 28, 30]), np.array([232, 132, 58])
    t = np.clip(y / ufuk, 0, 1)
    renk = np.where(t[..., None] < 0.6,
                    ust + (orta - ust) * (t[..., None] / 0.6),
                    orta + (alt - orta) * ((t[..., None] - 0.6) / 0.4))
    parilti = np.exp(-((x * 0.9) ** 2) * 2.2 - ((y - ufuk) * 4.0) ** 2)[..., None]
    renk = renk + parilti * np.array([90, 60, 20])
    return Image.fromarray(np.clip(renk, 0, 255).astype(np.uint8))


def kubbe(d, cx, taban, r, renk):
    d.ellipse([cx - r, taban - r * 1.05, cx + r, taban + r * 1.05], fill=renk)
    d.rectangle([cx - r, taban, cx + r, taban + r * 0.25], fill=renk)
    d.line([cx, taban - r * 1.05, cx, taban - r * 1.45], fill=renk, width=max(2, int(r * 0.05)))
    hr = r * 0.09
    d.ellipse([cx - hr, taban - r * 1.36 - hr, cx + hr, taban - r * 1.36 + hr], fill=renk)


def minare(d, cx, taban, boy, gen, renk):
    d.rectangle([cx - gen / 2, taban - boy, cx + gen / 2, taban], fill=renk)
    for k in (0.42, 0.68):   # şerefeler
        y = taban - boy * k
        d.rectangle([cx - gen * 0.95, y - gen * 0.22, cx + gen * 0.95, y], fill=renk)
    d.polygon([(cx - gen * 0.62, taban - boy), (cx + gen * 0.62, taban - boy), (cx, taban - boy - gen * 4.2)], fill=renk)


def cami(d, cx, taban, s, renk):
    """Genel bir Osmanlı selâtin camisi silueti (belirli bir yapının kopyası değil)."""
    d.rectangle([cx - 3.4 * s, taban - 0.9 * s, cx + 3.4 * s, taban + 2 * s], fill=renk)
    for ox, r in ((-2.5, 0.55), (2.5, 0.55), (-1.55, 0.8), (1.55, 0.8)):
        kubbe(d, cx + ox * s, taban - 0.9 * s, r * s, renk)
    d.rectangle([cx - 1.9 * s, taban - 1.7 * s, cx + 1.9 * s, taban - 0.9 * s], fill=renk)
    kubbe(d, cx, taban - 1.7 * s, 1.5 * s, renk)
    for ox, boy in ((-3.9, 6.2), (3.9, 6.2), (-3.1, 4.9), (3.1, 4.9)):
        minare(d, cx + ox * s, taban + 0.1 * s, boy * s, 0.26 * s, renk)


def yildiz8(d, cx, cy, r, renk, kalin):
    """Sekiz köşeli yıldız (iki iç içe kare) – Osmanlı/Selçuklu süslemesinin temel motifi."""
    for aci in (0, 45):
        pts = [(cx + r * math.cos(math.radians(aci + 90 * k)), cy + r * math.sin(math.radians(aci + 90 * k))) for k in range(4)]
        d.polygon(pts, outline=renk, width=kalin)


def ortala_yazi(d, metin, font, y, w, renk, aralik=0):
    if aralik:
        gen = sum(d.textlength(c, font=font) for c in metin) + aralik * (len(metin) - 1)
        x = (w - gen) / 2
        for c in metin:
            d.text((x, y), c, font=font, fill=renk)
            x += d.textlength(c, font=font) + aralik
    else:
        d.text(((w - d.textlength(metin, font=font)) / 2, y), metin, font=font, fill=renk)


def profil(yol):
    N = 800 * SS
    im = gok(N, N, 0.72)
    d = ImageDraw.Draw(im)
    # arkada büyük altın çember (güneş/hale)
    r = N * 0.30
    d.ellipse([N / 2 - r, N * 0.40 - r, N / 2 + r, N * 0.40 + r], outline=ALTIN, width=int(N * 0.012))
    cami(d, N / 2, N * 0.70, N * 0.056, GOLGE)
    d.rectangle([0, N * 0.70 + N * 0.11, N, N], fill=GOLGE)
    # altta ince altın çizgi ve yıldız: yuvarlak kırpmada güvenli bölgede
    d.line([N * 0.30, N * 0.86, N * 0.44, N * 0.86], fill=ALTIN, width=int(N * 0.006))
    d.line([N * 0.56, N * 0.86, N * 0.70, N * 0.86], fill=ALTIN, width=int(N * 0.006))
    yildiz8(d, N / 2, N * 0.86, N * 0.03, ALTIN, int(N * 0.005))
    im = im.resize((800, 800), Image.LANCZOS)
    im.save(yol, quality=95)


def kapak(yol):
    W, H = 2560 * SS, 1440 * SS
    im = gok(W, H, 0.86)
    d = ImageDraw.Draw(im)
    # silüet şeridi: ortada büyük cami, iki yanda daha küçük ve uzak olanlar
    taban = H * 0.85
    uzak = (60, 22, 28)
    for cx, s in ((W * 0.16, H * 0.022), (W * 0.84, H * 0.022), (W * 0.30, H * 0.016), (W * 0.70, H * 0.016)):
        cami(d, cx, taban + H * 0.01, s, uzak)
    cami(d, W * 0.5, taban, H * 0.026, GOLGE)
    d.rectangle([0, taban + H * 0.05, W, H], fill=GOLGE)
    # güvenli alan (tüm cihazlar): ortadaki 1546x423 → başlık ve alt yazı burada
    ft = ImageFont.truetype(BASLIK_FONT, int(150 * SS))
    fa = ImageFont.truetype(ALT_FONT, int(46 * SS))
    y_baslik = H / 2 - 175 * SS
    ortala_yazi(d, "SARAYIN GÖLGESİ", ft, y_baslik, W, ALTIN_ACIK, aralik=int(14 * SS))
    cy = y_baslik + 205 * SS
    d.line([W / 2 - 520 * SS, cy, W / 2 - 40 * SS, cy], fill=ALTIN, width=int(4 * SS))
    d.line([W / 2 + 40 * SS, cy, W / 2 + 520 * SS, cy], fill=ALTIN, width=int(4 * SS))
    yildiz8(d, W / 2, cy, 22 * SS, ALTIN, int(4 * SS))
    ortala_yazi(d, "Osmanlı tarihinin bilinmeyen hikâyeleri  ·  Her gün yeni Shorts", fa, cy + 38 * SS, W, (240, 226, 200))
    # başlığa hafif gölge: arkasını biraz karart
    im = im.resize((2560, 1440), Image.LANCZOS)
    im.save(yol, quality=93)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "out"
    os.makedirs(out, exist_ok=True)
    profil(os.path.join(out, "profil_resmi.jpg"))
    kapak(os.path.join(out, "kapak_gorseli.jpg"))
    print("hazır:", out)
