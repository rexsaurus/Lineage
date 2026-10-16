// "Reserve your spot" / "Get updates" form on /join/. POST /api/lead  { name, email, surname, src, website (honeypot) }
// Stores the lead only if a store is configured (see api/_leads.js); otherwise it fails closed and asks the visitor
// to use Rex's paper sign-up sheet. Nothing a visitor types is ever logged.
const { store, addLead } = require("./_leads.js");

const RATE = { windowMs: 60 * 60 * 1000, max: 8 };   // per IP per hour (best effort, per instance)
const hits = new Map();
const SHEET = "Sorry, this didn't go through. Please write your email on Rex's sheet.";

function clean(s, max) {
  return String(s == null ? "" : s).normalize("NFKC").replace(/[\u0000-\u001f\u007f<>]/g, "").replace(/\s+/g, " ").trim().slice(0, max);
}

async function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  if (typeof req.body === "string") { try { return JSON.parse(req.body); } catch { return {}; } }
  const chunks = [];
  let size = 0;
  for await (const c of req) { size += c.length; if (size > 8192) return {}; chunks.push(c); }
  try { return JSON.parse(Buffer.concat(chunks).toString("utf8")); } catch { return {}; }
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Robots-Tag", "noindex");
  if (req.method !== "POST") { res.status(405).json({ ok: false, message: "Please use the form on the page." }); return; }

  const ip = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim() || "anon";
  const now = Date.now();
  const recent = (hits.get(ip) || []).filter(t => now - t < RATE.windowMs);
  if (recent.length >= RATE.max) {
    res.status(429).json({ ok: false, message: "That's a lot of sign-ups from here. Please write your email on Rex's sheet." });
    return;
  }
  recent.push(now);
  hits.set(ip, recent);

  const b = await readBody(req);
  if (clean(b.website, 100)) { res.status(200).json({ ok: true, message: "Thank you. I'll be in touch." }); return; }   // honeypot
  const email = clean(b.email, 120).toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) { res.status(400).json({ ok: false, message: "Please check your email address." }); return; }
  const srcRaw = clean(b.src, 64).toLowerCase();
  const lead = {
    at: new Date().toISOString(),
    name: clean(b.name, 80),
    email,
    surname: clean(b.surname, 60),
    src: /^[a-z0-9-]{1,64}$/.test(srcRaw) ? srcRaw : "direct",
  };

  const s = store();
  if (!s) { res.status(503).json({ ok: false, message: SHEET }); return; }
  try {
    await addLead(s, lead);
    res.status(200).json({ ok: true, message: "Thank you. I'll be in touch." });
  } catch {
    console.error("lead store write failed");        // no PII in logs
    res.status(503).json({ ok: false, message: SHEET });
  }
};
