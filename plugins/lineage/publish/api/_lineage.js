// Shared code for a family site's subscription functions (api/subscribe.js, confirm.js, unsubscribe.js,
// digest.js, google.js, notify.js, account.js).
// Not a route: files starting with "_" are not functions. Copied into the built site by updates_page.py, with
// _lineage-config.json (site_url, title, slug, sender line, postal address, app_path from lineage.json).
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
  const appPath = "/" + String(CFG.app_path || "/lineage/").replace(/^\/+|\/+$/g, "") + "/";
  const notifyFrom = env("NOTIFY_FROM") || v.DIGEST_FROM;
  const owner = env("OWNER_NOTIFY_EMAIL").toLowerCase();
  const unsubFlag = env("OWNER_NOTIFY_UNSUBSCRIBES").toLowerCase();
  return {
    kv: { url: v.KV_REST_API_URL.replace(/\/+$/, ""), token: v.KV_REST_API_TOKEN },
    resend: { key: v.RESEND_API_KEY, base: (env("RESEND_API_BASE") || "https://api.resend.com").replace(/\/+$/, "") },
    from: v.DIGEST_FROM, replyTo: v.DIGEST_REPLY_TO, cron: v.CRON_SECRET, secret: v.SUBSCRIBE_SECRET,
    postal, site, title: String(CFG.title || "The family book"), sender: String(CFG.sender_line || ""),
    prefix: `lineage:${String(CFG.slug || "site").replace(/[^a-z0-9-]/g, "")}:`,
    slash: CFG.trailing_slash === true ? "/" : "",
    // Subscriber mail uses NOTIFY_FROM when Rex has set it, otherwise the existing DIGEST_FROM.
    notifyFrom, owner,
    admin: env("ADMIN_SECRET"),
    sessionSecret: env("SESSION_SECRET"),
    webhook: env("RESEND_WEBHOOK_SECRET"),
    appPath,
    // Unsubscribe notes are on unless OWNER_NOTIFY_UNSUBSCRIBES is explicitly false.
    unsubAlerts: !!owner && !["false", "0", "no", "off"].includes(unsubFlag),
  };
}

// Path only, as posted by the form. Anything else is dropped.
const SOURCE_RE = /^\/[A-Za-z0-9/_.#?=-]{0,200}$/;
function sourceOk(s) {
  const t = String(s == null ? "" : s).slice(0, 200);
  return SOURCE_RE.test(t) ? t : "";
}

function subscriberFrom(c) { return env("NOTIFY_FROM") || c.from; }
function sessionReady(c) { return !!(c && c.sessionSecret && c.sessionSecret.length >= 16); }
function adminReady(c) { return !!(c && c.admin && c.admin.length >= 16); }

function frequencyOf(rec) {
  const f = rec && rec.frequency;
  return f === "each" || f === "weekly" || f === "paused" ? f : "weekly";
}
function pausedNow(rec, now) {
  if (!rec) return true;
  if (frequencyOf(rec) === "paused") return true;
  const until = String(rec.paused_until || "");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(until)) return false;
  const today = (now || new Date()).toISOString().slice(0, 10);
  return until >= today;
}
function wantsEach(rec) { return rec && rec.status === "confirmed" && rec.email && rec.frequency === "each" && !pausedNow(rec); }
function wantsWeekly(rec) { return rec && rec.status === "confirmed" && rec.email && frequencyOf(rec) === "weekly" && !pausedNow(rec); }

function ptStamp(iso) {
  try {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: "America/Los_Angeles",
      year: "numeric", month: "long", day: "numeric",
      hour: "numeric", minute: "2-digit", timeZoneName: "short",
    }).format(new Date(iso));
  } catch { return String(iso || ""); }
}

function managePage(c) { return `${c.site}${c.appPath}#account`; }

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
function mailPayload(c, msg) {
  const row = Object.assign({ from: subscriberFrom(c), reply_to: c.replyTo }, msg);
  if (msg.reply_to === false) delete row.reply_to;
  return row;
}
async function postResend(c, path, payload, idempotencyKey) {
  const headers = { Authorization: `Bearer ${c.resend.key}`, "Content-Type": "application/json" };
  if (idempotencyKey) headers["Idempotency-Key"] = String(idempotencyKey).slice(0, 256);
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 15000);
  try {
    const r = await fetch(`${c.resend.base}${path}`, {
      method: "POST", headers, signal: ctl.signal, body: JSON.stringify(payload),
    });
    const retryAfter = Number(r.headers.get("retry-after") || 0) || 0;
    return { ok: r.ok, status: r.status, retryAfter };
  } catch { return { ok: false, status: 0, retryAfter: 0 }; } finally { clearTimeout(t); }
}
async function sendEmail(c, msg, idempotencyKey) {
  const r = await postResend(c, "/emails", mailPayload(c, msg), idempotencyKey);
  return r.ok;
}
const BATCH = Math.max(1, Math.min(100, Number(process.env.LINEAGE_EMAIL_BATCH || 100) || 100));
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
async function sendBatch(c, messages, idempotencyKey) {
  let wait = 0;
  for (let attempt = 0; attempt < 4; attempt++) {
    if (wait) await sleep(Math.min(wait, 2000));
    const r = await postResend(c, "/emails/batch", messages.map(m => mailPayload(c, m)), idempotencyKey);
    if (r.status !== 429) return r;
    wait = Math.max(1, (r.retryAfter || 1)) * 1000;
  }
  return { ok: false, status: 429, retryAfter: 0 };
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
function oauthState(c, extra) {
  const mode = extra && (extra.mode === "signin" || extra.mode === "both") ? extra.mode : "subscribe";
  const body = { exp: Date.now() + 10 * 60 * 1000, nonce: b64u(crypto.randomBytes(16)), mode, source: sourceOk(extra && extra.source) };
  const payload = b64u(Buffer.from(JSON.stringify(body)));
  return `${payload}.${hmac(c, "gstate:" + payload)}`;
}
function readOauthState(c, t) {
  const m = /^([A-Za-z0-9_-]{10,})\.([A-Za-z0-9_-]{20,})$/.exec(String(t || ""));
  if (!m || !same(m[2], hmac(c, "gstate:" + m[1]))) return null;
  let body;
  try { body = JSON.parse(Buffer.from(m[1], "base64url").toString("utf8")); } catch { return null; }
  if (!body || Number(body.exp) < Date.now()) return null;
  body.token = m[0];
  body.mode = body.mode === "signin" || body.mode === "both" ? body.mode : "subscribe";
  body.source = sourceOk(body.source);
  return body;
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

function page(res, status, title, message, c, link) {
  const site = c ? c.site : String(CFG.site_url || "").replace(/\/+$/, "");
  const name = c ? c.title : String(CFG.title || "");
  const extra = link && link.href
    ? `<p><a href="${esc(link.href)}">${esc(link.text || "Manage my subscription")}</a></p>` : "";
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
${extra}
<p><a href="${esc(site || "/")}/updates/">Back to the updates</a></p></div></body></html>`);
}
function alreadyPayload(c) {
  return { ok: true, status: "already", already: true, manage_url: managePage(c), message: "You are already subscribed." };
}
function alreadyPage(res, c) {
  return page(res, 200, "You are already subscribed", "You are already subscribed.", c, { href: managePage(c), text: "Manage my subscription" });
}
function closed(req, res) {
  res.setHeader("Retry-After", "86400");
  if (wantsHtml(req)) return page(res, 503, "Not open yet", CLOSED, null);
  res.setHeader("Cache-Control", "no-store");
  res.status(503).json({ ok: false, open: false, message: CLOSED });
}

// ------------------------------------------------------------------------------------------- sessions and links
const LINK_TTL = 15 * 60;
const SESSION_MS = 30 * 24 * 3600 * 1000;
function manageToken(c, id) {
  const exp = Date.now() + 7 * 24 * 3600 * 1000;
  return `${id}.${exp}.${hmac(c, `manage:${id}.${exp}`)}`;
}
function readManageToken(c, t) {
  const m = /^([0-9a-f]{32})\.(\d{10,})\.([A-Za-z0-9_-]{20,})$/.exec(String(t || ""));
  if (!m || Number(m[2]) < Date.now() || !same(m[3], hmac(c, `manage:${m[1]}.${m[2]}`))) return null;
  return m[1];
}
function linkToken(c, email) {
  const id = subId(c, email);
  const nonce = b64u(crypto.randomBytes(18));
  const exp = Date.now() + LINK_TTL * 1000;
  return { id, token: `${id}.${exp}.${nonce}.${hmac(c, `link:${id}.${exp}.${nonce}`)}`, hash: sha(nonce), exp };
}
function readLinkToken(c, t) {
  const m = /^([0-9a-f]{32})\.(\d{10,})\.([A-Za-z0-9_-]{10,64})\.([A-Za-z0-9_-]{20,})$/.exec(String(t || ""));
  if (!m || Number(m[2]) < Date.now() || !same(m[4], hmac(c, `link:${m[1]}.${m[2]}.${m[3]}`))) return null;
  return { id: m[1], hash: sha(m[3]) };
}
function emailChangeToken(c, id, email) {
  const nonce = b64u(crypto.randomBytes(18));
  const exp = Date.now() + PENDING_TTL * 1000;
  return { token: `${id}.${exp}.${nonce}.${hmac(c, `email:${id}.${exp}.${nonce}`)}`, hash: sha(nonce + ":" + email) };
}
function readEmailChangeToken(c, t) {
  const m = /^([0-9a-f]{32})\.(\d{10,})\.([A-Za-z0-9_-]{10,64})\.([A-Za-z0-9_-]{20,})$/.exec(String(t || ""));
  if (!m || Number(m[2]) < Date.now() || !same(m[4], hmac(c, `email:${m[1]}.${m[2]}.${m[3]}`))) return null;
  return { id: m[1], nonce: m[3] };
}
function sessionToken(c, id) {
  const exp = Date.now() + SESSION_MS;
  const jti = b64u(crypto.randomBytes(12));
  const body = `${id}.${exp}.${jti}`;
  return { token: `${body}.${hmacSession(c, body)}`, id, exp, jti };
}
function hmacSession(c, s) { return b64u(crypto.createHmac("sha256", c.sessionSecret).update(s).digest()); }
function readSession(c, t) {
  if (!sessionReady(c)) return null;
  const m = /^([0-9a-f]{32})\.(\d{10,})\.([A-Za-z0-9_-]{8,})\.([A-Za-z0-9_-]{20,})$/.exec(String(t || ""));
  if (!m || Number(m[2]) < Date.now() || !same(m[4], hmacSession(c, `${m[1]}.${m[2]}.${m[3]}`))) return null;
  return { id: m[1], exp: Number(m[2]), jti: m[3] };
}
function csrfFor(c, sess) { return hmacSession(c, `csrf:${sess.id}.${sess.exp}.${sess.jti}`); }
function sessionCookie(c, token, maxAge) {
  const secure = c.site.startsWith("https://") ? "; Secure" : "";
  const age = maxAge == null ? Math.floor(SESSION_MS / 1000) : maxAge;
  return `lsess=${token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=${age}${secure}`;
}
async function confirmedCount(c) { return Number(await kv(c, "SCARD", confirmedSet(c)) || 0); }
async function issueSession(c, id) {
  const curKey = `${c.prefix}sess:current:${id}`;
  const prev = await kv(c, "GET", curKey);
  if (prev) await kv(c, "SET", `${c.prefix}sess:revoked:${prev}`, "1", "EX", 40 * 24 * 3600);
  const sess = sessionToken(c, id);
  await kv(c, "SET", curKey, sess.jti);
  return sess;
}
async function sessionLive(c, sess) {
  if (!sess) return false;
  if (await kv(c, "GET", `${c.prefix}sess:revoked:${sess.jti}`)) return false;
  return true;
}
function userKey(c, id) { return `${c.prefix}user:${id}`; }

const rateHits = new Map();
async function limited(c, req, bucket, max) {
  const cap = max || 5;
  const ip = String(req.headers["x-forwarded-for"] || req.socket?.remoteAddress || "anon").split(",")[0].trim();
  const who = sha(c.secret + ":" + bucket + ":" + ip).slice(0, 24);
  const now = Date.now();
  const recent = (rateHits.get(who) || []).filter(t => now - t < 3600 * 1000);
  recent.push(now); rateHits.set(who, recent);
  if (recent.length > cap) return true;
  const key = `${c.prefix}rl:${bucket}:${who}:${Math.floor(now / 3600000)}`;
  const n = await kv(c, "INCR", key);
  if (n === 1) await kv(c, "EXPIRE", key, 3600);
  return n > cap;
}
function bearerMatch(c, req, secret) {
  if (!secret) return false;
  return same(String(req.headers.authorization || ""), `Bearer ${secret}`);
}

// ---------------------------------------------------------------------------------------------- owner alerts
async function ownerNote(c, kind, rec, id, method) {
  if (!c.owner) return false;
  if (kind === "unsub" && !c.unsubAlerts) return false;
  let n = 0;
  try { n = await confirmedCount(c); } catch { n = 0; }
  const when = ptStamp((rec && rec.confirmed) || new Date().toISOString());
  const subject = kind === "unsub"
    ? `Unsubscribed from ${c.title} (${n} total)`
    : `New subscriber to ${c.title} (${n} total)`;
  const lines = [
    kind === "unsub" ? "Someone unsubscribed." : "Someone new confirmed a subscription.",
    "",
    `Email: ${rec.email}`,
    `When: ${when}`,
    `Method: ${method || rec.method || ""}`,
    `Page: ${rec.source || "(not recorded)"}`,
    `Confirmed subscribers: ${n}`,
  ];
  const html = `<div style="font:16px/1.6 Georgia,serif;color:#1d1a17;max-width:560px"><p>${esc(lines[0])}</p><ul>` +
    lines.slice(2).map(x => `<li>${esc(x)}</li>`).join("") + "</ul></div>";
  const key = kind === "unsub" ? `owner-unsub-${id}-${sha(String(rec.confirmed || rec.email)).slice(0, 12)}` : `owner-new-${id}`;
  try {
    return await sendEmail(c, {
      from: c.notifyFrom, reply_to: false, to: [c.owner], subject, text: lines.join("\n") + "\n", html,
    }, key);
  } catch { return false; }
}

function listHeaders(c, unsub) {
  const mail = c.replyTo ? `, <mailto:${c.replyTo}?subject=unsubscribe>` : "";
  return { "List-Unsubscribe": `<${unsub}>${mail}`, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click" };
}
function footerBits(c, links) {
  const text = ["", "--", c.sender, c.postal, `Manage my subscription: ${links.manage}`, `Unsubscribe (one click): ${links.unsub}`];
  const html = `<hr style="border:0;border-top:1px solid #d9d2c4;margin:24px 0 10px">
<p style="color:#6b645b;font-size:13px">${c.sender ? esc(c.sender) + "<br>" : ""}${esc(c.postal)}<br>
<a href="${esc(links.manage)}" style="color:#6b645b">Manage my subscription</a><br>
<a href="${esc(links.unsub)}" style="color:#6b645b">Unsubscribe with one click</a>.</p>`;
  return { text, html };
}
function subscriberLinks(c, id, test) {
  if (test) {
    return {
      unsub: `${c.site}/api/unsubscribe/?t=test-link-not-valid`,
      manage: `${c.site}/api/account/?op=manage&t=test-link-not-valid`,
    };
  }
  return { unsub: apiUrl(c, "unsubscribe", unsubToken(c, id)), manage: `${c.site}/api/account${c.slash}?op=manage&t=${encodeURIComponent(manageToken(c, id))}` };
}
function renderPostEmail(c, post, links) {
  const url = c.site + (post.url || "/");
  const nice = post.date || "";
  const text = [post.title, "", post.summary || "", url, ...footerBits(c, links).text].join("\n");
  const img = post.image ? `<img src="${esc(post.image.startsWith("http") ? post.image : c.site + post.image)}" alt="" width="560" style="max-width:100%;height:auto;border-radius:4px;display:block;margin:0 0 8px">` : "";
  const html = `<div style="font:16px/1.6 Georgia,serif;color:#1d1a17;max-width:600px">
<p style="color:#6b645b;margin:0 0 8px">${esc(c.title)}</p>
${img}<p style="margin:0 0 8px"><a href="${esc(url)}" style="color:#b3261e;font-size:20px">${esc(post.title)}</a></p>
${nice ? `<p style="color:#6b645b;font-size:14px;margin:0 0 8px">${esc(nice)}</p>` : ""}
${post.summary ? `<p>${esc(post.summary)}</p>` : ""}
${footerBits(c, links).html}</div>`;
  return { subject: post.title || c.title, text, html };
}
function renderDigestEmail(c, posts, entries, links) {
  const lines = [];
  for (const e of entries || []) for (const x of e.changes || []) lines.push(x);
  const shown = lines.slice(0, 40);
  const more = lines.length - shown.length;
  const T = [`${c.title}: this week`, ""];
  let H = `<div style="font:16px/1.6 Georgia,serif;color:#1d1a17;max-width:600px">
<h1 style="font-weight:400;color:#b3261e;font-size:26px;margin:0 0 4px">${esc(c.title)}</h1>
<p style="color:#6b645b;margin:0 0 18px">What's new this week</p>`;
  if (posts.length) {
    T.push("NEW POSTS", "");
    H += `<h2 style="font-size:19px;margin:18px 0 6px">New posts</h2>`;
    for (const p of posts) {
      const url = c.site + p.url;
      T.push(`${p.title} (${p.date || ""})`, p.summary || "", url, "");
      H += `<p style="margin:0 0 14px">${p.image ? `<img src="${esc(String(p.image).startsWith("http") ? p.image : c.site + p.image)}" alt="" width="560" style="max-width:100%;height:auto;border-radius:4px;display:block;margin:0 0 6px">` : ""}` +
        `<a href="${esc(url)}" style="color:#b3261e;font-size:18px">${esc(p.title)}</a>` +
        `${p.summary ? `<br>${esc(p.summary)}` : ""}</p>`;
    }
  }
  if (shown.length) {
    T.push("CHANGES TO THE SITE", "");
    H += `<h2 style="font-size:19px;margin:18px 0 6px">Changes to the site</h2><ul style="padding-left:20px">`;
    for (const x of shown) { T.push("- " + x); H += `<li style="margin:0 0 6px">${esc(x)}</li>`; }
    H += "</ul>";
    if (more > 0) { T.push(`and ${more} more`); H += `<p>and ${more} more.</p>`; }
    T.push("", `Everything: ${c.site}/changelog/`);
    H += `<p><a href="${esc(c.site)}/changelog/" style="color:#b3261e">The full changelog</a></p>`;
  }
  const foot = footerBits(c, links);
  return { subject: `${c.title}: what's new this week`, text: T.concat(foot.text).join("\n"), html: H + foot.html + "</div>" };
}

function verifySvix(secret, headers, raw) {
  const id = headers["svix-id"], ts = headers["svix-timestamp"], sig = headers["svix-signature"];
  if (!secret || !id || !ts || !sig || !raw) return false;
  const now = Date.now() / 1000;
  if (Math.abs(now - Number(ts)) > 300) return false;
  let key;
  try { key = Buffer.from(String(secret).replace(/^whsec_/, ""), "base64"); } catch { return false; }
  if (!key.length) return false;
  const expect = crypto.createHmac("sha256", key).update(`${id}.${ts}.${raw}`).digest("base64");
  return String(sig).split(" ").some(part => {
    const s = part.startsWith("v1,") ? part.slice(3) : "";
    const a = Buffer.from(s), b = Buffer.from(expect);
    return a.length === b.length && a.length > 0 && crypto.timingSafeEqual(a, b);
  });
}

async function rawBody(req) {
  if (typeof req.body === "string") return req.body;
  if (Buffer.isBuffer(req.body)) return req.body.toString("utf8");
  if (req.rawBody) return String(req.rawBody);
  if (req.body && typeof req.body === "object") return null;
  const chunks = []; let size = 0;
  for await (const ch of req) { size += ch.length; if (size > 65536) return ""; chunks.push(ch); }
  return Buffer.concat(chunks).toString("utf8");
}

module.exports = {
  CFG, CLOSED, PENDING_TTL, LINK_TTL, BATCH, config, kv, sendEmail, sendBatch, sleep, postResend,
  subId, subKey, confirmedSet, sha, same, confirmToken, readConfirmToken, unsubToken, readUnsubToken, apiUrl,
  readBody, rawBody, wantsHtml, esc, page, closed, alreadyPayload, alreadyPage,
  googleOn, googleRedirect, oauthState, readOauthState, cookieVal,
  sourceOk, subscriberFrom, sessionReady, adminReady, frequencyOf, pausedNow, wantsEach, wantsWeekly, ptStamp, managePage,
  manageToken, readManageToken, linkToken, readLinkToken, emailChangeToken, readEmailChangeToken,
  sessionToken, readSession, csrfFor, sessionCookie, confirmedCount, issueSession, sessionLive, userKey,
  limited, bearerMatch, ownerNote,
  listHeaders, subscriberLinks, renderPostEmail, renderDigestEmail, verifySvix,
};
