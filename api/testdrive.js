// Lineage Test Drive: a free, read-only taste of the research Lineage does for a family.
// GET /api/testdrive?surname=Calder&state=minnesota&from=1880&to=1949   (state: optional, a US state, filters the newspapers)
//
// Searches three open public archives at once and returns what a family's research would start from:
//   - Library of Congress, Chronicling America: digitized historic newspapers (page image + text snippet)
//   - Internet Archive: books, directories, yearbooks and histories
//   - Wikidata: notable people with this family name who were born before 1925 and have died
// Cost controls: no AI by default; every distinct query is cached at the edge for a week (identical searches
// are free); a per-visitor rate limit; dates are capped at 1949 and only people known to have died are listed,
// so this can't be used to look up living people. Nothing about the visitor or the query is stored.
//
// Optional one-paragraph AI summary (off unless both are set in the Vercel project's environment):
//   ANTHROPIC_API_KEY, TESTDRIVE_AI_DAILY_CAP (e.g. 200 summaries per day per instance; 0 or unset = off)

const UA = "LineageTestDrive/1.0 (+https://lineage.rexstjohn.com/testdrive/)";
const MAX_YEAR = 1949;
const STATES = ["alabama","alaska","arizona","arkansas","california","colorado","connecticut","delaware","district of columbia",
  "florida","georgia","hawaii","idaho","illinois","indiana","iowa","kansas","kentucky","louisiana","maine","maryland",
  "massachusetts","michigan","minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire","new jersey",
  "new mexico","new york","north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania","puerto rico","rhode island",
  "south carolina","south dakota","tennessee","texas","utah","vermont","virginia","washington","west virginia","wisconsin","wyoming"];
const RATE = { windowMs: 60 * 60 * 1000, max: 12 };       // per IP per hour (best effort, per instance)
const hits = new Map();
let aiDay = "", aiCount = 0;

function clean(s, max) {
  return String(s || "").normalize("NFKC").replace(/[^\p{L}\p{M}' .-]/gu, "").replace(/\s+/g, " ").trim().slice(0, max);
}

async function getJSON(url, opts = {}) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), opts.timeout || 9000);
  try {
    const r = await fetch(url, { headers: { "User-Agent": UA, Accept: "application/json", ...(opts.headers || {}) }, signal: ctl.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } finally {
    clearTimeout(t);
  }
}

function snippet(text, word) {
  const s = (Array.isArray(text) ? text.join(" ") : text) || "";
  const i = s.toLowerCase().indexOf(word.toLowerCase());
  if (i < 0) return "";
  return "…" + s.slice(Math.max(0, i - 110), i + 150).replace(/\s+/g, " ").trim() + "…";
}

async function newspapers(surname, state, from, to) {
  const q = encodeURIComponent(surname);
  const fa = state ? `&fa=location_state:${encodeURIComponent(state)}` : "";
  const d = await getJSON(`https://www.loc.gov/collections/chronicling-america/?q=${q}&dates=${from}/${to}${fa}&fo=json&c=8&at=results,pagination`, { timeout: 25000 });
  return {
    total: d.pagination?.of || 0,
    more: `https://www.loc.gov/collections/chronicling-america/?q=${q}&dates=${from}/${to}${fa}`,
    items: (d.results || []).map(r => ({
      title: String(r.title || "").replace(/^Image \d+ of /, ""),
      date: r.date,
      url: r.url,
      image: (r.image_url || [])[0]?.split("#")[0] || null,
      state: (r.location_state || [])[0] || "",
      snippet: snippet(r.description, surname),
    })),
  };
}

async function books(surname, from, to) {
  // the family name in the title or subject (family histories, genealogies, local histories), not anywhere in the text
  const parts = [`(title:("${surname}") OR subject:("${surname}"))`, "mediatype:texts", `year:[${from} TO ${to}]`];
  const q = encodeURIComponent(parts.join(" AND "));
  const d = await getJSON(`https://archive.org/advancedsearch.php?q=${q}&fl[]=identifier&fl[]=title&fl[]=year&fl[]=creator&sort[]=downloads+desc&rows=8&output=json`);
  return {
    total: d.response?.numFound || 0,
    more: `https://archive.org/search?query=${q}`,
    items: (d.response?.docs || []).map(x => ({
      title: Array.isArray(x.title) ? x.title[0] : x.title,
      year: x.year,
      creator: Array.isArray(x.creator) ? x.creator[0] : x.creator || "",
      url: `https://archive.org/details/${x.identifier}`,
      image: `https://archive.org/services/img/${x.identifier}`,
    })),
  };
}

async function people(surname) {
  const s = surname.replace(/"/g, "");
  const sparql = `SELECT ?p ?pLabel ?pDescription (YEAR(?b) AS ?born) (YEAR(?d) AS ?died) ?img WHERE {
    ?fn wdt:P31/wdt:P279* wd:Q101352; rdfs:label "${s}"@en.
    ?p wdt:P734 ?fn; wdt:P569 ?b; wdt:P570 ?d.
    FILTER(YEAR(?b) < 1925)
    OPTIONAL { ?p wdt:P18 ?img }
    SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
  } ORDER BY ?b LIMIT 12`;
  const d = await getJSON("https://query.wikidata.org/sparql?format=json&query=" + encodeURIComponent(sparql),
    { headers: { Accept: "application/sparql-results+json" } });
  const seen = new Set();
  const items = [];
  for (const b of d.results?.bindings || []) {
    const url = b.p.value;
    if (seen.has(url)) continue;
    seen.add(url);
    items.push({
      name: b.pLabel?.value, about: b.pDescription?.value || "", born: b.born?.value, died: b.died?.value,
      url, image: b.img ? b.img.value.replace(/^http:/, "https:") + "?width=160" : null,
    });
  }
  return { total: items.length, items };
}

async function summary(result) {
  const key = process.env.ANTHROPIC_API_KEY;
  const cap = parseInt(process.env.TESTDRIVE_AI_DAILY_CAP || "0", 10);
  if (!key || !cap) return null;
  const today = new Date().toISOString().slice(0, 10);
  if (aiDay !== today) { aiDay = today; aiCount = 0; }
  if (aiCount >= cap) return null;
  aiCount++;
  const facts = JSON.stringify({
    surname: result.surname, state: result.state, years: `${result.from}-${result.to}`,
    newspapers: result.sources.newspapers.total, newspaperTitles: result.sources.newspapers.items.map(i => `${i.title} ${i.date}`).slice(0, 5),
    books: result.sources.books.total, bookTitles: result.sources.books.items.map(i => i.title).slice(0, 5),
    people: result.sources.people.items.map(p => `${p.name} (${p.born}-${p.died}) ${p.about}`).slice(0, 6),
  });
  try {
    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({
        model: "claude-haiku-5-5", max_tokens: 220,
        messages: [{ role: "user", content:
          "In three plain sentences, tell a family historian what these public search results suggest is worth following up " +
          "for their family. Only mention what the results show; do not invent people or facts.\n\n" + facts }],
      }),
    });
    if (!r.ok) return null;
    const j = await r.json();
    return (j.content || []).map(c => c.text || "").join("").trim() || null;
  } catch {
    return null;
  }
}

module.exports = async function handler(req, res) {
  const url = new URL(req.url, "http://x");
  const surname = clean(url.searchParams.get("surname"), 40);
  const st = clean(url.searchParams.get("state"), 30).toLowerCase();
  const state = STATES.includes(st) ? st : "";
  let from = parseInt(url.searchParams.get("from") || "1800", 10);
  let to = parseInt(url.searchParams.get("to") || String(MAX_YEAR), 10);
  if (!(from >= 1600)) from = 1800;
  if (!(to <= MAX_YEAR)) to = MAX_YEAR;
  if (from > to) from = to;

  if (surname.length < 2) {
    res.status(400).json({ error: "Enter a family name of at least two letters." });
    return;
  }

  const ip = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim() || "anon";
  const now = Date.now();
  const recent = (hits.get(ip) || []).filter(t => now - t < RATE.windowMs);
  if (recent.length >= RATE.max) {
    res.status(429).json({ error: "That's a lot of searches. Please try again in an hour." });
    return;
  }
  recent.push(now);
  hits.set(ip, recent);

  const settle = async (p) => { try { return await p; } catch (e) { return { total: 0, items: [], error: "This archive didn't answer in time." }; } };
  const [n, b, p] = await Promise.all([
    settle(newspapers(surname, state, from, to)),
    settle(books(surname, from, to)),
    settle(people(surname)),
  ]);
  const result = { surname, state, from, to, sources: { newspapers: n, books: b, people: p } };
  result.summary = await summary(result);

  // the CDN keeps each distinct query for a week, so repeat searches cost nothing; a result with an archive that
  // didn't answer is kept only five minutes, so the next visitor gets a fresh try
  const partial = [n, b, p].some(x => x.error);
  res.setHeader("Cache-Control", partial ? "public, s-maxage=300" : "public, s-maxage=604800, stale-while-revalidate=86400");
  res.status(200).json(result);
};
