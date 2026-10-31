#!/usr/bin/env node
// Ask the site to mail a test to the owner address only.
//
//   ADMIN_SECRET=... node plugins/lineage/publish/send_test.js https://family.example.org post
//
// kind is owner-alert, digest-preview or post. The secret is read from the environment, never from
// the command line. The endpoint will not mail the subscriber list.
const http = require("http");
const https = require("https");

const site = String(process.argv[2] || "").replace(/\/+$/, "");
const kind = process.argv[3] || "post";
const secret = String(process.env.ADMIN_SECRET || "");
if (!site || !/^https?:\/\//.test(site) || !secret) {
  console.error("usage: ADMIN_SECRET=... node send_test.js <site_url> <owner-alert|digest-preview|post>");
  console.error("The secret comes from the environment, not the command line.");
  process.exit(2);
}
if (!["owner-alert", "digest-preview", "post"].includes(kind)) {
  console.error("kind must be owner-alert, digest-preview or post");
  process.exit(2);
}
const url = new URL(`${site}/api/account/?op=test`);
const lib = url.protocol === "https:" ? https : http;
const payload = JSON.stringify({ kind });
const req = lib.request(url, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${secret}`,
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(payload),
  },
}, res => {
  let body = "";
  res.on("data", c => { body += c; });
  res.on("end", () => {
    console.log(res.statusCode);
    process.exit(res.statusCode >= 400 ? 1 : 0);
  });
});
req.on("error", () => { console.error("send_test: request failed"); process.exit(1); });
req.end(payload);
