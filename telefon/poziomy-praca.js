// Wątek roboczy strony „poziomy przybliżenia” (docs/projekt-paczek-20km.md §7, krok 2: §8 - nadajniki i teren 100 m całej Polski). Układ: metry EPSG:2180 minus E0/N0 (rynek Garwolina).
//   {typ: "scena", poziom, x0, y1, nx, ny, f} -> warstwy miasta poziomu w oknie (f > 1: blok f × f uśredniony, gdy okno za duże)
//   {typ: "swiatlo", siatka, hRx, S, f[]}    -> straty L [dB] w punktach siatki dla każdej częstotliwości (stacja S = {x, y, h})
//   {typ: "pole", siatka, hRx, gi, rodzaj, program} -> natężenie E [dBµV/m] grupy nadajników radia/TV gi
//   {typ: "grupy", P, hRx, rodzaj}           -> grupy radia/TV najmocniejsze w punkcie P (zwykle środek widoku)
//   {typ: "punkt", P, hRx, stacje[]}         -> stacje komórkowe z kierunkiem i oceną + radio/TV w punkcie (silnik/punkt.js) + wysokości
//                                               budynków wokół P (dach, punkt orientacyjny); scena najdokładniejsza: ulica 4 m w pasie, poza nim sam teren
//   {typ: "wysokosci", P, hs[], rodzaj}      -> radio/TV danego rodzaju w punkcie dla każdej wysokości anteny z hs (od ilu metrów jest odbiór)
// błąd w dowolnym zadaniu -> {id, blad}. siatka = {x0, y1, n, krok}: n × n punktów w środkach kratek krok × krok. Wątek nie wysyła żadnych zapytań poza plikami danych.
import { geometriaLaczona, stratyLaczone } from "../silnik/laczony.js";
import { probnikDolek } from "../silnik/teren-dolek.js";
import { wczytajZestaw } from "../silnik/dane.js";
import { POZIOMY, warstwyPoziomu, paczkiOkna, otworzPaczke } from "../silnik/paczka.js";
import { fmZPunktu, poleNaSiatce, widokZPunktu, PROGI_RTV } from "../silnik/punkt.js";

const PACZKI = "../dane/paczki/v1", pamiec = new Map();
// poziom powiat w całej Polsce: NMT 100 m kraju w kwadratach 100 km (docs §8.5) zamiast warstwy -100 paczek
const KRAJ100 = { ...POZIOMY[2], sufiks: "", bok: 100000 }, BAZA_KRAJ = "../dane/kraj/teren-100";
const R_PUNKTU = 1500;   // paczki 4 m: spis lista.json (bez spisu - dwie paczki Garwolina)
const LISTA_PACZEK = fetch(`${PACZKI}/lista.json?h=${Math.floor(Date.now() / 3.6e6)}`)   /* serwer daje dane/paczki/v1 "immutable" na rok, a spis rośnie co rano: nowy adres co godzinę */.then((r) => r.json()).then((l) => new Set(l.paczki)).catch(() => new Set(["E660N440", "E680N440"]));
const nazwaPaczki = (E, N) => `E${String(Math.floor(E / 20000) * 20).padStart(3, "0")}N${String(Math.floor(N / 20000) * 20).padStart(3, "0")}`;   // scena punktu: ± 1,5 km (jak obszar 2,88 km punkt.html)
const zrodlo = (p) => p.m === 100 ? [BAZA_KRAJ, KRAJ100, pamiecKraj] : [PACZKI, p, pamiec];
const gz = (u) => fetch(u).then((r) => new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).json());
let baza, scena = null, kluczSceny = "", scenaP = null, kluczP = "";   // scena widoku i scena punktu - osobno, żeby punkt nie wyrzucał widoku z pamięci
const pamiecKraj = new Map();                             // osobno od paczek: nazwy E600N400 bywają i paczką 20 km, i kwadratem 100 km
const krajGotowy = new Map();                             // ke * 1000 + kn -> Float32Array 1000 × 1000 | null, już wczytane (odczyt synchroniczny w wysokosc)
function zaladujKraj(x0, y0, x1, y1) {                    // EPSG:2180 bezwzględnie; całe pliki, nigdy fragment
  return Promise.all(paczkiOkna(x0, y0, x1, y1, 100000).map(async (n) => {
    const ke = +n.slice(1, 4) / 100, kn = +n.slice(5, 8) / 100, k = ke * 1000 + kn;
    if (krajGotowy.has(k)) return;
    if (!pamiecKraj.has(n)) pamiecKraj.set(n, fetch(`${BAZA_KRAJ}/${n}.pak`).then((r) => r.ok ? r.arrayBuffer() : null).catch(() => null)
      .then((b) => { if (!b) return null; const p = otworzPaczke(b); p.bajty = b.byteLength; return p; }));
    const pk = await pamiecKraj.get(n); krajGotowy.set(k, pk ? await pk.kafel(ke, kn, "G") : null);
  }));
}
async function przygotuj() {
  const [{ meta, t }, kr] = await Promise.all([wczytajZestaw("../dane/obszar-2880-2180-z"), gz("../dane/kraj/nadajniki.json.gz")]);
  const U = meta.uklad, T = probnikDolek(meta.teren, t), RL = meta.teren.RL;
  // nadajniki radia/TV całej Polski (rtv_kraj.py): e/n bezwzględnie -> układ wątku
  const fm = { meta: { ...kr.meta, grupy: kr.meta.grupy.map((g) => ({ ...g, x: g.e - U.E0, y: g.n - U.N0 })) } };
  // teren: T 30 m wokół rynku -> NMT 100 m kraju (wczytane kwadraty) -> 0 (zagranica, morze: teren nieznany)
  // ostatni kwadrat w pamięci podręcznej: kolejne próbki profilu prawie zawsze trafiają w ten sam (kąt prześwitu, krawędzie)
  let kOst = NaN, aOst = null;
  const wysokosc = (x, y) => {
    if (Math.abs(x) < RL && Math.abs(y) < RL) return T(x, y);
    const E = x + U.E0, N = y + U.N0, ke = Math.floor(E / 100000), kn = Math.floor(N / 100000), kk = ke * 1000 + kn;
    if (kk !== kOst) { aOst = krajGotowy.get(kk); kOst = aOst === undefined ? NaN : kk; }   // niewczytany: bez zapamiętania (dojdzie później)
    const a = aOst;
    if (a) { const v = a[Math.floor((kn * 100000 + 100000 - N) / 100) * 1000 + Math.floor((E - ke * 100000) / 100)]; if (!Number.isNaN(v)) return v; }
    return 0;
  };
  return { meta, U, fm, teren: { wysokosc, krok: meta.KROK_TERENU } };
}
const MARGINES_KRAJ = 20000;                              // teren kraju wczytany wokół okna (stacje za krawędzią, próbki drogi fali)
const krajOkna = (x0, y0, x1, y1) => zaladujKraj(x0 - MARGINES_KRAJ, y0 - MARGINES_KRAJ, x1 + MARGINES_KRAJ, y1 + MARGINES_KRAJ);

async function zbudujScene(z) {
  const [b, p, pm] = zrodlo(POZIOMY.find((q) => q.m === z.poziom));
  const [w] = await Promise.all([warstwyPoziomu(b, p, z.x0, z.y1, z.nx, z.ny, pm), krajOkna(z.x0, z.y1 - z.ny * p.m, z.x0 + z.nx * p.m, z.y1)]);
  let { G, O, ZW, BUD } = w, nx = z.nx, ny = z.ny, m = p.m;
  if (z.f > 1) {                                         // za duże okno: kratka f × f uśredniona (jak warstwy poziomów)
    const f = z.f, mx = Math.floor(nx / f), my = Math.floor(ny / f), sr = (a) => { const b = new Float32Array(mx * my);
      for (let i = 0; i < my; i++) for (let j = 0; j < mx; j++) { let s = 0; for (let a1 = 0; a1 < f; a1++) for (let b1 = 0; b1 < f; b1++) s += a[(i * f + a1) * nx + j * f + b1]; b[i * mx + j] = s / (f * f); }
      return b; };
    G = sr(G); O = O === w.G ? G : sr(O); ZW = sr(ZW); BUD = null; nx = mx; ny = my; m *= f;
  }
  const X0 = z.x0 - baza.U.E0, Y1 = z.y1 - baza.U.N0;
  if (O === G) O = Float32Array.from(G);
  for (let i = 0; i < ny; i++) for (let j = 0; j < nx; j++) {   // poza paczkami: grunt z próbnika terenu (NMT 100 m kraju), bez budynków
    const k = i * nx + j; if (!Number.isNaN(G[k])) continue;
    G[k] = O[k] = baza.teren.wysokosc(X0 + (j + 0.5) * m, Y1 - (i + 0.5) * m); ZW[k] = 0;
  }
  return { nx, ny, X0, Y1, DX: m, DY: m, G, O, ZW, BUD, bajty: w.bajty, komorek: w.komorek };
}
function odbiorniki({ x0, y1, n, krok }, hRx) {          // x0/y1 w układzie strony (lokalnym)
  const xs = Float64Array.from({ length: n }, (_, j) => x0 + (j + 0.5) * krok), ys = Float64Array.from({ length: n }, (_, i) => y1 - (i + 0.5) * krok);
  const Z = new Float32Array(n * n), s = scena;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const a = Math.floor((s.Y1 - ys[i]) / s.DY), b = Math.floor((xs[j] - s.X0) / s.DX), g = a >= 0 && b >= 0 && a < s.ny && b < s.nx ? s.G[a * s.nx + b] : NaN;
    Z[i * n + j] = (Number.isFinite(g) ? g : baza.teren.wysokosc(xs[j], ys[i])) + hRx;
  }
  return { xs, ys, Z };
}
const sc = (s = scena) => ({ miasto: s, teren: baza.teren, R_E: baza.meta.R_E, podstawaKorony: baza.meta.PODSTAWA_KORONY });
async function scenaPunktu(P) {                          // ulica 4 m ± R_PUNKTU wokół P w pasie; poza pasem null (sam teren kraju)
  const E = P.x + baza.U.E0, N = P.y + baza.U.N0;
  await krajOkna(E, N, E, N);
  if (!(await LISTA_PACZEK).has(nazwaPaczki(E, N))) return null;   // przy brzegu paczki część sceny poza paczkami: grunt z NMT 100 m, bez budynków
  const n = 2 * R_PUNKTU / 4, x0 = Math.floor((E - R_PUNKTU) / 4) * 4, y1 = Math.ceil((N + R_PUNKTU) / 4) * 4, k = `${x0}|${y1}`;
  if (k !== kluczP) { scenaP = await zbudujScene({ poziom: 4, x0, y1, nx: n, ny: n, f: 1 }); kluczP = k; }
  return scenaP;
}
const gruntW = (s, P) => { if (s) { const i = Math.floor((s.Y1 - P.y) / s.DY), j = Math.floor((P.x - s.X0) / s.DX), g = s.G[i * s.nx + j]; if (Number.isFinite(g)) return g; }
  return baza.teren.wysokosc(P.x, P.y); };
const tylko = (rodzaj) => ({ ...baza.fm, meta: { ...baza.fm.meta, grupy: baza.fm.meta.grupy.map((g) => ({ ...g, programy: g.programy.filter((p) => (p.typ ?? "fm") === rodzaj) })) } });

// komunikaty po kolei: dwie sceny liczone naraz mogłyby skończyć w odwrotnej kolejności (starsza nadpisałaby nowszą);
// błąd (np. plik nie doszedł) wraca jako {id, blad}, żeby strona nie czekała w nieskończoność - baza wczyta się przy następnym
let kolej = Promise.resolve();
onmessage = ({ data: z }) => { kolej = kolej.then(() => obsluz(z)).catch((e) => postMessage({ id: z.id, blad: String(e?.message ?? e) })); };
async function obsluz(z) {
  baza ??= await przygotuj();
  if (z.typ === "scena") {
    const k = JSON.stringify([z.poziom, z.x0, z.y1, z.nx, z.ny, z.f]);
    if (k !== kluczSceny) { scena = await zbudujScene(z); kluczSceny = k; }
    postMessage({ id: z.id, bajty: scena.bajty, komorek: scena.komorek, wszystkich: z.nx * z.ny, komorka: scena.DX });
  } else if (z.typ === "swiatlo") {
    const odb = odbiorniki(z.siatka, z.hRx), T = [z.S.x, z.S.y, baza.teren.wysokosc(z.S.x, z.S.y) + z.S.h], geo = geometriaLaczona(odb, T, sc());
    const L = z.f.map((f) => stratyLaczone(odb, T, geo, f, { rozpraszanie: true }).L);
    postMessage({ id: z.id, L }, L.map((a) => a.buffer));
  } else if (z.typ === "pole") {
    const E = poleNaSiatce(odbiorniki(z.siatka, z.hRx), baza.fm, z.gi, z.rodzaj, sc(), z.hRx, z.program);
    postMessage({ id: z.id, E }, [E.buffer]);
  } else if (z.typ === "grupy") {
    await krajOkna(z.P.x + baza.U.E0, z.P.y + baza.U.N0, z.P.x + baza.U.E0, z.P.y + baza.U.N0);
    const g = baza.teren.wysokosc(z.P.x, z.P.y), lista = fmZPunktu(z.P, tylko(z.rodzaj), { ...sc(), miasto: null }, { hRx: z.hRx, gruntPunktu: g });
    postMessage({ id: z.id, grupy: [...new Set(lista.map((p) => p.gi))] });
  } else if (z.typ === "punkt") {
    const s = await scenaPunktu(z.P), op = { hRx: z.hRx, gruntPunktu: gruntW(s, z.P) }, scn = sc(s);
    const stacje = widokZPunktu(z.P, z.stacje, scn, op);
    // radio/TV: cała Polska daje tysiące programów - do strony tylko te w pobliżu progu, reszta jako liczba
    const fm = [], reszta = { fm: 0, dab: 0, dvbt: 0 };
    for (const p of fmZPunktu(z.P, baza.fm, scn, op)) {
      if (p.E_dBuVm < PROGI_RTV[p.typ].granica - 20) { reszta[p.typ]++; continue; }
      const { typ, program, kanal, mhz, stacja, pol, gi, km, azymut, E_dBuVm, zaslona_db, krawedz, ocena } = p;
      fm.push({ typ, program, kanal, mhz, stacja, pol, gi, km, azymut, E_dBuVm, zaslona_db, krawedz, ocena });
    }
    let dach = null;                                    // wysokość budynku nad gruntem w kratce 4 m (0 poza budynkami) - dach w punkcie i punkt orientacyjny
    if (s?.BUD) { const H = new Float32Array(s.nx * s.ny); for (let k = 0; k < H.length; k++) H[k] = s.BUD[k] ? s.O[k] - s.G[k] : 0;
      dach = { X0: s.X0, Y1: s.Y1, kom: s.DX, nx: s.nx, ny: s.ny, H }; }
    postMessage({ id: z.id, stacje, fm, reszta, dach, scena: s ? "ulica" : "teren" }, dach ? [dach.H.buffer] : []);
  } else if (z.typ === "wysokosci") {
    const s = await scenaPunktu(z.P), g = gruntW(s, z.P), fm = tylko(z.rodzaj), scn = sc(s);
    postMessage({ id: z.id, wys: z.hs.map((h) => ({ h, fm: fmZPunktu(z.P, fm, scn, { hRx: h, gruntPunktu: g })
      .filter((p) => p.ocena !== "nie").map(({ gi, program, ocena }) => ({ gi, program, ocena })) })) });
  }
}
