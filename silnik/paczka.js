// Odczyt paczek 20 km (.pak, przygotuj/paczka.py) i sklejanie okna z 1-4 paczek. Telefon pobiera CALE paczki - nigdy kafel ani zakres bajtow.
// Plik: "PAK1" + uint32 LE dlugosc naglowka + naglowek JSON + bloki gzip (warstwa x kafel). Dekodowanie bit w bit wzgledem kodera.
// Okno: kwadrat osiowy w EPSG:2180, krawedzie na wielokrotnosciach 4 m; wynik Float32Array/Uint8Array, wiersz 0 = polnoc, NaN poza danymi.
const rozpakuj = async (b) =>
  new Uint8Array(await new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream("gzip"))).arrayBuffer());

export function otworzPaczke(bufor) {                 // ArrayBuffer -> {nag, kafel(e, n, warstwa)}
  const u = new Uint8Array(bufor), dv = new DataView(bufor);
  if (new TextDecoder().decode(u.subarray(0, 4)) !== "PAK1") throw new Error("to nie jest paczka PAK1");
  const dl = dv.getUint32(4, true), nag = JSON.parse(new TextDecoder().decode(u.subarray(8, 8 + dl))), start = 8 + dl;
  const pamiec = new Map();
  async function surowa(klucz, w) {
    const [off, len] = nag.kafle[klucz][w], o = nag.warstwy[w], [ny, nx] = nag.ksztalt_kafla;
    const b = await rozpakuj(u.slice(start + off, start + off + len));
    if (o.dtype === "uint8") return b;
    const d = new Int16Array(b.buffer), a = new Float32Array(d.length);
    for (let i = 0; i < ny; i++) {
      let v = 0;
      for (let j = 0, p = i * nx; j < nx; j++) { v = (v + d[p + j]) << 16 >> 16; a[p + j] = v === o.brak ? NaN : v * o.skala; }
    }
    return a;
  }
  async function kafel(e, n, w) {                     // null, gdy kafla nie ma w paczce
    const klucz = `${e}_${n}`; if (!nag.kafle[klucz]) return null;
    const id = `${klucz}/${w}`; if (pamiec.has(id)) return pamiec.get(id);
    const p = (async () => {
      const a = await surowa(klucz, w), baza = nag.warstwy[w].baza;
      if (baza) { const g = await kafel(e, n, baza); for (let i = 0; i < a.length; i++) a[i] += g[i]; }
      return a;
    })();
    pamiec.set(id, p); return p;
  }
  return { nag, kafel };
}

// Nazwy paczek przecinajacych okno [x0, x1) x [y0, y1) w metrach EPSG:2180 (1, 2 albo 4).
export function paczkiOkna(x0, y0, x1, y1, bok = 20000) {
  const n = [];
  for (let pe = Math.floor(x0 / bok); pe <= Math.floor((x1 - 1e-6) / bok); pe++)
    for (let pn = Math.floor(y0 / bok); pn <= Math.floor((y1 - 1e-6) / bok); pn++)
      n.push(`E${String(pe * bok / 1000).padStart(3, "0")}N${String(pn * bok / 1000).padStart(3, "0")}`);
  return n;
}

// Poziomy przyblizenia (docs §7.1): ~360 x 360 punktow na ekran; poziom = najgrubsza siatka danych nie wieksza niz krok punktow.
// Pliki poziomu leza obok paczki: E...N....pak (4 m), E...N...-16.pak, E...N...-100.pak (sam teren). Bok widoku > 72 km -> null (bez nakladki).
export const POZIOMY = [
  { nazwa: "ulica", m: 4, sufiks: "", warstwy: ["G", "O", "ZW", "BUD"] },
  { nazwa: "okolica", m: 16, sufiks: "-16", warstwy: ["G", "O", "ZW", "BUD"] },
  { nazwa: "powiat", m: 100, sufiks: "-100", warstwy: ["G"] },
];
export function poziomWidoku(bok, punktow = 360) {   // -> {poziom, k} : krok punktow = k komorek poziomu
  const krok = bok / punktow;
  for (let p = POZIOMY.length - 1; p >= 0; p--) if (POZIOMY[p].m <= krok || p === 0) {
    const k = Math.max(1, Math.floor(krok / POZIOMY[p].m));
    return p === POZIOMY.length - 1 && krok > 2 * POZIOMY[p].m ? null : { poziom: POZIOMY[p], k };
  }
}
// Warstwy silnika poziomu w oknie [x0, x0 + nx*m) x (y1 - ny*m, y1]: pobiera CALE pliki poziomu (1 albo wiecej paczek), pamiec: Map nazwa -> Promise.
// Poziom bez O/ZW (powiat): O = G, ZW = 0 - sam teren. poziom.bok: bok pliku w metrach (domyslnie paczka 20 km; teren kraju: 100 km). Wynik: {G, O, ZW, BUD, paczki, z, bajty, nowe_bajty, komorek}
export async function warstwyPoziomu(baza, poziom, x0, y1, nx, ny, pamiec = new Map()) {
  const m = poziom.m, nazwy = paczkiOkna(x0, y1 - ny * m, x0 + nx * m, y1, poziom.bok).map((n) => n + poziom.sufiks);
  let nowe = 0;
  const pk = (await Promise.all(nazwy.map((n) => {
    if (!pamiec.has(n)) pamiec.set(n, fetch(`${baza}/${n}.pak`).then((r) => r.ok ? r.arrayBuffer() : null).catch(() => null)
      .then((b) => { if (!b) return null; nowe += b.byteLength; const p = otworzPaczke(b); p.bajty = b.byteLength; return p; }));
    return pamiec.get(n);
  }))).filter(Boolean);
  const w = { paczki: pk.length, z: nazwy.length, bajty: pk.reduce((s, p) => s + p.bajty, 0), komorek: 0 };
  for (const nw of ["G", "O", "ZW", "BUD"]) {
    if (!pk.length || !poziom.warstwy.includes(nw)) continue;
    w[nw] = await okno(pk, nw, x0, y1, nx, ny); w[nw].ksztalt = [ny, nx];
  }
  w.G ??= new Float32Array(nx * ny).fill(NaN); w.G.ksztalt = [ny, nx];
  w.O ??= w.G; w.ZW ??= new Float32Array(nx * ny); w.BUD ??= new Uint8Array(nx * ny);
  for (let q = 0; q < w.G.length; q++) if (!Number.isNaN(w.G[q])) w.komorek++;
  w.nowe_bajty = nowe; return w;
}

// Okno z otwartych paczek: x0 (zachod), y1 (polnoc), nx x ny komorek po komorka_m z naglowka (4 m paczki, 16 / 100 m pliki poziomow).
export async function okno(paczki, w, x0, y1, nx, ny) {
  const p0 = paczki[0].nag, KOM = p0.komorka_m, KAF = p0.kafel_m, NK = p0.ksztalt_kafla[1];
  const u8 = p0.warstwy[w].dtype === "uint8", wy = u8 ? new Uint8Array(nx * ny) : new Float32Array(nx * ny).fill(NaN);
  const c0 = Math.round(x0 / KOM), r0 = Math.round(y1 / KOM);        // indeks komorki globalnej: kolumna od x = 0, wiersz od y = 0 w gore
  for (let ke = Math.floor(x0 / KAF); ke * KAF < x0 + nx * KOM; ke++)
    for (let kn = Math.floor((y1 - ny * KOM) / KAF); kn * KAF < y1; kn++) {
      const pk = paczki.find(p => p.nag.kafle[`${ke}_${kn}`]); if (!pk) continue;
      const a = await pk.kafel(ke, kn, w), kc0 = ke * NK, kr0 = (kn + 1) * NK;   // lewa kolumna, gorna krawedz kafla
      for (let i = 0; i < NK; i++) {
        const r = r0 - (kr0 - i); if (r < 0 || r >= ny) continue;            // wiersz okna
        const jj0 = Math.max(0, c0 - kc0), jj1 = Math.min(NK, c0 + nx - kc0); if (jj1 <= jj0) continue;
        wy.set(a.subarray(i * NK + jj0, i * NK + jj1), r * nx + kc0 + jj0 - c0);
      }
    }
  return wy;
}

// PUWG 1992 (EPSG:2180) z szerokosci/dlugosci, GRS80, poludnik 19, k0 0,9993 - wzory Snydera jak dane/nmpt/puwg92.py. -> [polnoc, wschod]
export function na2180(lat, lon) {
  const A = 6378137, F = 1 / 298.257222101, E2 = F * (2 - F), EP2 = E2 / (1 - E2), K0 = 0.9993;
  const p = lat * Math.PI / 180, l = lon * Math.PI / 180, s = Math.sin(p), c = Math.cos(p);
  const N = A / Math.sqrt(1 - E2 * s * s), T = Math.tan(p) ** 2, C = EP2 * c * c, a = (l - 19 * Math.PI / 180) * c, e4 = E2 * E2, e6 = E2 ** 3;
  const M = A * ((1 - E2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * p - (3 * E2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * Math.sin(2 * p)
    + (15 * e4 / 256 + 45 * e6 / 1024) * Math.sin(4 * p) - (35 * e6 / 3072) * Math.sin(6 * p));
  const w = K0 * N * (a + (1 - T + C) * a ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * EP2) * a ** 5 / 120);
  const n = K0 * (M + N * Math.tan(p) * (a * a / 2 + (5 - T + 9 * C + 4 * C * C) * a ** 4 / 24 + (61 - 58 * T + T * T + 600 * C - 330 * EP2) * a ** 6 / 720));
  return [n - 5300000, w + 500000];
}

// ETAP PRZEJSCIOWY: warstwy miasta z paczek wpisane w dotychczasowa siatke lokalna (metry od rynku, obrocona ok. 2 st. wobec 2180),
// najblizsza komorka 4 m. Komorki bez paczki zostaja z dotychczasowego zestawu. Pobierane sa CALE paczki okna (1-4), nie kafle.
export async function nalozPaczki(meta, t, baza) {
  if (meta.uklad?.nazwa === "EPSG:2180") return paczki2180(meta, t, baza);
  const t0 = performance.now(), m = meta.miasto, tr = meta.teren, W = m.nx * m.DX, H = m.ny * m.DY;
  const p2 = (x, y) => na2180(tr.SR[0] + y / tr.KY, tr.SR[1] + x / tr.KX);
  const [n00, e00] = p2(m.X0, m.Y1), [n10, e10] = p2(m.X0 + W, m.Y1), [n01, e01] = p2(m.X0, m.Y1 - H), [n11, e11] = p2(m.X0 + W, m.Y1 - H);
  const K = 4, x0 = Math.floor(Math.min(e00, e01) / K) * K, y1 = Math.ceil(Math.max(n00, n10) / K) * K;
  const nx = Math.ceil((Math.max(e10, e11) - x0) / K), ny = Math.ceil((y1 - Math.min(n01, n11)) / K);
  const nazwy = paczkiOkna(x0, y1 - ny * K, x0 + nx * K, y1);
  const pliki = await Promise.all(nazwy.map(n => fetch(`${baza}/${n}.pak`).then(r => r.ok ? r.arrayBuffer() : null).catch(() => null)));
  const pk = pliki.filter(Boolean).map(otworzPaczke), bajty = pliki.reduce((s, b) => s + (b ? b.byteLength : 0), 0);
  const wynik = { paczki: pk.length, z: nazwy.length, bajty, komorek: 0, wszystkich: m.nx * m.ny };
  if (pk.length) {
    const warstwy = ["G", "O", "ZW", "BUD", "NMPT_PROC"].filter(w => t[w]), okna = {};
    for (const w of warstwy) okna[w] = await okno(pk, w, x0, y1, nx, ny);
    for (let i = 0; i < m.ny; i++) {
      const fi = (i + 0.5) / m.ny;
      for (let j = 0; j < m.nx; j++) {
        const fj = (j + 0.5) / m.nx, E = e00 + (e10 - e00) * fj + (e01 - e00) * fi, N = n00 + (n10 - n00) * fj + (n01 - n00) * fi;
        const c = Math.floor((E - x0) / K), r = Math.floor((y1 - N) / K), q = r * nx + c;
        if (c < 0 || r < 0 || c >= nx || r >= ny || Number.isNaN(okna.G[q])) continue;
        const k = i * m.nx + j; for (const w of warstwy) t[w][k] = okna[w][q]; wynik.komorek++;
      }
    }
  }
  wynik.ms = performance.now() - t0; return wynik;
}

// Uklad 2180 (przygotuj/na2180.py): siatka miasta to okno paczek 1:1 (rynek zaokraglony do 4 m), warstwy miasta tylko z paczek.
// Komorki bez paczki: NaN w G/O/ZW, 0 w BUD - strona mowi o tym w linii stanu (komorek < wszystkich).
async function paczki2180(meta, t, baza) {
  const t0 = performance.now(), m = meta.miasto, u = meta.uklad, x0 = u.E0 + m.X0, y1 = u.N0 + m.Y1;
  const nazwy = paczkiOkna(x0, y1 - m.ny * m.DY, x0 + m.nx * m.DX, y1);
  const pliki = await Promise.all(nazwy.map(n => fetch(`${baza}/${n}.pak`).then(r => r.ok ? r.arrayBuffer() : null).catch(() => null)));
  const pk = pliki.filter(Boolean).map(otworzPaczke), bajty = pliki.reduce((s, b) => s + (b ? b.byteLength : 0), 0);
  const wynik = { paczki: pk.length, z: nazwy.length, bajty, komorek: 0, wszystkich: m.nx * m.ny };
  for (const w of ["G", "O", "ZW", "BUD", "NMPT_PROC"]) {
    t[w] = pk.length ? await okno(pk, w, x0, y1, m.nx, m.ny) : w === "BUD" || w === "NMPT_PROC" ? new Uint8Array(m.nx * m.ny) : new Float32Array(m.nx * m.ny).fill(NaN);
    t[w].ksztalt = [m.ny, m.nx];
  }
  for (let k = 0; k < t.G.length; k++) if (!Number.isNaN(t.G[k])) wynik.komorek++;
  wynik.ms = performance.now() - t0; return wynik;
}
