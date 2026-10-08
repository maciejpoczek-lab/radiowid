// Czytnik silnik/paczka.js wobec wzorca z test-paczki.py: okno przez granice dwoch paczek, porownanie bit w bit.
import { readFileSync, readdirSync } from "node:fs";
import { otworzPaczke, paczkiOkna, okno } from "../silnik/paczka.js";
const [X0, Y1, NX, NY] = process.argv.slice(2).map(Number), D = new URL("../dane/paczki/v1/", import.meta.url).pathname;
const S = (process.env.WZOR ?? "/tmp/paczki-wzor") + "/";
const nazwy = paczkiOkna(X0, Y1 - 4 * NY, X0 + 4 * NX, Y1), pliki = new Set(readdirSync(D));
const p = nazwy.filter(n => pliki.has(n + ".pak")).map(n => { const b = readFileSync(D + n + ".pak"); return otworzPaczke(b.buffer.slice(b.byteOffset, b.byteOffset + b.length)); });
console.log("paczki okna:", nazwy.join(" "), "| na dysku:", p.map(q => q.nag.paczka).join(" "));
let zle = 0;
for (const w of ["G", "O", "ZW", "BUD", "NMPT_PROC"]) {
  const t0 = performance.now(), a = await okno(p, w, X0, Y1, NX, NY), ms = performance.now() - t0;
  const r = readFileSync(S + `wzor-${w}.bin`), wz = a instanceof Uint8Array ? new Uint8Array(r.buffer, r.byteOffset, r.length) : new Float32Array(r.buffer, r.byteOffset, r.length / 4);
  let roz = 0, nan = 0; for (let i = 0; i < a.length; i++) { const x = a[i], y = wz[i]; if (Number.isNaN(x) && Number.isNaN(y)) { nan++; continue; } if (x !== y) roz++; }
  zle += roz; console.log(`${w}: ${roz} rozbieznosci z ${a.length}, poza danymi ${nan}, ${ms.toFixed(0)} ms`);
}
process.exit(zle ? 1 : 0);
