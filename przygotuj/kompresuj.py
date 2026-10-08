#!/usr/bin/env python3
# Zestaw danych (manifest.json + *.bin) -> wersja do przegladarki ok. 10x mniejsza: kazda tablica float32 zapisana jako
# int16 w centymetrach (blad <= 5 mm; przy 10 cm wynik stacji przesuwal sie do 3,4 dB - krawedzie styczne sa czule), roznice wzdluz wiersza, gzip.
# O (wierzch pokrycia) zapisywany jako wysokosc nad G - to sie kompresuje znacznie lepiej niz bezwzgledna.
# NaN -> -32768. Roznice i sumy modulo 2^16 (int16 z przepelnieniem po obu stronach) - dekodowanie bit w bit.
# Dekoduje silnik/dane.js (pole "kodowanie" w manifest). Kazdy wynik z tych danych to SYMULACJA.
# Uzycie: python3 kompresuj.py ../dane/rynek  -> ../dane/rynek-z/
import gzip, json, os, shutil, sys
import numpy as np

WE = os.path.abspath(sys.argv[1]); WY = WE.rstrip("/") + "-z"
SKALA, BRAK, BAZA = 0.01, -32768, {"O": "G"}
man = json.load(open(os.path.join(WE, "manifest.json")))
os.makedirs(WY, exist_ok=True)
czyt = lambda n, o: np.fromfile(os.path.join(WE, n + ".bin"), dtype=o["dtype"]).reshape(o["ksztalt"])
wyj = {"tablice": {}, "meta": man["meta"]}
for n, o in man["tablice"].items():
    a = czyt(n, o)
    if o["dtype"] != "float32":
        open(os.path.join(WY, n + ".bin.gz"), "wb").write(gzip.compress(np.ascontiguousarray(a).astype(a.dtype.newbyteorder("<")).tobytes(), 9, mtime=0))
        wyj["tablice"][n] = {**o, "kodowanie": {"gzip": True}}; continue
    b = n in BAZA and BAZA[n] in man["tablice"]
    if b: a = a - czyt(BAZA[n], man["tablice"][BAZA[n]])
    q = np.round(a / SKALA)
    assert np.nanmax(np.abs(q)) < 32767, (n, np.nanmax(np.abs(q)))
    q = np.where(np.isnan(q), BRAK, q).astype(np.int16)
    d = np.diff(q, axis=-1, prepend=np.zeros(q.shape[:-1] + (1,), np.int16)).astype(np.int16)   # modulo 2^16
    open(os.path.join(WY, n + ".bin.gz"), "wb").write(gzip.compress(d.astype("<i2").tobytes(), 9, mtime=0))
    wyj["tablice"][n] = {**o, "kodowanie": {"gzip": True, "int16": True, "skala": SKALA, "brak": BRAK, "roznice": True,
                                            **({"baza": BAZA[n]} if b else {})}}
json.dump(wyj, open(os.path.join(WY, "manifest.json"), "w"), indent=1, ensure_ascii=False)
we = sum(os.path.getsize(os.path.join(WE, n + ".bin")) for n in man["tablice"])
wy = sum(os.path.getsize(os.path.join(WY, n + ".bin.gz")) for n in man["tablice"])
print(f"{WE} -> {WY}: {we / 1e6:.2f} MB -> {wy / 1e6:.2f} MB")
