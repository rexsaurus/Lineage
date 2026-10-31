// One router for sign-in, subscription management, the owner test email and the Resend webhook.
//   GET  /api/account/?op=me
//   POST /api/account/?op=link          {email} magic link, same answer either way
//   GET  /api/account/?op=verify&t=
//   POST /api/account/?op=signout       header X-Lineage-CSRF
//   POST /api/account/?op=prefs         {frequency, paused_until}
//   POST /api/account/?op=unsubscribe
//   POST /api/account/?op=change-email  {email}
//   GET  /api/account/?op=confirm-email&t=
//   POST /api/account/?op=delete        {confirm:"delete"}
//   POST /api/account/?op=test          Bearer ADMIN_SECRET, or the owner session. Only the owner address.
//   POST /api/account/?op=resend-webhook
//   GET  /api/account/?op=manage        no-JS page. ?t= a 7 day manage link signs that subscription in.
// Fails closed (503) when SESSION_SECRET is missing, except the webhook which needs RESEND_WEBHOOK_SECRET
// and the test send which needs ADMIN_SECRET. State-changing posts need the CSRF value from op=me.
const L = require("./_lineage.js");

function queryOf(req) {
  const q = Object.assign({}, req.query || {});
  try {
    const u = new URL(req.url || "/", "http://localhost");
    for (const [k, v] of u.searchParams) if (q[k] == null) q[k] = v;
  } catch { /* req.url is not always a full URL */ }
  return q;
}
function cleanEmail(s) {
  return String(s == null ? "" : s).normalize("NFKC").replace(/[\u0000-\u001f\u007f<>]/g, "").trim().toLowerCase().slice(0, 254);
}
function emailOk(e) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(e); }

async function loadSession(c, req) {
  if (!L.sessionReady(c)) return null;
  const sess = L.readSession(c, L.cookieVal(req, "lsess"));
  if (!sess || !(await L.sessionLive(c, sess))) return null;
  return sess;
}
function setSess(c, res, sess) { res.setHeader("Set-Cookie", L.sessionCookie(c, sess.token)); }
async function csrfOk(c, req, sess) {
  if (!sess) return false;
  const got = String(req.headers["x-lineage-csrf"] || "");
  return !!got && L.same(got, L.csrfFor(c, sess));
}
async function ensureUser(c, email, extra) {
  const id = L.subId(c, email);
  const key = L.userKey(c, id);
  const cur = JSON.parse((await L.kv(c, "GET", key)) || "null") || {};
  const rec = Object.assign({ email, created: cur.created || new Date().toISOString() }, cur, extra || {}, { email });
  await L.kv(c, "SET", key, JSON.stringify(rec));
  return { id, rec };
}

async function me(c, req, res) {
  if (!L.sessionReady(c)) return res.status(503).json({ ok: false, open: false, status: "not-configured" });
  const sess = await loadSession(c, req);
  if (!sess) return res.status(200).json({ ok: true, open: true, signed_in: false });
  const user = JSON.parse((await L.kv(c, "GET", L.userKey(c, sess.id))) || "null");
  const sub = JSON.parse((await L.kv(c, "GET", L.subKey(c, sess.id))) || "null");
  const email = (user && user.email) || (sub && sub.email) || "";
  const owner = !!(c.owner && email && email === c.owner);
  const body = {
    ok: true, open: true, signed_in: true, email, csrf: L.csrfFor(c, sess), owner,
    manage_url: L.managePage(c),
    subscriber: sub ? {
      status: sub.status, since: sub.confirmed || sub.created || null, method: sub.method || "",
      frequency: L.frequencyOf(sub), paused_until: sub.paused_until || "",
    } : { status: "none" },
  };
  if (owner) {
    try { body.confirmed_count = await L.confirmedCount(c); } catch { body.confirmed_count = null; }
  }
  res.setHeader("Cache-Control", "no-store");
  return res.status(200).json(body);
}

async function sendLink(c, req, res) {
  if (!L.sessionReady(c)) return res.status(503).json({ ok: false, status: "not-configured" });
  const b = await L.readBody(req);
  const email = cleanEmail(b.email);
  const same = { ok: true, message: "If that address can sign in, a link is on its way. It expires in 15 minutes." };
  if (!emailOk(email)) return res.status(400).json({ ok: false, message: "Please check your email address." });
  try {
    if (await L.limited(c, req, "link", 5)) return res.status(429).json({ ok: false, message: "Too many links from here. Please try again in an hour." });
    const { id, token, hash } = L.linkToken(c, email);
    await L.kv(c, "SET", `${c.prefix}link:${hash}`, JSON.stringify({ id, email }), "EX", L.LINK_TTL);
    const url = `${c.site}/api/account${c.slash}?op=verify&t=${encodeURIComponent(token)}`;
    const text = `Sign in to ${c.title}.\n\n${url}\n\nThis link works once and expires in 15 minutes. If you did not ask for it, ignore this email.\n`;
    const html = `<div style="font:16px/1.6 Georgia,serif;color:#1d1a17;max-width:560px"><p>Sign in to <b>${L.esc(c.title)}</b>.</p>
<p><a href="${L.esc(url)}" style="display:inline-block;padding:10px 18px;background:#8E1A14;color:#fff;text-decoration:none;border-radius:6px">Sign in</a></p>
<p style="color:#6b645b;font-size:14px">This link works once and expires in 15 minutes. If you did not ask for it, ignore this email.</p></div>`;
    const sent = await L.sendEmail(c, { from: c.notifyFrom, reply_to: false, to: [email], subject: `Sign in to ${c.title}`, text, html });
    if (!sent) return res.status(502).json({ ok: false, message: "Sorry, that did not go through. Please try again later." });
    return res.status(200).json(same);
  } catch {
    console.error("account: link store unavailable");
    return res.status(503).json({ ok: false, message: "Sorry, that did not go through. Please try again later." });
  }
}

async function verify(c, req, res, q) {
  if (!L.sessionReady(c)) return L.page(res, 503, "Not open yet", L.CLOSED, c);
  const tok = L.readLinkToken(c, q.t);
  if (!tok) return L.page(res, 400, "Link not valid", "This sign-in link is not valid or has expired. Ask for a new one.", c);
  try {
    const key = `${c.prefix}link:${tok.hash}`;
    const row = JSON.parse((await L.kv(c, "GET", key)) || "null");
    await L.kv(c, "DEL", key);
    if (!row || row.id !== tok.id || !emailOk(row.email)) return L.page(res, 400, "Link not valid", "This sign-in link was already used or has expired. Ask for a new one.", c);
    await ensureUser(c, row.email);
    const sess = await L.issueSession(c, tok.id);
    setSess(c, res, sess);
    res.setHeader("Location", L.managePage(c));
    return res.status(302).send("");
  } catch {
    console.error("account: verify failed");
    return L.page(res, 503, "Please try again", "Something went wrong on our side. Please try the link again later.", c);
  }
}

async function signOut(c, req, res, sess) {
  await L.kv(c, "SET", `${c.prefix}sess:revoked:${sess.jti}`, "1", "EX", 40 * 24 * 3600);
  await L.kv(c, "DEL", `${c.prefix}sess:current:${sess.id}`);
  res.setHeader("Set-Cookie", L.sessionCookie(c, "", 0));
  return res.status(200).json({ ok: true, signed_in: false });
}

async function prefs(c, req, res, sess) {
  const b = await L.readBody(req);
  const freq = ["each", "weekly", "paused"].includes(b.frequency) ? b.frequency : null;
  let until = String(b.paused_until || "");
  if (until && !/^\d{4}-\d{2}-\d{2}$/.test(until)) return res.status(400).json({ ok: false, message: "Use a date as YYYY-MM-DD, or leave it blank." });
  const key = L.subKey(c, sess.id);
  const rec = JSON.parse((await L.kv(c, "GET", key)) || "null");
  if (!rec || rec.status !== "confirmed") return res.status(404).json({ ok: false, message: "You are not subscribed yet." });
  if (freq) rec.frequency = freq;
  rec.paused_until = until || "";
  await L.kv(c, "SET", key, JSON.stringify(rec));
  return res.status(200).json({ ok: true, frequency: L.frequencyOf(rec), paused_until: rec.paused_until || "" });
}

async function dropSubscriber(c, id, reason) {
  const key = L.subKey(c, id);
  const rec = JSON.parse((await L.kv(c, "GET", key)) || "null");
  await L.kv(c, "DEL", key);
  await L.kv(c, "SREM", L.confirmedSet(c), id);
  if (rec && rec.email && reason === "unsubscribe") {
    try { await L.ownerNote(c, "unsub", rec, id, rec.method || ""); }
    catch (e) { console.error("account: unsubscribe note failed"); }
  }
  return rec;
}

async function changeEmail(c, req, res, sess) {
  const b = await L.readBody(req);
  const email = cleanEmail(b.email);
  if (!emailOk(email)) return res.status(400).json({ ok: false, message: "Please check your email address." });
  const id = sess.id;
  const key = L.subKey(c, id);
  const rec = JSON.parse((await L.kv(c, "GET", key)) || "null");
  if (!rec || !rec.email) return res.status(404).json({ ok: false, message: "No subscription to change." });
  if (email === String(rec.email).toLowerCase()) return res.status(200).json({ ok: true, message: "That is already the address on this subscription." });
  const other = L.subId(c, email);
  const taken = JSON.parse((await L.kv(c, "GET", L.subKey(c, other))) || "null");
  if (taken && taken.status === "confirmed") return res.status(409).json({ ok: false, message: "That address already has a subscription." });
  const { token, hash } = L.emailChangeToken(c, id, email);
  rec.pending_email = email;
  rec.pending_email_hash = hash;
  await L.kv(c, "SET", key, JSON.stringify(rec));
  const url = `${c.site}/api/account${c.slash}?op=confirm-email&t=${encodeURIComponent(token)}`;
  const text = `Confirm ${email} for ${c.title}.\n\n${url}\n\nIf you did not ask for this, ignore this email. The subscription stays on the old address.\n`;
  const html = `<div style="font:16px/1.6 Georgia,serif;color:#1d1a17"><p>Confirm this address for <b>${L.esc(c.title)}</b>.</p>
<p><a href="${L.esc(url)}">Confirm the new address</a></p>
<p style="color:#6b645b;font-size:14px">If you did not ask for this, ignore this email. The subscription stays on the old address.</p></div>`;
  const sent = await L.sendEmail(c, { from: c.notifyFrom, reply_to: false, to: [email], subject: `Confirm your new address for ${c.title}`, text, html });
  if (!sent) return res.status(502).json({ ok: false, message: "Sorry, that did not go through. Please try again later." });
  return res.status(200).json({ ok: true, message: "Check the new inbox for a confirmation link. Nothing changes until you open it." });
}

async function confirmEmail(c, req, res, q) {
  const tok = L.readEmailChangeToken(c, q.t);
  if (!tok) return L.page(res, 400, "Link not valid", "This confirmation link is not valid or has expired.", c);
  try {
    const key = L.subKey(c, tok.id);
    const rec = JSON.parse((await L.kv(c, "GET", key)) || "null");
    const email = rec && rec.pending_email;
    const expect = email ? L.sha(tok.nonce + ":" + email) : "";
    if (!rec || !email || !rec.pending_email_hash || !L.same(rec.pending_email_hash, expect)) {
      return L.page(res, 400, "Link not valid", "This confirmation link was already used or has expired.", c);
    }
    const nid = L.subId(c, email);
    const next = Object.assign({}, rec, { email, pending_email: null, pending_email_hash: null });
    await L.kv(c, "SET", L.subKey(c, nid), JSON.stringify(next));
    if (nid !== tok.id) {
      await L.kv(c, "DEL", key);
      await L.kv(c, "SREM", L.confirmedSet(c), tok.id);
    }
    if (next.status === "confirmed") await L.kv(c, "SADD", L.confirmedSet(c), nid);
    const user = JSON.parse((await L.kv(c, "GET", L.userKey(c, tok.id))) || "null");
    if (user) {
      user.email = email;
      await L.kv(c, "SET", L.userKey(c, nid), JSON.stringify(user));
      if (nid !== tok.id) await L.kv(c, "DEL", L.userKey(c, tok.id));
    }
    const old = rec.email;
    const notice = `The subscription to ${c.title} is now sent to a different address. If you did not ask for that, reply to this note.\n\n${c.sender ? c.sender + "\n" : ""}${c.postal}\n`;
    await L.sendEmail(c, { to: [old], subject: `Your subscription address for ${c.title} changed`, text: notice, html: `<p>${L.esc(notice)}</p>` });
    if (L.sessionReady(c)) {
      const sess = await L.issueSession(c, nid);
      setSess(c, res, sess);
    }
    return L.page(res, 200, "Address updated", "The subscription now uses the new address. The previous address was told.", c, { href: L.managePage(c), text: "Manage my subscription" });
  } catch {
    console.error("account: email change failed");
    return L.page(res, 503, "Please try again", "Something went wrong on our side. Please try the link again later.", c);
  }
}

async function deleteData(c, req, res, sess) {
  const b = await L.readBody(req);
  if (b.confirm !== "delete") return res.status(400).json({ ok: false, message: "Send confirm: delete to remove the data." });
  const id = sess.id;
  const removed = [];
  if (await L.kv(c, "GET", L.subKey(c, id))) { await L.kv(c, "DEL", L.subKey(c, id)); removed.push("subscriber record"); }
  await L.kv(c, "SREM", L.confirmedSet(c), id);
  if (await L.kv(c, "GET", L.userKey(c, id))) { await L.kv(c, "DEL", L.userKey(c, id)); removed.push("sign-in record"); }
  await L.kv(c, "SET", `${c.prefix}sess:revoked:${sess.jti}`, "1", "EX", 40 * 24 * 3600);
  await L.kv(c, "DEL", `${c.prefix}sess:current:${id}`);
  removed.push("this sign-in session");
  res.setHeader("Set-Cookie", L.sessionCookie(c, "", 0));
  return res.status(200).json({ ok: true, deleted: removed });
}

async function testSend(c, req, res, sess) {
  const admin = L.adminReady(c) && L.bearerMatch(c, req, c.admin);
  const ownerSess = sess && c.owner;
  if (!admin && !ownerSess) return res.status(401).json({ ok: false, status: "unauthorized" });
  if (!c.owner) return res.status(503).json({ ok: false, status: "not-configured" });
  if (ownerSess && !admin) {
    const user = JSON.parse((await L.kv(c, "GET", L.userKey(c, sess.id))) || "null");
    const sub = JSON.parse((await L.kv(c, "GET", L.subKey(c, sess.id))) || "null");
    const email = ((user && user.email) || (sub && sub.email) || "").toLowerCase();
    if (email !== c.owner) return res.status(401).json({ ok: false, status: "unauthorized" });
  }
  const b = await L.readBody(req);
  const kind = b.kind === "owner-alert" || b.kind === "digest-preview" || b.kind === "post" ? b.kind : "";
  if (!kind) return res.status(400).json({ ok: false, message: "kind must be owner-alert, digest-preview or post." });
  const links = L.subscriberLinks(c, "0".repeat(32), true);
  let msg;
  if (kind === "owner-alert") {
    msg = {
      subject: `[TEST] New subscriber to ${c.title} (0 total)`,
      text: `[TEST] This is a sample owner alert. It was not sent to subscribers.\nMethod: test\nPage: (test)\n`,
      html: `<p>[TEST] This is a sample owner alert. It was not sent to subscribers.</p>`,
    };
  } else if (kind === "digest-preview") {
    let posts = [], entries = [];
    try {
      const r = await fetch(`${c.site}/updates/posts.json`, { cache: "no-store" });
      const j = r.ok ? await r.json() : {};
      posts = (j.posts || []).slice(0, 5);
    } catch { posts = []; }
    msg = L.renderDigestEmail(c, posts, entries, links);
    msg.subject = `[TEST] ${msg.subject}`;
    msg.text = `[TEST] Sample only. The unsubscribe link does nothing.\n\n` + msg.text;
  } else {
    let post = { title: "Test update", summary: "This is a test copy.", url: "/updates/", date: "" };
    try {
      const r = await fetch(`${c.site}/updates/posts.json`, { cache: "no-store" });
      const j = r.ok ? await r.json() : {};
      const list = j.posts || [];
      const hit = b.slug ? list.find(p => p.slug === b.slug) : list[0];
      if (hit) post = hit;
    } catch { /* keep the placeholder */ }
    msg = L.renderPostEmail(c, post, links);
    msg.subject = `[TEST] ${msg.subject}`;
    msg.text = `[TEST] Sample only. The unsubscribe link does nothing.\n\n` + msg.text;
  }
  const sent = await L.sendEmail(c, { from: c.notifyFrom, reply_to: false, to: [c.owner], ...msg });
  if (!sent) return res.status(502).json({ ok: false, status: "not-sent" });
  return res.status(200).json({ ok: true, status: "sent", to_owner: true });
}

async function webhook(c, req, res) {
  if (!c.webhook) return res.status(503).json({ ok: false, status: "not-configured" });
  const raw = await L.rawBody(req);
  if (raw == null) return res.status(400).json({ ok: false, status: "raw-body-required" });
  const headers = {};
  for (const [k, v] of Object.entries(req.headers || {})) headers[k.toLowerCase()] = v;
  if (!L.verifySvix(c.webhook, headers, raw)) return res.status(401).json({ ok: false, status: "bad-signature" });
  let ev;
  try { ev = JSON.parse(raw); } catch { return res.status(400).json({ ok: false }); }
  const type = ev && ev.type;
  if (type !== "email.bounced" && type !== "email.complained") return res.status(200).json({ ok: true, status: "ignored" });
  const bounceType = String((ev.data && ev.data.bounce && ev.data.bounce.type) || "");
  if (type === "email.bounced" && /transient|temporary|soft/i.test(bounceType)) return res.status(200).json({ ok: true, status: "soft" });
  const tos = [].concat((ev.data && ev.data.to) || []);
  for (const addr of tos) {
    const email = cleanEmail(addr);
    if (!emailOk(email)) continue;
    const id = L.subId(c, email);
    const key = L.subKey(c, id);
    const rec = JSON.parse((await L.kv(c, "GET", key)) || "null");
    if (!rec) continue;
    rec.status = "suppressed";
    rec.suppressed_reason = type === "email.complained" ? "complaint" : "bounce";
    await L.kv(c, "SET", key, JSON.stringify(rec));
    await L.kv(c, "SREM", L.confirmedSet(c), id);
  }
  return res.status(200).json({ ok: true, status: "suppressed" });
}

function manageHtml(c, view) {
  const freq = view.frequency || "weekly";
  const radio = (v, label) => `<label style="display:block;margin:6px 0"><input type="radio" name="frequency" value="${v}" ${freq === v ? "checked" : ""}> ${L.esc(label)}</label>`;
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Manage my subscription · ${L.esc(c.title)}</title>
<style>body{margin:0;background:#f8f5ee;color:#1d1a17;font:18px/1.5 Georgia,serif}.wrap{max-width:640px;margin:0 auto;padding:32px 16px}button,input{font:inherit;min-height:44px}button{background:#1d1a17;color:#fff;border:0;border-radius:8px;padding:8px 16px;cursor:pointer}a{color:#8E1A14}</style></head>
<body><div class="wrap"><h1>Manage my subscription</h1>
<p>Status: ${L.esc(view.statusLine)}</p>
<form method="post" action="/api/account/?op=prefs"><input type="hidden" name="csrf" value="${L.esc(view.csrf)}">
<fieldset><legend>How often</legend>
${radio("each", "Each new update")}
${radio("weekly", "Monday digest")}
${radio("paused", "Paused")}
</fieldset>
<p><label>Pause until <input name="paused_until" value="${L.esc(view.paused_until || "")}" placeholder="YYYY-MM-DD"></label></p>
<p><button type="submit">Save</button></p></form>
<form method="post" action="/api/account/?op=unsubscribe"><input type="hidden" name="csrf" value="${L.esc(view.csrf)}"><button type="submit">Unsubscribe</button></form>
</div></body></html>`;
}

async function manage(c, req, res, q) {
  if (!L.sessionReady(c)) return L.page(res, 503, "Not open yet", L.CLOSED, c);
  let sess = await loadSession(c, req);
  if (q.t) {
    const id = L.readManageToken(c, q.t);
    if (!id) return L.page(res, 400, "Link not valid", "This manage link is not valid or has expired. Sign in and open Manage my subscription.", c);
    const sub = JSON.parse((await L.kv(c, "GET", L.subKey(c, id))) || "null");
    if (sub && sub.email) await ensureUser(c, sub.email);
    sess = await L.issueSession(c, id);
    setSess(c, res, sess);
  }
  if (!sess) return L.page(res, 401, "Sign in", "Sign in to manage a subscription.", c, { href: L.managePage(c), text: "Manage my subscription" });
  if (req.method === "POST") {
    const b = await L.readBody(req);
    const header = req.headers["x-lineage-csrf"] || b.csrf;
    req.headers["x-lineage-csrf"] = header;
    if (!(await csrfOk(c, req, sess))) return L.page(res, 403, "Not saved", "That form expired. Open Manage my subscription again.", c);
    if ((q.op || "") === "manage" && b.frequency) {
      req.body = b;
      return prefs(c, req, res, sess).then(() => L.page(res, 200, "Saved", "Your preference is saved.", c, { href: L.managePage(c), text: "Manage my subscription" }));
    }
  }
  const sub = JSON.parse((await L.kv(c, "GET", L.subKey(c, sess.id))) || "null");
  const statusLine = !sub ? "Not subscribed" : sub.status === "confirmed" ? `Subscribed since ${sub.confirmed || sub.created || ""}` : sub.status;
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  return res.status(200).send(manageHtml(c, {
    frequency: sub ? L.frequencyOf(sub) : "each",
    paused_until: (sub && sub.paused_until) || "",
    statusLine, csrf: L.csrfFor(c, sess),
  }));
}

module.exports = async function handler(req, res) {
  res.setHeader("X-Robots-Tag", "noindex");
  res.setHeader("Cache-Control", "no-store");
  const c = L.config();
  if (!c) return L.closed(req, res);
  const q = queryOf(req);
  const op = String(q.op || "me");
  try {
    if (op === "resend-webhook") {
      if (req.method !== "POST") return res.status(405).json({ ok: false });
      return await webhook(c, req, res);
    }
    if (op === "test" && req.method === "POST" && L.adminReady(c) && L.bearerMatch(c, req, c.admin)) {
      return await testSend(c, req, res, null);
    }
    if (op === "link") {
      if (req.method !== "POST") return res.status(405).json({ ok: false });
      return await sendLink(c, req, res);
    }
    if (op === "verify") return await verify(c, req, res, q);
    if (op === "confirm-email") return await confirmEmail(c, req, res, q);
    if (op === "me") return await me(c, req, res);
    if (op === "manage") return await manage(c, req, res, q);

    const sess = await loadSession(c, req);
    if (!sess) return res.status(401).json({ ok: false, status: "signed-out" });
    if (req.method !== "POST") return res.status(405).json({ ok: false });
    const posted = await L.readBody(req);
    if (!req.headers["x-lineage-csrf"] && posted && posted.csrf) req.headers["x-lineage-csrf"] = String(posted.csrf);
    req.body = posted;
    if (!(await csrfOk(c, req, sess))) return res.status(403).json({ ok: false, status: "csrf" });
    if (op === "signout") return await signOut(c, req, res, sess);
    if (op === "prefs") return await prefs(c, req, res, sess);
    if (op === "unsubscribe") {
      await dropSubscriber(c, sess.id, "unsubscribe");
      return res.status(200).json({ ok: true, status: "unsubscribed" });
    }
    if (op === "change-email") return await changeEmail(c, req, res, sess);
    if (op === "delete") return await deleteData(c, req, res, sess);
    if (op === "test") return await testSend(c, req, res, sess);
    return res.status(404).json({ ok: false, status: "unknown" });
  } catch (e) {
    console.error("account: failed");
    return res.status(503).json({ ok: false, status: "error" });
  }
};

module.exports.ensureUser = ensureUser;
