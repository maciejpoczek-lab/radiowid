// Pomiar czasu silnika na wielu watkach (Node worker_threads = ten sam V8 co Chrome).
// Praca dzielona na porcje po PORCJA wierszy rozdawane na zadanie (rdzenie wydajne i energooszczedne licza w roznym tempie).
// Uzycie: node czas-watki.mjs [watki...]   np. node czas-watki.mjs 1 4 8 12
import { Worker, isMainThread, parentPort } from "node:worker_threads";
import { readFile } from "node:fs/promises";
import { availableParallelism } from "node:os";
import { geometriaTeren, geometriaMiasto, stratyMiasto, dmaxMiasto, J, C_MHZ } from "../silnik/silnik.js";
import { probnikDolek, odbiornikiDolek } from "../silnik/teren-dolek.js";
import { wczytajZestaw } from "../silnik/dane.js";

const URL_TU = new URL(import.meta.url), PORCJA = 4;
const czytaj = (p) => readFile(new URL(p, URL_TU));

if (!isMainThread) {
  const { meta, t } = await wczytajZestaw("./dane/dolek", czytaj), wys = probnikDolek(meta, t), Z = odbiornikiDolek(t.xs, wys, meta.H_RX);
  const f = await wczytajZestaw("./dane/fala", czytaj), mf = f.meta;
  const scena = { nx: mf.nx, ny: mf.ny, X0: mf.X0, Y1: mf.Y1, DX: mf.DX, DY: mf.DY, O: f.t.O, G: f.t.G, ZW: f.t.ZW };
  const sl = Math.sqrt(C_MHZ / meta.F_MHZ);
  parentPort.on("message", (z) => {
    if (z.rodzaj === "teren") {
      const { umax } = geometriaTeren(t.xs, Z, z.T, wys, { krok: meta.KROK, R_E: meta.R_E, wiersze: z.wiersze });
      parentPort.postMessage({ L: Float32Array.from(umax, (u) => J(u / sl)), wiersze: z.wiersze });
    } else {
      const geo = geometriaMiasto(scena, z.T, { hRx: mf.H_RX, podstawaKorony: mf.PODSTAWA_KORONY, smaxGeom: mf.smaxGeom, wiersze: z.wiersze, Dmax: z.Dmax });
      parentPort.postMessage({ L: stratyMiasto(scena, z.T, geo, z.f, { hRx: mf.H_RX }).L, wiersze: z.wiersze });
    }
  });
  parentPort.postMessage({ gotowy: true });
} else {
  const LICZBY = process.argv.slice(2).map(Number); if (!LICZBY.length) LICZBY.push(1, availableParallelism());
  const { meta } = await wczytajZestaw("./dane/dolek", czytaj), { meta: mf } = await wczytajZestaw("./dane/fala", czytaj);
  const scena = { nx: mf.nx, ny: mf.ny, X0: mf.X0, Y1: mf.Y1, DX: mf.DX, DY: mf.DY };
  const zadania = [
    ...meta.nadajniki.map((n) => ({ nazwa: `teren 8x8 km / 30 m: ${n.nazwa}`, rodzaj: "teren", T: n.T, wierszy: 267 })),
    ...Object.entries(mf.nadajniki).map(([n, v]) => ({ nazwa: `miasto 2,2x1,7 km / 4,8 m: ${n} ${v.f[0]} MHz`, rodzaj: "miasto",
      T: v.T, f: v.f[0], Dmax: dmaxMiasto(scena, v.T), wierszy: mf.ny })),
  ];
  for (const n of LICZBY) {
    const pula = await Promise.all(Array.from({ length: n }, () => new Promise((ok) => {
      const w = new Worker(URL_TU); w.once("message", () => ok(w));
    })));
    const przebieg = (z) => new Promise((ok) => {
      let nast = 0, gotowe = 0; const t0 = performance.now(), porcji = Math.ceil(z.wierszy / PORCJA);
      const daj = (w) => { if (nast >= porcji) return; const i0 = nast++ * PORCJA; w.postMessage({ ...z, wiersze: [i0, Math.min(i0 + PORCJA, z.wierszy)] }); };
      for (const w of pula) {
        w.removeAllListeners("message");
        w.on("message", () => { if (++gotowe === porcji) ok(performance.now() - t0); else daj(w); });
        daj(w);
      }
    });
    for (const z of zadania) await przebieg(z);                           // rozgrzewka (JIT)
    for (const z of zadania) {
      const ms = []; for (let r = 0; r < 3; r++) ms.push(await przebieg(z));
      console.log(`${String(n).padStart(2)} watk.  ${z.nazwa.padEnd(42)} mediana z 3: ${(ms.sort((a, b) => a - b)[1] / 1000).toFixed(3)} s`);
    }
    await Promise.all(pula.map((w) => w.terminate()));
  }
}
