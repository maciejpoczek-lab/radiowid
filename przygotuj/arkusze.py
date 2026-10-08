#!/usr/bin/env python3
# Arkusze NMT / NMPT GUGiK dla JEDNEJ paczki 20 km (siatka krajowa EPSG:2180, docs/projekt-paczek-20km.md) -> kafle 1 km po 1 m.
# Bez WCS: lista adresow ze skorowidza ArcGIS REST (SkorowidzeFOTOMF/MapServer/4), pliki .asc z opendata.geoportal.gov.pl.
# Zapytania dotycza wylacznie kwadratu siatki krajowej (wyrownanego do 20 km) - nie mowia nic o zadnym punkcie w srodku.
# Wybor arkuszy (zachlannie, siatka pokrycia 10 m): EVRF2007 przed KRON86, w obrebie ukladu najnowszy rocznik, przy remisie
#   .asc przed .xyz (zip), gestsza siatka; arkusz bierzemy, gdy dokrywa >= 1 ha. NMPT 0,5 m -> srednia 2 x 2 do 1 m. KRON86 -> poprawka wysokosci
#   z mediany roznicy na zakladce z juz wpisanymi danymi EVRF2007 (bez zakladki: arkusz pominiety, ostrzezenie).
# Pobieranie grzeczne: jeden plik naraz, pauza, wznawianie (stan.json); arkusz .asc kasowany zaraz po przeliczeniu.
# Wyjscie: <katalog>/kafle/{nmt,nmpt}/{e}_{n}.npy (float32 1000 x 1000, wiersz 0 = polnoc, NaN = brak), lista.json, stan.json.
# Uzycie: python3 arkusze.py E_KM N_KM KATALOG [--lista]      np. 660 440 ~/paczki/praca/E660N440
import json, os, sys, time, urllib.parse, urllib.request
import numpy as np
from PIL import Image, ImageDraw

E_KM, N_KM, KAT = int(sys.argv[1]), int(sys.argv[2]), os.path.expanduser(sys.argv[3])
TYLKO_LISTA = "--lista" in sys.argv
X0, Y0, BOK = E_KM * 1000, N_KM * 1000, 20000
SKOR = "https://mapy.geoportal.gov.pl/gprest/services/SkorowidzeFOTOMF/MapServer/4/query"
UA = {"User-Agent": "showreel-mapa-swiatla/1.0 (pobieranie arkuszy NMT/NMPT po jednym, z pauza)"}
PAUZA, MIN_HA = 1.0, 1.0
os.makedirs(KAT, exist_ok=True)

def pobierz_json(params):
    u = SKOR + "?" + urllib.parse.urlencode(params)
    for p in range(5):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        except Exception as e: print("skorowidz, ponawiam:", e); time.sleep(5 * (p + 1))
    raise SystemExit("skorowidz nie odpowiada")

# --- 1. skorowidz: kwadrat paczki w kawalkach 5 km (limit 1000 rekordow na zapytanie) ---
def lista():
    rek = {}
    for dx in range(0, BOK, 5000):
        for dy in range(0, BOK, 5000):
            g = {"xmin": X0 + dx, "ymin": Y0 + dy, "xmax": X0 + dx + 5000, "ymax": Y0 + dy + 5000, "spatialReference": {"wkid": 2180}}
            d = pobierz_json({"geometry": json.dumps(g), "geometryType": "esriGeometryEnvelope", "spatialRel": "esriSpatialRelIntersects",
                              "inSR": 2180, "outSR": 2180, "f": "json", "returnGeometry": "true",
                              "where": "asortyment in ('NMT','NMPT') and format in ('ARC/INFO ASCII GRID','ASCII XYZ GRID') and char_przestrz in ('1.00 m','0.50 m')",
                              "outFields": "godlo,asortyment,char_przestrz,uklad_h,akt_rok,akt_data,url_do_pobrania,czy_ark_wypelniony,format"})
            assert not d.get("exceededTransferLimit"), "skorowidz uciął wynik - zmniejsz kawalek"
            for f in d.get("features", []):
                a = f["attributes"]; a["rings"] = f["geometry"]["rings"]; rek[a["url_do_pobrania"]] = a
            time.sleep(PAUZA)
    wybor = {}
    for prod in ("NMT", "NMPT"):
        # godla PL-1992 zaczynaja sie litera (N-34-138-B-a-2-4); cyfrowe (7.175.19.14) to arkusze w ukladzie PL-2000 (xllcorner 7 488 800) -
        # bez przeliczenia trafialyby poza paczke, a i tak zajmowalyby pokrycie (E620N480, 2026-10-08: 47 arkuszy NMT, ok. 47 km2 dziury)
        kand = [a for a in rek.values() if a["asortyment"] == prod and a["godlo"][:1].isalpha()]
        kand.sort(key=lambda a: (a["uklad_h"] != "PL-EVRF2007-NH", -int(a["akt_rok"] or 0), -(a["akt_data"] or 0), a["format"] != "ARC/INFO ASCII GRID", a["char_przestrz"] != "0.50 m"))
        maska = np.zeros((BOK // 10, BOK // 10), bool); wyb = []
        for a in kand:
            im = Image.new("1", maska.shape[::-1], 0); dr = ImageDraw.Draw(im)
            for r in a["rings"]: dr.polygon([((x - X0) / 10, (Y0 + BOK - y) / 10) for x, y in r], fill=1)
            m = np.asarray(im, bool); nowe = m & ~maska
            if nowe.sum() * 100 / 1e4 >= MIN_HA:
                maska |= m; wyb.append({k: a[k] for k in a if k != "rings"} | {"dokrywa_ha": round(nowe.sum() / 100, 1)})
        wybor[prod] = wyb
        print(f"{prod}: kandydatow {len(kand)}, wybranych {len(wyb)}, pokrycie {maska.mean() * 100:.2f}% "
              f"(uklady: {sorted({(w['uklad_h'], w['char_przestrz'], w['akt_rok']) for w in wyb})})")
    json.dump(wybor, open(os.path.join(KAT, "lista.json"), "w"), indent=1, ensure_ascii=False)
    return wybor

# --- 2. arkusz .asc -> tablica 1 m ---
def czytaj_xyz(f):                                   # "x y z" w wierszach, siatka regularna; os wschodnia rozpoznana po zakresie paczki
    t = f.read(); t = t[3:] if t.startswith(b"\xef\xbb\xbf") else t     # BOM UTF-8 na poczatku czesci plikow .xyz (Warszawa, 2026-10-08)
    v = np.array(t.split(), dtype=np.float64).reshape(-1, 3)
    a_, b_ = v[:, 0], v[:, 1]
    if not (X0 - 5000 <= np.median(a_) <= X0 + BOK + 5000): a_, b_ = b_, a_
    c = np.median(np.diff(np.unique(a_))); xs, ys = np.round(a_ / c).astype(np.int64), np.round(b_ / c).astype(np.int64)
    t = np.full((ys.max() - ys.min() + 1, xs.max() - xs.min() + 1), np.nan, np.float32); t[ys.max() - ys, xs - xs.min()] = v[:, 2]
    t[t == -9999] = np.nan
    return {"ncols": t.shape[1], "nrows": t.shape[0], "xllcenter": xs.min() * c, "yllcenter": ys.min() * c, "cellsize": c}, t

def czytaj_asc(sciezka):
    if sciezka.endswith(".zip"):
        import zipfile; z = zipfile.ZipFile(sciezka); n = [m for m in z.namelist() if m.lower().endswith((".xyz", ".asc", ".txt"))][0]
        f = z.open(n); nag, a = czytaj_xyz(f) if n.lower().endswith((".xyz", ".txt")) else (None, None)
        if nag is None: raise SystemExit("asc w zipie - nieobslugiwane: " + n)
        return siatka(nag, a)
    with open(sciezka, "rb") as f:
        nag = {}
        while True:
            poz = f.tell(); l = f.readline().split()
            if not l or not l[0][:1].isalpha(): f.seek(poz); break
            nag[l[0].decode().lower()] = float(l[1])
        a = np.array(f.read().split(), dtype=np.float32); nc, nr = int(nag["ncols"]), int(nag["nrows"])
        if a.size != nr * nc and a.size % nc == 0:      # wadliwy naglowek GUGiK (N-33-131-C-c-2-3, 2024: 2372 wierszy, naglowek 2323) - gorna krawedz
            ext = a.size // nc - nr                      # z naglowka jest dobra, nadmiarowe wiersze sa na dole (zgodnosc z obrysem skorowidza 99,92%
            k = "yllcorner" if "yllcorner" in nag else "yllcenter"   # wobec 96,6% przy dole z naglowka; 2026-10-08)
            nag[k] -= ext * nag["cellsize"]; nag["nrows"] = nr = a.size // nc
            print(f"OSTRZEZENIE: {os.path.basename(sciezka)} ma {ext:+d} wierszy wobec naglowka - gorna krawedz z naglowka, dol przesuniety", flush=True)
        a = a.reshape(nr, nc)
    a[a == nag.get("nodata_value", -9999)] = np.nan
    return siatka(nag, a)

def siatka(nag, a):                                  # naglowek + tablica -> lewy dolny rog na pelnych metrach, 1 m
    c = nag["cellsize"]
    x0 = nag["xllcorner"] if "xllcorner" in nag else nag["xllcenter"] - c / 2
    y0 = nag["yllcorner"] if "yllcorner" in nag else nag["yllcenter"] - c / 2
    if abs(c - 1.0) < 1e-6 and abs(x0 % 1 - 0.5) < 1e-6 and abs(y0 % 1 - 0.5) < 1e-6:
        x0, y0 = x0 - 0.5, y0 + 0.5                      # arkusze 1 m: srodki na pelnych metrach -> pol komorki na zachod i polnoc, tak jak
                                                         # WCS GUGiK (zmierzone 2026-10-07: 0,000 m roznicy wobec mozaiki WCS Garwolina)
    if abs(c - 0.5) < 1e-6:                              # 0,5 m -> 1 m na pelnych metrach (srednia z czterech, bez brakow)
        gora = y0 + a.shape[0] * c; x1m, g1m = np.ceil(x0), np.floor(gora)
        jo, io = int(round((x1m - x0) / c)), int(round((gora - g1m) / c))
        a = a[io:, jo:]; h, w = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2; a = a[:h, :w]
        with np.errstate(all="ignore"):
            import warnings; warnings.simplefilter("ignore", RuntimeWarning)
            a = np.nanmean(a.reshape(h // 2, 2, w // 2, 2), (1, 3)).astype(np.float32)
        x0, y0, c = x1m, g1m - a.shape[0], 1.0
    assert abs(c - 1.0) < 1e-6 and abs(x0 - round(x0)) < 1e-6 and abs(y0 - round(y0)) < 1e-6, ("siatka arkusza nie na pelnych metrach", nag)
    assert 0 < x0 < 1e6 and 0 < y0 < 1e6, ("arkusz poza ukladem EPSG:2180 (PL-2000?)", x0, y0)
    return int(round(x0)), int(round(y0)), a                   # lewy dolny rog [m], wiersz 0 = polnoc

# --- 3. wpisanie w kafle km (tylko w puste komorki: arkusze ida od najlepszego) ---
def kafel_sciezka(prod, e, n): return os.path.join(KAT, "kafle", prod.lower(), f"{e}_{n}.npy")
def wpisz(prod, x0, y0, a, poprawka=0.0, tylko_pomiar=False):
    ny, nx = a.shape; roz = []; wpis = 0
    for e in range(max(x0 // 1000, E_KM), min((x0 + nx - 1) // 1000 + 1, E_KM + 20)):
        for n in range(max(y0 // 1000, N_KM), min((y0 + ny - 1) // 1000 + 1, N_KM + 20)):
            p = kafel_sciezka(prod, e, n)
            k = np.load(p) if os.path.exists(p) else np.full((1000, 1000), np.nan, np.float32)
            # wycinek arkusza nad kaflem: kolumny [e*1000 - x0, ...), wiersze od gornej krawedzi
            cx0, cx1 = max(e * 1000, x0), min((e + 1) * 1000, x0 + nx)
            cy0, cy1 = max(n * 1000, y0), min((n + 1) * 1000, y0 + ny)
            if cx1 <= cx0 or cy1 <= cy0: continue
            src = a[y0 + ny - cy1:y0 + ny - cy0, cx0 - x0:cx1 - x0]
            dst = k[(n + 1) * 1000 - cy1:(n + 1) * 1000 - cy0, cx0 - e * 1000:cx1 - e * 1000]
            obie = ~np.isnan(src) & ~np.isnan(dst)
            if obie.any(): roz.append(dst[obie] - src[obie])
            if tylko_pomiar: continue
            puste = np.isnan(dst) & ~np.isnan(src); dst[puste] = src[puste] + poprawka; wpis += int(puste.sum())
            os.makedirs(os.path.dirname(p), exist_ok=True); np.save(p, k)
    return wpis, (np.concatenate(roz) if roz else np.array([], np.float32))

# --- 4. pobieranie po kolei ---
def pobierz(url, cel):
    for p in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r, open(cel + ".part", "wb") as f:
                while (b := r.read(1 << 20)): f.write(b)
            os.replace(cel + ".part", cel); return
        except Exception as e: print("  pobieranie, ponawiam:", e); time.sleep(10 * (p + 1))
    raise SystemExit("nie udalo sie pobrac " + url)

wybor = json.load(open(os.path.join(KAT, "lista.json"))) if os.path.exists(os.path.join(KAT, "lista.json")) else lista()
if TYLKO_LISTA: raise SystemExit(0)
STAN = os.path.join(KAT, "stan.json"); stan = json.load(open(STAN)) if os.path.exists(STAN) else {"zrobione": [], "bajty": 0, "sekundy": 0}
STARE = os.path.join(KAT, "kron86"); os.makedirs(STARE, exist_ok=True)
def zapisz_stan(): json.dump(stan, open(STAN, "w"))
for prod in ("NMT", "NMPT"):
    stare, pula = [], []
    for k, a in enumerate(wybor[prod]):
        u = a["url_do_pobrania"]; evrf = a["uklad_h"] == "PL-EVRF2007-NH"
        plik = os.path.join(STARE if not evrf else KAT, ("" if evrf else f"{k}_") + ("arkusz.zip" if u.endswith(".zip") else "arkusz.asc"))
        if u in stan["zrobione"]: continue
        t0 = time.time()
        if not (not evrf and os.path.exists(plik)): pobierz(u, plik)
        rozm = os.path.getsize(plik); t1 = time.time(); x0, y0, tab = czytaj_asc(plik)
        if not evrf:                                     # KRON86: zostaje na dysku do poprawki liczonej z calej puli zakladek
            _, r = wpisz(prod, x0, y0, tab, tylko_pomiar=True); pula.append(r); stare.append((k, a, plik, rozm)); continue
        os.remove(plik); wpis, _ = wpisz(prod, x0, y0, tab)
        if wpis == 0 and a["dokrywa_ha"] >= 10: print(f"OSTRZEZENIE: {a['godlo']} mial dokryc {a['dokrywa_ha']} ha, wpisal 0 komorek", flush=True)
        stan["zrobione"].append(u); stan["bajty"] += rozm; stan["sekundy"] += time.time() - t0; zapisz_stan()
        print(f"{prod} {k + 1}/{len(wybor[prod])} {a['godlo']} {a['akt_rok']} {a['char_przestrz']}: {rozm / 1e6:.0f} MB w {t1 - t0:.0f} s, "
              f"przeliczenie {time.time() - t1:.0f} s, nowych komorek {wpis / 1e6:.2f} mln", flush=True)
        time.sleep(PAUZA)
    if stare:                                        # przesuniecie ukladu wysokosci jedno dla NMT i NMPT - mierzone na gruncie (NMT)
        r = np.concatenate(pula) if pula else np.array([])
        if prod == "NMT":
            stan["kron86_na_evrf"] = float(np.median(r)) if len(r) >= 10000 else None
            stan["kron86_komorek"] = int(len(r)); stan["kron86_rozrzut_m"] = float(np.subtract(*np.percentile(r, [75, 25]))) if len(r) else None
        popr = stan.get("kron86_na_evrf")
        print(f"{prod}: KRON86 -> EVRF2007 poprawka {popr} m (z {stan.get('kron86_komorek')} komorek gruntu, IQR {stan.get('kron86_rozrzut_m')})", flush=True)
        for k, a, plik, rozm in stare:
            if popr is None: print(f"  POMINIETY {a['godlo']}: brak poprawki"); os.remove(plik); stan["zrobione"].append(a["url_do_pobrania"]); continue
            x0, y0, tab = czytaj_asc(plik); os.remove(plik); wpis, _ = wpisz(prod, x0, y0, tab, popr)
            stan["zrobione"].append(a["url_do_pobrania"]); stan["bajty"] += rozm; zapisz_stan()
            print(f"{prod} {k + 1}/{len(wybor[prod])} {a['godlo']} {a['akt_rok']} KRON86{popr:+.3f}: nowych komorek {wpis / 1e6:.2f} mln", flush=True)
print(f"koniec: {stan['bajty'] / 1e9:.1f} GB, {stan['sekundy'] / 60:.0f} min")
