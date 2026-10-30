// One-click unsubscribe: GET /api/unsubscribe?t=<signed token> (the link in every digest), or POST to the same URL
// (RFC 8058 List-Unsubscribe-Post, what mail apps send). The subscriber's record is deleted, not just flagged.
const L = require("./_lineage.js");

module.exports = async function handler(req, res) {
  const c = L.config();
  if (!c) return L.page(res, 503, "Not open yet", L.CLOSED, null);
  const id = L.readUnsubToken(c, (req.query && req.query.t) || new URL(req.url, "http://x").searchParams.get("t"));
  if (!id) return L.page(res, 400, "Link not valid", "This unsubscribe link is not valid. Reply to any digest and you will be removed by hand.", c);
  try {
    await L.kv(c, "DEL", L.subKey(c, id));
    await L.kv(c, "SREM", L.confirmedSet(c), id);
  } catch {
    console.error("unsubscribe: store unavailable");
    return L.page(res, 503, "Please try again", "Something went wrong on our side. Please try the link again in a few minutes.", c);
  }
  if (req.method === "POST") { res.setHeader("Cache-Control", "no-store"); return res.status(200).json({ ok: true }); }
  return L.page(res, 200, "Unsubscribed", `You will get no more emails from ${c.title}. Your address has been deleted.`, c);
};
