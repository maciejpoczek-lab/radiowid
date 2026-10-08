#!/usr/bin/env python3
# Nadajniki radia i TV calej Polski (docs/projekt-paczek-20km.md §8.4) -> kraj/nadajniki.json(.gz), jeden plik dla wszystkich.
# Zrodlo: wykaz pozwolen radiowych UKE, stan 2026-09-18 (pliki *_r, jak rtv.py): UKF FM, T-DAB, naziemna TV cyfrowa - CALY KRAJ, bez promienia.
# Filtry jak rtv.py (bez tymczasowych, wygaslych, bez ERP / wysokosci anteny) i fm.mjs (to samo miejsce + czestotliwosc -> najpozniej wazne;
# grupa = miejsce do ~100 m + wysokosc anteny). Wspolrzedne: EPSG:2180, bezwzglednie (e = wschod, n = polnoc) - strona odejmuje swoje E0/N0.
# Wysokosc efektywna (ITU-R P.1546 §3): heff[k] = antena + grunt pod masztem - sredni teren 3-15 km od masztu w kierunku k*10 st.
# W OSIACH SIATKI 2180 (jak azymut w silniku), profil co 100 m, srednia trapezami, teren = NMT 100 m kraju (teren_kraj.py, teren100.npy).
# Poza Polska (zagranica, morze) NMT nie ma - srednia z punktow, ktore sa; heff_pokrycie = najmniejszy udzial punktow z danymi w sektorach.
# Sektor bez zadnego punktu -> null (silnik bierze wtedy wysokosc anteny). Nadajnikow zagranicznych w wykazie UKE nie ma.
# Kazdy wynik to SYMULACJA.
# Uzycie: python3 rtv_kraj.py KATALOG_CSV_UKE [rtv-2180.json do kontroli heff w strone rynku]
import csv, datetime, gzip, json, math, os, re, sys
import numpy as np
sys.path.insert(0, os.path.expanduser("~/dev/showreel-2/dane/nmpt")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from puwg92 import na_2180

HERE = os.path.dirname(os.path.abspath(__file__)); MAPA = os.path.dirname(HERE)
KRAJ = os.environ.get("KRAJ_WYJSCIE") or os.path.join(MAPA, "dane", "kraj")
E0, N0, BOK, KOM = 100_000, 100_000, 800_000, 100           # siatka teren100.npy (teren_kraj.py)
DZIS = datetime.date(2026, 10, 7)
POLA = {"fm": dict(mhz="F [MHz]", program="Program", lon="Dł. geogr.", lat="Sz. geogr.", hter="H ter.", hant="H ant.", pol="Pol.", char="Char.", system="Syst."),
        "dab": dict(mhz="Czestotliwość środkowa [MHz]", program="Nazwa multipleksu", kanal="Kanał/blok częstotliwościowy", lon="Dł.geogr. (WGS84)",
                    lat="Sz.geogr. (WGS84)", hter="Wysokość lokalizacji [m. npm]", hant="Wysokość anteny [m. npt]", pol="Polaryzacja", char="Charakterystyka", system="System emisji")}
POLA["dvbt"] = POLA["dab"]
PLIKI = [("fm", "pozwolenie_ukf_r_2026-09-18.csv", "utf-8-sig"), ("dab", "pozwolenia_dab_r_2026-09-18.csv", "cp1250"), ("dvbt", "pozwolenia_ntc_r_2026-09-18.csv", "cp1250")]

def dms(s):                                                  # 21E00'22" ; litera bez znaczenia (literowki UKE)
    m = re.match(r"\s*(\d+)[NSEW](\d+)'(\d+)", s or ""); return int(m[1]) + int(m[2]) / 60 + int(m[3]) / 3600 if m else None
liczba = lambda s: float(s.replace(",", ".")) if s and s.strip() not in ("", "-") else None
def data(s):
    for f in ("%Y-%m-%d", "%d.%m.%Y"):
        try: return datetime.datetime.strptime((s or "").strip(), f).date()
        except ValueError: pass

# --- pozwolenia -> jednoznaczne nadajniki ---
pominiete, jedn = {}, {}
def pomin(typ, co): pominiete[f"{typ}: {co}"] = pominiete.get(f"{typ}: {co}", 0) + 1
for typ, plik, kod in PLIKI:
    p = POLA[typ]
    for w in csv.DictReader(open(os.path.join(sys.argv[1], plik), encoding=kod), delimiter=";"):
        lat, lon, wazn = dms(w[p["lat"]]), dms(w[p["lon"]]), data(w["Ważny do"])
        if lat is None or lon is None: pomin(typ, "bez wspolrzednych"); continue
        if re.search(r"eksperym|okazjonal|czasow", w["Status"], re.I): pomin(typ, "tymczasowe"); continue
        if wazn and wazn < DZIS: pomin(typ, "wygasle"); continue
        erp, hant, mhz = liczba(w["ERP[kW]"]), liczba(w[p["hant"]]), liczba(w[p["mhz"]])
        if not erp or not hant or not mhz: pomin(typ, "bez ERP / H ant / czestotliwosci"); continue
        s = {"typ": typ, "kanal": (w.get(p.get("kanal", "")) or "").strip(), "system": w[p["system"]].strip(), "mhz": mhz,
             "program": w[p["program"]].strip(), "stacja": w["Nazwa stacji"].strip(), "erp_kw": erp, "pol": w[p["pol"]].strip(),
             "tlumienie_db": [liczba(w.get(f"{a}°")) or 0.0 for a in range(0, 360, 10)], "waznosc": wazn.isoformat() if wazn else "",
             "_lat": lat, "_lon": lon, "_hant": hant, "_hter": liczba(w[p["hter"]])}
        k = (typ, round(lat, 3), round(lon, 3), round(mhz, 1)); o = jedn.get(k)
        if o is None or s["waznosc"] > o["waznosc"]:
            if o is not None: pomin(typ, "powtorzone (starsze pozwolenie)")
            jedn[k] = s
        else: pomin(typ, "powtorzone (starsze pozwolenie)")

# --- grupy: miejsce + wysokosc anteny ---
T = np.load(os.path.join(KRAJ, "teren100.npy"), mmap_mode="r")
def teren(e, n):                                             # komorka 100 m pod punktem (NaN poza Polska)
    i, j = np.floor((N0 + BOK - np.asarray(n)) / KOM).astype(int), np.floor((np.asarray(e) - E0) / KOM).astype(int)
    ok = (i >= 0) & (i < T.shape[0]) & (j >= 0) & (j < T.shape[1]); w = np.full(np.shape(i), np.nan, np.float32)
    w[ok] = T[i[ok], j[ok]]; return w
R = np.arange(3000, 15001, 100.0)
def heff_sektory(e, n, z):
    h, pokr = [], []
    for k in range(36):
        a = math.radians(10 * k); t = teren(e + R * math.sin(a), n + R * math.cos(a)); m = ~np.isnan(t); pokr.append(m.mean())
        if not m.any(): h.append(None); continue
        r, v = R[m], t[m]
        sr = float(v[0]) if len(v) == 1 else float(np.sum((v[1:] + v[:-1]) / 2 * np.diff(r)) / (r[-1] - r[0]))
        h.append(round(z - sr))
    return h, round(float(min(pokr)), 2)

grupy = {}
for s in sorted(jedn.values(), key=lambda s: (s["_lat"], s["_lon"], s["_hant"], s["typ"], s["mhz"])):
    k = (round(s["_lat"], 3), round(s["_lon"], 3), s["_hant"])
    if k not in grupy:
        pn, pe = na_2180(s["_lat"], s["_lon"]); pn2, pe2 = na_2180(s["_lat"] + 0.01, s["_lon"])
        grunt = float(teren(pe, pn)); zr = "NMT 100 m"
        if math.isnan(grunt): grunt, zr = (s["_hter"] or 0.0), "UKE (poza NMT)"
        grupy[k] = {"e": round(float(pe), 1), "n": round(float(pn), 1), "hant": s["_hant"], "hter_uke": s["_hter"], "grunt": round(grunt, 1),
                    "grunt_zrodlo": zr, "z": round(grunt + s["_hant"], 1),
                    "zbieznosc": round(-math.degrees(math.atan2(float(pe2 - pe), float(pn2 - pn))), 4), "programy": []}
    grupy[k]["programy"].append({kk: v for kk, v in s.items() if not kk.startswith("_")})
G = list(grupy.values())
for i, g in enumerate(G):
    g["id"] = i; g["heff"], g["heff_pokrycie"] = heff_sektory(g["e"], g["n"], g["z"])

meta = {"grupy": G, "uklad": "EPSG:2180, e/n bezwzglednie; heff[k] = kierunek k*10 st. w osiach siatki 2180 (od polnocy siatki, zgodnie z ruchem wskazowek)",
        "uwaga": "SYMULACJA, nie pomiar; pole liczy strona wg ITU-R P.1546-6 (silnik/p1546.js); tylko polskie nadajniki (wykaz UKE)",
        "zrodla": ["Nadajniki FM, DAB+, DVB-T: UKE, wykaz pozwolen radiowych, stan 2026-09-18, przetworzone",
                   "Teren do wysokosci efektywnej: NMT 100 m GUGiK, przetworzone"]}
os.makedirs(KRAJ, exist_ok=True); tekst = json.dumps({"meta": meta}, ensure_ascii=False, separators=(",", ":")).encode()
open(os.path.join(KRAJ, "nadajniki.json"), "wb").write(tekst); gz = gzip.compress(tekst, 9, mtime=0)
open(os.path.join(KRAJ, "nadajniki.json.gz"), "wb").write(gz)
prog = sum(len(g["programy"]) for g in G)
print(f"grupy {len(G)}, programy {prog} (" + ", ".join(f"{t} {sum(p['typ'] == t for g in G for p in g['programy'])}" for t in ("fm", "dab", "dvbt"))
      + f"), plik {len(tekst) / 1e3:.0f} kB, gzip {len(gz) / 1e3:.0f} kB")
print("grunt spoza NMT:", sum(g["grunt_zrodlo"] != "NMT 100 m" for g in G), "| heff_pokrycie < 0,5:", sum(g["heff_pokrycie"] < 0.5 for g in G),
      "| sektory bez terenu:", sum(h is None for g in G for h in g["heff"]))
print("pominiete:", dict(sorted(pominiete.items())))

# --- kontrola: sektor w strone rynku Garwolina vs heff z rtv-2180.json (fm.mjs: T 30 m / Copernicus; tylko grupy >= 15 km) ---
if len(sys.argv) > 2:
    stare = json.load(open(sys.argv[2]))["meta"]["grupy"]; RE, RN = 679860, 451200; d = []
    for s in stare:
        se, sn = RE + s["x"], RN + s["y"]; dkm = math.hypot(s["x"], s["y"]) / 1000
        if dkm < 15: continue
        g = min(G, key=lambda g: math.hypot(g["e"] - se, g["n"] - sn) + (0 if g["hant"] == s["hant"] else 1e6))
        if math.hypot(g["e"] - se, g["n"] - sn) > 300 or g["hant"] != s["hant"]: print("  bez pary:", s["programy"][0]["stacja"]); continue
        az = (math.degrees(math.atan2(RE - g["e"], RN - g["n"])) + 360) % 360; k0 = int(az // 10); f = az / 10 - k0
        a, b = g["heff"][k0], g["heff"][(k0 + 1) % 36]
        if a is None or b is None: continue
        d.append((a + (b - a) * f - s["heff"], s["programy"][0]["stacja"], s["heff"], dkm))
    r = np.array([x[0] for x in d]); ar = np.abs(r)
    print(f"kontrola heff w strone rynku ({len(d)} grup >= 15 km): nowe - stare mediana {np.median(r):+.1f} m, |d| 50% {np.percentile(ar, 50):.1f}, "
          f"90% {np.percentile(ar, 90):.1f}, max {ar.max():.1f} m")
    for x in sorted(d, key=lambda x: -abs(x[0]))[:5]: print(f"  {x[1][:24]:24s} {x[3]:5.1f} km  stare {x[2]:5d}  roznica {x[0]:+6.1f} m")
