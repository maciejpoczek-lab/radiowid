// Kalibracja komórek pomiarami z telefonu: dziennik CSV (NetMonster albo inny - kolumny rozpoznawane po nazwach) z położeniem
// GPS i siłą sygnału (RSRP / SS-RSRP [dBm]) -> dla każdego punktu model liczy w tym samym miejscu stratę drogi L [dB] do
// najlepszej stacji tego operatora w tym paśmie (prawdziwy wątek mapy, jak weryfikacja/pomiar-fizyki.mjs). Model nie zna mocy
// nadajnika na podnośną, więc porównuje się K = RSRP + L: gdyby model był dokładny, K byłoby prawie stałe (moc + zyski anten).
// Rozrzut K między punktami = błąd modelu; mediana K w danym otoczeniu wobec innych = przesunięcie do poprawienia.
// Telefon w budynku traci 10-20 dB (Korkowa 35, 3,6 GHz: 14 dB) - takie punkty oznacz kolumną "wewnatrz" albo nie zbieraj.
// Pomiary to trasy właściciela telefonu: trzymaj je POZA repo (~/dev/showreel-2/pomiary/), do gita idzie tylko ten skrypt.
// Uzycie: node weryfikacja/kalibracja.mjs <dziennik.csv albo pomiar_*.jsonl> [--wiek 10] [--dokladnosc 30] [--operator P4|Orange|T-Mobile|Polkomtel] [--siatka 50] [--max 300] [--wynik plik.json]
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { na2180 } from "../silnik/paczka.js";

const arg = process.argv.slice(2), opcja = (n, d) => { const i = arg.indexOf(`--${n}`); return i >= 0 ? arg[i + 1] : d; };
const plik = arg.find((a, i) => !a.startsWith("--") && !arg[i - 1]?.startsWith("--"));
if (!plik) { console.error("podaj plik CSV z pomiarami"); process.exit(2); }

// --- .jsonl z weryfikacja/telefon-pomiar.sh (Termux:API) -> te same wiersze co CSV. Bierze tylko komórki zarejestrowane
// (u sąsiadów telefony MediaTek podają pasmo stale [1]) i tylko świeżą pozycję GPS: elapsedMs = wiek poprawki,
// --wiek [s] domyślnie 10, --dokladnosc [m] domyślnie 30 (w budynku "-r last" oddaje poprawkę sprzed wejścia).
// Pola NR (5G) wg Termux:API niezweryfikowane na prawdziwym odczycie - stąd kilka nazw naraz.
function zJsonl(t) {
  const wiek = +opcja("wiek", 10) * 1000, dokl = +opcja("dokladnosc", 30), w = ["lat;lon;rsrp;sinr;tech;band;pci;mnc"];
  for (const l of t.split(/\r?\n/)) {
    if (!l.trim()) continue;
    let r; try { r = JSON.parse(l); } catch { continue; }
    const g = r.loc, dobra = g && g.provider === "gps" && g.elapsedMs <= wiek && g.accuracy <= dokl;
    for (const c of (r.cells ?? []).filter((c) => c.registered)) {
      const rsrp = c.rsrp ?? c.ss_rsrp ?? c.ssRsrp ?? c.csi_rsrp, sinr = c.rssnr ?? c.ss_sinr ?? c.ssSinr ?? c.sinr ?? "";
      w.push([dobra ? g.latitude : "", dobra ? g.longitude : "", rsrp ?? "", sinr, c.type, (c.bands ?? [])[0] ?? "", c.pci ?? "", c.mnc ?? ""].join(";"));
    }
  }
  return w.join("\n");
}

// --- CSV: separator z nagłówka, kolumny po nazwach (bez wielkości liter i znaków innych niż litery/cyfry) ---
const surowy = readFileSync(plik, "utf8").replace(/^﻿/, "");
const tekst = /\.jsonl$/i.test(plik) ? zJsonl(surowy) : surowy, wiersze = tekst.split(/\r?\n/).filter((l) => l.trim());
const sep = [";", "\t", ","].find((s) => wiersze[0].includes(s)) ?? ",";
const pola = (l) => l.split(sep).map((v) => v.trim().replace(/^"(.*)"$/, "$1"));
const nag = pola(wiersze[0]).map((n) => n.toLowerCase().replace(/[^a-z0-9]/g, ""));
const ALIASY = {
  lat: ["latitude", "lat", "gpslat"], lon: ["longitude", "lon", "lng", "long", "gpslon"],
  rsrp: ["ssrsrp", "rsrp", "nrrsrp", "ltersrp", "signal", "dbm"], sinr: ["sssinr", "sinr", "snr", "rssnr"],
  tech: ["tech", "technology", "type", "network", "networktype", "rat", "system"], band: ["band", "nrband", "lteband"],
  arfcn: ["nrarfcn", "earfcn", "arfcn", "channel"], pci: ["pci", "physicalcellid"], mnc: ["mnc"], operator: ["operator", "network operator", "plmnname", "carrier"],
  wewnatrz: ["wewnatrz", "indoor"],
};
const kol = Object.fromEntries(Object.entries(ALIASY).map(([k, a]) => [k, a.map((n) => nag.indexOf(n.replace(/[^a-z0-9]/g, ""))).find((i) => i >= 0) ?? -1]));
for (const k of ["lat", "lon", "rsrp"]) if (kol[k] < 0) { console.error(`brak kolumny ${k}; nagłówek: ${pola(wiersze[0]).join(" | ")}`); process.exit(2); }

// --- pasmo z (technologii, numeru pasma) albo z numeru kanału; nazwy jak w plikach UKE (silnik/punkt.js PASMA_MHZ) ---
const NR = { 78: "5g3600", 1: "5g2100", 28: "5g700", 3: "5g1800", 7: "5g2600", 8: "5g900" };
const LTE = { 1: "lte2100", 3: "lte1800", 7: "lte2600", 8: "lte900", 20: "lte800", 28: "lte700" };
const PASMA_NR_ARFCN = [[620000, 653333, 78], [422000, 434000, 1], [151600, 160600, 28], [361000, 376000, 3], [524000, 538000, 7], [185000, 192000, 8]];
const PASMA_EARFCN = [[0, 599, 1], [1200, 1949, 3], [2750, 3449, 7], [3450, 3799, 8], [6150, 6449, 20], [9210, 9659, 28]];
function pasmo(tech, band, arfcn) {
  const nr = /nr|5g/i.test(tech ?? "") || arfcn > 100000, b = +String(band ?? "").replace(/\D/g, "") ||
    ((nr ? PASMA_NR_ARFCN : PASMA_EARFCN).find(([a, z]) => arfcn >= a && arfcn <= z) ?? [])[2];
  return b ? (nr ? NR : LTE)[b] ?? null : null;
}
const MNC = { 1: "Polkomtel", 2: "T-Mobile", 3: "Orange", 6: "P4" };
const operatorWiersza = (w) => opcja("operator") ?? MNC[+w[kol.mnc]] ??
  ((o) => /play|p4/i.test(o) ? "P4" : /plus|polkomtel/i.test(o) ? "Polkomtel" : /orange/i.test(o) ? "Orange" : /t-?mobile/i.test(o) ? "T-Mobile" : null)(w[kol.operator] ?? "");

// --- punkty: odrzuć bez GPS/RSRP, uśrednij w kratce (mediana RSRP na kratkę × operator × pasmo) ---
const E0 = 679860, N0 = 451200, siatka = +opcja("siatka", 50), kratki = new Map(), odrzucone = { gps: 0, rsrp: 0, pasmo: 0, operator: 0, wewnatrz: 0 };
for (const l of wiersze.slice(1)) {
  const w = pola(l), lat = +w[kol.lat], lon = +w[kol.lon], rsrp = +w[kol.rsrp];
  if (!(lat > 48 && lat < 55 && lon > 13 && lon < 25)) { odrzucone.gps++; continue; }
  if (!(rsrp < -30 && rsrp > -160)) { odrzucone.rsrp++; continue; }
  if (kol.wewnatrz >= 0 && /^(1|t|tak|true|yes)$/i.test(w[kol.wewnatrz])) { odrzucone.wewnatrz++; continue; }
  const pa = pasmo(w[kol.tech], w[kol.band], +w[kol.arfcn]); if (!pa) { odrzucone.pasmo++; continue; }
  const op = operatorWiersza(w); if (!op) { odrzucone.operator++; continue; }
  const [N, E] = na2180(lat, lon), klucz = `${Math.round(E / siatka)},${Math.round(N / siatka)},${op},${pa}`;
  if (!kratki.has(klucz)) kratki.set(klucz, { E: 0, N: 0, lat, lon, op, pa, rsrp: [], sinr: [], pci: new Set() });
  const k = kratki.get(klucz); k.E += E; k.N += N; k.rsrp.push(rsrp); if (kol.sinr >= 0 && w[kol.sinr] !== "") k.sinr.push(+w[kol.sinr]); if (kol.pci >= 0) k.pci.add(w[kol.pci]);
}
const mediana = (a) => { const s = [...a].sort((x, y) => x - y); return s.length ? (s.length % 2 ? s[s.length >> 1] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : NaN; };
let punkty = [...kratki.values()].map((k) => ({ ...k, E: k.E / k.rsrp.length, N: k.N / k.rsrp.length, n: k.rsrp.length, rsrp: mediana(k.rsrp), sinr: mediana(k.sinr) }));
const max = +opcja("max", 300);
if (punkty.length > max) punkty = punkty.filter((_, i) => i % Math.ceil(punkty.length / max) === 0);
console.log(`${plik}: ${wiersze.length - 1} wierszy -> ${punkty.length} punktów (kratka ${siatka} m); odrzucone ${JSON.stringify(odrzucone)}`);
console.log(`kolumny: ${Object.entries(kol).filter(([, i]) => i >= 0).map(([k, i]) => `${k}=${pola(wiersze[0])[i]}`).join(", ")}`);

// --- wątek mapy w Node (jak weryfikacja/pomiar-fizyki.mjs) ---
const HERE = dirname(fileURLToPath(import.meta.url)), TELEFON = join(HERE, "../telefon");
globalThis.fetch = async (u) => { const p = join(TELEFON, String(u).split("?")[0]); return existsSync(p) ? new Response(readFileSync(p)) : new Response(null, { status: 404 }); };
const wyniki = new Map();
globalThis.postMessage = (m) => { wyniki.get(m.id)?.(m); };
globalThis.onmessage = null;
await import("../telefon/poziomy-praca.js");
let nr = 0;
const zlec = (z) => new Promise((ok) => { const id = ++nr; wyniki.set(id, ok); globalThis.onmessage({ data: { ...z, id } }); });
const kr = JSON.parse(new TextDecoder().decode(await new Response(new Response(readFileSync(join(HERE, "../dane/kraj/stacje.json.gz"))).body
  .pipeThrough(new DecompressionStream("gzip"))).arrayBuffer()));
const stacje = kr.stacje.map(([x, y, h, op, pa, adres]) => ({ x, y, ...(h == null ? {} : { h_ant: h }), operatorzy: op.map((k) => kr.operatorzy[k]), pasma: pa.map((k) => kr.pasma[k]), adres }));

const wynik = [];
for (const p of punkty) {
  const P = { x: p.E - E0, y: p.N - N0 }, rx = new RegExp(p.op.replace("-", "-?"), "i");
  const blisko = stacje.filter((s) => s.operatorzy.some((o) => rx.test(o)) && s.pasma.includes(p.pa) && Math.hypot(s.x - P.x, s.y - P.y) <= 10000);
  if (!blisko.length) { console.log(`  ${p.lat.toFixed(5)},${p.lon.toFixed(5)} ${p.op} ${p.pa}: brak stacji w rejestrze do 10 km`); continue; }
  const w = await zlec({ typ: "punkt", P, hRx: 1.5, stacje: blisko });
  if (w.blad) { console.log(`  ${p.lat.toFixed(5)},${p.lon.toFixed(5)}: ${w.blad}`); continue; }
  const naj = w.stacje.map((s) => ({ s, r: s.pasma_wynik[p.pa] })).filter((x) => x.r).sort((a, b) => a.r.strata_db - b.r.strata_db)[0];
  if (!naj) continue;
  const r = { lat: +p.lat.toFixed(5), lon: +p.lon.toFixed(5), op: p.op, pasmo: p.pa, n: p.n, rsrp: p.rsrp, sinr: p.sinr, pci: [...p.pci].join("/"),
    scena: w.scena, otoczenie: w.otoczenie, L: naj.r.strata_db, zapas: naj.r.zapas_db, snop: naj.r.snop_db, K: +(p.rsrp + naj.r.strata_db).toFixed(1),
    stacja: naj.s.adres, km: +naj.s.km.toFixed(2), h_ant: naj.s.h_ant ?? null };
  wynik.push(r);
  console.log(`  ${String(r.lat).padEnd(8)} ${String(r.lon).padEnd(8)} ${r.op.padEnd(9)} ${r.pasmo.padEnd(7)} RSRP ${String(r.rsrp).padStart(6)} (n ${r.n})  model L ${r.L} zapas ${r.zapas}  K ${r.K}  ` +
    `${r.km} km ${r.stacja}${r.h_ant == null ? " (antena 35 m założona)" : ""}`);
}

// --- podsumowanie: K per pasmo (moc nadajnika zależy od pasma) i w nim per otoczenie/scena ---
const NAZWY_OT = ["wieś", "miasto", "duże miasto"];
for (const pa of [...new Set(wynik.map((r) => r.pasmo))]) {
  const z = wynik.filter((r) => r.pasmo === pa), K = z.map((r) => r.K), q = (a, f) => [...a].sort((x, y) => x - y)[Math.min(a.length - 1, Math.floor(f * a.length))];
  console.log(`\n${pa}: ${z.length} punktów, K mediana ${mediana(K).toFixed(1)}, rozrzut 10-90% ${(q(K, 0.9) - q(K, 0.1)).toFixed(1)} dB`);
  for (const [nazwa, f] of [...NAZWY_OT.map((n, i) => [n, (r) => r.otoczenie === i]), ["ulica (budynki)", (r) => r.scena === "ulica"], ["sam teren", (r) => r.scena !== "ulica"]]) {
    const a = z.filter(f).map((r) => r.K); if (a.length) console.log(`  ${nazwa.padEnd(16)} ${String(a.length).padStart(4)} pkt  K mediana ${mediana(a).toFixed(1)}  (wobec całości ${(mediana(a) - mediana(K)).toFixed(1)} dB)`);
  }
}
if (opcja("wynik")) writeFileSync(opcja("wynik"), JSON.stringify({ plik, punkty: wynik }, null, 1));
