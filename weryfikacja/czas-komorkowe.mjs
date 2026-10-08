// Czas liczenia komórkowych jak na stronie (jeden wątek, Node): kierunki (widokZPunktu), okolica 1,2 km (6 stacji, k=1),
// cała mapa (k=4, stacje do 3 km za krawędzią, przycięte do PROMIEN_X × d3). Uzycie: MIEJSCE=warszawa RODZAJ=lte node czas-komorkowe.mjs
import { readFile } from "node:fs/promises";
import { geometriaLaczona, stratyLaczone } from "../silnik/laczony.js";
import { probnikDolek } from "../silnik/teren-dolek.js";
import { wczytajZestaw } from "../silnik/dane.js";
import { widokZPunktu } from "../silnik/punkt.js";
const MIEJSCE = process.env.MIEJSCE ?? "garwolin", P = MIEJSCE === "garwolin" ? "" : `-${MIEJSCE}`;
const RODZAJ = process.env.RODZAJ ?? "lte", PX = +(process.env.PROMIEN_X ?? 3), KROK = +(process.env.KROK ?? 4);
const RE = { lte: (b) => /^lte(?!4[25]0)/.test(b), "5g": (b) => b.startsWith("5g"), wszystko: () => true }[RODZAJ];
const U = new URL(import.meta.url), czytaj = async (p) => new Uint8Array(await readFile(new URL(p, U)));
const { meta, t } = await wczytajZestaw(`../dane/obszar-2880${P}-z`, czytaj);
if (+process.env.G_KROK) {                       // próba: grunt zapisany z krokiem G_KROK m (O i ZW przesunięte razem z G)
  const k = +process.env.G_KROK;
  for (let q = 0; q < t.G.length; q++) { const g = Math.fround(Math.round(t.G[q] / k) * k), d = g - t.G[q]; t.G[q] = g; t.O[q] = Math.fround(t.O[q] + d); t.ZW[q] = Math.fround(t.ZW[q] + d); }
}
if (+process.env.ZW_KROK) {                      // próba: wysokość korony nad gruntem zapisana z krokiem ZW_KROK m (jak w paczce)
  const k = +process.env.ZW_KROK;
  for (let q = 0; q < t.ZW.length; q++) if (t.ZW[q]) t.ZW[q] = Math.fround(Math.round(t.ZW[q] / k) * k);
}
const st = JSON.parse(await readFile(new URL(`../dane/stacje${P}.json`, U)));
const m = meta.miasto, teren = { wysokosc: probnikDolek(meta.teren, t), krok: meta.KROK_TERENU };
const scena = { miasto: { ...m, O: t.O, G: t.G, ZW: t.ZW }, teren, R_E: meta.R_E, podstawaKorony: meta.PODSTAWA_KORONY };
const MHZ = (b) => +(b.match(/(\d+)$/)?.[1] ?? 0);
const GR = [[806, (f) => f < 1000], [1842, (f) => f >= 1000 && f < 2000], [2140, (f) => f >= 2000 && f < 3000], [3600, (f) => f >= 3000]];
function siatka({ i0, j0, n, k }) {
  const c = (a) => a * k + (k >> 1);
  const xs = Float64Array.from({ length: n }, (_, j) => m.X0 + (j0 + c(j) + 0.5) * m.DX);
  const ys = Float64Array.from({ length: n }, (_, i) => m.Y1 - (i0 + c(i) + 0.5) * m.DY);
  const Z = new Float32Array(n * n);
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) Z[i * n + j] = t.G[(i0 + c(i)) * m.nx + j0 + c(j)] + 10;
  return { xs, ys, Z };
}
let tGeo = 0, tStr = 0;
const swiatlo = (o, s) => {
  const odb = siatka(o), T = [s.x, s.y, teren.wysokosc(s.x, s.y) + s.h_ant_uzyta];
  let a = performance.now(); const geo = geometriaLaczona(odb, T, scena); tGeo += performance.now() - a; a = performance.now();
  const fs = GR.filter(([, g]) => s.pasma.some((b) => g(MHZ(b)))).map(([f]) => f);
  for (const f of fs) { const L = stratyLaczone(odb, T, geo, f, { rozpraszanie: true }).L, gi = GR.findIndex(([ff]) => ff === f);
    if (o.k === KROK && MAPA) for (let i = 0; i < o.n; i++) for (let j = 0; j < o.n; j++) { const p = gi * nm * nm + (o.i0 / KROK + i) * nm + o.j0 / KROK + j; if (L[i * o.n + j] < MAPA[p]) MAPA[p] = L[i * o.n + j]; } }
  tStr += performance.now() - a;
  return fs.length;
};
let t0 = performance.now();
const wyn = widokZPunktu({ x: 0, y: 0 }, st.stacje, scena, { hRx: 10, gruntPunktu: t.G[(m.ny >> 1) * m.nx + (m.nx >> 1)] });
const tKier = performance.now() - t0;
const ls = wyn.map((s) => ({ ...s, pasma: s.pasma.filter(RE) })).filter((s) => s.pasma.length);
let MAPA = null;
const NX = m.nx, NY = m.ny, nm = Math.floor(Math.min(NX, NY) / KROK), o = { i0: 0, j0: 0, n: nm, k: KROK };
const prom = new Map(ls.map((s) => { const d = ls.map((q) => Math.hypot(q.x - s.x, q.y - s.y)).sort((a, b) => a - b); return [s, Math.max(800, PX * (d[3] ?? Infinity))]; }));
const przytnij = (s) => { const r = prom.get(s), kr = KROK * m.DX, n = Math.min(nm, 2 * Math.ceil(r / kr) + 1); if (n >= nm) return o;
  const ic = (m.Y1 - s.y) / kr, jc = (s.x - m.X0) / kr, c = (v) => Math.min(Math.max(Math.round(v - (n >> 1)), 0), nm - n);
  return { i0: c(ic) * KROK, j0: c(jc) * KROK, n, k: KROK }; };
const zaKr = (s) => Math.max(m.X0 - s.x, s.x - (m.X0 + NX * m.DX), (m.Y1 - NY * m.DY) - s.y, s.y - m.Y1, 0);
const grube = ls.filter((s) => zaKr(s) <= Math.min(3000, prom.get(s)));
t0 = performance.now(); const n6 = Math.min(300, NX); for (const s of ls.slice(0, 6)) swiatlo({ i0: (NY - n6) >> 1, j0: (NX - n6) >> 1, n: n6, k: 1 }, s);
const tOk = performance.now() - t0;
MAPA = new Float32Array(4 * nm * nm).fill(Infinity);
let probek = 0, czest = 0, czasy = []; t0 = performance.now();
for (const s of grube) { const oo = przytnij(s), a = performance.now(); czest += swiatlo(oo, s); probek += oo.n * oo.n; czasy.push(performance.now() - a); }
const tMapa = performance.now() - t0; czasy.sort((a, b) => b - a);
console.log(`${MIEJSCE} ${RODZAJ} PROMIEN_X ${PX} krok ${KROK}: stacji w danych ${st.stacje.length}, z rodzajem ${ls.length}, cała mapa ${grube.length}`);
console.log(`  kierunki ${(tKier / 1000).toFixed(1)} s · okolica ${(tOk / 1000).toFixed(1)} s · cała mapa ${(tMapa / 1000).toFixed(1)} s (${(probek / 1e6).toFixed(2)} mln próbek, ${czest} częstotliwości; 10 najdłuższych stacji ${(czasy.slice(0, 10).reduce((a, b) => a + b, 0) / 1000).toFixed(1)} s)`);
console.log(`  w tym geometria ${(tGeo/1000).toFixed(1)} s, straty per częstotliwość ${(tStr/1000).toFixed(1)} s`);
if (process.env.ZAPISZ) (await import("node:fs")).writeFileSync(process.env.ZAPISZ, Buffer.from(MAPA.buffer));
