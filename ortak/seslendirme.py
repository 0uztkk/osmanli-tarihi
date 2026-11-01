"""Google Cloud Text-to-Speech ile Türkçe seslendirme.

GCP_TTS_KEY ortam değişkeni yoksa sessizce None döner; video seslendirmesiz üretilir.
Üretilen sesler out/tts/ altında önbelleğe alınır.
"""
import base64, hashlib, io, json, os, sys, urllib.error, urllib.request, wave

import numpy as np

API = "https://texttospeech.googleapis.com/v1"
SR = 44100
# Sıcak, çocuklara uygun kadın sesleri; ilk bulunan kullanılır
TERCIH = ["Chirp3-HD-Aoede", "Chirp3-HD-Leda", "Chirp3-HD-Kore", "Chirp3-HD-Zephyr",
          "Wavenet-A", "Wavenet-C", "Wavenet-D"]
# Başka kanallar ses listesini ve hızı ortam değişkeniyle değiştirebilir:
#   TTS_SESLER="Chirp3-HD-Charon,Wavenet-B"   TTS_HIZ=1.0
if os.environ.get("TTS_SESLER", "").strip():
    TERCIH = [s.strip() for s in os.environ["TTS_SESLER"].split(",") if s.strip()]
HIZ = float(os.environ.get("TTS_HIZ") or 0.92)

_voice = None


def _key():
    return os.environ.get("GCP_TTS_KEY", "").strip()


def _call(path, body=None):
    url = f"{API}/{path}{'&' if '?' in path else '?'}key={_key()}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def ses_sec():
    global _voice
    if _voice:
        return _voice
    names = [v["name"] for v in _call("voices?languageCode=tr-TR").get("voices", [])]
    for t in TERCIH:
        for n in names:
            if n.endswith(t):
                _voice = n
                print("Seslendirme sesi:", n, file=sys.stderr)
                return n
    _voice = names[0]
    print("Seslendirme sesi (varsayılan):", _voice, file=sys.stderr)
    return _voice


def seslendir(text, cache_dir):
    """Metni seslendirir, float32 mono numpy dizisi (44.1 kHz) döner. Anahtar yoksa None."""
    if not _key():
        return None
    os.makedirs(cache_dir, exist_ok=True)
    voice = ses_sec()
    path = os.path.join(cache_dir, hashlib.md5(f"{voice}|{HIZ}|{text}".encode()).hexdigest() + ".wav")
    if not os.path.exists(path):
        body = {"input": {"text": text},
                "voice": {"languageCode": "tr-TR", "name": voice},
                "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": SR, "speakingRate": HIZ}}
        try:
            resp = _call("text:synthesize", body)
        except urllib.error.HTTPError:
            body["audioConfig"].pop("speakingRate")   # bazı sesler hız ayarını desteklemiyor
            resp = _call("text:synthesize", body)
        with open(path, "wb") as f:
            f.write(base64.b64decode(resp["audioContent"]))
    with wave.open(path) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            a = a.reshape(-1, 2).mean(axis=1)
    if sr != SR:
        a = np.interp(np.linspace(0, len(a), int(len(a) * SR / sr), endpoint=False), np.arange(len(a)), a)
    # baştaki/sondaki sessizliği kırp
    nz = np.where(np.abs(a) > 0.01)[0]
    if len(nz):
        a = a[max(0, nz[0] - 400): nz[-1] + 2000]
    return a.astype(np.float32)
