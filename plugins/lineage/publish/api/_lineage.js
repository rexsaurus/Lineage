// Shared code for a family site's subscription functions (api/subscribe.js, confirm.js, unsubscribe.js, digest.js).
// Not a route: files starting with "_" are not functions. Copied into the built site by updates_page.py, with
// _lineage-config.json (site_url, title, slug, sender line, postal address from lineage.json settings.publish).
//
// The site has no npm install step, so everything is plain fetch: Upstash Redis over REST for storage and Resend's
// REST API for email. Until EVERY variable below is set in the Vercel project, config() returns null and every
// endpoint answers 503: nothing is stored and nothing is sent (fail closed).
//
//   KV_REST_API_URL, KV_REST_API_TOKEN   Upstash Redis REST (Vercel Marketplace "Upstash for Redis" sets both)
//   RESEND_API_KEY                       Resend API key (sending access only)
//   DIGEST_FROM                          e.g. "The Book of Daniel <updates@example.org>" (a Resend-verified domain)
//   DIGEST_REPLY_TO                      where replies go
//   CRON_SECRET                          Vercel sends it as "Authorization: Bearer ..." to api/digest
//   SUBSCRIBE_SECRET                     signs confirmation and unsubscribe links (32+ random characters)
//   DIGEST_POSTAL_ADDRESS                the footer's postal address (or settings.publish.digest.postal_address)
//
// Privacy: an email address is never logged. A subscriber record holds only email, status, created/confirmed
// timestamps and the hash of the pending confirmation token. Unsubscribing deletes the record.
const crypto = require("crypto");

let CFG = {};
try { CFG = require("./_lineage-config.json"); } catch { CFG = {}; }

const NEED = ["KV_REST_API_URL", "KV_REST_API_TOKEN", "RESEND_API_KEY", "DIGEST_FROM", "DIGEST_REPLY_TO",
  "CRON_SECRET", "SUBSCRIBE_SECRET"];
const CLOSED = "Subscriptions are not open yet. Follow the RSS feed meanwhile.";
const PENDING_TTL = 7 * 24 * 3600;          // an unconfirmed address is forgotten after a week

function env(k) { return String(process.env[k] || "").trim(); }

function config() {
  const v = {};
  for (const k of NEED) { v[k] = env(k); if (!v[k]) return null; }
  if (v.SUBSCRIBE_SECRET.length < 16) return null;
  const postal = env("DIGEST_POSTAL_ADDRESS") || String(CFG.postal_address || "").trim();
  const site = (env("SITE_URL") || String(CFG.site_url || "")).replace(/\/+$/, "");
  if (!postal || !/^https?:\/\//.test(site)) return null;
  return {
    kv: { url: v.KV_REST_API_URL.replace(/\/+$/, ""), token: v.KV_REST_API_TOKEN },
    resend: { key: v.RESEND_API_KEY, base: (env("RESEND_API_BASE") || "https://api.resend.com").replace(/\/+$/, "") },
    from: v.DIGEST_FROM, replyTo: v.DIGEST_REPLY_TO, cron: v.CRON_SECRET, secret: v.SUBSCRIBE_SECRET,
    postal, site, title: String(CFG.title || "The family book"), sender: String(CFG.sender_line || ""),
    prefix: `lineage:${String(CFG.slug || "site").replace(/[^a-z0-9-]/g, "")}:`,
    slash: CFG.trailing_slash === true ? "/" : "",
  };
}

// ------------------------------------------------------------------------------------------- Upstash Redis REST
async function kv(c, ...args) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 8000);
  try {
    const r = await fetch(c.kv.url, {
      method: "POST",
      headers: { Authorization: `Bearer ${c.kv.token}`, "Content-Type": "application/json" },
      body: JSON.stringify(args.map(String)),
      signal: ctl.signal,
    });
    if (!r.ok) throw new Error(`store HTTP ${r.status}`);
    const j = await r.json();
    if (j.error) throw new Error("store error");
    return j.result;
  } finally { clearTimeout(t); }
}

// ------------------------------------------------------------------------------------------------- Resend REST
async function sendEmail(c, msg, idempotencyKey) {
  const headers = { Authorization: `Bearer ${c.resend.key}`, "Content-Type": "application/json" };
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 10000);
  try {
    const r = await fetch(`${c.resend.base}/emails`, {
      method: "POST", headers, signal: ctl.signal,
      body: JSON.stringify({ from: c.from, reply_to: c.replyTo, ...msg }),
    });
    return r.ok;
  } catch { return false; } finally { clearTimeout(t); }
}

// ------------------------------------------------------------------------------------------- ids and tokens
const b64u = b => Buffer.from(b).toString("base64url");
const hmac = (c, s) => b64u(crypto.createHmac("sha256", c.secret).update(s).digest());
const sha = s => crypto.createHash("sha256").update(s).digest("hex");
function same(a, b) {
  const x = Buffer.from(String(a)), y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}
// a subscriber's id: a keyed hash of the address, so keys in the store do not reveal it
const subId = (c, email) => crypto.createHmac("sha256", c.secret).update("id:" + email).digest("hex").slice(0, 32);
const subKey = (c, id) => `${c.prefix}sub:${id}`;
const confirmedSet = c => `${c.prefix}confirmed`;

function confirmToken(c, id) {
  const nonce = b64u(crypto.randomBytes(18));
  return { token: `${id}.${nonce}.${hmac(c, `confirm:${id}.${nonce}`)}`, hash: sha(nonce) };
}
function readConfirmToken(c, t) {
  const m = /^([0-9a-f]{32})\.([A-Za-z0-9_-]{10,64})\.([A-Za-z0-9_-]{20,64})$/.exec(String(t || ""));
  if (!m || !same(m[3], hmac(c, `confirm:${m[1]}.${m[2]}`))) return null;
  return { id: m[1], hash: sha(m[2]) };
}
const unsubToken = (c, id) => `${id}.${hmac(c, `unsub:${id}`)}`;
function readUnsubToken(c, t) {
  const m = /^([0-9a-f]{32})\.([A-Za-z0-9_-]{20,64})$/.exec(String(t || ""));
  return m && same(m[2], hmac(c, `unsub:${m[1]}`)) ? m[1] : null;
}
const apiUrl = (c, name, token) => `${c.site}/api/${name}${c.slash}?t=${encodeURIComponent(token)}`;

// Google sign-in is optional. Email double opt-in works without it. Both client values must be set;
// nothing here is a default credential.
function googleOn() {
  const id = env("GOOGLE_CLIENT_ID"), secret = env("GOOGLE_CLIENT_SECRET");
  if (!id || !secret) return null;
  return {
    id, secret,
    auth: env("GOOGLE_AUTH_URL") || "https://accounts.google.com/o/oauth2/v2/auth",
    token: env("GOOGLE_TOKEN_URL") || "https://oauth2.googleapis.com/token",
    userinfo: env("GOOGLE_USERINFO_URL") || "https://openidconnect.googleapis.com/v1/userinfo",
  };
}
const googleRedirect = c => `${c.site}/api/google${c.slash}`;
function oauthState(c) {
  const exp = Date.now() + 10 * 60 * 1000;
  const nonce = b64u(crypto.randomBytes(16));
  const payload = `${exp}.${nonce}`;
  return `${payload}.${hmac(c, "gstate:" + payload)}`;
}
function readOauthState(c, t) {
  const m = /^(\d{10,})\.([A-Za-z0-9_-]{8,})\.([A-Za-z0-9_-]{20,})$/.exec(String(t || ""));
  if (!m || Number(m[1]) < Date.now() || !same(m[3], hmac(c, `gstate:${m[1]}.${m[2]}`))) return null;
  return m[0];
}
function cookieVal(req, name) {
  for (const part of String((req.headers && req.headers.cookie) || "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0 && part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return "";
}

// ---------------------------------------------------------------------------------------------- HTTP helpers
async function readBody(req) {
  if (req.body && typeof req.body === "object" && !Buffer.isBuffer(req.body)) return req.body;
  let raw = typeof req.body === "string" ? req.body : Buffer.isBuffer(req.body) ? req.body.toString("utf8") : null;
  if (raw == null) {
    const chunks = []; let size = 0;
    for await (const ch of req) { size += ch.length; if (size > 8192) return {}; chunks.push(ch); }
    raw = Buffer.concat(chunks).toString("utf8");
  }
  try { return JSON.parse(raw); } catch { /* a plain form post */ }
  return Object.fromEntries(new URLSearchParams(raw));
}
const wantsHtml = req => /text\/html/.test(String(req.headers.accept || "")) && !/application\/json/.test(String(req.headers.accept || ""));
const esc = s => String(s).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));

function page(res, status, title, message, c) {
  const site = c ? c.site : String(CFG.site_url || "").replace(/\/+$/, "");
  const name = c ? c.title : String(CFG.title || "");
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Robots-Tag", "noindex");
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.status(status).send(`<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>${esc(title)}${name ? " · " + esc(name) : ""}</title>
<style>:root{--ink:#1d1a17;--paper:#f8f5ee;--rubric:#b3261e;--muted:#6b645b}
@media (prefers-color-scheme: dark){:root{--ink:#ece6da;--paper:#171512;--rubric:#e0574d;--muted:#a59d90}}
body{margin:0;background:var(--paper);color:var(--ink);font:19px/1.6 "EB Garamond",Georgia,serif}
.wrap{max-width:760px;margin:0 auto;padding:48px 16px}a{color:var(--rubric)}h1{font-weight:400;color:var(--rubric)}</style>
</head><body><div class="wrap"><h1>${esc(title)}</h1><p>${esc(message)}</p>
<p><a href="${esc(site || "/")}/updates/">Back to the updates</a></p></div></body></html>`);
}
function closed(req, res) {
  res.setHeader("Retry-After", "86400");
  if (wantsHtml(req)) return page(res, 503, "Not open yet", CLOSED, null);
  res.setHeader("Cache-Control", "no-store");
  res.status(503).json({ ok: false, open: false, message: CLOSED });
}

module.exports = {
  CFG, CLOSED, PENDING_TTL, config, kv, sendEmail, subId, subKey, confirmedSet, sha, same,
  confirmToken, readConfirmToken, unsubToken, readUnsubToken, apiUrl, readBody, wantsHtml, esc, page, closed,
  googleOn, googleRedirect, oauthState, readOauthState, cookieVal,
};
