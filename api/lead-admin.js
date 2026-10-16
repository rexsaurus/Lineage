// Rex's view of the /join/ sign-ups. GET /api/lead-admin?key=ADMIN_KEY  (add &format=csv to download)
// 404 unless ADMIN_KEY is set (16+ characters) and matches; 503 if no store is configured.
const crypto = require("crypto");
const { store, listLeads } = require("./_leads.js");

function same(a, b) {
  const x = crypto.createHash("sha256").update(String(a)).digest();
  const y = crypto.createHash("sha256").update(String(b)).digest();
  return crypto.timingSafeEqual(x, y);
}
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const csvCell = s => {
  let v = String(s == null ? "" : s);
  if (/^[=+\-@\t\r]/.test(v)) v = "'" + v;              // no spreadsheet formulas
  return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
};

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Robots-Tag", "noindex, nofollow");
  const url = new URL(req.url, "http://x");
  const want = process.env.ADMIN_KEY || "";
  if (want.length < 16 || !same(url.searchParams.get("key") || "", want)) { res.status(404).send("Not found"); return; }
  const s = store();
  if (!s) { res.status(503).send("No lead store is configured (see docs/JOIN.md)."); return; }
  let leads;
  try { leads = await listLeads(s); } catch { res.status(502).send("The lead store didn't answer."); return; }

  const cols = ["at", "name", "email", "surname", "src"];
  if (url.searchParams.get("format") === "csv") {
    res.setHeader("Content-Type", "text/csv; charset=utf-8");
    res.setHeader("Content-Disposition", `attachment; filename="lineage-leads-${new Date().toISOString().slice(0, 10)}.csv"`);
    res.status(200).send([cols.join(","), ...leads.map(l => cols.map(c => csvCell(l[c])).join(","))].join("\n") + "\n");
    return;
  }
  const bySrc = {};
  for (const l of leads) bySrc[l.src] = (bySrc[l.src] || 0) + 1;
  const csvHref = `?key=${encodeURIComponent(url.searchParams.get("key"))}&format=csv`;
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.status(200).send(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Join sign-ups</title>
<style>body{font:17px/1.5 system-ui,sans-serif;margin:16px;color:#1C1A17;background:#fff}table{border-collapse:collapse;width:100%}
th,td{border:1px solid #ccc;padding:6px 8px;text-align:left}th{background:#f3eee6}.wrap{overflow-x:auto}</style></head><body>
<h1>Join sign-ups: ${leads.length}</h1>
<p>${Object.entries(bySrc).map(([k, v]) => `${esc(k)}: ${v}`).join(" · ") || "None yet."}</p>
<p><a href="${esc(csvHref)}">Download CSV</a></p>
<div class="wrap"><table><thead><tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr></thead><tbody>
${leads.slice().reverse().map(l => `<tr>${cols.map(c => `<td>${esc(l[c])}</td>`).join("")}</tr>`).join("\n")}
</tbody></table></div></body></html>`);
};
