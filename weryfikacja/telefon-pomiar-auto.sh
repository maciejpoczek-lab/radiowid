#!/data/data/com.termux/files/usr/bin/bash
# Samoczynny pomiar sieci na telefonie (Termux + Termux:API) do kalibracji: weryfikacja/kalibracja.mjs.
# Uruchamiany przez Androida co 15 min (termux-job-scheduler, przetrwa restart telefonu):
#  - do 40 s prób GPS (kolejne żądania "-r once" po 10 s); brak świeżej poprawki <= 25 m = telefon w budynku albo w kieszeni bez nieba -> nic nie zapisuje
#    (to zarazem odsiewa pomiary zza ścian), GPS gaszony, telefon zasypia;
#  - jest poprawka -> zapis co 5 s (na postoju co 60 s), dopóki poprawka świeża, najwyżej ok. 9 min na jedno uruchomienie.
# Pliki dzienne Documents/RadioWid/auto_<data>.jsonl (format jak telefon-pomiar.sh). Gdy najstarszy nieodebrany plik ma
# 7 dni - powiadomienie "podłącz telefon do Maca"; weryfikacja/telefon-pobierz.sh odbiera pliki do Documents/RadioWid/pobrane/.
# Instalacja: ~/bin/pomiar-auto + termux-job-scheduler --job-id 7 --period-ms 900000 --persisted true --script ~/bin/pomiar-auto
D="$HOME/storage/shared/Documents/RadioWid"
mkdir -p "$D" || exit 1
L="$D/.auto.log"; log() { echo "$(date +%Y-%m-%dT%H:%M:%S) $*" >> "$L"; }
BLOKADA="$HOME/.pomiar-auto.lock"                  # jedno uruchomienie naraz; blokada starsza niż 15 min = po zabitym zadaniu
if ! mkdir "$BLOKADA" 2>/dev/null; then
  [ -n "$(find "$BLOKADA" -maxdepth 0 -mmin +15)" ] && rm -rf "$BLOKADA" && mkdir "$BLOKADA" || exit 0
fi

# --- przypomnienie: najstarszy nieodebrany plik sprzed >= 7 dni ---
if [ -n "$(find "$D" -maxdepth 1 -name 'auto_*.jsonl' -mtime +6 | head -1)" ]; then
  termux-notification --id radiowid-odczyt --title "RadioWid: pomiary z tygodnia" \
    --content "Podłącz telefon do Maca i napisz w Claude: pobierz pomiar" >/dev/null 2>&1
fi

termux-wake-lock
TMP="$HOME/.pomiar-auto.loc"
koniec() { pkill -f 'termux-location' 2>/dev/null; termux-wake-unlock; rm -f "$TMP"; rmdir "$BLOKADA" 2>/dev/null; }
trap 'koniec; exit 0' INT TERM EXIT

# odczyt świeżej poprawki: LOC = surowy JSON, P = "lat lon dokl wiek_ms" albo pusto (bez podpowłoki - LOC idzie do zapisu).
# Każdy krok to nowe żądanie "-r once": aplikacja w tle dostaje od Androida (prawdopodobnie - ograniczanie lokalizacji w tle,
# niezmierzone) tylko pierwszą poprawkę z ciągłego "-r updates"
# (2026-10-09: 29 uruchomień, jedna poprawka, potem "-r last" stało w miejscu). "-r once" bez nieba wisi - stąd limit 10 s.
poprawka() {
  : > "$TMP"; termux-location -p gps -r once > "$TMP" 2>/dev/null &
  local j=$! i=0
  while [ "$i" -lt 10 ] && kill -0 "$j" 2>/dev/null; do sleep 1; i=$((i + 1)); done
  kill -0 "$j" 2>/dev/null && { pkill -P "$j" 2>/dev/null; kill "$j" 2>/dev/null; }
  LOC=$(tr -d '\n' < "$TMP")
  P=$(printf '%s' "$LOC" | awk '{
    if (match($0, /"latitude": *[-0-9.]+/)) lat = substr($0, RSTART, RLENGTH); sub(/.*: */, "", lat)
    if (match($0, /"longitude": *[-0-9.]+/)) lon = substr($0, RSTART, RLENGTH); sub(/.*: */, "", lon)
    if (match($0, /"accuracy": *[0-9.]+/)) a = substr($0, RSTART, RLENGTH); sub(/.*: */, "", a)
    if (match($0, /"elapsedMs": *[0-9]+/)) w = substr($0, RSTART, RLENGTH); sub(/.*: */, "", w)
    if (lat != "" && a != "" && a + 0 <= 25 && w != "" && w + 0 <= 10000) print lat, lon, a, w }')
}

START=$(date +%s); P=""
while [ $(( $(date +%s) - START )) -lt 40 ]; do poprawka; [ -n "$P" ] && break; done
if [ -z "$P" ]; then log "brak poprawki GPS - pomijam"; exit 0; fi

F="$D/auto_$(date +%Y-%m-%d).jsonl"; N=0; STALE=0; OST_LAT=""; OST_LON=""; OST_T=0
while [ $(( $(date +%s) - START )) -lt 540 ]; do
  poprawka
  if [ -z "$P" ]; then STALE=$((STALE + 1)); [ "$STALE" -ge 3 ] && break; continue; fi
  STALE=0; set -- $P; TERAZ=$(date +%s)
  # postój: < 20 m od ostatniego zapisu i < 60 s -> pomiń krok
  if [ -n "$OST_LAT" ]; then
    ODL=$(awk -v a="$1" -v b="$2" -v c="$OST_LAT" -v d="$OST_LON" 'BEGIN { dy = (a - c) * 111320; dx = (b - d) * 111320 * cos(a * 3.14159265 / 180); printf "%d", sqrt(dx * dx + dy * dy) }')
    if [ "$ODL" -lt 20 ] && [ $((TERAZ - OST_T)) -lt 60 ]; then sleep 5; continue; fi
  fi
  CELLS=$(termux-telephony-cellinfo 2>/dev/null | tr -d '\n')
  case "$CELLS" in "["*) ;; *) CELLS=null ;; esac
  printf '{"t":"%s","loc":%s,"cells":%s}\n' "$(date +%Y-%m-%dT%H:%M:%S%z)" "$LOC" "$CELLS" >> "$F"
  N=$((N + 1)); OST_LAT=$1; OST_LON=$2; OST_T=$TERAZ
  sleep 5
done
log "zapisano $N krokow do $(basename "$F")"
