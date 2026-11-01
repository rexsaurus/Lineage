// Lead storage for /join/ (api/lead.js, api/lead-admin.js). Not a route: files starting with "_" are not functions.
// The site has no npm install step, so the store is reached over plain HTTPS: Upstash Redis REST, which Vercel's
// Marketplace "Upstash for Redis" integration provides as KV_REST_API_URL / KV_REST_API_TOKEN (or
// UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN). With neither set there is no store, and callers fail closed.
const KEY = "join:leads";

function store() {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  return url && token ? { url: url.replace(/\/+$/, ""), token } : null;
}

async function cmd(s, args) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 8000);
  try {
    const r = await fetch(s.url, {
      method: "POST",
      headers: { Authorization: `Bearer ${s.token}`, "Content-Type": "application/json" },
      body: JSON.stringify(args),
      signal: ctl.signal,
    });
    if (!r.ok) throw new Error(`store HTTP ${r.status}`);
    const j = await r.json();
    if (j.error) throw new Error("store error");
    return j.result;
  } finally {
    clearTimeout(t);
  }
}

async function addLead(s, lead) {
  return cmd(s, ["RPUSH", KEY, JSON.stringify(lead)]);
}

async function listLeads(s) {
  const rows = (await cmd(s, ["LRANGE", KEY, "0", "-1"])) || [];
  return rows.map(r => { try { return JSON.parse(r); } catch { return null; } }).filter(Boolean);
}

module.exports = { store, addLead, listLeads };
