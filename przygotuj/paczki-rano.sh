#!/bin/bash
# Co rano (LaunchAgent wg przygotuj/radiowid-paczki.plist, 07:45): paczki policzone w nocy -> strona. Ustawienia: przygotuj/ustawienia.sh.
# Wgrywa WYLACZNIE dane paczek (E...N....pak, -16, -100, -budynki.json.gz, na koncu lista.json) - nigdy strony: zmiana
# poziomy.html w toku innej sesji nie moze wyjsc na serwer bez zgody. Bez --delete. Nowych paczek brak -> nic nie wysyla.
# Log: ~/Library/Logs/radiowid-paczki.log. Reczne: przygotuj/paczki-rano.sh
set -uo pipefail
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"
MAPA="$(cd "$(dirname "$0")/.." && pwd)"; V="$MAPA/dane/paczki/v1"
. "$MAPA/przygotuj/ustawienia.sh"; wymagaj KOLEJKA SERWER SERWER_KATALOG STRONA
CEL="$SERWER:$SERWER_KATALOG/dane/paczki/v1/"
ZAMEK="$MAPA/.paczki-rano.lock"; mkdir "$ZAMEK" 2>/dev/null || { echo "$(date '+%F %T') juz dziala (zamek $ZAMEK)"; exit 0; }; trap 'rmdir "$ZAMEK"' EXIT
echo "=== $(date '+%F %T') start"
# Mac budzi sie o 07:45 bez gotowej sieci (Tailscale): czekaj na kolejke (20 prob co 30 s, do ~15 min) zamiast padac; zerwane polaczenie rsync nie wisi (2026-10-09: 33 min)
export RSYNC_RSH="ssh -o ConnectTimeout=20 -o ServerAliveInterval=15 -o ServerAliveCountMax=4"
for i in $(seq 20); do ssh -n -o ConnectTimeout=20 "$KOLEJKA" true 2>/dev/null && break; [ "$i" = 20 ] && { echo "$(date '+%F %T') BLAD: $KOLEJKA nie odpowiada po 20 probach"; exit 1; }; sleep 30; done
przed="$(cat "$V/lista.json" 2>/dev/null)"
if ! "$MAPA/przygotuj/paczki-na-strone.sh"; then echo "$(date '+%F %T') BLAD: paczki-na-strone.sh"; exit 1; fi
po="$(cat "$V/lista.json")"
zdalna="$(ssh -n "$SERWER" "cat $SERWER_KATALOG/dane/paczki/v1/lista.json" 2>/dev/null)"
if [ "$po" = "$zdalna" ]; then echo "$(date '+%F %T') bez nowych paczek (lokalnie: $( [ "$przed" = "$po" ] && echo bez zmian || echo zmiana))"; exit 0; fi
# najpierw pliki paczek, spis na koncu - strona nie siegnie po paczke, ktorej jeszcze nie ma na serwerze
if ! rsync -a --include='E[0-9][0-9][0-9]N[0-9][0-9][0-9].pak' --include='E[0-9][0-9][0-9]N[0-9][0-9][0-9]-16.pak' \
     --include='E[0-9][0-9][0-9]N[0-9][0-9][0-9]-100.pak' --include='E[0-9][0-9][0-9]N[0-9][0-9][0-9]-budynki.json.gz' --exclude='*' "$V/" "$CEL"; then
  echo "$(date '+%F %T') BLAD: rsync paczek"; exit 1; fi
rsync -a "$V/lista.json" "$CEL" && { [ -z "$WLASCICIEL" ] || ssh -n "$SERWER" "chown -R $WLASCICIEL $SERWER_KATALOG/dane/paczki"; } || { echo "$(date '+%F %T') BLAD: lista/chown"; exit 1; }
n="$(python3 -c 'import json,sys;print(len(json.load(sys.stdin)["paczki"]))' <<<"$po")"
kod="$(curl -s -o /dev/null -w '%{http_code}' $STRONA/dane/paczki/v1/lista.json)"
echo "$(date '+%F %T') wgrane: $n paczek w spisie, lista.json -> $kod"
