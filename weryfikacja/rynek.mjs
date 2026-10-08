// Silnik laczony na danych wokol rynku (przygotuj/rynek.py): czasy i kontrole spojnosci.
//  - stacja przy rynku: promien nie wychodzi z siatki miasta -> wynik z terenem == bez terenu (teren nie moze nic dodac);
//  - laczony >= samo miasto w kazdym punkcie (te same probki w miescie + probki terenu za miastem). NIE >= sam teren:
//    sam teren probkuje tez wnetrze miasta z siatki 30 m, ktorej laczony tam swiadomie nie uzywa (bierze dachy i grunt 4 m);
//  - ile punktow zmienia wynik dzieki polaczeniu (krawedz w miescie vs w terenie).
// Uzycie: node rynek.mjs
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { geometriaLaczona, stratyLaczone } from "../silnik/laczony.js";
import { probnikDolek } from "../silnik/teren-dolek.js";
import { wczytajZestaw } from "../silnik/dane.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const { meta, t } = await wczytajZestaw(join(HERE, "../dane/rynek"), async (p) => new Uint8Array(readFileSync(p)));
const m = meta.miasto, n = m.nx;
const odb = { xs: Float64Array.from({ length: n }, (_, j) => m.X0 + (j + 0.5) * m.DX),
              ys: Float64Array.from({ length: m.ny }, (_, i) => m.Y1 - (i + 0.5) * m.DY),
              Z: Float32Array.from(t.G, (g) => g + meta.H_RX) };
const miasto = { ...m, O: t.O, G: t.G, ZW: t.ZW };
const teren = { wysokosc: probnikDolek(meta.teren, t), krok: meta.KROK_TERENU };
const op = { R_E: meta.R_E, podstawaKorony: meta.PODSTAWA_KORONY };
const pct = (a, q) => Float32Array.from(a).sort()[Math.floor(q * (a.length - 1))].toFixed(1);
let zle = 0;
for (const nd of meta.nadajniki) {
  const t0 = performance.now();
  const gL = geometriaLaczona(odb, nd.T, { ...op, miasto, teren }); const ms = performance.now() - t0;
  const gM = geometriaLaczona(odb, nd.T, { ...op, miasto });
  const gT = geometriaLaczona(odb, nd.T, { ...op, teren });
  for (const f of nd.f) {
    const L = stratyLaczone(odb, nd.T, gL, f).nad, M = stratyLaczone(odb, nd.T, gM, f).nad, T = stratyLaczone(odb, nd.T, gT, f).nad;
    let mniej = 0, zmiana = 0, rozne = 0;
    for (let k = 0; k < L.length; k++) {
      if (L[k] < M[k]) mniej++;
      if (Math.abs(L[k] - M[k]) > 1) zmiana++;
      if (L[k] !== M[k]) rozne++;
    }
    const zasieg = Math.hypot(nd.T[0], nd.T[1]) / 1000;
    const okLokal = nd.rodzaj !== "stacja" || rozne === 0, okMax = mniej === 0;
    if (!okLokal || !okMax) zle++;
    console.log(`${nd.nazwa.padEnd(13)} ${String(f).padStart(6)} MHz ${zasieg.toFixed(1).padStart(5)} km  ${ms.toFixed(0).padStart(5)} ms (1 watek)  ` +
      `nadwyzka mediana/p90: laczony ${pct(L, .5)}/${pct(L, .9)}  miasto ${pct(M, .5)}/${pct(M, .9)}  teren ${pct(T, .5)}/${pct(T, .9)} dB  ` +
      `teren zmienia >1 dB: ${(zmiana / L.length * 100).toFixed(1)}%  ${okMax ? "OK" : "ZLE"} laczony>=miasto` +
      (nd.rodzaj === "stacja" ? `  ${okLokal ? "OK" : "ZLE"} stacja: z terenem == bez (${rozne} roznych)` : ""));
  }
}
console.log(zle ? `${zle} kontroli ZLE` : "kontrole OK");
process.exitCode = zle ? 1 : 0;
