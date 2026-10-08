// Ile psuje cięcie liczenia radia/TV: max pola z 1-4 najsilniejszych nadajników (ranking w środku mapy) zamiast 6
// oraz siatka 32 m zamiast 16 m. Wynik 2026-10-06: 3 nadajniki = 0,0% komórek innych o >1 dB (dvbt, fm, dab).
// Uzycie: node ciecie-rtv.mjs [dvbt|fm|dab]
import { readFileSync } from "node:fs";
const { wczytajZestaw } = await import("../silnik/dane.js");
const { poleNaSiatce, PROGI_RTV } = await import("../silnik/punkt.js");
const { meta, t } = await wczytajZestaw("../dane/obszar-2880-z", async (p) => new Uint8Array(readFileSync(p)));
const fm = JSON.parse(readFileSync("../dane/rtv.json", "utf8")), m = meta.miasto, scena = { miasto: { ...m, O: t.O, G: t.G, ZW: t.ZW }, teren: null, R_E: meta.R_E };
const siatka = (n, k) => { const c = (a) => a * k + (k >> 1);
  const xs = Float64Array.from({ length: n }, (_, j) => m.X0 + (c(j) + .5) * m.DX), ys = Float64Array.from({ length: n }, (_, i) => m.Y1 - (c(i) + .5) * m.DY), Z = new Float32Array(n * n);
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) Z[i * n + j] = t.G[c(i) * m.nx + c(j)] + 10; return { xs, ys, Z }; };
const typ = process.argv[2] || "dvbt", prog = PROGI_RTV[typ];
const gs = fm.meta.grupy.map((g, gi) => gi).filter((gi) => fm.meta.grupy[gi].programy.some((p) => p.typ === typ));
const s4 = siatka(360, 4), s8 = siatka(180, 8), c = 180 * 360 + 180;
const E4 = gs.map((gi) => poleNaSiatce(s4, fm, gi, typ, scena, 10));
const kol = gs.map((_, q) => q).sort((a, b) => E4[b][c] - E4[a][c]);   // ranking po polu w środku mapy (rynek)
const maks = (lista, n) => { const w = new Float32Array(n).fill(-Infinity); for (const q of lista) for (let k = 0; k < n; k++) if (lista.E[q][k] > w[k]) w[k] = lista.E[q][k]; return w; };
const top = (E, ile) => { const l = kol.slice(0, ile); l.E = E; return maks(l, E[0].length); };
const klasa = (e) => e >= prog.slychac ? 2 : e >= prog.granica ? 1 : 0;
const por = (A, B, opis) => { let d1 = 0, kl = 0; for (let k = 0; k < A.length; k++) { if (Math.abs(A[k] - B[k]) > 1) d1++; if (klasa(A[k]) !== klasa(B[k])) kl++; }
  console.log(opis.padEnd(34), `>1 dB: ${(100 * d1 / A.length).toFixed(1)}%  inna ocena (dobry/granica/brak): ${(100 * kl / A.length).toFixed(1)}%`); };
const wzor = top(E4, 6);
for (const ile of [1, 2, 3, 4]) por(top(E4, ile), wzor, `${ile} nadajn. zamiast 6 (16 m)`);
const E8 = kol.slice(0, 6).map((q) => poleNaSiatce(s8, fm, gs[q], typ, scena, 10));
const l8 = [0, 1, 2, 3, 4, 5]; l8.E = E8; const w8 = maks(l8, 180 * 180);
const w8na4 = Float32Array.from(wzor, (_, k) => w8[(Math.floor(k / 360) >> 1) * 180 + ((k % 360) >> 1)]);
por(w8na4, wzor, "siatka 32 m zamiast 16 m (6 nadajn.)");
