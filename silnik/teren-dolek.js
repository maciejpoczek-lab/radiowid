// Probnik terenu jak w proby/teren/dolek.py (MODEL=nmt): w promieniu RL od rynku siatka NMT GUGiK (CL m),
// dalej mozaika Copernicus GLO-30 (wycinek). Najblizszy sasiad, polowki do parzystej (np.rint).
// meta i t: z weryfikacja/dane/dolek (manifest.json + *.bin). Zwraca wysokosc(x, y) w metrach od rynku.
import { rint } from "./silnik.js";

export function probnikDolek(meta, t) {
  if (meta.uklad === "EPSG:2180") return probnik2180(meta, t);
  const { SR, KX, KY, RL, CL, LAT_TOP, LON_L, DLAT, DLON } = meta;
  const [Tn0, Tn1] = t.T.ksztalt, [Mc0, Mc1] = t.M.ksztalt, [Mf0, Mf1] = meta.M_ksztalt_calej;
  const r0 = meta.M_wiersz0, c0 = meta.M_kolumna0;
  const clip = (v, a, b) => Math.min(Math.max(v, a), b);
  const h = (lat, lon) => {
    const x = (lon - SR[1]) * KX, y = (lat - SR[0]) * KY;
    if (Math.abs(x) < RL && Math.abs(y) < RL)
      return t.T[clip(rint((RL - y) / CL), 0, Tn0 - 1) * Tn1 + clip(rint((x + RL) / CL), 0, Tn1 - 1)];
    const i = clip(rint((LAT_TOP - lat) / DLAT - 0.5), 0, Mf0 - 1) - r0;
    const j = clip(rint((lon - LON_L) / DLON - 0.5), 0, Mf1 - 1) - c0;
    if (i < 0 || i >= Mc0 || j < 0 || j >= Mc1) throw new Error(`probka poza wycinkiem mozaiki: ${lat}, ${lon}`);
    return t.M[i * Mc1 + j];
  };
  return (x, y) => h(SR[0] + y / KY, SR[1] + x / KX);
}

// Uklad 2180 (przygotuj/na2180.py): T jak wyzej, ale w osiach 2180 od rynku; dalej M = Copernicus przepróbkowany do siatki 2180
// (M_X0 zachod, M_Y1 polnoc, krok M_C) - bez przeliczenia na stopnie. Poza wycinkiem (NaN) blad jak dotad.
function probnik2180({ RL, CL, M_X0, M_Y1, M_C }, t) {
  const [Tn0, Tn1] = t.T.ksztalt, [Mn0, Mn1] = t.M.ksztalt;
  const clip = (v, a, b) => Math.min(Math.max(v, a), b);
  return (x, y) => {
    if (Math.abs(x) < RL && Math.abs(y) < RL)
      return t.T[clip(rint((RL - y) / CL), 0, Tn0 - 1) * Tn1 + clip(rint((x + RL) / CL), 0, Tn1 - 1)];
    const i = Math.floor((M_Y1 - y) / M_C), j = Math.floor((x - M_X0) / M_C), v = i >= 0 && i < Mn0 && j >= 0 && j < Mn1 ? t.M[i * Mn1 + j] : NaN;
    if (Number.isNaN(v)) throw new Error(`probka poza wycinkiem mozaiki: ${x}, ${y}`);
    return v;
  };
}

// Wysokosc odbiornika dla calej siatki (Z = teren + hRx, float32 jak w Pythonie)
export function odbiornikiDolek(xs, wysokosc, hRx) {
  const N = xs.length, Z = new Float32Array(N * N);
  for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) Z[i * N + j] = Math.fround(wysokosc(xs[j], -xs[i]) + hRx);
  return Z;
}
