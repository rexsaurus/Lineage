// The weekly digest. Run by the Vercel cron in vercel.json (Mondays 15:00 UTC by default), which sends
// "Authorization: Bearer $CRON_SECRET"; any other caller gets 401.
//
// It reads what the site itself publishes, /changelog.json (the site changelog, privacy-filtered exactly like
// /changelog/) and /updates/posts.json, takes what no earlier digest has carried (the first digest: the last
// 7 days), and emails each confirmed subscriber, with a one-click unsubscribe link and the sender/postal footer.
//
// Idempotent per ISO week: a week that has been sent is never sent again; a run that failed part way resumes and
// skips everyone already sent (and Resend's Idempotency-Key guards a retry of the same email for 24 hours).
// A week with nothing new sends nothing.
const L = require("./_lineage.js");

function isoWeek(d) {
  const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const y = t.getUTCFullYear();
  const w = Math.ceil(((t - Date.UTC(y, 0, 1)) / 86400000 + 1) / 7);
  return `${y}-W${String(w).padStart(2, "0")}`;
}

async function getJson(url) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 10000);
  try {
    const r = await fetch(url, { headers: { Accept: "application/json" }, cache: "no-store", signal: ctl.signal });
    return r.ok ? await r.json() : null;
  } catch { return null; } finally { clearTimeout(t); }
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Robots-Tag", "noindex");
  const c = L.config();
  if (!c) return res.status(503).json({ ok: false, status: "not-configured" });
  const auth = String(req.headers.authorization || "");
  if (!L.same(auth, `Bearer ${c.cron}`)) return res.status(401).json({ ok: false, status: "unauthorized" });

  const now = new Date();
  const week = isoWeek(now);
  const P = c.prefix + "digest:";
  try {
    if (await L.kv(c, "GET", `${P}${week}:done`)) return res.status(200).json({ ok: true, status: "already-sent", week });
    if ((await L.kv(c, "SET", `${P}${week}:lock`, "1", "NX", "EX", 900)) == null) {
      return res.status(409).json({ ok: false, status: "in-progress", week });
    }
  } catch {
    console.error("digest: store unavailable");
    return res.status(503).json({ ok: false, status: "store-unavailable" });
  }
  const unlock = () => L.kv(c, "DEL", `${P}${week}:lock`).catch(() => {});

  try {
    const [clog, pj] = await Promise.all([getJson(`${c.site}/changelog.json`), getJson(`${c.site}/updates/posts.json`)]);
    if (!clog && !pj) { await unlock(); return res.status(502).json({ ok: false, status: "site-data-unavailable", week }); }
    const first = !(await L.kv(c, "GET", `${P}last`));
    const floor = new Date(now.getTime() - 7 * 86400000).toISOString();
    const sentPosts = new Set((await L.kv(c, "SMEMBERS", `${P}posts`)) || []);
    const sentEntries = new Set((await L.kv(c, "SMEMBERS", `${P}entries`)) || []);
    const posts = ((pj && pj.posts) || []).filter(p => p && p.slug && !sentPosts.has(p.slug) && (!first || String(p.date) >= floor.slice(0, 10)));
    const entries = ((clog && clog.entries) || []).filter(e => e && e.id && !sentEntries.has(e.id) && (e.changes || []).length
      && (!first || String(e.at || `${e.date}T00:00:00`) >= floor));
    const markItems = async () => {
      if (posts.length) await L.kv(c, "SADD", `${P}posts`, ...posts.map(p => p.slug));
      if (entries.length) await L.kv(c, "SADD", `${P}entries`, ...entries.map(e => e.id));
      await L.kv(c, "SET", `${P}last`, now.toISOString());
      await L.kv(c, "SET", `${P}${week}:done`, now.toISOString(), "EX", 60 * 86400);
    };
    if (!posts.length && !entries.length) {
      await markItems(); await unlock();
      return res.status(200).json({ ok: true, status: "nothing-new", week });
    }

    const ids = (await L.kv(c, "SMEMBERS", L.confirmedSet(c))) || [];
    let sent = 0, skipped = 0, failed = 0;
    for (const id of ids) {
      if (await L.kv(c, "SISMEMBER", `${P}${week}:sent`, id)) { skipped++; continue; }
      const rec = JSON.parse((await L.kv(c, "GET", L.subKey(c, id))) || "null");
      if (!rec || rec.status !== "confirmed" || !rec.email) { await L.kv(c, "SREM", L.confirmedSet(c), id); skipped++; continue; }
      if (!L.wantsWeekly(rec)) { skipped++; continue; }
      const links = L.subscriberLinks(c, id);
      const msg = L.renderDigestEmail(c, posts, entries, links);
      const ok = await L.sendEmail(c, {
        to: [rec.email], ...msg,
        headers: L.listHeaders(c, links.unsub),
      }, `digest-${c.prefix}${week}-${id}`);
      if (ok) { sent++; await L.kv(c, "SADD", `${P}${week}:sent`, id); await L.kv(c, "EXPIRE", `${P}${week}:sent`, 60 * 86400); }
      else failed++;
    }
    if (failed) {
      console.error(`digest ${week}: ${failed} of ${ids.length} emails not accepted; run again to resume`);
      await unlock();
      return res.status(502).json({ ok: false, status: "partial", week, sent, skipped, failed });
    }
    await markItems(); await unlock();
    return res.status(200).json({ ok: true, status: "sent", week, posts: posts.length, entries: entries.length, sent, skipped });
  } catch {
    console.error("digest: failed");
    await unlock();
    return res.status(503).json({ ok: false, status: "error", week });
  }
};

module.exports.isoWeek = isoWeek;
