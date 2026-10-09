#!/bin/bash
# Wgrywa strone (_telefon/ z telefon/zloz.sh) na serwer. Bez argumentu: tylko pokazuje roznice; --wyslij: wysyla.
# dane/paczki/ POMINIETE i chronione przed --delete: paczki 20 km wysyla sam komputer z kolejka (przygotuj/paczki-wyslij.sh),
# wiec lokalna kopia na Macu bywa starsza od serwera - bez wykluczenia wgranie strony skasowaloby nocne paczki.
set -euo pipefail
M="$(cd "$(dirname "$0")/.." && pwd)"
. "$M/przygotuj/ustawienia.sh"; wymagaj SERWER SERWER_KATALOG
[ -f "$M/_telefon/index.html" ] || { echo "brak _telefon/ - najpierw telefon/zloz.sh" >&2; exit 1; }
OPCJE=(-c --delete --exclude=/dane/paczki/)
if [ "${1:-}" != "--wyslij" ]; then
  rsync -an "${OPCJE[@]}" -i "$M/_telefon/" "$SERWER:$SERWER_KATALOG/" | grep -vE '^\.[fd]\.\.[.t]\.og\.' || echo "bez roznic"
  echo "(podglad; wyslanie: telefon/wgraj.sh --wyslij)"; exit 0
fi
rsync -a "${OPCJE[@]}" "$M/_telefon/" "$SERWER:$SERWER_KATALOG/"
[ -z "${WLASCICIEL:-}" ] || ssh -n "$SERWER" "chown -R $WLASCICIEL $SERWER_KATALOG"
echo "wgrane: $(date '+%F %T')"
