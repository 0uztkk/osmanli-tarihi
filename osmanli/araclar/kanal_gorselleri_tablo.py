#!/usr/bin/env python3
"""Kanal profil resmi ve kapağını kamu malı tablolardan üretir (Wikimedia Commons; GitHub Actions'ta çalışır).

Kapak: Ivan Aivazovski, "Ay Işığında Konstantinopolis Manzarası" (1846) – kamu malı.
Profil: Ivan Aivazovski, "Konstantinopolis Manzarası" (1876) – minare ve ay – kamu malı.
Kullanım: python osmanli/araclar/kanal_gorselleri_tablo.py <çıkış klasörü>
"""
import io, os, sys

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from gorsel import _get, ara  # noqa: E402

KAPAK_TABLO = "File:Вид Константинополя при лунном освещении Айвазовский.jpg"
PROFIL_TABLO = "File:Ivan Constantinovich Aivazovsky View of Constantinople 1876.jpg"
ALTIN = (246, 214, 150)
BASLIK_FONT = "/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf"
ALT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def indir(dosya):
    a = ara(dosya, genislik=4000)
    if not a:
        sys.exit(f"Bulunamadı: {dosya}")
    return Image.open(io.BytesIO(_get(a[0]["url"], timeout=120))).convert("RGB")


def kirp(im, w, h, odak_x=0.5, odak_y=0.5):
    s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x = int((im.width - w) * odak_x)
    y = int((im.height - h) * odak_y)
    return im.crop((x, y, x + w, y + h))


def yildiz8(d, cx, cy, r, renk, kalin):
    import math
    for aci in (0, 45):
        pts = [(cx + r * math.cos(math.radians(aci + 90 * k)), cy + r * math.sin(math.radians(aci + 90 * k))) for k in range(4)]
        d.polygon(pts, outline=renk, width=kalin)


def harfli(d, metin, font, y, w, renk, aralik, golge=True):
    gen = sum(d.textlength(c, font=font) for c in metin) + aralik * (len(metin) - 1)
    x0 = (w - gen) / 2
    for katman in ((golge, (0, 0, 0)), (True, renk)):
        if not katman[0]:
            continue
        x = x0 + (4 if katman[1] == (0, 0, 0) else 0)
        for c in metin:
            d.text((x, y + (4 if katman[1] == (0, 0, 0) else 0)), c, font=font, fill=katman[1])
            x += d.textlength(c, font=font) + aralik


def kapak(yol):
    W, H = 2560, 1440
    im = kirp(indir(KAPAK_TABLO), W, H, 0.5, 0.55)
    im = ImageEnhance.Contrast(im).enhance(1.05)
    # ortadaki güvenli alanda yazı okunsun diye yumuşak koyulaştırma
    y = np.linspace(-1, 1, H)[:, None]
    x = np.linspace(-1, 1, W)[None, :]
    maske = np.clip(1 - ((x / 0.55) ** 2 + (y / 0.38) ** 2), 0, 1) * 0.55
    a = np.asarray(im).astype(np.float32) * (1 - maske[..., None])
    im = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(im)
    ft = ImageFont.truetype(BASLIK_FONT, 150)
    fa = ImageFont.truetype(ALT_FONT, 46)
    yb = H / 2 - 150
    harfli(d, "SARAYIN GÖLGESİ", ft, yb, W, ALTIN, 14)
    cy = yb + 200
    d.line([W / 2 - 500, cy, W / 2 - 40, cy], fill=ALTIN, width=4)
    d.line([W / 2 + 40, cy, W / 2 + 500, cy], fill=ALTIN, width=4)
    yildiz8(d, W / 2, cy, 22, ALTIN, 4)
    alt = "Osmanlı tarihinin bilinmeyen hikâyeleri  ·  Her gün yeni Shorts"
    d.text(((W - d.textlength(alt, font=fa)) / 2 + 3, cy + 41), alt, font=fa, fill=(0, 0, 0))
    d.text(((W - d.textlength(alt, font=fa)) / 2, cy + 38), alt, font=fa, fill=(245, 232, 210))
    im.save(yol, quality=93)


def profil(yol):
    tablo = indir(PROFIL_TABLO)
    # minare ve ayın olduğu üst-orta bölge: kare kırp
    w, h = tablo.size
    k = int(min(w, h) * 0.78)
    x0 = int(w * 0.5 - k * 0.5)
    y0 = int(h * 0.04)
    im = tablo.crop((x0, y0, x0 + k, y0 + k)).resize((800, 800), Image.LANCZOS)
    im = ImageEnhance.Contrast(im).enhance(1.08)
    # yuvarlak kırpmada kenarlar koyulaşsın (vinyet)
    y = np.linspace(-1, 1, 800)[:, None]
    x = np.linspace(-1, 1, 800)[None, :]
    v = np.clip((np.sqrt(x ** 2 + y ** 2) - 0.75) / 0.35, 0, 1) * 0.6
    a = np.asarray(im).astype(np.float32) * (1 - v[..., None])
    im = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.ellipse([18, 18, 782, 782], outline=(226, 184, 104), width=10)
    im.save(yol, quality=95)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "out/kanal"
    os.makedirs(out, exist_ok=True)
    kapak(os.path.join(out, "kapak_gorseli.jpg"))
    profil(os.path.join(out, "profil_resmi.jpg"))
    print("hazır:", out)
