// The "Subscribe" form on /updates/, each post and /changelog/.
//   GET  /api/subscribe   200 {open: true} once configured, else 503 {open: false} (the form stays closed)
//   POST /api/subscribe   {email, website (honeypot)} as JSON or a plain form post
// Double opt-in: the address is stored as "pending" (forgotten after 7 days) and a confirmation link is emailed;
// only api/confirm makes it a subscriber. The same answer is given whether or not the address is already known.
const L = require("./_lineage.js");

const RATE = { windowS: 3600, max: 5 };        // per visitor per hour (hashed IP; the IP itself is never stored)
const hits = new Map();
const OK = "Thank you. Check your inbox for a link to confirm your subscription.";
const FAIL = "Sorry, that didn't go through. Please try again later, or follow the RSS feed.";

function clean(s, max) {
  return String(s == null ? "" : s).normalize("NFKC").replace(/[\u0000-\u001f\u007f<>]/g, "").trim().slice(0, max);
}

function reply(req, res, status, ok, message, c) {
  if (L.wantsHtml(req)) return L.page(res, status, ok ? "Almost done" : "Not subscribed", message, c);
  res.setHeader("Cache-Control", "no-store");
  res.status(status).json({ ok, message });
}

async function limited(c, req) {
  const ip = String(req.headers["x-forwarded-for"] || req.socket?.remoteAddress || "anon").split(",")[0].trim();
  const who = L.sha(c.secret + ":" + ip).slice(0, 24);
  const now = Date.now();
  const recent = (hits.get(who) || []).filter(t => now - t < RATE.windowS * 1000);
  recent.push(now); hits.set(who, recent);
  if (recent.length > RATE.max) return true;
  const key = `${c.prefix}rl:${who}:${Math.floor(now / (RATE.windowS * 1000))}`;
  const n = await L.kv(c, "INCR", key);
  if (n === 1) await L.kv(c, "EXPIRE", key, RATE.windowS);
  return n > RATE.max;
}

function confirmEmail(c, link) {
  const text = `Please confirm that you want the weekly digest of ${c.title}: new posts and changes to ${c.site}, ` +
    `once a week.\n\nConfirm: ${link}\n\nIf you did not ask for this, ignore this email and the address is ` +
    `forgotten within a week.\n\n${c.sender ? c.sender + "\n" : ""}${c.postal}\n`;
  const html = `<div style="font:16px/1.6 Georgia,serif;color:#1d1a17;max-width:560px">
<p>Please confirm that you want the weekly digest of <b>${L.esc(c.title)}</b>: new posts and changes to the site, once a week.</p>
<p><a href="${L.esc(link)}" style="display:inline-block;padding:10px 18px;background:#b3261e;color:#fff;text-decoration:none;border-radius:6px">Confirm my subscription</a></p>
<p style="color:#6b645b;font-size:14px">If you did not ask for this, ignore this email and the address is forgotten within a week.</p>
<p style="color:#6b645b;font-size:13px">${c.sender ? L.esc(c.sender) + "<br>" : ""}${L.esc(c.postal)}</p></div>`;
  return { subject: `Confirm your subscription to ${c.title}`, text, html };
}

module.exports = async function handler(req, res) {
  res.setHeader("X-Robots-Tag", "noindex");
  const c = L.config();
  if (!c) return L.closed(req, res);
  if (req.method === "GET" || req.method === "HEAD") {
    res.setHeader("Cache-Control", "no-store");
    const g = L.googleOn();
    return res.status(200).json({
      ok: true, open: true, google: !!g,
      google_url: g ? L.googleRedirect(c) : null,
    });
  }
  if (req.method !== "POST") return reply(req, res, 405, false, "Please use the form on the page.", c);

  const b = await L.readBody(req);
  if (clean(b.website, 200)) return reply(req, res, 200, true, OK, c);          // honeypot: pretend, do nothing
  const email = clean(b.email, 254).toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return reply(req, res, 400, false, "Please check your email address.", c);

  try {
    if (await limited(c, req)) return reply(req, res, 429, false, "Too many sign-ups from here. Please try again in an hour.", c);
    const id = L.subId(c, email);
    const key = L.subKey(c, id);
    const cur = JSON.parse((await L.kv(c, "GET", key)) || "null");
    if (cur && cur.status === "confirmed") return reply(req, res, 200, true, OK, c);   // already subscribed: say nothing more
    const { token, hash } = L.confirmToken(c, id);
    const rec = { email, status: "pending", created: (cur && cur.created) || new Date().toISOString(), confirmed: null, token_hash: hash };
    await L.kv(c, "SET", key, JSON.stringify(rec), "EX", L.PENDING_TTL);
    const sent = await L.sendEmail(c, { to: [email], ...confirmEmail(c, L.apiUrl(c, "confirm", token)) });
    if (!sent) {
      await L.kv(c, "DEL", key);
      console.error("subscribe: confirmation email not accepted by the mail service");   // never the address
      return reply(req, res, 502, false, FAIL, c);
    }
    return reply(req, res, 200, true, OK, c);
  } catch {
    console.error("subscribe: store unavailable");
    return reply(req, res, 503, false, FAIL, c);
  }
};
