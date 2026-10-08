// nalozPaczki na zestawie obszar-2880-z (Node): ile komorek z paczek, roznica wobec dotychczasowych warstw.
import { readFileSync } from "node:fs";
import { wczytajZestaw } from "../silnik/dane.js";
import { nalozPaczki } from "../silnik/paczka.js";
const M = new URL("../", import.meta.url).pathname;
globalThis.fetch = async (u) => { try { const b = readFileSync(M + "telefon/" + u); return { ok: true, arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.length) }; } catch { return { ok: false }; } };
const czytaj = async (p) => new Uint8Array(readFileSync(M + "telefon/" + p));
const { meta, t } = await wczytajZestaw("../dane/obszar-2880-z", czytaj);
const stare = Object.fromEntries(Object.entries(t).map(([k, v]) => [k, v.slice()]));
const w = await nalozPaczki(meta, t, "../dane/paczki/v1");
console.log(w);
const pct = (a, p) => { const s = Float64Array.from(a).sort(); return s[Math.floor(p * (s.length - 1))]; };
for (const k of ["G", "O", "ZW"]) {
  const d = []; for (let i = 0; i < t[k].length; i++) if (t[k][i] !== stare[k][i]) d.push(Math.abs(t[k][i] - stare[k][i]));
  console.log(k, `zmienione ${d.length}, |roznica| mediana ${pct(d, .5).toFixed(3)} m, 99% ${pct(d, .99).toFixed(2)} m, max ${pct(d, 1).toFixed(2)} m`);
}
let b = 0; for (let i = 0; i < t.BUD.length; i++) if (t.BUD[i] !== stare.BUD[i]) b++; console.log("BUD zmienione", b);
