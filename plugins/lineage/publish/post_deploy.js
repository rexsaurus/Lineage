#!/usr/bin/env node
// After a production deploy: check that subscriptions are open, then ask notify to send any new posts.
// CRON_SECRET is read from the environment. This does not deploy, and it does not print addresses.
//
//   SITE_URL=https://family.example.org CRON_SECRET=... node plugins/lineage/publish/post_deploy.js
const http = require("http");
const https = require("https");

function get(url) {
  const lib = url.protocol === "https:" ? https : http;
  return new Promise((resolve, reject) => {
    const req = lib.request(url, { method: "GET", headers: { Accept: "application/json" } }, res => {
      let body = "";
      res.on("data", c => { body += c; });
      res.on("end", () => resolve({ status: res.statusCode, body }));
    });
    req.on("error", reject);
    req.end();
  });
}
function post(url, secret) {
  const lib = url.protocol === "https:" ? https : http;
  return new Promise((resolve, reject) => {
    const req = lib.request(url, { method: "POST", headers: { Authorization: `Bearer ${secret}`, Accept: "application/json" } }, res => {
      let body = "";
      res.on("data", c => { body += c; });
      res.on("end", () => resolve({ status: res.statusCode, body }));
    });
    req.on("error", reject);
    req.end();
  });
}

async function main() {
  const site = String(process.env.SITE_URL || "").replace(/\/+$/, "");
  const secret = String(process.env.CRON_SECRET || "");
  if (!site || !secret) {
    console.error("post_deploy: set SITE_URL and CRON_SECRET in the environment");
    process.exit(2);
  }
  const sub = await get(new URL(`${site}/api/subscribe/`));
  let open = false;
  try { open = JSON.parse(sub.body).open === true; } catch { open = false; }
  if (!open) {
    console.error(`post_deploy: GET /api/subscribe/ did not return open: true (HTTP ${sub.status})`);
    process.exit(1);
  }
  console.log("subscribe: open");
  const note = await post(new URL(`${site}/api/notify/`), secret);
  let status = "";
  try { status = JSON.parse(note.body).status || ""; } catch { status = ""; }
  console.log(`notify: HTTP ${note.status} ${status}`);
  process.exit(note.status >= 400 ? 1 : 0);
}
main().catch(() => { console.error("post_deploy: request failed"); process.exit(1); });
