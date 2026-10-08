// Przejscie na uklad 2180 (przygotuj/na2180.py): te same punkty (stopnie) liczone w starym zestawie (uklad lokalny, miasto z kafli WCS)
// i w zestawie 2180 z warstwami miasta z paczek. Roznice to suma: uklad (azymut, odleglosc) + inne dane miasta (arkusze 2025 vs WCS).
// Uzycie: [STARE_Z_PACZKAMI=1] node porownaj-2180.mjs [krok_m=1500]   (1: stary uklad z paczkami przepróbkowanymi - sam wplyw ukladu)
import { readFileSync } from "node:fs";
import { wczytajZestaw } from "../silnik/dane.js";
import { nalozPaczki, na2180 } from "../silnik/paczka.js";
import { probnikDolek } from "../silnik/teren-dolek.js";
import { widokZPunktu, fmZPunktu } from "../silnik/punkt.js";
const M = new URL("../", import.meta.url).pathname, TEL = M + "telefon/";
globalThis.fetch = async (u) => { try { const b = readFileSync(TEL + u); return { ok: true, arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.length) }; } catch { return { ok: false }; } };
const czytaj = async (p) => new Uint8Array(readFileSync(TEL + p)), json = (p) => JSON.parse(readFileSync(M + "dane/" + p, "utf8"));

async function scena(zestaw, prz, paczki = false) {
  const { meta, t } = await wczytajZestaw(`../dane/${zestaw}`, czytaj);
  const pak = meta.uklad || paczki ? await nalozPaczki(meta, t, "../dane/paczki/v1") : null;
  return { meta, t, pak, st: json(`stacje${prz}.json`).stacje, fm: json(`rtv${prz}.json`),
           sc: { miasto: { ...meta.miasto, O: t.O, G: t.G, ZW: t.ZW }, teren: { wysokosc: probnikDolek(meta.teren, t), krok: meta.KROK_TERENU }, R_E: meta.R_E, podstawaKorony: meta.PODSTAWA_KORONY } };
}
const A = await scena("obszar-2880-z", "", process.env.STARE_Z_PACZKAMI === "1"), B = await scena("obszar-2880-2180-z", "-2180");
console.log("paczki:", B.pak);
const { SR, KX, KY } = A.meta.teren, U = B.meta.uklad, ZB = U.zbieznosc_deg;
const grunt = (s, P) => { const m = s.meta.miasto, j = Math.floor((P.x - m.X0) / m.DX), i = Math.floor((m.Y1 - P.y) / m.DY); return s.t.G[i * m.nx + j]; };
const daz = (a, b) => Math.abs(((a - b) % 360 + 540) % 360 - 180);
const KROK = +(process.argv[2] ?? 1500), st = { az: [], km: [], nad: [], oc: 0, n: 0, E: [], azf: [], ocf: 0, nf: 0 };
for (const dy of [-KROK, 0, KROK]) for (const dx of [-KROK, 0, KROK]) {
  const lat = SR[0] + dy / KY, lon = SR[1] + dx / KX, [n, e] = na2180(lat, lon);
  const Pa = { x: dx, y: dy }, Pb = { x: e - U.E0, y: n - U.N0 };
  for (const hRx of [1.5, 10]) {
    const wa = widokZPunktu(Pa, A.st, A.sc, { hRx, gruntPunktu: grunt(A, Pa) }), wb = widokZPunktu(Pb, B.st, B.sc, { hRx, gruntPunktu: grunt(B, Pb) });
    const mb = new Map(wb.map((s) => [`${s.lat},${s.lon}`, s]));
    for (const a of wa) { const b = mb.get(`${a.lat},${a.lon}`); st.n++;
      st.az.push(daz(a.azymut, b.azymut + ZB)); st.km.push(Math.abs(a.km - b.km) * 1000); st.nad.push(Math.abs(a.nadwyzka_min_db - b.nadwyzka_min_db)); if (a.ocena !== b.ocena) st.oc++; }
    const fa = fmZPunktu(Pa, A.fm, A.sc, { hRx, gruntPunktu: grunt(A, Pa) }), fb = fmZPunktu(Pb, B.fm, B.sc, { hRx, gruntPunktu: grunt(B, Pb) });
    const mf = new Map(fb.map((p) => [`${p.gi},${p.mhz},${p.program}`, p]));
    for (const a of fa) { const b = mf.get(`${a.gi},${a.mhz},${a.program}`); st.nf++;
      st.E.push(Math.abs(a.E_dBuVm - b.E_dBuVm)); st.azf.push(daz(a.azymut, b.azymut + ZB)); if (a.ocena !== b.ocena) st.ocf++; }
  }
}
const q = (a, p) => { const s = Float64Array.from(a).sort(); return s[Math.floor(p * (s.length - 1))]; };
const r = (a, j) => `mediana ${q(a, .5).toFixed(2)}, 95% ${q(a, .95).toFixed(2)}, max ${q(a, 1).toFixed(2)} ${j}`;
console.log(`komorkowe (${st.n} par stacja-punkt-wysokosc): azymut geograficzny ${r(st.az, "st.")}; odleglosc ${r(st.km, "m")}`);
console.log(`  nadwyzka strat ${r(st.nad, "dB")}; inna ocena w ${st.oc} (${(100 * st.oc / st.n).toFixed(1)}%)`);
console.log(`radio/TV (${st.nf} par program-punkt-wysokosc): natezenie ${r(st.E, "dB")}; azymut ${r(st.azf, "st.")}; inna ocena w ${st.ocf} (${(100 * st.ocf / st.nf).toFixed(1)}%)`);
