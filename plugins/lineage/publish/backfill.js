#!/usr/bin/env node
// One-time send of a post that is already on the site.
//
//   SITE_URL=https://family.example.org ADMIN_SECRET=... node backfill.js --slug weekly-2026-w44
//   SITE_URL=... ADMIN_SECRET=... node backfill.js --send --slug weekly-2026-w44 --i-approve
//
// The default is a dry run: it prints the slug, the subject and how many people would be mailed.
// It never prints an address and it writes nothing.
// --send without --i-approve refuses, and does not call the site.
// ADMIN_SECRET is read from the environment, never from the command line.
// This script does not send mail itself. The site function does, and only after --i-approve.
const http = require("http");
const https = require("https");

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : "";
}
const send = process.argv.includes("--send");
const approve = process.argv.includes("--i-approve");
const slug = arg("--slug") || "weekly-2026-w44";
const site = String(process.env.SITE_URL || "").replace(/\/+$/, "");
const secret = String(process.env.ADMIN_SECRET || "");

if (!/^[a-z0-9][a-z0-9-]{0,80}$/.test(slug)) {
  console.error("backfill: slug must be letters, numbers and hyphens");
  process.exit(2);
}
if (send && !approve) {
  console.error("backfill: refusing to send. A dry run is the default. Sending needs --send and --i-approve.");
  process.exit(2);
}
if (!site || !secret) {
  console.error("backfill: set SITE_URL and ADMIN_SECRET in the environment. Do not pass the secret as an argument.");
  process.exit(2);
}

const dry = send ? "" : "&dry_run=1";
const url = new URL(`${site}/api/notify/?slug=${encodeURIComponent(slug)}${dry}`);
const lib = url.protocol === "https:" ? https : http;
const req = lib.request(url, {
  method: "POST",
  headers: { Authorization: `Bearer ${secret}`, Accept: "application/json" },
}, res => {
  let body = "";
  res.on("data", c => { body += c; });
  res.on("end", () => {
    let j = {};
    try { j = JSON.parse(body); } catch { j = {}; }
    const posts = j.posts || j.results || [];
    const lines = Array.isArray(posts) ? posts : [];
    if (!lines.length && j.slug) lines.push(j);
    if (j.dry_run || !send) {
      for (const p of lines) console.log(`${p.slug || slug}\t${p.subject || ""}\t${p.recipients != null ? p.recipients : ""}`);
      if (!lines.length) console.log(`${slug}\t\t${j.status || ""}`);
      console.log("dry run: nothing written, no addresses printed");
      process.exit(res.statusCode >= 400 ? 1 : 0);
    }
    console.log(j.status || res.statusCode);
    process.exit(res.statusCode >= 400 ? 1 : 0);
  });
});
req.setTimeout(8000, () => { req.destroy(); console.error("backfill: timed out"); process.exit(1); });
req.on("error", () => { console.error("backfill: request failed"); process.exit(1); });
req.end();
