#!/usr/bin/env python3
# Kafle 1 km z arkuszy (arkusze.py) wobec mozaiki WCS wokol rynku (dane/nmpt/kafle): przesuniecie siatki i roznica wysokosci.
# Uzycie: python3 porownaj-arkusze.py KATALOG_KAFLI_KM   (kafle/{nmt,nmpt}/{e}_{n}.npy)
import json, os, sys
import numpy as np
K = os.path.expanduser(sys.argv[1]); D = os.path.expanduser("~/dev/showreel-2/dane/nmpt/kafle")
zk = json.load(open(os.path.join(D, "zakres.json"))); nk = zk["kafli_na_bok"]; W0, N0 = zk["x_zachod"], zk["y_polnoc"]
for m in ("nmt", "nmpt"):
    a = np.empty((nk * 1000, nk * 1000), np.float32)
    for i in range(nk):
        for j in range(nk): a[i * 1000:(i + 1) * 1000, j * 1000:(j + 1) * 1000] = np.load(os.path.join(D, f"{m}/{i}_{j}.npy"))
    a[a == 0] = np.nan
    wyn = {}
    for e in range(677, 682):
        for n in range(449, 454):
            p = os.path.join(K, m, f"{e}_{n}.npy")
            if not os.path.exists(p): continue
            b = np.load(p); i0, j0 = int(N0 - (n + 1) * 1000), int(e * 1000 - W0)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    w = a[i0 + 50 + dy:i0 + 950 + dy, j0 + 50 + dx:j0 + 950 + dx] - b[50:950, 50:950]
                    wyn.setdefault((dy, dx), []).append(w[~np.isnan(w)])
    print(m.upper(), "przesuniecie (wiersz, kolumna) WCS wobec arkuszy -> mediana |roznicy| [m], mediana roznicy [m]")
    for k, v in sorted(wyn.items()):
        v = np.concatenate(v); print(f"  {k}: {np.median(np.abs(v)):.3f}  {np.median(v):+.3f}  (komorek {len(v)})")
