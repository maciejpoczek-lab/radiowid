// Porownanie silnika JS z wzorcem z Pythona (eksport.py) w tych samych punktach siatki.
// Uzycie: node porownaj.mjs [fala] [dolek]
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { geometriaMiasto, stratyMiasto, geometriaTeren, J, C_MHZ } from "../silnik/silnik.js";
import { probnikDolek, odbiornikiDolek } from "../silnik/teren-dolek.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const ZESTAWY = process.argv.slice(2).length ? process.argv.slice(2) : ["fala", "dolek"];
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

function roznica(nazwa, js, ref) {
  const d = new Float64Array(js.length); let max = 0, gdzie = -1, n01 = 0, n1 = 0;
  for (let k = 0; k < js.length; k++) {
    d[k] = Math.abs(js[k] - ref[k]);
    if (d[k] > max) { max = d[k]; gdzie = k; }
    if (d[k] > 0.01) n01++; if (d[k] > 1) n1++;
  }
  const p999 = Float64Array.from(d).sort()[Math.floor(0.999 * (d.length - 1))];
  console.log(`  ${nazwa.padEnd(26)} max ${max.toExponential(2)} dB  p99,9 ${p999.toExponential(2)}  >0,01 dB: ${n01}  >1 dB: ${n1}  z ${js.length}` +
    (max > 0.01 ? `  (najwieksza w komorce ${gdzie}: JS ${js[gdzie].toFixed(3)} / Py ${ref[gdzie].toFixed(3)})` : ""));
  return max;
}

const ms = (t0) => (performance.now() - t0).toFixed(0) + " ms";

if (ZESTAWY.includes("fala")) {
  const { meta, t } = wczytaj("fala");
  console.log(`fala.py: siatka ${meta.ny}x${meta.nx} po ${meta.DX.toFixed(2)} m; Python (caly przebieg do map) ${meta.sekundy_python.toFixed(1)} s; ` +
    `zapisany fala.npz vs obecny kod: ${JSON.stringify(meta.roznica_do_zapisanego_npz_dB)}`);
  const scena = { nx: meta.nx, ny: meta.ny, X0: meta.X0, Y1: meta.Y1, DX: meta.DX, DY: meta.DY, O: t.O, G: t.G, ZW: t.ZW };
  for (const jakNumpy of [true, false]) {
    console.log(jakNumpy ? "\n[zaokraglenia jak NumPy float32]" : "\n[czysty float64 - wariant produkcyjny]");
    for (const [nazwa, { T, f }] of Object.entries(meta.nadajniki)) {
      const t0 = performance.now();
      const geo = geometriaMiasto(scena, T, { hRx: meta.H_RX, podstawaKorony: meta.PODSTAWA_KORONY, smaxGeom: meta.smaxGeom, jakNumpy });
      console.log(` ${nazwa}: geometria ${ms(t0)}`);
      for (const fq of f) {
        const { L, nad } = stratyMiasto(scena, T, geo, fq, { hRx: meta.H_RX, jakNumpy });
        roznica(`${nazwa}_${fq} L`, L, t[`${nazwa}_${fq}_L`]);
        roznica(`${nazwa}_${fq} nadwyzka`, nad, t[`${nazwa}_${fq}_nad`]);
      }
    }
  }
}

if (ZESTAWY.includes("dolek")) {
  const { meta, t } = wczytaj("dolek");
  const wysokosc = probnikDolek(meta, t);
  const xs = t.xs, N = xs.length, Z = odbiornikiDolek(xs, wysokosc, meta.H_RX);
  console.log(`\ndolek.py (MODEL=nmt): siatka ${N}x${N} po ${meta.KROK} m, ${meta.F_MHZ} MHz; Python (caly przebieg) ${meta.sekundy_python.toFixed(1)} s; ` +
    `zapisany dolek.npz vs obecny kod: ${JSON.stringify(meta.roznica_do_zapisanego_npz_dB)}`);
  roznica("Z (teren + odbiornik) [m]", Z, t.Z);
  const sl = Math.sqrt(C_MHZ / meta.F_MHZ);
  for (const jakNumpy of [true, false]) {
    console.log(jakNumpy ? "[zaokraglenia jak NumPy float32]" : "[czysty float64 - wariant produkcyjny]");
    for (const { nazwa, T } of meta.nadajniki) {
      const t0 = performance.now();
      const { umax } = geometriaTeren(xs, Z, T, wysokosc, { krok: meta.KROK, R_E: meta.R_E, jakNumpy });
      const dt = ms(t0);
      const L = Float64Array.from(umax, (u) => J(u / sl));
      roznica(`${nazwa} zaslona (${dt})`, L, t["ref_" + nazwa]);
    }
  }
}
