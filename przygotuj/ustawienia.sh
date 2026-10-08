# Ustawienia wdrozenia dla przygotuj/paczki-na-strone.sh i paczki-rano.sh.
# Wartosci tej instalacji wpisz do przygotuj/ustawienia.lokalne.sh (poza gitem), np.:
#   KOLEJKA=moj-serwer-obliczen      # host ssh, na ktorym liczy sie kolejka paczek (~/paczki)
#   SERWER=moj-serwer-www            # host ssh ze strona
#   SERWER_KATALOG=/srv/radiowid     # katalog strony na serwerze
#   STRONA=https://example.org       # adres strony (sprawdzenie curl po wgraniu)
#   WLASCICIEL=root:root             # wlasciciel plikow na serwerze po wgraniu (puste = bez chown)
# Zmienne srodowiska maja pierwszenstwo przed plikiem lokalnym.
_U="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/ustawienia.lokalne.sh"
_E_KOLEJKA="${KOLEJKA:-}" _E_SERWER="${SERWER:-}" _E_KATALOG="${SERWER_KATALOG:-}" _E_STRONA="${STRONA:-}" _E_WL="${WLASCICIEL-__brak__}"
[ -f "$_U" ] && . "$_U"
KOLEJKA="${_E_KOLEJKA:-${KOLEJKA:-}}"; SERWER="${_E_SERWER:-${SERWER:-}}"
SERWER_KATALOG="${_E_KATALOG:-${SERWER_KATALOG:-}}"; STRONA="${_E_STRONA:-${STRONA:-}}"
[ "$_E_WL" != "__brak__" ] && WLASCICIEL="$_E_WL"; WLASCICIEL="${WLASCICIEL:-}"
wymagaj() { for v in "$@"; do [ -n "${!v}" ] || { echo "brak ustawienia $v - wpisz je do $_U" >&2; exit 2; }; done; }
