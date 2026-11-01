#!/usr/bin/env python3
"""yt-chapters kuralları: uzun videolar için bölüm listesi üretir ve YouTube kurallarına göre doğrular.

Kurallar (uymayan liste sessizce bölüm olmaz):
- İlk satır 00:00 olmalı.
- En az 3 bölüm olmalı.
- Her bölüm en az 10 saniye sürmeli.
- Her başlık o bölümün vaadi olmalı, 3-5 kelime (konu kelimesi yığını değil).

Bu kanal şu an yalnızca Shorts üretiyor; Shorts'ta bölüm yok. Uzun video (ör. haftalık derleme)
eklendiğinde: bolum_listesi([(saniye, "başlık"), ...], toplam_sure) → açıklamaya yapıştırılacak blok.

yt-shorts notu: bu kanal Shorts'u doğrudan üretir, uzun videodan kesmez. Uzun video eklenirse her
Short için: kendi başına anlaşılan 20-55 sn'lik parça, YENİ bir ilk cümle (hookscore_tr ile puanlanır),
ilk 2 saniyede sözden farklı ekran yazısı ve sonu başa bağlayan bir döngü cümlesi gerekir.
"""
import sys


def mmss(t):
    t = int(t)
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def dogrula(bolumler, toplam):
    sorun = []
    if not bolumler or bolumler[0][0] != 0:
        sorun.append("ilk bölüm 00:00'da başlamalı")
    if len(bolumler) < 3:
        sorun.append("en az 3 bölüm gerekli")
    sinirlar = [b[0] for b in bolumler] + [toplam]
    for i, (bas, ad) in enumerate(bolumler):
        if sinirlar[i + 1] - bas < 10:
            sorun.append(f"'{ad}' 10 saniyeden kısa")
        n = len(ad.split())
        if not 2 <= n <= 6:
            sorun.append(f"'{ad}' {n} kelime (3-5 olmalı)")
    return sorun


def bolum_listesi(bolumler, toplam):
    bolumler = sorted(bolumler)
    sorun = dogrula(bolumler, toplam)
    if sorun:
        raise ValueError("Bölüm listesi geçersiz: " + "; ".join(sorun))
    return "\n".join(f"{mmss(t)} {ad}" for t, ad in bolumler)


if __name__ == "__main__":
    ornek = [(0, "Kuşatma nasıl başladı"), (42, "Haliç'i kapatan zincir"), (95, "Gemiler karadan yürüyor"),
             (160, "29 Mayıs sabahı")]
    print(bolum_listesi(ornek, 220))
    try:
        bolum_listesi([(5, "a"), (8, "b")], 20)
    except ValueError as e:
        print("Beklenen hata:", e, file=sys.stderr)
