// Silnik laczony (silnik/laczony.js) w przypadkach granicznych: musi dac to samo co fala.py (samo miasto, ziemia plaska)
// i dolek.py (sam teren, ziemia 4/3) - porownanie z wzorcem z Pythona (eksport.py) i z osobnymi silnikami JS.
// Uzycie: node laczony.mjs
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { geometriaMiasto, stratyMiasto, geometriaTeren, J, C_MHZ } from "../silnik/silnik.js";
import { geometriaLaczona, stratyLaczone } from "../silnik/laczony.js";
import { probnikDolek, odbiornikiDolek } from "../silnik/teren-dolek.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const TYP = { float32: Float32Array, float64: Float64Array, uint8: Uint8Array };
function wczytaj(zestaw) {
  const kat = join(HERE, "dane", zestaw), man = JSON.parse(readFileSync(join(kat, "manifest.json")));
  const t = {};
  for (const [n, o] of Object.entries(man.tablice)) {
    const b = readFileSync(join(kat, n + ".bin"));
    t[n] = new TYP[o.dtype](b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength)); t[n].ksztalt = o.ksztalt;
  }
  return { meta: man.meta, t };
}
let zle = 0;
function roznica(nazwa, a, b, prog) {
  let max = 0;
  for (let k = 0; k < a.length; k++) { const d = Math.abs(a[k] - b[k]); if (d > max || Number.isNaN(d)) max = Number.isNaN(d) ? Infinity : d; }
  const ok = max <= prog; if (!ok) zle++;
  console.log(`  ${ok ? "OK " : "ZLE"} ${nazwa.padEnd(34)} max ${max.toExponential(2)} dB (prog ${prog})`);
}
// ile dodaja krawedzie wtorne (P.526-13 §4.3) - poza wzorcem Pythona, tylko rozklad do oceny
function rozklad(nazwa, a, b) {
  const d = Float64Array.from(a, (v, k) => v - b[k]).sort(), q = (p) => d[Math.min(d.length - 1, Math.floor(p * d.length))].toFixed(1);
  console.log(`      krawedzie wtorne ${nazwa}: >0 w ${(100 * d.filter((v) => v > 0).length / d.length).toFixed(0)}% punktow, mediana ${q(0.5)}, p90 ${q(0.9)}, p99 ${q(0.99)}, max ${q(1)} dB`);
}
const ms = (t0) => (performance.now() - t0).toFixed(0) + " ms";

{ // samo miasto: fala.py
  const { meta, t } = wczytaj("fala");
  const scena = { nx: meta.nx, ny: meta.ny, X0: meta.X0, Y1: meta.Y1, DX: meta.DX, DY: meta.DY, O: t.O, G: t.G, ZW: t.ZW };
  const xs = Float64Array.from({ length: meta.nx }, (_, j) => meta.X0 + (j + 0.5) * meta.DX);
  const ys = Float64Array.from({ length: meta.ny }, (_, i) => meta.Y1 - (i + 0.5) * meta.DY);
  const Z = Float32Array.from(t.G, (g) => g + meta.H_RX);
  const odb = { xs, ys, Z };
  console.log(`samo miasto (fala.py), siatka ${meta.ny}x${meta.nx}, ziemia plaska:`);
  for (const [nazwa, { T, f }] of Object.entries(meta.nadajniki)) {
    let t0 = performance.now();
    const geo = geometriaLaczona(odb, T, { miasto: scena, R_E: Infinity, podstawaKorony: meta.PODSTAWA_KORONY, smaxGeom: meta.smaxGeom });
    const czas = ms(t0);
    const ref = geometriaMiasto(scena, T, { hRx: meta.H_RX, podstawaKorony: meta.PODSTAWA_KORONY, smaxGeom: meta.smaxGeom });
    for (const fq of f) {
      const { L, nad } = stratyLaczone(odb, T, geo, fq, { wtorne: false, snop: null, korony: "weissberger" });   // wzorce Pythona: jedna krawedz, bez snopa, Weissberger
      rozklad(`${nazwa}_${fq}`, stratyLaczone(odb, T, geo, fq, { snop: null, korony: "weissberger" }).L, L);
      const r = stratyMiasto(scena, T, ref, fq, { hRx: meta.H_RX });
      roznica(`${nazwa}_${fq} L vs silnik miasta JS (${czas})`, L, r.L, 0);
      roznica(`${nazwa}_${fq} L vs fala.py`, L, t[`${nazwa}_${fq}_L`], 1e-4);
      roznica(`${nazwa}_${fq} nadwyzka vs fala.py`, nad, t[`${nazwa}_${fq}_nad`], 1e-4);
    }
  }
}

{ // sam teren: dolek.py
  const { meta, t } = wczytaj("dolek");
  const wysokosc = probnikDolek(meta, t);
  const xs = t.xs, N = xs.length, Z = odbiornikiDolek(xs, wysokosc, meta.H_RX);
  const odb = { xs, ys: Float64Array.from(xs, (x) => -x), Z };
  const sl = Math.sqrt(C_MHZ / meta.F_MHZ);
  console.log(`\nsam teren (dolek.py MODEL=nmt), siatka ${N}x${N} po ${meta.KROK} m, ziemia 4/3:`);
  for (const { nazwa, T } of meta.nadajniki) {
    const t0 = performance.now();
    const geo = geometriaLaczona(odb, T, { teren: { wysokosc, krok: meta.KROK }, R_E: meta.R_E });
    const czas = ms(t0);
    const ref = geometriaTeren(xs, Z, T, wysokosc, { krok: meta.KROK, R_E: meta.R_E });
    roznica(`${nazwa} u vs silnik terenu JS (${czas})`, geo.umax, ref.umax, 0);
    roznica(`${nazwa} zaslona vs dolek.py`, Float64Array.from(geo.umax, (u) => J(u / sl)), t["ref_" + nazwa], 1e-4);
  }
}
console.log(zle ? `\n${zle} porownan ZLE` : "\nwszystkie porownania OK");
process.exitCode = zle ? 1 : 0;
