#!/data/data/com.termux/files/usr/bin/bash
# Zapis pomiarów sieci komórkowej na telefonie (Termux + Termux:API) do kalibracji modelu: weryfikacja/kalibracja.mjs.
# Co krok: ostatnia pozycja GPS (termux-location -r last; GPS trzymany w tle przez -r updates, wiek poprawki w elapsedMs)
# i wszystkie widziane komórki z siłą sygnału (termux-telephony-cellinfo), jedna linia JSON na krok.
# Pasmo ("bands") jest wiarygodne tylko dla komórki zarejestrowanej - u sąsiadów telefony MediaTek podają stale [1].
# Plik w Documents/RadioWid na telefonie; nic nie jest nigdzie wysyłane.
# Instalacja (raz, przez adb z Maca): plik do ~/bin/pomiar, chmod +x; w Termuxie: pkg install termux-api, termux-setup-storage.
# Uzycie w Termuxie: pomiar [sekundy_miedzy_krokami, domyslnie 5]   - koniec: Ctrl+C (albo zamkniecie sesji Termuxa)
KROK=${1:-5}
D="$HOME/storage/shared/Documents/RadioWid"
mkdir -p "$D" || { echo "brak dostepu do pamieci: uruchom termux-setup-storage"; exit 1; }
F="$D/pomiar_$(date +%Y-%m-%d_%H%M%S).jsonl"
termux-wake-lock                                   # bez tego Android usypia Termuxa przy zgaszonym ekranie
termux-location -p gps -r updates -d 1000 > /dev/null 2>&1 &   # trzyma odbiornik GPS wlaczony
GPS=$!
N=0
koniec() { kill "$GPS" 2>/dev/null; pkill -f 'termux-location' 2>/dev/null; termux-wake-unlock; echo; echo "zapisano $N krokow: $F"; exit 0; }
trap koniec INT TERM
echo "zapis do $F co $KROK s (Ctrl+C konczy)"
while true; do
  T=$(date +%Y-%m-%dT%H:%M:%S%z)
  LOC=$(termux-location -p gps -r last 2>/dev/null | tr -d '\n')
  case "$LOC" in "{"*) ;; *) LOC=null ;; esac
  CELLS=$(termux-telephony-cellinfo 2>/dev/null | tr -d '\n')
  case "$CELLS" in "["*) ;; *) CELLS=null ;; esac
  printf '{"t":"%s","loc":%s,"cells":%s}\n' "$T" "$LOC" "$CELLS" >> "$F"
  N=$((N + 1))
  DOKL=$(printf '%s' "$LOC" | grep -o '"accuracy": *[0-9]*' | grep -o '[0-9]*$')
  WIEK=$(printf '%s' "$LOC" | grep -o '"elapsedMs": *[0-9]*' | grep -o '[0-9]*$')
  printf '\r%s  krokow: %d  GPS: %s m, %s s temu     ' "$T" "$N" "${DOKL:--}" "$(( ${WIEK:-0} / 1000 ))"
  sleep "$KROK"
done
