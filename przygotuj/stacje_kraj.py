#!/usr/bin/env python3
# Stacje bazowe UKE (stan 2026-09-25) z calej Polski -> mapa/dane/kraj/stacje.json.gz dla poziomy.html (4G/5G poza pasem paczek).
# Uklad jak stacje-pas.json (x = E - E0, y = N - N0, rynek Garwolina). Wysokosc anteny tylko ze stacje-pas.json (pas paczek:
# NMPT 1 m albo paczka 4 m); poza pasem brak - silnik bierze zalozenie 35 m (rejestr UKE wysokosci nie ma).
# Zapis kolumnowy (slowniki operatorow i pasm), zeby plik byl maly: stacje = [x, y, h_ant|null, [operatorzy], [pasma], adres].
# Uzycie: python3 stacje_kraj.py
import glob, gzip, json, os, re, sys
DANE = os.path.expanduser("~/dev/showreel-2/dane")
sys.path.insert(0, os.path.join(DANE, "nmpt")); sys.path.insert(0, os.path.expanduser("~/dev/showreel-2/proby/budynki"))
from puwg92 import na_2180
from uke import wiersze
HERE = os.path.dirname(os.path.abspath(__file__)); MAPA = os.path.dirname(HERE)
PAS = json.load(open(os.path.join(MAPA, "dane", "stacje-pas.json"))); E0, N0 = 679860, 451200
assert "E0 679860" in PAS["uklad"] and "N0 451200" in PAS["uklad"], "zmienil sie uklad strony"
ZNANE = {(s["lat"], s["lon"]): s["h_ant"] for s in PAS["stacje"] if s.get("h_ant") is not None}

def dms(s):
    m = re.match(r"(\d+)[NSEW](\d+)'(\d+)\"", (s or "").strip())
    return int(m[1]) + int(m[2]) / 60 + int(m[3]) / 3600 if m else None

st = {}
for p in sorted(glob.glob(os.path.join(DANE, "uke/*.xlsx"))):
    pasmo = os.path.basename(p).split("_-_")[0]
    for i, w in enumerate(wiersze(p)):
        if i == 0: continue
        lon, lat = dms(w.get("E")), dms(w.get("F"))
        if lon is None: continue
        s = st.setdefault((round(lat, 4), round(lon, 4)), {"lat": round(lat, 5), "lon": round(lon, 5), "operatorzy": set(), "pasma": set(),
                          "adres": f'{w.get("G", "")}, {w.get("H", "")}'.strip(", ")})
        s["operatorzy"].add(w.get("A", "").strip()); s["pasma"].add(pasmo)

OP = sorted({o for s in st.values() for o in s["operatorzy"] if o}); PA = sorted({p for s in st.values() for p in s["pasma"]})
iop, ipa = {o: k for k, o in enumerate(OP)}, {p: k for k, p in enumerate(PA)}
# rejestr podaje wspolrzedne w pelnych sekundach, a ten sam maszt roznych operatorow bywa zgloszony z roznica 1-2" (20-60 m):
# punkty blizej niz SKLEJ m to jedna stacja (inaczej "3 najblizsze stacje" bywaja jednym masztem)
SKLEJ = 60
siatka, wsp = {}, []
for s in st.values():
    n, e = (float(v) for v in na_2180(s["lat"], s["lon"])); x, y = e - E0, n - N0
    kx, ky = int(x // SKLEJ), int(y // SKLEJ)
    cel = next((c for i in (-1, 0, 1) for j in (-1, 0, 1) for c in siatka.get((kx + i, ky + j), ()) if (c["x"] - x) ** 2 + (c["y"] - y) ** 2 < SKLEJ ** 2), None)
    if cel is None:
        cel = {"x": x, "y": y, "h": None, "operatorzy": set(), "pasma": set(), "adres": s["adres"], "n": 0}; siatka.setdefault((kx, ky), []).append(cel); wsp.append(cel)
    cel["operatorzy"] |= s["operatorzy"]; cel["pasma"] |= s["pasma"]; cel["n"] += 1
    h = ZNANE.get((s["lat"], s["lon"]))
    if h is not None: cel["h"] = h if cel["h"] is None else max(cel["h"], h)
# stacje zgloszone jako rozebrane, a jeszcze w rejestrze (decyzja Macka 2026-10-17): operator zdjety z punktu, pusty punkt znika.
# Pasma sa wspolne dla punktu, wiec gdy zostaje inny operator, pasma zostaja w calosci.
for r in json.load(open(os.path.join(HERE, "stacje-rozebrane.json")))["stacje"]:
    traf = [c for c in wsp if (c["x"] - r["x"]) ** 2 + (c["y"] - r["y"]) ** 2 < SKLEJ ** 2 and r["operator"] in c["operatorzy"]]
    if not traf: print(f'rozebrana juz nie w rejestrze - usun wpis: {r["adres"]} ({r["operator"]})'); continue
    for c in traf: c["operatorzy"].discard(r["operator"])
    print(f'zdjeta jako rozebrana: {r["adres"]} ({r["operator"]})')
# stacje nieczynne wg BTSearch (decyzja Macka 2026-10-17): zdejmujemy operatora z punktu do BTS_PROMIEN m. Stacja z notatka
# w BTSearch zostaje - notatki mowia o stacjach tymczasowych, przeniesionych albo "sygnal z anten innego operatora".
from btsearch import nieczynne
BTS_PROMIEN = 50
bts, BTS_STAN = nieczynne(os.path.join(MAPA, "dane", "kraj", "btsearch-nieczynne.json")); zdjete = 0
for b in bts:
    if b["notatka"]: continue
    n, e = (float(v) for v in na_2180(b["lat"], b["lon"])); x, y = e - E0, n - N0
    for c in wsp:
        if (c["x"] - x) ** 2 + (c["y"] - y) ** 2 >= BTS_PROMIEN ** 2: continue
        ops = {o for o in c["operatorzy"] if o.startswith(b["operatorzy"])}
        if ops: c["operatorzy"] -= ops; zdjete += 1
print(f"BTSearch: nieczynnych {len(bts)}, zdjetych z mapy {zdjete}")
# stacje zlikwidowane wg SI2PEM (2026-10-18): jak wyzej, ale zostaje punkt, przy ktorym SI2PEM ma AKTYWNA stacje tego
# samego operatora (przeniesienie anten, nowa instalacja w tym samym miejscu)
from si2pem import stacje as si2pem_stacje
zlik, akt, SI_STAN = si2pem_stacje(os.path.join(MAPA, "dane", "kraj", "si2pem-stacje.json")); zdjete = 0
def _xy(lon, lat): n, e = (float(v) for v in na_2180(lat, lon)); return e - E0, n - N0
okolica = {(round(s[1], 2), round(s[0], 2)) for s in zlik}
akt_xy = [(*_xy(s[0], s[1]), s[2]) for s in akt if any((round(s[1], 2) + i, round(s[0], 2) + j) in okolica for i in (-0.01, 0, 0.01) for j in (-0.01, 0, 0.01))]
siatka_w = {}
for c in wsp: siatka_w.setdefault((int(c["x"] // BTS_PROMIEN), int(c["y"] // BTS_PROMIEN)), []).append(c)
for s in zlik:
    x, y = _xy(s[0], s[1])
    if any(o == s[2] and (ax - x) ** 2 + (ay - y) ** 2 < BTS_PROMIEN ** 2 for ax, ay, o in akt_xy): continue
    for c in (c for i in (-1, 0, 1) for j in (-1, 0, 1) for c in siatka_w.get((int(x // BTS_PROMIEN) + i, int(y // BTS_PROMIEN) + j), ())):
        if (c["x"] - x) ** 2 + (c["y"] - y) ** 2 >= BTS_PROMIEN ** 2: continue
        ops = {o for o in c["operatorzy"] if o.startswith(s[2])}
        if ops: c["operatorzy"] -= ops; zdjete += 1
print(f"SI2PEM: zlikwidowanych {len(zlik)}, zdjetych z mapy {zdjete}")
DOPISEK = (f"; bez stacji nieczynnych wg BTSearch (btsearch.pl), stan {BTS_STAN}" if BTS_STAN else "") + \
          (f"; bez stacji zlikwidowanych wg SI2PEM (si2pem.gov.pl), stan {SI_STAN}" if SI_STAN else "")
wsp = [c for c in wsp if any(c["operatorzy"])]
out = [[round(c["x"]), round(c["y"]), c["h"], sorted(iop[o] for o in c["operatorzy"] if o), sorted(ipa[p] for p in c["pasma"]), c["adres"]] for c in wsp]
zh = sum(c["h"] is not None for c in wsp)
out.sort(key=lambda r: (r[1], r[0]))
os.makedirs(os.path.join(MAPA, "dane", "kraj"), exist_ok=True)
cel = os.path.join(MAPA, "dane", "kraj", "stacje.json.gz")
with gzip.open(cel, "wt", encoding="utf-8", compresslevel=9) as f:
    json.dump({"zrodlo": "UKE rejestr stacji bazowych, stan 2026-09-25 (bez wysokosci anten, azymutow i mocy)" + DOPISEK, "uklad": "EPSG:2180 minus E0 679860, N0 451200 (rynek Garwolina); azymut geograficzny = siatki + zbieznosc poludnikow w punkcie (liczy strona)",
               "kolumny": ["x", "y", "h_ant", "operatorzy", "pasma", "adres"], "operatorzy": OP, "pasma": PA, "stacje": out},
              f, ensure_ascii=False, separators=(",", ":"))
print(f"punktow rejestru: {len(st)}; stacji po sklejeniu < {SKLEJ} m: {len(out)}; z wysokoscia anteny (pas): {zh}; plik {os.path.getsize(cel) / 1e6:.2f} MB")
