#!/usr/bin/env bash
# ffmpeg ve DejaVu yazı tiplerini kurar. Ubuntu paket sunucuları zaman zaman takılıyor
# (11 Kasım 2026: apt-get bir saat bekleyip hata verdi, video yüklenemedi). Bu yüzden:
#  1) zaten kuruluysa hiçbir şey yapma,
#  2) apt'yi kısa zaman aşımıyla dene,
#  3) olmazsa ffmpeg'i ve yazı tiplerini GitHub sürümlerinden indir.
set -u
FONT=/usr/share/fonts/truetype/dejavu
var() { command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null && [ -f "$FONT/DejaVuSans-Bold.ttf" ] && [ -f "$FONT/DejaVuSerif-Bold.ttf" ]; }
if var; then echo "Araçlar zaten kurulu."; exit 0; fi

if timeout 180 sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 update -qq \
   && timeout 300 sudo apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 \
        install -y -qq --no-install-recommends ffmpeg fonts-dejavu-core; then
  if var; then echo "apt ile kuruldu."; exit 0; fi
fi

echo "apt çalışmadı; GitHub'dan indiriliyor."
T=$(mktemp -d)
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  curl -fsSL --retry 3 --max-time 300 -o "$T/ff.tar.xz" \
    https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz
  tar -xf "$T/ff.tar.xz" -C "$T"
  sudo install -m 755 "$T"/ffmpeg-*/bin/ffmpeg "$T"/ffmpeg-*/bin/ffprobe /usr/local/bin/
fi
if [ ! -f "$FONT/DejaVuSans-Bold.ttf" ] || [ ! -f "$FONT/DejaVuSerif-Bold.ttf" ]; then
  curl -fsSL --retry 3 --max-time 120 -o "$T/dv.zip" \
    https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip
  unzip -q "$T/dv.zip" -d "$T"
  sudo mkdir -p "$FONT"
  sudo cp "$T"/dejavu-fonts-ttf-2.37/ttf/*.ttf "$FONT"/
fi
var && echo "Yedek yoldan kuruldu." || { echo "HATA: araçlar kurulamadı"; exit 1; }
