// Ile psuje pominiecie stacji komorkowych daleko za krawedzia mapy (swiatlo calej mapy, 16 m, 10 m, z rozpraszaniem P.1411).
// Wynik 2026-10-06: do 3 km za krawedzia - lte 17/29 stacji, widoczna zmiana jasnosci 0,07% komorek; wszystko 20/36, 0,19%.
// Uzycie: node ciecie-komorkowe.mjs [lte|wszystko]
import { Worker, isMainThread, parentPort, workerData } from "node:worker_threads";
import { readFileSync } from "node:fs";
const GR = [806, 1842, 2140, 3600], gdy = [(f) => f < 1000, (f) => f >= 1000 && f < 2000, (f) => f >= 2000 && f < 3000, (f) => f >= 3000];
if (isMainThread) {
  const { PASMA_MHZ } = await import("../silnik/punkt.js");
  const st = JSON.parse(readFileSync("../dane/stacje.json", "utf8")).stacje;
  const p = { lte: (b) => /^lte(?!4[25]0)/.test(b), wszystko: () => true }[process.argv[2] || "lte"];
  const lista = st.map((s) => ({ ...s, pasma: s.pasma.filter(p) })).filter((s) => s.pasma.some((b) => PASMA_MHZ[b]));
  const W = 6, pula = Array.from({ length: W }, () => new Worker(new URL(import.meta.url)));
  const zlec = (w, z) => new Promise((ok) => { w.once("message", ok); w.postMessage(z); });
  const t0 = performance.now(), kolejka = lista.map((s, k) => k);
  const wyn = new Array(lista.length);
  await Promise.all(pula.map(async (w) => { while (kolejka.length) { const k = kolejka.shift(); const s = lista[k];
    const fs = GR.map((f, g) => s.pasma.some((b) => PASMA_MHZ[b] && gdy[g](PASMA_MHZ[b])) ? f : null);
    wyn[k] = await zlec(w, { S: { x: s.x, y: s.y, h: s.h_ant ?? 35 }, fs }); } }));
  console.log(`${lista.length} stacji, ${((performance.now() - t0) / 1000).toFixed(1)} s`); pula.forEach((w) => w.terminate());
  const n = 360 * 360, jas = (L) => Math.min(Math.max((135 - L) / 50, 0), 1);
  const mapa = (wybor) => GR.map((_, g) => { const m = new Float32Array(n).fill(Infinity);
    for (const k of wybor) { const a = wyn[k][g]; if (a) for (let q = 0; q < n; q++) if (a[q] < m[q]) m[q] = a[q]; } return m; });
  const wzor = mapa(lista.map((_, k) => k));
  const poza = (s) => Math.max(Math.abs(s.x), Math.abs(s.y)) - 2880;
  for (const km of [0, 1, 2, 3, 4]) {
    const wyb = lista.map((s, k) => k).filter((k) => poza(lista[k]) <= km * 1000), m = mapa(wyb);
    let d1 = 0, dj = 0, ile = 0;
    for (let g = 0; g < 4; g++) for (let q = 0; q < n; q++) { if (!isFinite(wzor[g][q])) continue; ile++;
      if (Math.abs(m[g][q] - wzor[g][q]) > 1) d1++; if (Math.abs(jas(m[g][q]) - jas(wzor[g][q])) > 0.04) dj++; }
    console.log(`do ${km} km za krawędzią: ${String(wyb.length).padStart(2)} stacji  >1 dB: ${(100 * d1 / ile).toFixed(2)}%  widoczna zmiana jasności (>2 dB w skali): ${(100 * dj / ile).toFixed(2)}%`);
  }
} else {
  const { wczytajZestaw } = await import("../silnik/dane.js");
  const { geometriaLaczona, stratyLaczone } = await import("../silnik/laczony.js");
  const { probnikDolek } = await import("../silnik/teren-dolek.js");
  const { meta, t } = await wczytajZestaw("../dane/obszar-2880-z", async (p) => new Uint8Array(readFileSync(p)));
  const m = meta.miasto, teren = { wysokosc: probnikDolek(meta.teren, t), krok: meta.KROK_TERENU };
  const scena = { miasto: { ...m, O: t.O, G: t.G, ZW: t.ZW }, teren, R_E: meta.R_E, podstawaKorony: meta.PODSTAWA_KORONY };
  const n = 360, k = 4, c = (a) => a * k + (k >> 1);
  const odb = { xs: Float64Array.from({ length: n }, (_, j) => m.X0 + (c(j) + .5) * m.DX), ys: Float64Array.from({ length: n }, (_, i) => m.Y1 - (c(i) + .5) * m.DY), Z: new Float32Array(n * n) };
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) odb.Z[i * n + j] = t.G[c(i) * m.nx + c(j)] + 10;
  parentPort.on("message", ({ S, fs }) => {
    const T = [S.x, S.y, teren.wysokosc(S.x, S.y) + S.h], geo = geometriaLaczona(odb, T, scena);
    parentPort.postMessage(fs.map((f) => f && stratyLaczone(odb, T, geo, f, { rozpraszanie: true }).L));
  });
}
