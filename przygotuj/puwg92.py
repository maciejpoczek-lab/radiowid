# PUWG 1992 (EPSG:2180): odwzorowanie Gaussa-Krugera na GRS80, poludnik 19 st., k0 = 0,9993.
# Wzory Snydera (USGS PP 1395, 8-9..8-12) - blad ponizej centymetra w pasie +-3,5 st.
import numpy as np
A, F = 6378137.0, 1 / 298.257222101
E2 = F * (2 - F); EP2 = E2 / (1 - E2)
L0, K0, FE, FN = np.radians(19.0), 0.9993, 500000.0, -5300000.0

def na_2180(lat, lon):
    """stopnie -> (x = polnoc, y = wschod) w metrach, jak osie x/y uslugi WCS GUGiK"""
    p, l = np.radians(lat), np.radians(lon)
    s, c = np.sin(p), np.cos(p)
    N = A / np.sqrt(1 - E2 * s * s); T = np.tan(p) ** 2; C = EP2 * c * c; a = (l - L0) * c
    e4, e6 = E2 * E2, E2 ** 3
    M = A * ((1 - E2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * p - (3 * E2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * np.sin(2 * p)
             + (15 * e4 / 256 + 45 * e6 / 1024) * np.sin(4 * p) - (35 * e6 / 3072) * np.sin(6 * p))
    wsch = K0 * N * (a + (1 - T + C) * a ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * EP2) * a ** 5 / 120)
    pln = K0 * (M + N * np.tan(p) * (a * a / 2 + (5 - T + 9 * C + 4 * C * C) * a ** 4 / 24
                                     + (61 - 58 * T + T * T + 600 * C - 330 * EP2) * a ** 6 / 720))
    return pln + FN, wsch + FE

if __name__ == "__main__":
    # kontrola: Warszawa, Palac Kultury ok. 52,2318 N 21,0060 E -> ok. x 487 000, y 637 000 (wartosci przyblizone z map)
    print([round(float(v)) for v in na_2180(52.2318, 21.0060)])
