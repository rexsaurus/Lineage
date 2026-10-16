// The link in the confirmation email: GET /api/confirm?t=<signed token>. Turns a pending address into a subscriber.
const L = require("./_lineage.js");

module.exports = async function handler(req, res) {
  const c = L.config();
  if (!c) return L.page(res, 503, "Not open yet", L.CLOSED, null);
  const tok = L.readConfirmToken(c, (req.query && req.query.t) || new URL(req.url, "http://x").searchParams.get("t"));
  if (!tok) return L.page(res, 400, "Link not valid", "This confirmation link is not valid. Please subscribe again from the updates page.", c);
  try {
    const key = L.subKey(c, tok.id);
    const cur = JSON.parse((await L.kv(c, "GET", key)) || "null");
    if (cur && cur.status === "confirmed") {
      await L.kv(c, "SADD", L.confirmedSet(c), tok.id);
      return L.page(res, 200, "You're subscribed", `You already confirmed. The digest of ${c.title} comes once a week.`, c);
    }
    if (!cur || cur.status !== "pending" || !cur.token_hash || !L.same(cur.token_hash, tok.hash)) {
      return L.page(res, 400, "Link expired", "This confirmation link has expired or was replaced by a newer one. Please subscribe again from the updates page.", c);
    }
    const rec = { email: cur.email, status: "confirmed", created: cur.created, confirmed: new Date().toISOString(), token_hash: null };
    await L.kv(c, "SET", key, JSON.stringify(rec));                 // no expiry once confirmed
    await L.kv(c, "SADD", L.confirmedSet(c), tok.id);
    return L.page(res, 200, "You're subscribed", `Thank you. The digest of ${c.title} comes once a week; every email has a one-click unsubscribe link.`, c);
  } catch {
    console.error("confirm: store unavailable");
    return L.page(res, 503, "Please try again", "Something went wrong on our side. Please try the link again later.", c);
  }
};
