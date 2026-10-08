#!/usr/bin/env python3
# Podklad orientacyjny strony poziomow (docs/projekt-paczek-20km.md §7): drogi, tory, rzeki, wody, nazwy miejscowosci i ulic
# dla pasu paczek + margines, oraz adresy do wyszukiwarki w telefonie (wpisany adres nigdzie nie wychodzi).
# Zrodla (GUGiK, dane otwarte, bezplatnie), per powiat w dane/gugik-wektor-pas/:
#   {TERYT}_GML.zip - BDOT10k schemat 2021 (opendata.geoportal.gov.pl/bdot10k/schemat2021/{woj}/{TERYT}_GML.zip):
#     OT_SKJZ_L jezdnie, OT_SKTR_L tory, OT_SWRS_L rzeki, OT_PTWP_A wody, OT_ADMS_P miejscowosci (nazwa, rodzaj, mieszkancy)
#   {TERYT}_PRG.zip - PRG (opendata.geoportal.gov.pl/prg/adresy/PunktyAdresowe/{woj}/{TERYT}.zip): ulice, punkty adresowe
# Powiaty pasa ustalone ULDK GetCountyByXY po siatce 5 km (2026-10-07): 0611 0616 1403 1406 1407 1412 1417 1418 1426.
# Wyjscie (uklad strony 2180: x = E - E0, y = N - N0, metry calkowite):
#   dane/mapa-pas.json.gz   - linie w dwoch szczegolowosciach: pelna (punkty co >= 2 m) i ogolna (>= 30 m, tylko wazne obiekty)
#   dane/adresy-pas.json.gz - ulice_nazwy + adresy [k, numer, x, y], wczytywane dopiero przy pierwszym wyszukiwaniu
# Uzycie: python3 mapa_pasa.py [E_od N_od E_do N_do km] [margines_km=3]   (domyslnie pas E660N440 + E680N440)
import glob, gzip, io, json, os, re, struct, sys, zipfile
import xml.etree.ElementTree as ET
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); MAPA = os.path.dirname(HERE)
D = os.path.expanduser("~/dev/showreel-2/dane/gugik-wektor-pas")
A = sys.argv[1:]
E_OD, N_OD, E_DO, N_DO = (float(v) * 1000 for v in (A[:4] if len(A) >= 4 else (660, 440, 700, 460)))
MAR = float(A[4]) * 1000 if len(A) >= 5 else 3000.0
E0, N0 = 679860, 451200                                    # = przygotuj/uklad.py przy UKLAD=2180 (rynek Garwolina)
X0, X1, Y0, Y1 = E_OD - MAR - E0, E_DO + MAR - E0, N_OD - MAR - N0, N_DO + MAR - N0

def w_ramce(x, y): return (x >= X0) & (x <= X1) & (y >= Y0) & (y <= Y1)

def uprosc(pk, tol):                                       # punkty (E, N) -> plaska lista int m w ukladzie strony; odrzuca punkty blizej niz tol
    x, y = pk[:, 0] - E0, pk[:, 1] - N0
    if not w_ramce(x, y).any(): return None
    out, ost = [], None
    for k in range(len(x)):
        a, b = x[k], y[k]
        if ost is None or k == len(x) - 1 or (a - ost[0]) ** 2 + (b - ost[1]) ** 2 >= tol * tol: out += [int(round(a)), int(round(b))]; ost = (a, b)
    return out if len(out) >= 4 else None

def dlugosc(l): a = np.array(l, float).reshape(-1, 2); return float(np.hypot(*np.diff(a, axis=0).T).sum())
def pole(l): a = np.array(l, float).reshape(-1, 2); return abs(float(np.dot(a[:-1, 0], a[1:, 1]) - np.dot(a[1:, 0], a[:-1, 1]))) / 2

def gml(z, cecha):                                         # (atrybuty, [posList jako (E, N)]) z warstwy BDOT10k w zipie
    nazwy = [n for n in z.namelist() if n.endswith(f"__{cecha}.xml")]
    if not nazwy: return
    with z.open(nazwy[0]) as f:
        for _, el in ET.iterparse(f):
            if el.tag.endswith("}" + cecha):
                atr = {c.tag.split("}")[1]: (c.text or "").strip() for c in el if len(c) == 0}
                geo = [np.array(p.text.split(), float).reshape(-1, 2) for p in el.iter() if p.tag.endswith("}posList") or p.tag.endswith("}pos")]
                yield atr, geo; el.clear()

def dbf(b):                                                # rekordy DBF (pola tekstowe) z bajtow
    n, hl, rl = struct.unpack("<IHH", b[4:12]); pola = [(b[32 + 32 * i:43 + 32 * i].split(b"\0")[0].decode(), b[48 + 32 * i]) for i in range((hl - 33) // 32)]
    for r in range(n):
        o, w = hl + r * rl + 1, {}
        for nazwa, dl in pola: w[nazwa] = b[o:o + dl].decode("utf-8", "replace").strip(); o += dl
        yield w

def shp(b):                                                # geometrie SHP: punkt -> [(E, N)], linia -> lista czesci
    o = 100
    while o < len(b):
        _, dl = struct.unpack(">II", b[o:o + 8]); typ = struct.unpack("<i", b[o + 8:o + 12])[0]; s = o + 8
        if typ in (1, 11, 21): yield [np.array([struct.unpack("<dd", b[s + 4:s + 20])])]
        elif typ in (3, 5, 13, 15, 23, 25):
            nc, npk = struct.unpack("<ii", b[s + 36:s + 44]); cz = list(struct.unpack(f"<{nc}i", b[s + 44:s + 44 + 4 * nc])) + [npk]
            pk = np.frombuffer(b, "<f8", 2 * npk, s + 44 + 4 * nc).reshape(-1, 2); yield [pk[cz[i]:cz[i + 1]] for i in range(nc)]
        else: yield []
        o += 8 + 2 * dl

KLASA = {"droga autostradowa": 4, "droga ekspresowa": 4, "droga główna ruchu przyśpieszonego": 4, "droga główna": 4,
         "droga zbiorcza": 3, "droga lokalna": 2, "droga dojazdowa": 1}          # reszta (wewnetrzne, inne) = 0
TOL, TOL_OGOL = 2.0, 30.0
wyn = {k: [] for k in ("jezdnie", "jezdnie_ogol", "tory", "tory_ogol", "rzeki", "rzeki_ogol", "wody", "wody_ogol", "ulice")}
msc, ulice_nazwy, adresy, idx, powiaty = {}, [], [], {}, []
for zp in sorted(glob.glob(os.path.join(D, "*_GML.zip"))):
    p = os.path.basename(zp)[:4]; powiaty.append(p); z = zipfile.ZipFile(zp)
    for atr, geo in gml(z, "OT_SKJZ_L"):
        kl = KLASA.get(atr.get("klasaDrogi"), 0)
        for pk in geo:
            l = uprosc(pk, TOL)
            if l: wyn["jezdnie"].append([kl, l])
            if l and kl >= 3: wyn["jezdnie_ogol"].append([kl, uprosc(pk, TOL_OGOL) or l])
    for atr, geo in gml(z, "OT_SKTR_L"):
        for pk in geo:
            l = uprosc(pk, TOL)
            if l: wyn["tory"].append(l); wyn["tory_ogol"].append(uprosc(pk, TOL_OGOL) or l)
    for atr, geo in gml(z, "OT_SWRS_L"):
        for pk in geo:
            l = uprosc(pk, TOL)
            if not l: continue
            wyn["rzeki"].append([atr.get("nazwa", ""), l])
            if atr.get("nazwa") and dlugosc(l) > 2000: wyn["rzeki_ogol"].append([atr["nazwa"], uprosc(pk, TOL_OGOL) or l])
    for atr, geo in gml(z, "OT_PTWP_A"):
        if not geo: continue
        l = uprosc(geo[0], TOL)                            # tylko obwod zewnetrzny
        if not l: continue
        wyn["wody"].append(l)
        if pole(l) > 50000: wyn["wody_ogol"].append(uprosc(geo[0], TOL_OGOL) or l)
    for atr, geo in gml(z, "OT_ADMS_P"):
        if not geo or not atr.get("nazwa"): continue
        x, y = geo[0][0, 0] - E0, geo[0][0, 1] - N0
        if not w_ramce(np.array([x]), np.array([y]))[0]: continue
        k = atr.get("identyfikatorSIMC") or atr["nazwa"] + f"{x:.0f}"
        msc[k] = [atr["nazwa"], atr.get("rodzaj", ""), int(atr.get("liczbaMieszkancow") or 0), int(round(x)), int(round(y))]
    zr = os.path.join(D, f"{p}_PRG.zip")
    if not os.path.exists(zr): print(f"brak PRG {p}"); continue
    q = zipfile.ZipFile(zr); naz = lambda s: next(n for n in q.namelist() if n.endswith(s))
    for rek, g in zip(dbf(q.read(naz(f"PRG_Ulice_{p}.dbf"))), shp(q.read(naz(f"PRG_Ulice_{p}.shp")))):
        for cz in g:
            l = uprosc(cz, TOL)
            if l and rek.get("NAZWA_ULC"): wyn["ulice"].append([rek["NAZWA_ULC"], l])
    for rek, g in zip(dbf(q.read(naz(f"PRG_PunktyAdresowe_{p}.dbf"))), shp(q.read(naz(f"PRG_PunktyAdresowe_{p}.shp")))):
        if not g: continue
        x, y = g[0][0, 0] - E0, g[0][0, 1] - N0
        if not (X0 + MAR <= x <= X1 - MAR and Y0 + MAR <= y <= Y1 - MAR): continue      # adresy tylko w samym pasie
        u = rek.get("NAZWA_ULC") or rek.get("NAZWA_MSC"); m = rek.get("NAZWA_MSC")
        k = idx.setdefault((u, m), len(ulice_nazwy))
        if k == len(ulice_nazwy): ulice_nazwy.append([u, m])
        adresy.append([k, rek.get("NUMER_PORZ", ""), int(round(x)), int(round(y))])
    print(f"{p}: jezdnie {len(wyn['jezdnie'])}, miejscowosci {len(msc)}, adresy {len(adresy)}", flush=True)

ZRODLO = ["Drogi, tory, rzeki, wody, miejscowości: BDOT10k, GUGiK (dane otwarte), przetworzone",
          "Ulice i punkty adresowe: PRG, GUGiK (dane otwarte), przetworzone"]
UKLAD = f"EPSG:2180 minus rynek (E0 {E0}, N0 {N0}), metry, x = wschod, y = polnoc"
def zapisz(nazwa, d):
    p = os.path.join(MAPA, "dane", nazwa); open(p, "wb").write(gzip.compress(json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode(), 9, mtime=0))
    return os.path.getsize(p) / 1e6
mb1 = zapisz("mapa-pas.json.gz", {"zrodlo": ZRODLO, "uklad": UKLAD, "ramka_m": [X0, Y0, X1, Y1], "powiaty": powiaty,
    "miejscowosci": sorted(msc.values(), key=lambda m: -m[2]), **wyn})
mb2 = zapisz("adresy-pas.json.gz", {"zrodlo": ZRODLO[1:], "uklad": UKLAD, "ulice_nazwy": ulice_nazwy, "adresy": adresy})
print({k: len(v) for k, v in wyn.items()}, f"miejscowosci {len(msc)}, adresy {len(adresy)}; mapa-pas {mb1:.2f} MB, adresy-pas {mb2:.2f} MB")
