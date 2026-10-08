// Watek roboczy: liczy fragment siatki (wiersze [i0, i1)) i odsyla wynik. Dane wczytuje sam (pamiec podreczna przegladarki).
import { geometriaTeren, geometriaMiasto, stratyMiasto, J, C_MHZ } from "../silnik/silnik.js";
import { probnikDolek, odbiornikiDolek } from "../silnik/teren-dolek.js";
import { wczytajZestaw } from "../silnik/dane.js";

const zestawy = {};
const zestaw = (n) => (zestawy[n] ??= wczytajZestaw(`../weryfikacja/dane/${n}`));

onmessage = async ({ data: z }) => {
  const t0 = performance.now();
  if (z.rodzaj === "teren") {
    const { meta, t } = await zestaw("dolek");
    const wys = probnikDolek(meta, t), xs = t.xs;
    const Z = (zestawy.Z ??= odbiornikiDolek(xs, wys, meta.H_RX));
    const t1 = performance.now();
    const { umax } = geometriaTeren(xs, Z, z.T, wys, { krok: meta.KROK, R_E: meta.R_E, wiersze: z.wiersze });
    const sl = Math.sqrt(C_MHZ / meta.F_MHZ), L = Float32Array.from(umax, (u) => J(u / sl));
    postMessage({ id: z.id, L, ms: performance.now() - t1, msDane: t1 - t0 }, [L.buffer]);
  } else {
    const { meta, t } = await zestaw("fala");
    const scena = { nx: meta.nx, ny: meta.ny, X0: meta.X0, Y1: meta.Y1, DX: meta.DX, DY: meta.DY, O: t.O, G: t.G, ZW: t.ZW };
    const t1 = performance.now();
    const geo = geometriaMiasto(scena, z.T, { hRx: meta.H_RX, podstawaKorony: meta.PODSTAWA_KORONY, smaxGeom: meta.smaxGeom,
                                              wiersze: z.wiersze, Dmax: z.Dmax });
    const { L } = stratyMiasto(scena, z.T, geo, z.f, { hRx: meta.H_RX });
    postMessage({ id: z.id, L, ms: performance.now() - t1, msDane: t1 - t0 }, [L.buffer]);
  }
};
