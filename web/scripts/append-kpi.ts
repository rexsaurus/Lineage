// npm run kpi:append -- <path/to/second-brain-fundraising/kpi-log.csv> [--url https://<app>/api/admin/kpi.csv]
// Fetches today's row from the live app with KPI_EXPORT_TOKEN and appends it to the log. It never writes a number the
// app didn't compute, and never adds a second row for a date already in the file.
import fs from "node:fs";

export function appendRow(existing: string, fetched: string): { text: string; added: boolean; reason?: string } {
  const lines = fetched.trim().split(/\r?\n/);
  if (lines[0] !== "date,families,archivists" || lines.length !== 2) return { text: existing, added: false, reason: "unexpected CSV from the app" };
  const row = lines[1];
  if (!/^\d{4}-\d{2}-\d{2},\d+,\d+$/.test(row)) return { text: existing, added: false, reason: "malformed row" };
  const date = row.slice(0, 10);
  const have = existing.split(/\r?\n/).some(l => l.startsWith(date + ","));
  if (have) return { text: existing, added: false, reason: `a row for ${date} is already in the log` };
  const base = existing.trim() ? existing.replace(/\s*$/, "\n") : "date,families,archivists\n";
  return { text: base + row + "\n", added: true };
}

async function main() {
  const args = process.argv.slice(2);
  const file = args.find(a => !a.startsWith("--"));
  const ui = args.indexOf("--url");
  const url = ui >= 0 ? args[ui + 1] : process.env.KPI_URL;
  const token = process.env.KPI_EXPORT_TOKEN;
  if (!file || !url || !token) {
    console.error("usage: KPI_EXPORT_TOKEN=… npm run kpi:append -- <kpi-log.csv> --url https://<app>/api/admin/kpi.csv");
    process.exit(1);
  }
  const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!r.ok) {
    console.error(`the app answered HTTP ${r.status}`);
    process.exit(1);
  }
  const existing = fs.existsSync(file) ? fs.readFileSync(file, "utf8") : "";
  const out = appendRow(existing, await r.text());
  if (!out.added) {
    console.log(`not appended: ${out.reason}`);
    return;
  }
  fs.writeFileSync(file, out.text);
  console.log(`appended: ${out.text.trim().split("\n").pop()}`);
}

if (process.argv[1]?.endsWith("append-kpi.ts")) main();
