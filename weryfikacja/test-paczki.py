#!/usr/bin/env python3
# Wzorzec dla test-paczki.mjs: niezalezny dekoder .pak w numpy, okno sklejone z mozaiki wszystkich kafli obu paczek.
import gzip, json, os, sys
import numpy as np
WZOR = os.environ.get("WZOR", "/tmp/paczki-wzor"); os.makedirs(WZOR, exist_ok=True)
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dane", "paczki", "v1")
X0, Y1, NX, NY = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
moz = {}
for f in sorted(f for f in os.listdir(D) if "-" not in f):   # same paczki 4 m (pliki poziomow E...-16.pak pomijane)
    b = open(os.path.join(D, f), "rb").read(); dl = int.from_bytes(b[4:8], "little"); nag = json.loads(b[8:8 + dl]); st = 8 + dl
    nk = nag["ksztalt_kafla"][0]
    for k, wp in nag["kafle"].items():
        e, n = map(int, k.split("_")); t = {}
        for w in ("G", "O", "ZW", "BUD", "NMPT_PROC"):
            off, ln = wp[w]; r = gzip.decompress(b[st + off:st + off + ln]); o = nag["warstwy"][w]
            if o["dtype"] == "uint8": t[w] = np.frombuffer(r, np.uint8).reshape(nk, nk); continue
            q = np.cumsum(np.frombuffer(r, "<i2").reshape(nk, nk).astype(np.int64), 1)
            q = ((q + 32768) % 65536 - 32768).astype(np.float64)
            t[w] = (q * o["skala"]).astype(np.float32)
        t["O"] = (t["O"] + t["G"]).astype(np.float32)
        moz[(e, n)] = t
for w in ("G", "O", "ZW", "BUD", "NMPT_PROC"):
    u8 = w in ("BUD", "NMPT_PROC"); a = np.zeros((NY, NX), np.uint8) if u8 else np.full((NY, NX), np.nan, np.float32)
    for i in range(NY):
        y = Y1 - 4 * i - 2
        for j in range(NX):
            x = X0 + 4 * j + 2; t = moz.get((x // 1000, y // 1000))
            if t is not None: a[i, j] = t[w][int((1000 * (y // 1000 + 1) - y) // 4), int((x - 1000 * (x // 1000)) // 4)]
    a.tofile(f"{WZOR}/wzor-{w}.bin")
print("wzorzec gotowy", {k: len(v) for k, v in [("kafle", moz)]})
