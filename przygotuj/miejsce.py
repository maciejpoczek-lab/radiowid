# Miejsce mapy - srodek kwadratu w PUNKCIE PUBLICZNYM (rynek, plac), nigdy dom. Wybor: zmienna srodowiska MIEJSCE.
# Garwolin (domyslny) zostaje w dotychczasowych katalogach; inne miejsca dostaja przyrostek "-<nazwa>".
# Uzycie w skryptach: from miejsce import SR, NAZWA, POWIAT, przyrostek
import os
MIEJSCA = {
    "garwolin": {"sr": (51.898, 21.615), "powiat": "1403", "opis": "Garwolin, rynek"},
    "warszawa": {"sr": (52.2297, 21.0122), "powiat": "1465", "opis": "Warszawa, plac Defilad (Palac Kultury)"},
}
NAZWA = os.environ.get("MIEJSCE", "garwolin")
assert NAZWA in MIEJSCA, f"nieznane MIEJSCE={NAZWA}; znane: {', '.join(MIEJSCA)}"
SR = MIEJSCA[NAZWA]["sr"]; POWIAT = MIEJSCA[NAZWA]["powiat"]; OPIS = MIEJSCA[NAZWA]["opis"]
def przyrostek(nazwa): return nazwa if NAZWA == "garwolin" else f"{nazwa}-{NAZWA}"
