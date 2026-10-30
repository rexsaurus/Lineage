// Continue with Google. GET /api/google starts the OAuth redirect. Google returns to the same path
// with ?code&state. A verified Google email is stored as confirmed (Google already checked the address)
// and a welcome note is sent through Resend, with the one-click unsubscribe link. Email double opt-in
// (api/subscribe.js) stays available beside it.
//
// Closed unless the email stack is configured AND GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set.
// Redirect URI to register: {SITE_URL}/api/google or {SITE_URL}/api/google/ to match vercel.json trailingSlash.
const L = require("./_lineage.js");

function queryOf(req) {
  const q = Object.assign({}, req.query || {});
  try {
    const u = new URL(req.url || "/", "http://localhost");
    for (const [k, v] of u.searchParams) if (q[k] == null) q[k] = v;
  } catch { /* req.url is not always a full URL */ }
  return q;
}

async function postForm(url, fields) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 10000);
  try {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
      body: new URLSearchParams(fields),
      signal: ctl.signal,
    });
    const j = await r.json().catch(() => ({}));
    return r.ok ? j : null;
  } catch { return null; } finally { clearTimeout(t); }
}

async function getJson(url, token) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 10000);
  try {
    const r = await fetch(url, { headers: { Authorization: `Bearer ${token}`, Accept: "application/json" }, signal: ctl.signal });
    return r.ok ? await r.json() : null;
  } catch { return null; } finally { clearTimeout(t); }
}

function welcome(c, link) {
  const text = `You are subscribed to the weekly digest of ${c.title}: new posts and changes to ${c.site}, once a week.\n\n` +
    `Unsubscribe (one click): ${link}\n\n${c.sender ? c.sender + "\n" : ""}${c.postal}\n`;
  const html = `<div style="font:16px/1.6 Georgia,serif;color:#1d1a17;max-width:560px">
<p>You are subscribed to the weekly digest of <b>${L.esc(c.title)}</b>: new posts and changes to the site, once a week.</p>
<p style="color:#6b645b;font-size:14px"><a href="${L.esc(link)}" style="color:#6b645b">Unsubscribe with one click</a></p>
<p style="color:#6b645b;font-size:13px">${c.sender ? L.esc(c.sender) + "<br>" : ""}${L.esc(c.postal)}</p></div>`;
  return { subject: `You are subscribed to ${c.title}`, text, html };
}

module.exports = async function handler(req, res) {
  res.setHeader("X-Robots-Tag", "noindex");
  const c = L.config();
  if (!c) return L.closed(req, res);
  const g = L.googleOn();
  if (!g) return L.page(res, 503, "Not open yet", "Google sign-in is not turned on for this site yet. You can subscribe with email from the updates page, or follow the RSS feed.", c);
  if (req.method !== "GET" && req.method !== "HEAD") return L.page(res, 405, "Not signed in", "Open the subscribe form and choose Continue with Google.", c);

  const q = queryOf(req);
  const redirect = L.googleRedirect(c);
  if (!q.code) {
    const state = L.oauthState(c);
    const secure = c.site.startsWith("https://") ? "; Secure" : "";
    res.setHeader("Set-Cookie", `lsub_g=${state}; HttpOnly; SameSite=Lax; Path=/; Max-Age=600${secure}`);
    const url = g.auth + "?" + new URLSearchParams({
      client_id: g.id, redirect_uri: redirect, response_type: "code",
      scope: "openid email", state, prompt: "select_account",
    });
    res.setHeader("Location", url);
    res.setHeader("Cache-Control", "no-store");
    return res.status(302).send("");
  }

  const state = L.readOauthState(c, q.state);
  const cookie = L.cookieVal(req, "lsub_g");
  res.setHeader("Set-Cookie", "lsub_g=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0");
  if (!state || !cookie || !L.same(cookie, state)) {
    return L.page(res, 400, "Please try again", "That sign-in expired. Open the subscribe form and choose Continue with Google again.", c);
  }

  try {
    const tok = await postForm(g.token, {
      code: q.code, client_id: g.id, client_secret: g.secret,
      redirect_uri: redirect, grant_type: "authorization_code",
    });
    const info = tok && tok.access_token ? await getJson(g.userinfo, tok.access_token) : null;
    const email = String(info && info.email || "").trim().toLowerCase();
    const verified = info && (info.email_verified === true || info.email_verified === "true");
    if (!verified || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
      return L.page(res, 400, "Email not confirmed", "Google did not confirm that email address. Subscribe with email instead, and confirm from your inbox.", c);
    }
    const id = L.subId(c, email);
    const key = L.subKey(c, id);
    const cur = JSON.parse((await L.kv(c, "GET", key)) || "null");
    if (!cur || cur.status !== "confirmed") {
      const rec = {
        email, status: "confirmed",
        created: (cur && cur.created) || new Date().toISOString(),
        confirmed: new Date().toISOString(), token_hash: null,
      };
      await L.kv(c, "SET", key, JSON.stringify(rec));
      await L.kv(c, "SADD", L.confirmedSet(c), id);
      const sent = await L.sendEmail(c, { to: [email], ...welcome(c, L.apiUrl(c, "unsubscribe", L.unsubToken(c, id))) });
      if (!sent) console.error("google: welcome email not accepted by the mail service");
    }
    return L.page(res, 200, "You're subscribed", `Thank you. The digest of ${c.title} comes once a week. Every email has a one-click unsubscribe link.`, c);
  } catch {
    console.error("google: store unavailable");
    return L.page(res, 503, "Please try again", "Something went wrong on our side. Please try Google sign-in again later.", c);
  }
};
