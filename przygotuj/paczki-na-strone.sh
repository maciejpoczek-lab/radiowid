#!/bin/bash
# Paczki 20 km policzone przez nocna kolejke ($KOLEJKA:~/paczki/gotowe/v1, przygotuj/ustawienia.sh) -> dane/paczki/v1 na Macu, gotowe do telefon/zloz.sh:
#   1. kopiuje nowe E...N....pak (istniejacych nie nadpisuje - paczki Garwolina liczone lokalnie zostaja),
#   2. robi poziomy -16.pak / -100.pak dla paczek, ktore ich nie maja albo sa od nich nowsze (paczka.py poziomy),
#   3. obrysy budynkow E...N...-budynki.json.gz (przygotuj/obrysy_paczki.py na $KOLEJKA),
#   4. zapisuje dane/paczki/v1/lista.json - spis paczek 4 m, z ktorego strona wie, gdzie sa budynki i drzewa.
# Uzycie: przygotuj/paczki-na-strone.sh [--bez-kopii]   potem: telefon/zloz.sh i rsync na serwer.
set -euo pipefail
MAPA="$(cd "$(dirname "$0")/.." && pwd)"; V="$MAPA/dane/paczki/v1"
. "$MAPA/przygotuj/ustawienia.sh"; wymagaj KOLEJKA; ZRODLO="$KOLEJKA:paczki/gotowe/v1/"
mkdir -p "$V"
if [ "${1:-}" != "--bez-kopii" ]; then
  rsync -a --ignore-existing --include='E[0-9][0-9][0-9]N[0-9][0-9][0-9].pak' --exclude='*' "$ZRODLO" "$V/"
fi
nowe=()
while IFS= read -r -d '' p; do
  b="${p%.pak}"
  if [ ! -f "$b-16.pak" ] || [ ! -f "$b-100.pak" ] || [ "$p" -nt "$b-16.pak" ] || [ "$p" -nt "$b-100.pak" ]; then nowe+=("$p"); fi
done < <(find "$V" -maxdepth 1 -name 'E[0-9][0-9][0-9]N[0-9][0-9][0-9].pak' -print0)
if [ ${#nowe[@]} -gt 0 ]; then
  echo "poziomy dla ${#nowe[@]} paczek"
  (cd "$MAPA/przygotuj" && python3 paczka.py poziomy "${nowe[@]}")
fi
# obrysy budynkow LoD1 (E...N...-budynki.json.gz) z budynki.json kolejki - liczone na $KOLEJKA, tu idzie tylko wynik
while IFS= read -r -d '' p; do
  n="$(basename "$p" .pak)"; o="$V/$n-budynki.json.gz"
  [ -s "$o" ] && continue
  if ssh -n "$KOLEJKA" "test -s ~/paczki/praca/$n/budynki.json"; then
    echo -n "obrysy $n: "; ssh "$KOLEJKA" "python3 - ~/paczki/praca/$n/budynki.json" < "$MAPA/przygotuj/obrysy_paczki.py" > "$o.tmp" && mv "$o.tmp" "$o"
  else echo "obrysy $n: brak budynki.json na $KOLEJKA - paczka bez obrysow"; fi
done < <(find "$V" -maxdepth 1 -name 'E[0-9][0-9][0-9]N[0-9][0-9][0-9].pak' -print0)
# ile paczek ma cala kolejka (licznik pokrycia na stronie); brak polaczenia -> wartosc z poprzedniego spisu
WSZYSTKIE="$(ssh -n "$KOLEJKA" 'python3 -c "import json; print(len(json.load(open(\"paczki/kolejka/lista.json\"))))"' 2>/dev/null || true)"
python3 - "$V" "$WSZYSTKIE" <<'EOF'
import json, os, re, sys
v = sys.argv[1]
nazwy = sorted(f[:-4] for f in os.listdir(v) if re.fullmatch(r"E\d{3}N\d{3}\.pak", f))
brak = [n for n in nazwy if not all(os.path.isfile(os.path.join(v, f"{n}{s}.pak")) for s in ("-16", "-100"))]
if brak: sys.exit(f"brak poziomow -16/-100: {brak}")
sl = os.path.join(v, "lista.json")
try: wszystkie = int(sys.argv[2])
except ValueError: wszystkie = (json.load(open(sl)).get("wszystkie") if os.path.isfile(sl) else None)
json.dump({"paczki": nazwy, "bok_m": 20000, "wszystkie": wszystkie}, open(sl + ".tmp", "w"), separators=(",", ":")); os.replace(sl + ".tmp", sl)
print(f"lista.json: {len(nazwy)} paczek z {wszystkie}")
EOF
