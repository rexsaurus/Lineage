// Email each new post once, to subscribers who chose "each new update".
// POST or GET /api/notify with Authorization: Bearer $CRON_SECRET or $ADMIN_SECRET.
// ?dry_run=1 prints the plan and writes nothing. ?slug= limits the run to one post.
// A daily cron is the safety net. The publish step can also call this once after a production deploy.
// Weekly subscribers are left for the Monday digest. This route does not add the slug to digest:posts,
// so that digest still carries the post for them. Subscribers on "each" are not on the digest list,
// so they are not mailed twice.
const L = require("./_lineage.js");

function queryOf(req) {
  const q = Object.assign({}, req.query || {});
  try {
    const u = new URL(req.url || "/", "http://localhost");
    for (const [k, v] of u.searchParams) if (q[k] == null) q[k] = v;
  } catch { /* req.url is not always a full URL */ }
  return q;
}

async function getJson(url) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 10000);
  try {
    const r = await fetch(url, { headers: { Accept: "application/json" }, cache: "no-store", signal: ctl.signal });
    return r.ok ? await r.json() : null;
  } catch { return null; } finally { clearTimeout(t); }
}

async function recipients(c, slug) {
  const ids = (await L.kv(c, "SMEMBERS", L.confirmedSet(c))) || [];
  const out = [];
  for (const id of ids) {
    if (await L.kv(c, "SISMEMBER", `${c.prefix}issue:${slug}:sent`, id)) continue;
    const rec = JSON.parse((await L.kv(c, "GET", L.subKey(c, id))) || "null");
    if (!L.wantsEach(rec)) continue;
    out.push({ id, email: rec.email });
  }
  return out;
}

async function sendIssue(c, post, deadline) {
  const slug = post.slug;
  const lock = `${c.prefix}issue:${slug}:lock`;
  if (await L.kv(c, "GET", `${c.prefix}issue:${slug}:done`)) return { slug, status: "already-sent" };
  if ((await L.kv(c, "SET", lock, "1", "NX", "EX", 900)) == null) return { slug, status: "in-progress" };
  const unlock = () => L.kv(c, "DEL", lock).catch(() => {});
  try {
    const people = await recipients(c, slug);
    let sent = 0, failed = 0;
    for (let i = 0; i < people.length; i += L.BATCH) {
      if (Date.now() > deadline) { await unlock(); return { slug, status: "partial", sent, failed, remaining: people.length - i }; }
      const chunk = people.slice(i, i + L.BATCH);
      const messages = chunk.map(p => {
        const links = L.subscriberLinks(c, p.id);
        const msg = L.renderPostEmail(c, post, links);
        return { to: [p.email], ...msg, headers: L.listHeaders(c, links.unsub) };
      });
      const idem = `issue-${c.prefix}${slug}-${chunk[0].id}`.replace(/[^A-Za-z0-9_-]/g, "").slice(0, 256);
      const r = await L.sendBatch(c, messages, idem);
      if (!r.ok) { failed += chunk.length; await unlock(); return { slug, status: "partial", sent, failed }; }
      sent += chunk.length;
      await L.kv(c, "SADD", `${c.prefix}issue:${slug}:sent`, ...chunk.map(p => p.id));
      if (i + L.BATCH < people.length) await L.sleep(600);
    }
    await L.kv(c, "SADD", `${c.prefix}issue:sent`, slug);
    await L.kv(c, "SET", `${c.prefix}issue:${slug}:done`, new Date().toISOString());
    await unlock();
    return { slug, status: "sent", sent, failed };
  } catch {
    await unlock();
    return { slug, status: "error" };
  }
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Robots-Tag", "noindex");
  if (req.method !== "GET" && req.method !== "POST" && req.method !== "HEAD") {
    return res.status(405).json({ ok: false, status: "method" });
  }
  const c = L.config();
  if (!c) return res.status(503).json({ ok: false, status: "not-configured" });
  const q = queryOf(req);
  const dry = q.dry_run === "1" || q.dry_run === "true";
  const allowed = L.bearerMatch(c, req, c.cron) || (L.adminReady(c) && L.bearerMatch(c, req, c.admin));
  if (!allowed) return res.status(401).json({ ok: false, status: "unauthorized" });

  const pj = await getJson(`${c.site}/updates/posts.json`);
  if (!pj) return res.status(502).json({ ok: false, status: "site-data-unavailable" });
  let posts = (pj.posts || []).filter(p => p && p.slug && p.title);
  if (q.slug) posts = posts.filter(p => p.slug === q.slug);
  else {
    const done = new Set((await L.kv(c, "SMEMBERS", `${c.prefix}issue:sent`)) || []);
    posts = posts.filter(p => !done.has(p.slug));
  }
  if (!posts.length) return res.status(200).json({ ok: true, status: "nothing-new", dry_run: dry });

  if (dry) {
    const plans = [];
    for (const p of posts) {
      const people = await recipients(c, p.slug);
      plans.push({ slug: p.slug, subject: p.title, recipients: people.length });
    }
    return res.status(200).json({ ok: true, status: "dry-run", dry_run: true, posts: plans });
  }

  const deadline = Date.now() + 50000;
  const results = [];
  let partial = false;
  for (const p of posts) {
    if (Date.now() > deadline) { partial = true; break; }
    const r = await sendIssue(c, p, deadline);
    results.push(r);
    if (r.status === "partial" || r.status === "error") { partial = true; break; }
  }
  return res.status(partial ? 502 : 200).json({ ok: !partial, status: partial ? "partial" : "sent", results });
};

module.exports.config = { maxDuration: 60 };
