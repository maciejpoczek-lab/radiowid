// Koszt krawedzi wtornych (P.526-13 §4.3) w geometriaLaczona: ta sama siatka z wtorne: true i false na przemian,
// najlepszy z kilku przebiegow (odporny na obciazenie maszyny). Uzycie: node weryfikacja/czas-krawedzi.mjs
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { geometriaLaczona } from "../silnik/laczony.js";
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
function ab(nazwa, licz) {
  const najl = { true: Infinity, false: Infinity };
  for (let r = 0; r < 5; r++) for (const w of [true, false]) { const t0 = performance.now(); licz(w); najl[w] = Math.min(najl[w], performance.now() - t0); }
  console.log(`  ${nazwa.padEnd(28)} jedna krawedz ${najl.false.toFixed(0).padStart(5)} ms · z wtornymi ${najl.true.toFixed(0).padStart(5)} ms · +${(100 * (najl.true / najl.false - 1)).toFixed(0)}%`);
}
{
  const { meta, t } = wczytaj("fala");
  const scena = { nx: meta.nx, ny: meta.ny, X0: meta.X0, Y1: meta.Y1, DX: meta.DX, DY: meta.DY, O: t.O, G: t.G, ZW: t.ZW };
  const odb = { xs: Float64Array.from({ length: meta.nx }, (_, j) => meta.X0 + (j + 0.5) * meta.DX),
    ys: Float64Array.from({ length: meta.ny }, (_, i) => meta.Y1 - (i + 0.5) * meta.DY), Z: Float32Array.from(t.G, (g) => g + meta.H_RX) };
  console.log(`miasto ${meta.ny}x${meta.nx}:`);
  for (const [nazwa, { T }] of Object.entries(meta.nadajniki))
    ab(nazwa, (w) => geometriaLaczona(odb, T, { miasto: scena, R_E: Infinity, podstawaKorony: meta.PODSTAWA_KORONY, smaxGeom: meta.smaxGeom, wtorne: w }));
}
{
  const { meta, t } = wczytaj("dolek");
  const wysokosc = probnikDolek(meta, t), xs = t.xs, odb = { xs, ys: Float64Array.from(xs, (x) => -x), Z: odbiornikiDolek(xs, wysokosc, meta.H_RX) };
  console.log(`teren ${xs.length}x${xs.length}:`);
  for (const { nazwa, T } of meta.nadajniki) ab(nazwa, (w) => geometriaLaczona(odb, T, { teren: { wysokosc, krok: meta.KROK }, R_E: meta.R_E, wtorne: w }));
}
