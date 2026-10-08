#!/usr/bin/env python3
# Teren calej Polski (docs/projekt-paczek-20km.md §8.5): NMT 100 m GUGiK -> pliki .pak w siatce EPSG:2180, ten sam format co paczki.
# Zrodlo: opendata.geoportal.gov.pl/NumDaneWys/NMT_100/ASCII_XYZ/{wojewodztwo}_grid100.zip (16 plikow, 137 MB, pobrane 2026-10-07
# na komputer testowy). W zipie jeden .txt: "wschod polnoc wysokosc" [m], punkty na pelnych 100 m, model TERENU (bez lasu i budynkow).
# Komorka 100 m [x, x + 100) x [y, y + 100) = srednia czterech punktow w rogach (tak jak komorka -100.pak = srednia 25 x 25 komorek 4 m),
# wiec siatka zgadza sie 1:1 z warstwa 100 m paczek. Komorka bez zadnego punktu = brak (NaN).
# Wyjscie (katalog KRAJ, domyslnie mapa/dane/kraj):
#   teren-100/E{km}N{km}.pak - kwadraty 100 x 100 km wyrownane do 100 km, 1000 x 1000 komorek, sam G (poziom powiat)
#   teren-1000.pak           - cala Polska co 1 km (srednia 10 x 10), kwadrat 700 km od (100 km, 100 km), do cieniowania widoku kraju
#   teren100.npy             - krajowa siatka 100 m (float32, wiersz 0 = polnoc) do wysokosci efektywnej nadajnikow (rtv_kraj.py)
# G int16 co 10 cm (paczki: 5 cm, ale 32767 x 5 cm = 1638 m < Rysy 2499 m), roznice wzdluz wiersza, gzip; brak = -32768.
# Kazdy wynik to SYMULACJA.
# Uzycie: python3 teren_kraj.py KATALOG_ZIPOW            -> pliki jak wyzej
#         python3 teren_kraj.py porownaj E660N440-100.pak  -> roznica G wzgledem warstwy 100 m paczki (wymaga teren100.npy)
#         python3 teren_kraj.py wytnij KATALOG E660N440 ... -> E...-100.pak paczek 20 km z siatki krajowej (do weryfikacja/poziomy.mjs BAZA100)
import glob, gzip, io, json, os, sys, zipfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); MAPA = os.path.dirname(HERE)
KRAJ = os.environ.get("KRAJ_WYJSCIE") or os.path.join(MAPA, "dane", "kraj")
E0, N0, BOK, KOM = 100_000, 100_000, 800_000, 100           # siatka krajowa: E 100-900 km, N 100-900 km (Polska: E 170-870, N 130-790)
NK = BOK // KOM                                              # 8000 komorek na bok
SKALA = 0.1

def int16_roznice(a, skala):                                 # jak paczka.py: NaN -> -32768
    q = np.round(np.nan_to_num(a, nan=0) / skala); assert np.abs(q).max() < 32767
    q = np.where(np.isnan(a), -32768, q).astype(np.int16)
    return gzip.compress(np.diff(q, axis=-1, prepend=np.zeros((q.shape[0], 1), np.int16)).astype("<i2").tobytes(), 9, mtime=0)

def zapisz(plik, a, rog, bok, kom, zrodlo):                  # jeden kafel = caly plik (jak -100.pak paczki)
    b = int16_roznice(a, SKALA); klucz = f"{rog[0] // bok}_{rog[1] // bok}"
    nag = {"format": "pak", "wersja_formatu": 1, "wersja_danych": 1, "uklad": "EPSG:2180", "paczka": os.path.basename(plik)[:-4],
           "rog_zachod_poludnie_m": list(rog), "bok_m": bok, "kafel_m": bok, "komorka_m": kom, "poziom_m": kom, "ksztalt_kafla": list(a.shape),
           "wiersz0": "polnoc", "warstwy": {"G": {"dtype": "int16", "skala": SKALA, "roznice": True, "brak": -32768}},
           "kafle": {klucz: {"G": [0, len(b)]}}, "zrodla": [zrodlo],
           "uwaga": "SYMULACJA, nie pomiar; sam teren, bez budynkow i drzew"}
    h = json.dumps(nag, ensure_ascii=False, separators=(",", ":")).encode()
    with open(plik, "wb") as f: f.write(b"PAK1"); f.write(len(h).to_bytes(4, "little")); f.write(h); f.write(b)
    return os.path.getsize(plik)

def czytaj_pak(plik):                                        # jednokaflowy .pak z G -> (naglowek, G)
    b = open(plik, "rb").read(); dl = int.from_bytes(b[4:8], "little"); nag = json.loads(b[8:8 + dl]); st = 8 + dl
    (off, ln), = [v["G"] for v in nag["kafle"].values()]; o = nag["warstwy"]["G"]; ny, nx = nag["ksztalt_kafla"]
    q = (np.cumsum(np.frombuffer(gzip.decompress(b[st + off:st + off + ln]), "<i2").reshape(ny, nx).astype(np.int64), 1) + 32768) % 65536 - 32768
    return nag, np.where(q == o.get("brak", 1 << 20), np.nan, q * o["skala"]).astype(np.float32)

if len(sys.argv) > 3 and sys.argv[1] == "wytnij":
    T = np.load(os.path.join(KRAJ, "teren100.npy"), mmap_mode="r"); os.makedirs(sys.argv[2], exist_ok=True)
    for nazwa in sys.argv[3:]:
        e, n = int(nazwa[1:4]) * 1000, int(nazwa[5:8]) * 1000; i0, j0 = (N0 + BOK - n - 20_000) // KOM, (e - E0) // KOM
        r = zapisz(os.path.join(sys.argv[2], f"{nazwa}-100.pak"), np.asarray(T[i0:i0 + 200, j0:j0 + 200]), (e, n), 20_000, KOM, "NMT 100 m GUGiK (wyciety z kraju)")
        print(f"{nazwa}-100.pak z kraju: {r / 1e3:.0f} kB")
    sys.exit(0)

if len(sys.argv) > 2 and sys.argv[1] == "porownaj":
    T = np.load(os.path.join(KRAJ, "teren100.npy"), mmap_mode="r")
    for plik in sys.argv[2:]:
        nag, G = czytaj_pak(plik); e, n = nag["rog_zachod_poludnie_m"]; s = nag["bok_m"] // KOM
        i0, j0 = (N0 + BOK - n - nag["bok_m"]) // KOM, (e - E0) // KOM
        d = np.asarray(T[i0:i0 + s, j0:j0 + s]) - G; d = d[~np.isnan(d)]; a = np.abs(d)
        print(f"{nag['paczka']}: {d.size} komorek, NMT_100 - paczka: mediana {np.median(d):+.2f} m, |d| 50% {np.percentile(a, 50):.2f}, "
              f"95% {np.percentile(a, 95):.2f}, 99% {np.percentile(a, 99):.2f}, max {a.max():.2f} m, > 1 m {(a > 1).mean() * 100:.2f}%")
    sys.exit(0)

# --- punkty -> wezly siatki (wezel (i, j) = punkt E0 + j*100, N0 + BOK - i*100) ---
W = np.full((NK + 1, NK + 1), np.nan, np.float32); ile = 0
for zp in sorted(glob.glob(os.path.join(sys.argv[1], "*_grid100.zip"))):
    z = zipfile.ZipFile(zp); (nazwa,) = z.namelist()
    p = np.loadtxt(io.TextIOWrapper(z.open(nazwa), encoding="utf-8-sig"), dtype=np.float64)
    j = np.round((p[:, 0] - E0) / KOM).astype(int); i = np.round((N0 + BOK - p[:, 1]) / KOM).astype(int)
    assert np.allclose(p[:, 0], E0 + j * KOM) and np.allclose(p[:, 1], N0 + BOK - i * KOM), "punkty poza pelnymi 100 m"
    stare = W[i, j]; rozne = ~np.isnan(stare) & (np.abs(stare - p[:, 2]) > 0.05)
    W[i, j] = p[:, 2]; ile += len(p)
    print(f"{os.path.basename(zp)}: {len(p)} punktow, wysokosc {p[:, 2].min():.1f}-{p[:, 2].max():.1f} m, "
          f"wspolne z poprzednimi {(~np.isnan(stare)).sum()} (rozne > 5 cm: {rozne.sum()})", flush=True)
print(f"razem {ile} punktow, wezlow z danymi {(~np.isnan(W)).sum()}")

# --- komorki: srednia z rogow, ktore maja dane ---
R = np.stack([W[:-1, :-1], W[:-1, 1:], W[1:, :-1], W[1:, 1:]])
with np.errstate(invalid="ignore"): T = np.nanmean(R, 0).astype(np.float32)
del R, W
os.makedirs(os.path.join(KRAJ, "teren-100"), exist_ok=True); np.save(os.path.join(KRAJ, "teren100.npy"), T)
ZR = "NMT 100 m (EVRF2007): GUGiK, opendata.geoportal.gov.pl NumDaneWys/NMT_100, przetworzone"

suma, plikow = 0, 0
for bi in range(BOK // 100_000):                             # kwadraty 100 km, wiersz 0 = polnoc
    for bj in range(BOK // 100_000):
        a = T[bi * 1000:(bi + 1) * 1000, bj * 1000:(bj + 1) * 1000]
        if np.isnan(a).all(): continue
        e, n = E0 + bj * 100_000, N0 + BOK - (bi + 1) * 100_000
        suma += zapisz(os.path.join(KRAJ, "teren-100", f"E{e // 1000:03d}N{n // 1000:03d}.pak"), a, (e, n), 100_000, KOM, ZR); plikow += 1
print(f"teren-100: {plikow} plikow, razem {suma / 1e6:.1f} MB, srednio {suma / plikow / 1e3:.0f} kB")

with np.errstate(invalid="ignore"): K = np.nanmean(T.reshape(NK // 10, 10, NK // 10, 10), (1, 3)).astype(np.float32)
r = zapisz(os.path.join(KRAJ, "teren-1000.pak"), K, (E0, N0), BOK, 1000, ZR)
print(f"teren-1000.pak: {K.shape[0]} x {K.shape[1]} po 1 km, {r / 1e3:.0f} kB, komorek z danymi {(~np.isnan(K)).sum()}")
