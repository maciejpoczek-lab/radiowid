#!/bin/bash
# Na komputerze z nocna kolejka (cron co 20 min): paczki 20 km prosto na serwer strony, bez Maca (od 2026-10-09, zastepuje paczki-rano.sh).
#   1. nowe ~/paczki/gotowe/v1/E...N....pak -> ~/paczki/strona/v1 (twarde dowiazanie; kolejka swojego katalogu nie widzi zmienionego),
#   2. poziomy -16/-100 (paczka.py poziomy) i obrysy budynkow (obrysy_paczki.py z praca/<paczka>/budynki.json),
#   3. pliki paczek na serwer, NA KONCU lista.json (strona nie siegnie po paczke, ktorej jeszcze nie ma).
# Klucz ~/.ssh/id_ed25519_radiowid na serwerze ograniczony: rrsync -wo -no-del do katalogu paczek (bez powloki, bez kasowania).
# Spis = suma spisu ze strony i paczek tutaj (paczki liczone gdzie indziej, np. Garwolin na Macu, nie wypadaja).
# Instalacja: kopia do ~/paczki/kod/ razem z obrysy_paczki.py; crontab: */20 * * * * ~/paczki/kod/paczki-wyslij.sh >> ~/paczki/wyslij.log 2>&1
set -euo pipefail
DOM="$HOME/paczki"; G="$DOM/gotowe/v1"; S="$DOM/strona/v1"; PY="$DOM/venv/bin/python"
CEL="root@88.198.92.22:"; STRONA="https://radio-wid.pl"
export RSYNC_RSH="ssh -i $HOME/.ssh/id_ed25519_radiowid -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ServerAliveCountMax=4"
exec 9> "$DOM/.wyslij.lock"; flock -n 9 || exit 0
mkdir -p "$S"
for p in "$G"/E[0-9][0-9][0-9]N[0-9][0-9][0-9].pak; do [ -e "$p" ] || continue; [ -e "$S/$(basename "$p")" ] || ln "$p" "$S/"; done
nowe=()
for p in "$S"/E[0-9][0-9][0-9]N[0-9][0-9][0-9].pak; do
  [ -e "$p" ] || continue; b="${p%.pak}"
  if [ ! -f "$b-16.pak" ] || [ ! -f "$b-100.pak" ] || [ "$p" -nt "$b-16.pak" ] || [ "$p" -nt "$b-100.pak" ]; then nowe+=("$p"); fi
done
[ ${#nowe[@]} -eq 0 ] || { echo "$(date '+%F %T') poziomy dla ${#nowe[@]}"; (cd "$DOM/kod" && PACZKI_WYJSCIE="$DOM/strona" nice "$PY" paczka.py poziomy "${nowe[@]}" > /dev/null); }
for p in "$S"/E[0-9][0-9][0-9]N[0-9][0-9][0-9].pak; do
  [ -e "$p" ] || continue; n="$(basename "$p" .pak)"; o="$S/$n-budynki.json.gz"
  [ -s "$o" ] || [ ! -s "$DOM/praca/$n/budynki.json" ] || { nice "$PY" "$DOM/kod/obrysy_paczki.py" "$DOM/praca/$n/budynki.json" > "$o.tmp" && mv "$o.tmp" "$o"; }
done
zdalna="$(curl -sf --max-time 30 "$STRONA/dane/paczki/v1/lista.json?w=$(date +%s)")" || { echo "$(date '+%F %T') BLAD: brak spisu ze strony"; exit 1; }
"$PY" - "$S" "$DOM/kolejka/lista.json" "$zdalna" <<'EOF'
import json, os, re, sys
s, kol, zdalna = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
tu = {f[:-4] for f in os.listdir(s) if re.fullmatch(r"E\d{3}N\d{3}\.pak", f)
      and all(os.path.isfile(os.path.join(s, f"{f[:-4]}{x}.pak")) for x in ("-16", "-100"))}
try: wszystkie = len(json.load(open(kol)))
except (OSError, ValueError): wszystkie = zdalna.get("wszystkie")
nowa = {"paczki": sorted(tu | set(zdalna["paczki"])), "bok_m": 20000, "wszystkie": wszystkie}
p = os.path.join(s, "lista.json")
json.dump(nowa, open(p + ".tmp", "w"), separators=(",", ":")); os.replace(p + ".tmp", p)
EOF
if python3 -c 'import json,sys; a=json.load(open(sys.argv[1])); b=json.loads(sys.argv[2]); sys.exit(a==b)' "$S/lista.json" "$zdalna"; then
  rsync -rt --no-o --no-g --chmod=F644 --include='E[0-9][0-9][0-9]N[0-9][0-9][0-9]*.pak' --include='E[0-9][0-9][0-9]N[0-9][0-9][0-9]-budynki.json.gz' \
    --exclude='*' "$S/" "$CEL" || { echo "$(date '+%F %T') BLAD: rsync paczek"; exit 1; }
  rsync -t --no-o --no-g --chmod=F644 "$S/lista.json" "$CEL" || { echo "$(date '+%F %T') BLAD: rsync spisu"; exit 1; }
  echo "$(date '+%F %T') wgrane: $(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["paczki"]))' "$S/lista.json") paczek w spisie"
fi
