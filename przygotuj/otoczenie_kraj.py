#!/usr/bin/env python3
# Otoczenie odbiornika radia FM (ITU-R BS.412: wies / miasto / duze miasto) dla calej Polski, z gestosci zabudowy.
# Miara: punkty adresowe PRG (paczki *-adresy.json.gz, caly kraj) w promieniu R_M wokol punktu - adres = budynek z numerem.
#   gestosc < PROG_MIASTO adresow/km2                               -> 0 wies (pola, lasy, wsie; pomiar: wsie 14-39, miasta 166-739)
#   gestosc >= PROG_MIASTO i wiekszosc tych adresow w miescie >= DUZE -> 2 duze miasto
#   pozostale                                                        -> 1 miasto
# Duze miasto z liczby mieszkancow (BDOT10k, miejscowosci.json.gz), nie z gestosci: bloki maja jeden adres na wiele mieszkan,
# wiec centrum Warszawy (292/km2) wychodzi rzadsze niz rynek Garwolina (494/km2) - gestosc adresow nie odroznia skali miasta.
# Siatka KROK m w EPSG:2180; poza paczkami (zagranica, morze) 0. Wynik to klasyfikacja do oceny odbioru, nie pomiar halasu.
# Uzycie: python3 przygotuj/otoczenie_kraj.py [KATALOG_PACZEK] -> dane/kraj/otoczenie.json.gz
import base64, glob, gzip, json, os, re, sys
import numpy as np

MAPA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACZKI = sys.argv[1] if len(sys.argv) > 1 else os.path.join(MAPA, "dane", "paczki", "v1")
WYJSCIE = os.path.join(MAPA, "dane", "kraj", "otoczenie.json.gz")
KROK, R_M, PROG_MIASTO, DUZE, ZASIEG_MIASTA = 250, 1000, 120, 100000, 25000   # m, m, adresow/km2, mieszkancow, m od srodka miasta

kr = json.load(gzip.open(os.path.join(MAPA, "dane", "kraj", "miejscowosci.json.gz")))
duze = {}                                                                   # nazwa -> [(E, N)] (nazwy miast sie powtarzaja)
for nazwa, rodzaj, mieszk, E, N, *_ in kr["miejscowosci"]:
    if rodzaj == "miasto" and (mieszk or 0) >= DUZE: duze.setdefault(nazwa, []).append((E, N))

pliki = sorted(glob.glob(os.path.join(PACZKI, "E*N*-adresy.json.gz")))
rogi = [tuple(int(v) * 1000 for v in re.match(r"E(\d+)N(\d+)", os.path.basename(p)).groups()) for p in pliki]
E0, N0 = min(e for e, _ in rogi), min(n for _, n in rogi)
E1, N1 = max(e for e, _ in rogi) + 20000, max(n for _, n in rogi) + 20000
nx, ny = (E1 - E0) // KROK, (N1 - N0) // KROK
wszystkie, w_duzych = np.zeros((ny, nx), np.int32), np.zeros((ny, nx), np.int32)   # wiersz 0 = polnoc
for p in pliki:
    a = json.load(gzip.open(p)); rx, ry = a["rog"]
    xy = np.array([(rx + x, ry + y) for _, _, x, y in a["adresy"]], float).reshape(-1, 2)
    if not len(xy): continue
    msc = [a["ulice_nazwy"][u][1] for u, *_ in a["adresy"]]
    w_duzym = np.array([any((xy[k, 0] - e) ** 2 + (xy[k, 1] - n) ** 2 < ZASIEG_MIASTA ** 2 for e, n in duze.get(m, ())) for k, m in enumerate(msc)])
    j = ((xy[:, 0] - E0) // KROK).astype(int); i = ((N1 - xy[:, 1]) // KROK).astype(int)
    np.add.at(wszystkie, (i, j), 1); np.add.at(w_duzych, (i, j), w_duzym.astype(np.int32))

r = R_M // KROK                                                             # suma w kole o promieniu R_M (przesuniecia siatki)
def kolo(a):
    s = np.zeros_like(a); pad = np.pad(a, r)
    for di in range(-r, r + 1):
        for dj in range(-r, r + 1):
            if di * di + dj * dj <= r * r: s += pad[r + di:r + di + ny, r + dj:r + dj + nx]
    return s
komorek = sum(1 for di in range(-r, r + 1) for dj in range(-r, r + 1) if di * di + dj * dj <= r * r)
n, nd = kolo(wszystkie), kolo(w_duzych)
gestosc = n / (komorek * KROK * KROK / 1e6)
klasa = np.where(gestosc < PROG_MIASTO, 0, np.where(2 * nd >= n, 2, 1)).astype(np.uint8)
print(f"siatka {nx} x {ny} co {KROK} m, paczek {len(pliki)}, miast >= {DUZE}: {sum(len(v) for v in duze.values())}; "
      f"komorek wies/miasto/duze: {[(klasa == k).sum() for k in range(3)]}")
d = {"opis": "otoczenie odbiornika FM (BS.412): 0 wies, 1 miasto, 2 duze miasto; wiersz 0 = polnoc; poza Polska 0",
     "zrodlo": ["Punkty adresowe: PRG, GUGiK (dane otwarte), przetworzone", "Miejscowosci i liczba mieszkancow: BDOT10k, GUGiK (dane otwarte)"],
     "uklad": "EPSG:2180", "E0": E0, "N1": N1, "krok": KROK, "nx": nx, "ny": ny,
     "parametry": {"promien_m": R_M, "prog_miasto_adresow_km2": PROG_MIASTO, "duze_miasto_mieszkancow": DUZE},
     "klasa": base64.b64encode(klasa.tobytes()).decode()}
with open(WYJSCIE, "wb") as f: f.write(gzip.compress(json.dumps(d, separators=(",", ":")).encode(), 9, mtime=0))
print(WYJSCIE, os.path.getsize(WYJSCIE), "B")
