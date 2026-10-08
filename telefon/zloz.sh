#!/bin/bash
# Sklada katalog do serwowania strony probnej w sieci domowej: TYLKO strona, silnik i dane wokol rynku.
# weryfikacja/ (siatka fala.py poza rynkiem) celowo poza kopia - serwer w Wi-Fi nie ma do niej dostepu.
# Uzycie: telefon/zloz.sh  -> ~/dev/showreel-2/mapa/_telefon/ ; potem: python3 -m http.server 8766 --directory <ten katalog>
set -euo pipefail
M="$(cd "$(dirname "$0")/.." && pwd)"; C="$M/_telefon"
rm -rf "$C"; mkdir -p "$C/telefon" "$C/silnik" "$C/dane/rynek" "$C/dane/rynek-z" "$C/dane/obszar-2880-z"
cp "$M"/telefon/index.html "$M"/telefon/praca.js "$M"/telefon/punkt.html "$M"/telefon/punkt-praca.js "$M"/telefon/poziomy.html "$M"/telefon/poziomy-praca.js "$C/telefon/"
for f in "$M"/silnik/*.js; do sed -E '/^[[:space:]]*\/\//d' "$f" > "$C/silnik/$(basename "$f")"; done   # bez komentarzy calolinijkowych (nazwy plikow weryfikacji)
cp "$M"/dane/rynek/* "$C/dane/rynek/"; cp "$M"/dane/rynek-z/* "$C/dane/rynek-z/"; cp "$M"/dane/obszar-2880-z/* "$C/dane/obszar-2880-z/"; cp "$M"/dane/stacje.json "$M"/dane/rtv.json "$M"/dane/budynki-wektor.json.gz "$M"/dane/mapa-wektor.json.gz "$C/dane/"
if [ -d "$M/dane/paczki/v1" ]; then mkdir -p "$C/dane/paczki/v1"; cp "$M"/dane/paczki/v1/*.pak "$C/dane/paczki/v1/"   # PROBA paczek 20 km (?paczki)
  if [ -f "$M/dane/paczki/v1/lista.json" ]; then cp "$M/dane/paczki/v1/lista.json" "$C/dane/paczki/v1/"; fi
  if compgen -G "$M/dane/paczki/v1/*-budynki.json.gz" > /dev/null; then cp "$M"/dane/paczki/v1/*-budynki.json.gz "$C/dane/paczki/v1/"; fi   # obrysy budynkow paczek (obrysy_paczki.py)   # spis paczek 4 m (przygotuj/paczki-na-strone.sh)
  if compgen -G "$M/dane/paczki/v1/*-mapa.json.gz" > /dev/null; then cp "$M"/dane/paczki/v1/*-mapa.json.gz "$M"/dane/paczki/v1/*-adresy.json.gz "$C/dane/paczki/v1/"; fi; fi   # podklad i adresy paczek (mapa_kraj.py)
if [ -d "$M/dane/obszar-2880-2180-z" ]; then                               # uklad 2180 (?paczki): teren + pliki -2180, miasto z paczek
  mkdir -p "$C/dane/obszar-2880-2180-z"; cp "$M/dane/obszar-2880-2180-z"/* "$C/dane/obszar-2880-2180-z/"
  for f in stacje rtv; do cp "$M/dane/$f-2180.json" "$C/dane/"; done
  if [ -d "$M/dane/kraj/teren-100" ]; then                                 # poziomy.html krok 2: pliki krajowe, jednakowe dla wszystkich (bez teren100.npy)
    mkdir -p "$C/dane/kraj/teren-100"; cp "$M"/dane/kraj/nadajniki.json.gz "$M"/dane/kraj/teren-1000.pak "$C/dane/kraj/"; for f in podklad miejscowosci stacje; do cp "$M/dane/kraj/$f.json.gz" "$C/dane/kraj/"; done; cp "$M"/dane/kraj/teren-100/*.pak "$C/dane/kraj/teren-100/"   # pliki kraju obowiazkowe: brak = blad, nie cicha pusta strona
  fi
  for f in budynki-wektor mapa-wektor; do cp "$M/dane/$f-2180.json.gz" "$C/dane/"; done
fi
for P in warszawa; do                                                       # inne miejsca: gdy ich dane sa juz zlozone
  [ -d "$M/dane/obszar-2880-$P-z" ] || continue
  mkdir -p "$C/dane/obszar-2880-$P-z"; cp "$M/dane/obszar-2880-$P-z"/* "$C/dane/obszar-2880-$P-z/"
  for f in stacje rtv; do cp "$M/dane/$f-$P.json" "$C/dane/"; done
  for f in budynki-wektor mapa-wektor; do cp "$M/dane/$f-$P.json.gz" "$C/dane/"; done
done
cp "$M"/ikony/* "$C/"                                                         # ikony i karta udostepniania (logo: ~/dev/RadioWid/logo) - w katalogu glownym strony
# strona startowa: przekierowanie + ikony i znaczniki podgladu linku (roboty komunikatorow nie ida za przekierowaniem, czytaja TEN plik)
cat > "$C/index.html" <<'HTML'
<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>RadioWid</title>
<meta http-equiv="refresh" content="0; url=telefon/poziomy.html">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32.png" sizes="32x32">
<link rel="apple-touch-icon" href="/apple-touch-icon-180.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#07090d">
<meta name="description" content="Zobacz, skąd przychodzi sygnał radia, telewizji i sieci komórkowych. Symulacja dla całej Polski.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="RadioWid">
<meta property="og:title" content="RadioWid">
<meta property="og:description" content="Zobacz, skąd przychodzi sygnał radia, telewizji i sieci komórkowych.">
<meta property="og:url" content="https://radio-wid.pl/">
<meta property="og:image" content="https://radio-wid.pl/karta-udostepniania.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Znak RadioWid i hasło: Zobacz, skąd przychodzi sygnał radia, telewizji i sieci komórkowych.">
<meta property="og:locale" content="pl_PL">
<meta name="twitter:card" content="summary_large_image">
</head>
<body style="background:#07090d"><a href="telefon/poziomy.html" style="color:#9fd0ff">RadioWid</a></body>
</html>
HTML
if grep -rqiE "fala\.py|fala\.npz|weryfikacja" "$C"; then echo "BLAD: w kopii jest odwolanie do danych weryfikacji" >&2; exit 1; fi
du -sh "$C"; find "$C" -type f | sed "s|$C/||" | sort
