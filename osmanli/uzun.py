"""Uzun video (16:9, 8-12 dk) üretir: out/uzun.mp4, out/kucuk_resim.jpg, out/meta.json

YouTube Agent Skill kuralları:
- yt-script: ilk 15 sn başlığın vaadini doğrular, açık bir soru bırakır; kanal tanıtımı yok.
- yt-chapters: her bölüm bir YouTube bölümü (00:00 ile başlar, ≥3 bölüm, her biri ≥10 sn) – açıklamaya eklenir.
- yt-package: başlık ≤60 karakter ve kapak yazısıyla aynı kelimeleri kullanmaz; küçük resimde ≤3 kelime.
- yt-seo: açıklamanın ilk iki satırı aranan kelimeleri taşır; etiketler ≤15.

Ortam değişkenleri:
  UZUN_KONU  osmanli/uzun/<id>.json; boşsa takvime göre sıradaki (osmanli/uzun/sira.json)
  SEED       YYYYMMDD; boşsa bugün
  GCP_TTS_KEY  seslendirme anahtarı (yoksa sessiz deneme videosu)
  ONIZLEME_SN  >0 ise videonun yalnızca ilk N saniyesi üretilir (hızlı deneme)
"""
import datetime, json, math, os, subprocess, sys, wave

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out")
sys.path[:0] = [os.path.join(ROOT, "ortak"), HERE]
os.environ.setdefault("TTS_HIZ", "0.96")

import build as B  # noqa: E402  (ses, görsel ve yazı yardımcıları Shorts üreticisiyle ortak)

W, H, FPS = 1920, 1080, 24
SR = B.SR
B.W, B.H = W, H   # Shorts yardımcılarının (sahne_hazirla, sahne_kare, parsomen) 16:9 çalışması için
F_ALT = B.font("DejaVuSans-Bold.ttf", 50)
F_ETIKET = B.font("DejaVuSerif-Bold.ttf", 34)
F_BOLUM = B.font("DejaVuSerif-Bold.ttf", 88)
F_BOLUM_NO = B.font("DejaVuSans-Bold.ttf", 30)
F_KAPAK = B.font("DejaVuSerif-Bold.ttf", 120)
F_KANAL = B.font("DejaVuSans-Bold.ttf", 26)
ALTIN = B.ALTIN
KANAL = "SARAYIN GÖLGESİ"
TAKVIM_BASI = datetime.date(2026, 11, 4)   # ilk uzun video (çarşamba)
GUNLER = (2, 6)                             # çarşamba ve pazar


# ---------------------------------------------------------------- konu seçimi
def konu_yukle(konu_id):
    with open(os.path.join(HERE, "uzun", f"{konu_id}.json"), encoding="utf-8") as f:
        return json.load(f)


def siradaki(bugun):
    """Takvim başından bugüne kadar kaçıncı yayın günü olduğunu sayar; o sıradaki konuyu döner.
    Banka biterse None döner: aynı videoyu iki kez yüklememek için yükleme yapılmaz."""
    with open(os.path.join(HERE, "uzun", "sira.json"), encoding="utf-8") as f:
        sira = json.load(f)
    n, g = -1, TAKVIM_BASI
    while g <= bugun:
        if g.weekday() in GUNLER:
            n += 1
        g += datetime.timedelta(days=1)
    if n < 0 or n >= len(sira):
        return None
    return sira[n]


# ---------------------------------------------------------------- ses
def ses_hazirla(parcalar):
    """parcalar: [(tur, metin, bolum_no)] → (wav yolu, zamanlar, süre). Bölüm geçişlerinde uzun nefes."""
    from seslendirme import seslendir
    cache = os.path.join(OUT, "tts")
    ses, zaman, t = [np.zeros(int(SR * 0.4), np.float32)], [], 0.4
    onceki_bolum = None
    for tur, metin, bno in parcalar:
        if onceki_bolum is not None and bno != onceki_bolum:
            bos = np.zeros(int(SR * 1.6), np.float32)   # bölüm başlığı ekranda dururken sessizlik
            ses.append(bos); t += len(bos) / SR
        onceki_bolum = bno
        a = seslendir(B.tts_metni(metin), cache)
        if a is None:
            a = np.zeros(int(SR * max(2.5, len(metin) / 14.0)), np.float32)
        zaman.append((t, t + len(a) / SR))
        bos = np.zeros(int(SR * 0.55), np.float32)
        ses += [a, bos]; t += len(a) / SR + len(bos) / SR
    ses.append(np.zeros(int(SR * 1.5), np.float32))
    ham = os.path.join(OUT, "uzun_ham.wav")
    B.wav_yaz(ham, np.concatenate(ses))
    yol = os.path.join(OUT, "uzun_ses.wav")
    perde = float(os.environ.get("SES_PERDE") or 0.92)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", ham, "-filter:a",
                    f"asetrate={SR * perde:.0f},aresample={SR},atempo={1 / perde:.5f},bass=g=4:f=120:w=0.8,alimiter=limit=0.95",
                    "-ar", str(SR), "-ac", "1", yol], check=True)
    with wave.open(yol) as w:
        sure = w.getnframes() / w.getframerate()
    return yol, zaman, sure


# ---------------------------------------------------------------- görüntü
def golge():
    a = np.zeros((H, W), np.float32)
    y = np.arange(H)[:, None]
    a += np.clip((y - 640) / 440, 0, 1) * 0.85          # altyazı için alt koyulaştırma
    a += np.clip((220 - y) / 220, 0, 1) * 0.45           # üst etiket için
    xx = np.linspace(-1, 1, W)[None, :]
    yy = np.linspace(-1, 1, H)[:, None]
    a += np.clip((xx ** 2 + yy ** 2) ** 1.6 * 0.30, 0, 0.35)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., 3] = (np.clip(a, 0, 0.9) * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def sahne_hazirla(yol):
    """Yatay görsel: ekranı kaplar (B.sahne_hazirla). Dikey/kare görsel: bulanık arka plan + yüksekliğe sığdırılmış ön görsel."""
    if not yol:
        return B.parsomen(), None, "yok"
    try:
        im = Image.open(yol).convert("RGB")
    except Exception:
        return B.parsomen(), None, "yok"
    if im.width / im.height >= 1.25:
        bg, fg = B.sahne_hazirla(yol)
        return bg, fg, "kapla"
    s = max(W / im.width, H / im.height)
    bg = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.BILINEAR)
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = karart(bg.filter(ImageFilter.GaussianBlur(30)), 0.38)
    s = (H - 60) / im.height
    fg = im.resize((max(1, int(im.width * s)), H - 60), Image.LANCZOS)
    fg = ImageEnhance.Contrast(fg).enhance(1.06)
    return bg, fg, "sigdir"


def kare_uret(s, yerel):
    if s["mod"] == "sigdir":
        kare = s["bg"].copy()
        u = B.yumusak(yerel)
        z = 1.0 + 0.06 * (u if s["hareket"] % 2 == 0 else 1 - u)
        f = s["fg"].resize((int(s["fg"].width * z), int(s["fg"].height * z)), Image.BILINEAR)
        kare.paste(f, (int((W - f.width) / 2), int((H - f.height) / 2 + 10)))
        return kare
    return B.sahne_kare(s, yerel, s["hareket"])


def karart(im, oran):
    return Image.fromarray((np.asarray(im).astype(np.float32) * oran).astype(np.uint8))


def render(sahneler, bolumler, toplam, kapak, yol):
    G = golge()
    sure = toplam
    lim = float(os.environ.get("ONIZLEME_SN") or 0)
    if lim > 0:
        sure = min(sure, lim)
    n = int(sure * FPS)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "20", "-pix_fmt", "yuv420p", yol], stdin=subprocess.PIPE)
    GECIS = 0.6
    i = 0
    for fr in range(n):
        t = fr / FPS
        while i + 1 < len(sahneler) and t >= sahneler[i + 1]["bas"]:
            i += 1
        s = sahneler[i]
        bitis = sahneler[i + 1]["bas"] if i + 1 < len(sahneler) else toplam
        yerel = min(1.0, max(0.0, (t - s["bas"]) / max(0.1, bitis - s["bas"])))
        kare = kare_uret(s, yerel)
        if i > 0 and t - s["bas"] < GECIS:
            o = sahneler[i - 1]
            kare = Image.blend(kare_uret(o, 1.0), kare, (t - s["bas"]) / GECIS)
        kare.paste(G, (0, 0), G)
        d = ImageDraw.Draw(kare)

        # sol üst: kanal adı, sağ üst: tarih/isim etiketi
        d.text((48, 40), KANAL, font=F_KANAL, fill=ALTIN)
        if s.get("yazi") and s["tur"] == "sahne":
            et = s["yazi"]
            tw = d.textlength(et, font=F_ETIKET)
            d.rounded_rectangle([W - 48 - tw - 44, 30, W - 48, 30 + 62], 12, fill=(25, 15, 10), outline=ALTIN, width=2)
            d.text((W - 48 - tw - 22, 40), et, font=F_ETIKET, fill=ALTIN)

        kart_suruyor = s.get("bolum_basi") is not None and t - s["bas"] < 2.6
        if s["fg"] is None and s.get("yazi") and not kart_suruyor:   # görselsiz sahne: ortada süslü büyük yazı
            et = B.tr_buyuk(s["yazi"])
            f = F_KAPAK
            while d.textlength(et, font=f) > 1500 and f.size > 60:
                f = B.font("DejaVuSerif-Bold.ttf", f.size - 8)
            y0 = H / 2 - f.size / 2 - 40
            d.text(((W - d.textlength(et, font=f)) / 2, y0), et, font=f, fill=ALTIN, stroke_width=3, stroke_fill=(0, 0, 0))
            for yy in (y0 - 50, y0 + f.size + 50):
                d.line([W / 2 - 300, yy, W / 2 - 30, yy], fill=ALTIN, width=3)
                d.line([W / 2 + 30, yy, W / 2 + 300, yy], fill=ALTIN, width=3)
                d.polygon([(W / 2, yy - 14), (W / 2 + 14, yy), (W / 2, yy + 14), (W / 2 - 14, yy)], fill=ALTIN)

        # bölüm başlık kartı: bölümün ilk 2.6 saniyesi
        if s.get("bolum_basi") is not None and t - s["bas"] < 2.6:
            k = t - s["bas"]
            alfa = min(1.0, k / 0.4, (2.6 - k) / 0.5)
            ust = Image.new("RGBA", (W, H), (0, 0, 0, int(150 * alfa)))
            kare.paste(ust, (0, 0), ust)
            d = ImageDraw.Draw(kare)
            no = f"BÖLÜM {s['bolum_basi'] + 1}"
            renk = tuple(int(c * alfa) for c in ALTIN)
            d.text(((W - d.textlength(no, font=F_BOLUM_NO)) / 2, H / 2 - 110), no, font=F_BOLUM_NO, fill=renk)
            ad = bolumler[s["bolum_basi"]]
            d.text(((W - d.textlength(ad, font=F_BOLUM)) / 2, H / 2 - 60), ad, font=F_BOLUM,
                   fill=tuple(int(c * alfa) for c in (255, 240, 210)), stroke_width=3, stroke_fill=(0, 0, 0))
            d.line([W / 2 - 160, H / 2 + 60, W / 2 + 160, H / 2 + 60], fill=renk, width=3)
        elif s["tur"] == "kanca" and t < 3.0:   # açılışta kapak yazısı
            alfa = min(1.0, t / 0.5, (3.0 - t) / 0.6)
            d.text(((W - d.textlength(kapak, font=F_KAPAK)) / 2, H / 2 - 150), kapak, font=F_KAPAK,
                   fill=tuple(int(c * alfa) for c in (255, 236, 160)), stroke_width=6, stroke_fill=(0, 0, 0))

        # altyazı
        if s["kon_bas"] <= t <= s["kon_bit"] + 0.3:
            ilerle = (t - s["kon_bas"]) / max(0.1, s["kon_bit"] - s["kon_bas"])
            for a, b, parca in s["altyazi"]:
                if a <= min(ilerle, 0.999) < b:
                    satirlar = B.satirla(d, parca, F_ALT, 1500)[:2]
                    y = H - 120 - len(satirlar) * 62
                    for st in satirlar:
                        d.text(((W - d.textlength(st, font=F_ALT)) / 2, y), st, font=F_ALT,
                               fill=(255, 236, 160) if s["tur"] in ("kanca", "soru") else (255, 255, 255),
                               stroke_width=5, stroke_fill=(0, 0, 0))
                        y += 62
                    break
        ff.stdin.write(kare.tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg görüntü kodlaması başarısız")


def altyazi_parcalari(metin):
    """Yatay ekranda daha uzun parçalar: ~44 karakter, cümle sonunda böl."""
    kelimeler, parcalar, p = metin.split(), [], []
    for k in kelimeler:
        p.append(k)
        if len(" ".join(p)) >= 44 or k.endswith((".", "?", "!")) and len(" ".join(p)) >= 18:
            parcalar.append(" ".join(p)); p = []
    if p:
        parcalar.append(" ".join(p))
    toplam = sum(len(x) for x in parcalar) or 1
    sinir, b = [], 0.0
    for x in parcalar:
        sinir.append((b, b + len(x) / toplam, x)); b += len(x) / toplam
    return sinir


# ---------------------------------------------------------------- küçük resim (yt-package)
def kucuk_resim(gorsel_yolu, kapak, yol):
    """1280x720: tablodan çarpıcı kesit, solda koyulaşma, ≤3 kelime büyük altın yazı (başlığı tekrar etmez)."""
    w, h = 1280, 720
    try:
        im = Image.open(gorsel_yolu).convert("RGB")
        s = max(w / im.width, h / im.height)
        im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
        im = im.crop(((im.width - w) // 2, (im.height - h) // 2, (im.width - w) // 2 + w, (im.height - h) // 2 + h))
        im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.2)).enhance(1.15)
    except Exception:
        im = Image.new("RGB", (w, h), (40, 22, 16))
    x = np.linspace(0, 1, w)[None, :, None]
    a = np.asarray(im).astype(np.float32) * (0.35 + 0.65 * np.clip((x - 0.05) / 0.6, 0, 1))
    im = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(im)
    kelimeler = B.tr_buyuk(kapak).split()
    satirlar = [" ".join(kelimeler[:2]), " ".join(kelimeler[2:])] if len(kelimeler) > 2 else [" ".join(kelimeler)]
    boy = 150
    while boy > 60:
        f = B.font("DejaVuSerif-Bold.ttf", boy)
        if max(d.textlength(sat, font=f) for sat in satirlar) <= 700:
            break
        boy -= 6
    y = (h - len(satirlar) * (boy + 12)) / 2
    for sat in satirlar:
        d.text((60, y), sat, font=f, fill=(255, 222, 140), stroke_width=8, stroke_fill=(0, 0, 0))
        y += boy + 12
    d.rectangle([60, y + 10, 260, y + 18], fill=ALTIN)
    im.save(yol, quality=92)


# ---------------------------------------------------------------- açıklama (yt-seo + yt-chapters)
def meta_olustur(konu, baslik, bolum_zamanlari, gorseller, toplam):
    sys.path.insert(0, os.path.join(HERE, "araclar"))
    from bolumler import bolum_listesi
    aramalar = [B.tr_baslik_harf(e) for e in konu["etiketler"][:3]]
    satir2 = ("Osmanlı tarihi belgeseli: " + ", ".join(aramalar[:-1]) + f" ve {aramalar[-1]} "
              "baştan sona, bölüm bölüm.")
    bolumler = bolum_listesi(bolum_zamanlari, toplam)
    sanatcilar = sorted({g["sanatci"] for g in gorseller if g and g.get("sanatci")})
    gorsel = "Görseller: Wikimedia Commons'taki kamu malı tarihi eserler"
    if sanatcilar:
        gorsel += " (" + ", ".join(sanatcilar[:6]) + ")"
    aciklama = (f"{konu['kanca'].split('. ')[0].rstrip('.')}.\n{satir2}\n\n"
                f"Bölümler:\n{bolumler}\n\n"
                f"{konu['soru']}\n\n"
                "Sarayın Gölgesi'nde Osmanlı tarihinin bilinmeyen ve kaotik hikâyelerini anlatıyoruz. "
                "Rivayetleri rivayet, bilgileri bilgi olarak aktarıyoruz; yanlış gördüğün bir şey olursa yorumlarda yaz.\n\n"
                f"{gorsel}\n\n#osmanlıtarihi #tarih #belgesel #osmanlı")
    etiketler = list(dict.fromkeys(konu["etiketler"] + ["osmanlı tarihi", "tarih belgeseli", "osmanlı"]))[:15]
    return {"title": baslik[:100], "description": aciklama[:4900], "tags": etiketler, "categoryId": "27",
            "konu": konu["id"], "uzun": True, "sesli": bool(os.environ.get("GCP_TTS_KEY", "").strip())}


# ---------------------------------------------------------------- ana akış
def main():
    os.makedirs(OUT, exist_ok=True)
    bugun = datetime.date.today()
    seed = int(os.environ.get("SEED") or bugun.strftime("%Y%m%d"))
    konu_id = (os.environ.get("UZUN_KONU") or "").strip() or siradaki(bugun)
    if not konu_id:
        print("Uzun video bankası bitti: yeni senaryo eklenmeden yükleme yapılmayacak.")
        with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"atla": True}, f)
        return
    konu = konu_yukle(konu_id)
    print("Uzun video:", konu_id, flush=True)

    from gorsel import bul
    klasor = os.path.join(OUT, "img")
    kullanilan, gorseller, onbellek = set(), [], {}

    def gorsel_al(liste):
        anahtar = tuple(liste)
        if anahtar not in onbellek:
            onbellek[anahtar] = bul(liste, "savaslar", klasor, kullanilan)
        return onbellek[anahtar]

    parcalar, kaynak = [("kanca", konu["kanca"], -1)], [(None, konu.get("kanca_gorsel") or konu["bolumler"][0]["sahneler"][0]["gorsel"], -1)]
    for bi, bol in enumerate(konu["bolumler"]):
        for si, sh in enumerate(bol["sahneler"]):
            parcalar.append(("sahne", sh["metin"], bi))
            kaynak.append((sh.get("yazi"), sh["gorsel"], bi if si == 0 else None))
    parcalar.append(("soru", konu["soru"], len(konu["bolumler"])))
    kaynak.append((None, konu["bolumler"][-1]["sahneler"][-1]["gorsel"], None))

    ses_yolu, zaman, toplam = ses_hazirla(parcalar)
    print(f"Süre: {toplam / 60:.1f} dk", flush=True)
    gecisler = [0.0] + [zaman[k][0] for k, (_, _, ilk) in enumerate(kaynak) if ilk is not None and ilk >= 0]
    B.sinematik_yatak(ses_yolu, gecisler)   # yumuşak geçiş sesi yalnızca bölüm başlarında

    sahneler, hazir, bolum_zamanlari = [], {}, [(0, "Hikâyeye giriş")]
    for k, ((tur, metin, _), (a, b), (yazi, gliste, ilk)) in enumerate(zip(parcalar, zaman, kaynak)):
        g = gorsel_al(gliste)
        gorseller.append(g)
        anahtar = g["yol"] if g else None
        if anahtar not in hazir:
            hazir[anahtar] = sahne_hazirla(anahtar)
        bg, fg, mod = hazir[anahtar]
        bas = max(0.0, a - (1.6 if ilk is not None and ilk >= 0 else 0.3))
        if ilk is not None and ilk >= 0:
            bolum_zamanlari.append((int(bas), konu["bolumler"][ilk]["ad"]))
        sahneler.append({"tur": tur, "yazi": yazi, "bg": bg, "fg": fg, "mod": mod, "bas": bas, "kon_bas": a, "kon_bit": b,
                         "altyazi": altyazi_parcalari(metin), "hareket": k,
                         "bolum_basi": ilk if (ilk is not None and ilk >= 0) else None})
    sahneler[0]["bas"] = 0.0

    baslik = B.baslik_sec(seed, konu)
    render(sahneler, [b["ad"] for b in konu["bolumler"]], toplam, B.tr_buyuk(konu["kapak"]), os.path.join(OUT, "uzun_v.mp4"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(OUT, "uzun_v.mp4"), "-i", ses_yolu,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", os.path.join(OUT, "uzun.mp4")], check=True)
    kucuk_resim(gorseller[0]["yol"] if gorseller[0] else None, konu["kapak"], os.path.join(OUT, "kucuk_resim.jpg"))
    meta = meta_olustur(konu, baslik, bolum_zamanlari, gorseller, toplam)
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
