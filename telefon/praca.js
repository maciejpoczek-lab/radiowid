// Watek roboczy strony probnej: silnik laczony (miasto + teren) na danych wokol rynku. Liczy wiersze [i0, i1).
import { geometriaLaczona, stratyLaczone } from "../silnik/laczony.js";
import { probnikDolek } from "../silnik/teren-dolek.js";
import { wczytajZestaw } from "../silnik/dane.js";

let stan;
async function przygotuj() {
  const { meta, t } = await wczytajZestaw("../dane/rynek");
  const m = meta.miasto, n = m.nx;
  const xs = Float64Array.from({ length: n }, (_, j) => m.X0 + (j + 0.5) * m.DX);
  const ys = Float64Array.from({ length: m.ny }, (_, i) => m.Y1 - (i + 0.5) * m.DY);
  const Z = Float32Array.from(t.G, (g) => g + meta.H_RX);
  return { meta, odb: { xs, ys, Z }, miasto: { ...m, O: t.O, G: t.G, ZW: t.ZW },
           teren: { wysokosc: probnikDolek(meta.teren, t), krok: meta.KROK_TERENU } };
}

onmessage = async ({ data: z }) => {
  const t0 = performance.now();
  stan ??= przygotuj();
  const { meta, odb, miasto, teren } = await stan;
  const t1 = performance.now();
  const geo = geometriaLaczona(odb, z.T, { miasto, teren: z.bezTerenu ? null : teren, R_E: meta.R_E,
                                           podstawaKorony: meta.PODSTAWA_KORONY, wiersze: z.wiersze, Dmax: z.Dmax });
  const { nad } = stratyLaczone(odb, z.T, geo, z.f);
  postMessage({ id: z.id, nad, ms: performance.now() - t1, msDane: t1 - t0 }, [nad.buffer]);
};
