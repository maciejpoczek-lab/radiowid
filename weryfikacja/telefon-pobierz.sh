#!/usr/bin/env bash
# Odbiór pomiarów z telefonu (kabel, debugowanie USB) - para do telefon-pomiar-auto.sh i telefon-pomiar.sh.
# Ściąga Documents/RadioWid/{auto,pomiar}_*.jsonl do ~/dev/showreel-2/pomiary/telefon/, skleja wszystkie dotąd pobrane w jeden plik
# i dopiero po sprawdzeniu kopii przenosi je na telefonie do Documents/RadioWid/pobrane/ (przypomnienie 7-dniowe już nie wraca;
# wiszące powiadomienie zamyka się ręcznie - adb nie ma dostępu do powiadomień Termuxa).
# Niczego na telefonie nie kasuje. Na koniec liczy kalibrację (weryfikacja/kalibracja.mjs).
# Uzycie: weryfikacja/telefon-pobierz.sh [opcje kalibracja.mjs, np. --operator P4]
set -euo pipefail
ADB=${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}
HERE=$(cd "$(dirname "$0")" && pwd)
CEL="$HERE/../../pomiary/telefon"; mkdir -p "$CEL"
TEL=/sdcard/Documents/RadioWid
"$ADB" get-state >/dev/null || { echo "telefon niepodłączony (adb)"; exit 1; }
PLIKI=$("$ADB" shell "ls $TEL/auto_*.jsonl $TEL/pomiar_*.jsonl 2>/dev/null" | tr -d "\r" || true)
[ -n "$PLIKI" ] || { echo "brak nowych pomiarów na telefonie"; exit 0; }
"$ADB" shell "mkdir -p $TEL/pobrane"
for p in $PLIKI; do
  n=$(basename "$p"); "$ADB" pull -q "$p" "$CEL/$n" >/dev/null
  zdalny=$("$ADB" shell "wc -c < '$p'" | tr -d '\r '); lokalny=$(wc -c < "$CEL/$n" | tr -d ' ')
  [ "$zdalny" = "$lokalny" ] || { echo "kopia $n niezgodna ($lokalny z $zdalny B) - zostaje na telefonie"; continue; }
  "$ADB" shell "mv '$p' $TEL/pobrane/"
  echo "pobrano $n ($lokalny B)"
done
"$ADB" shell "tail -5 $TEL/.auto.log 2>/dev/null" | tr -d '\r' || true
OKRES="$CEL/../wszystkie.jsonl"
cat "$CEL"/*.jsonl > "$OKRES"
echo "razem: $(wc -l < "$OKRES" | tr -d ' ') kroków -> $OKRES"
node "$HERE/kalibracja.mjs" "$OKRES" --wynik "${OKRES%.jsonl}.json" "$@"
