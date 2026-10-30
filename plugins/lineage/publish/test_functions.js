#!/usr/bin/env node
// Offline test of a built site's subscription functions against a fake Upstash Redis and a fake Resend. Nothing
// leaves the machine; no real email is sent.
//
//   node plugins/lineage/publish/test_functions.js <built site folder>
//
// The site folder must hold api/ (from updates_page.py) and, for the digest, changelog.json and updates/posts.json
// (seo_build.py and updates_page.py); a local server stands in for the live site. Covers: not configured -> 503,
// honeypot, subscribe -> pending, confirm, digest (CRON_SECRET required, sends, idempotent per week), one-click
// unsubscribe, and that no email address is ever logged.
const http = require("http");
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const site = path.resolve(process.argv[2] || ".");
const api = path.join(site, "api");
if (!fs.existsSync(path.join(api, "subscribe.js"))) { console.error(`no api/subscribe.js in ${site}`); process.exit(2); }

// ---------------------------------------------------------------------------------------- fake Upstash + Resend
const db = new Map(), sets = new Map(), emails = [], googlePosts = [];
function redis(cmd) {
  const [op, k, ...a] = cmd; const O = op.toUpperCase();
  const set = () => { if (!sets.has(k)) sets.set(k, new Set()); return sets.get(k); };
  switch (O) {
    case "GET": return db.has(k) ? db.get(k) : null;
    case "SET": { if (a.includes("NX") && db.has(k)) return null; db.set(k, a[0]); return "OK"; }
    case "DEL": return (db.delete(k) ? 1 : 0) + (sets.delete(k) ? 1 : 0);
    case "INCR": { const n = Number(db.get(k) || 0) + 1; db.set(k, String(n)); return n; }
    case "EXPIRE": return 1;
    case "SADD": { const s = set(); let n = 0; for (const x of a) if (!s.has(x)) { s.add(x); n++; } return n; }
    case "SREM": { const s = set(); let n = 0; for (const x of a) if (s.delete(x)) n++; return n; }
    case "SMEMBERS": return [...(sets.get(k) || [])];
    case "SISMEMBER": return (sets.get(k) || new Set()).has(a[0]) ? 1 : 0;
    default: throw new Error("unsupported " + O);
  }
}
let failFor = null;                               // an address the fake Resend refuses (to test resuming)
const server = http.createServer((req, res) => {
  let body = "";
  req.on("data", c => (body += c));
  req.on("end", () => {
    if (req.url === "/kv" && req.method === "POST") {
      assert.strictEqual(req.headers.authorization, "Bearer kv-token");
      try { res.end(JSON.stringify({ result: redis(JSON.parse(body)) })); } catch (e) { res.end(JSON.stringify({ error: String(e) })); }
    } else if (req.url === "/resend/emails" && req.method === "POST") {
      assert.strictEqual(req.headers.authorization, "Bearer re_test");
      const msg = JSON.parse(body);
      if (failFor && msg.to.includes(failFor)) { res.statusCode = 500; return res.end("{}"); }
      emails.push({ ...JSON.parse(body), idem: req.headers["idempotency-key"] });
      res.end(JSON.stringify({ id: "em_" + emails.length }));
    } else if (req.url === "/google/token" && req.method === "POST") {
      const fields = new URLSearchParams(body);
      googlePosts.push(Object.fromEntries(fields));
      if (fields.get("code") === "bad") { res.statusCode = 400; return res.end("{}"); }
      const code = fields.get("code");
      res.end(JSON.stringify({ access_token: "tok_" + code }));
    } else if (req.url.split("?")[0] === "/google/userinfo") {
      const auth = req.headers.authorization || "";
      if (auth.endsWith("tok_unverified")) res.end(JSON.stringify({ email: "person@example.org", email_verified: false }));
      else if (auth.endsWith("tok_ok")) res.end(JSON.stringify({ email: "person@example.org", email_verified: true }));
      else { res.statusCode = 401; res.end("{}"); }
    } else {                                          // the "live site": static files from the built folder
      const f = path.join(site, decodeURIComponent(req.url.split("?")[0]));
      if (f.startsWith(site) && fs.existsSync(f) && fs.statSync(f).isFile()) res.end(fs.readFileSync(f));
      else { res.statusCode = 404; res.end("not found"); }
    }
  });
});

// ------------------------------------------------------------------------------ Vercel-like req/res for handlers
function call(name, { method = "GET", query = {}, body, headers = {} } = {}) {
  const handler = require(path.join(api, name + ".js"));
  return new Promise(resolve => {
    const qs = new URLSearchParams(query).toString();
    const req = { method, query, body, headers: { "x-forwarded-for": "203.0.113.9", ...headers }, url: `/api/${name}/${qs ? "?" + qs : ""}` };
    const out = { statusCode: 200, headers: {}, body: "" };
    const res = {
      setHeader: (k, v) => { out.headers[k.toLowerCase()] = v; },
      status(c) { out.statusCode = c; return res; },
      json(o) { out.body = o; resolve(out); return res; },
      send(s) { out.body = s; resolve(out); return res; },
    };
    Promise.resolve(handler(req, res)).catch(e => { out.statusCode = 999; out.body = String(e); resolve(out); });
  });
}

const logs = [];
for (const k of ["log", "error", "warn"]) { const o = console[k]; console[k] = (...a) => { logs.push(a.join(" ")); if (k !== "log") o("  [fn log]", ...a); }; }
const results = [];
async function step(name, fn) {
  try { await fn(); results.push(`PASS  ${name}`); }
  catch (e) { results.push(`FAIL  ${name}: ${e.message}`); process.exitCode = 1; }
}

const ENV = { KV_REST_API_URL: "", KV_REST_API_TOKEN: "kv-token", RESEND_API_KEY: "re_test", DIGEST_FROM: "Test <digest@example.org>",
  DIGEST_REPLY_TO: "reply@example.org", CRON_SECRET: "cron-secret-123456", SUBSCRIBE_SECRET: "s".repeat(40),
  DIGEST_POSTAL_ADDRESS: "PO Box 1, Example Town", SITE_URL: "", RESEND_API_BASE: "" };

server.listen(0, "127.0.0.1", async () => {
  const base = `http://127.0.0.1:${server.address().port}`;
  const EMAIL = "reader@example.org";
  let gstate = "";
  for (const k of Object.keys(ENV)) delete process.env[k];

  await step("not configured: GET/POST subscribe -> 503, nothing stored or sent", async () => {
    let r = await call("subscribe");
    assert.strictEqual(r.statusCode, 503); assert.strictEqual(r.body.open, false);
    r = await call("subscribe", { method: "POST", body: { email: EMAIL } });
    assert.strictEqual(r.statusCode, 503);
    for (const n of ["confirm", "unsubscribe"]) assert.strictEqual((await call(n, { query: { t: "x" } })).statusCode, 503);
    assert.strictEqual((await call("digest", { headers: { authorization: "Bearer cron-secret-123456" } })).statusCode, 503);
    assert.strictEqual(db.size + sets.size + emails.length, 0);
  });

  Object.assign(process.env, ENV, { KV_REST_API_URL: base + "/kv", SITE_URL: base, RESEND_API_BASE: base + "/resend" });
  await step("partly configured (no RESEND_API_KEY) -> still 503", async () => {
    delete process.env.RESEND_API_KEY;
    assert.strictEqual((await call("subscribe", { method: "POST", body: { email: EMAIL } })).statusCode, 503);
    process.env.RESEND_API_KEY = "re_test";
    assert.strictEqual(db.size + emails.length, 0);
  });

  await step("configured: GET subscribe -> open", async () => {
    const r = await call("subscribe"); assert.strictEqual(r.statusCode, 200); assert.strictEqual(r.body.open, true);
  });

  await step("honeypot: pretends success, stores and sends nothing", async () => {
    const r = await call("subscribe", { method: "POST", body: { email: EMAIL, website: "spam.example" } });
    assert.strictEqual(r.statusCode, 200); assert.strictEqual(db.size + emails.length, 0);
  });

  await step("bad address -> 400", async () => {
    assert.strictEqual((await call("subscribe", { method: "POST", body: { email: "not-an-address" } })).statusCode, 400);
  });

  let confirmLink;
  await step("subscribe -> pending record + confirmation email (form post, urlencoded)", async () => {
    const r = await call("subscribe", { method: "POST", body: `email=${encodeURIComponent(EMAIL)}&website=`, headers: { accept: "text/html" } });
    assert.strictEqual(r.statusCode, 200); assert.match(r.body, /Check your inbox/);
    const recs = [...db.entries()].filter(([k]) => k.includes(":sub:"));
    assert.strictEqual(recs.length, 1);
    const rec = JSON.parse(recs[0][1]);
    assert.deepStrictEqual(Object.keys(rec).sort(), ["confirmed", "created", "email", "status", "token_hash"]);
    assert.strictEqual(rec.status, "pending"); assert.strictEqual(rec.email, EMAIL);
    assert.ok(!recs[0][0].includes(EMAIL), "key must not contain the address");
    assert.strictEqual(emails.length, 1); assert.deepStrictEqual(emails[0].to, [EMAIL]);
    confirmLink = new URL(/https?:\/\/[^\s"]+\/api\/confirm\/?\?t=[^\s"]+/.exec(emails[0].text)[0]);
    const cs = [...sets.keys()].find(k => k.endsWith(":confirmed"));
    assert.ok(!cs || sets.get(cs).size === 0, "not a subscriber before confirming");
  });

  await step("confirm: forged token -> 400; real token -> confirmed", async () => {
    const t = confirmLink.searchParams.get("t");
    assert.strictEqual((await call("confirm", { query: { t: t.slice(0, -2) + "xx" } })).statusCode, 400);
    const r = await call("confirm", { query: { t } });
    assert.strictEqual(r.statusCode, 200); assert.match(r.body, /subscribed/);
    const rec = JSON.parse([...db.entries()].find(([k]) => k.includes(":sub:"))[1]);
    assert.strictEqual(rec.status, "confirmed"); assert.ok(rec.confirmed); assert.strictEqual(rec.token_hash, null);
    assert.strictEqual((await call("confirm", { query: { t } })).statusCode, 200);      // a second click is harmless
  });

  await step("subscribe again when confirmed: same answer, no new email", async () => {
    const n = emails.length;
    const r = await call("subscribe", { method: "POST", body: { email: EMAIL } });
    assert.strictEqual(r.statusCode, 200); assert.strictEqual(emails.length, n);
  });

  await step("digest: CRON_SECRET required (none / wrong -> 401)", async () => {
    assert.strictEqual((await call("digest")).statusCode, 401);
    assert.strictEqual((await call("digest", { headers: { authorization: "Bearer wrong" } })).statusCode, 401);
  });

  let unsubLink;
  const AUTH = { authorization: "Bearer cron-secret-123456" };
  await step("digest: sends this week's posts and changes, with unsubscribe link and postal footer", async () => {
    const n = emails.length;
    const r = await call("digest", { headers: AUTH });
    assert.strictEqual(r.statusCode, 200, JSON.stringify(r.body)); assert.strictEqual(r.body.status, "sent");
    assert.strictEqual(emails.length, n + 1);
    const m = emails[emails.length - 1];
    assert.match(m.text, /PO Box 1, Example Town/); assert.match(m.html, /Unsubscribe/);
    assert.ok(m.headers["List-Unsubscribe"] && m.headers["List-Unsubscribe-Post"]); assert.ok(m.idem);
    unsubLink = new URL(/<(.+)>/.exec(m.headers["List-Unsubscribe"])[1]);
    results.push(`      digest: ${r.body.posts} posts, ${r.body.entries} changelog entries; subject "${m.subject}"`);
  });

  await step("digest: idempotent per week (second run sends nothing)", async () => {
    const n = emails.length;
    const r = await call("digest", { headers: AUTH });
    assert.strictEqual(r.statusCode, 200); assert.strictEqual(r.body.status, "already-sent"); assert.strictEqual(emails.length, n);
  });

  await step("digest: a run that fails part way resumes, skipping whoever was already sent (new week simulated)", async () => {
    const B = "second@example.org";
    await call("subscribe", { method: "POST", body: { email: B }, headers: { "x-forwarded-for": "203.0.113.10" } });
    const link = new URL(/https?:\/\/[^\s"]+\/api\/confirm\/?\?t=[^\s"]+/.exec(emails[emails.length - 1].text)[0]);
    assert.strictEqual((await call("confirm", { query: { t: link.searchParams.get("t") } })).statusCode, 200);
    for (const k of [...db.keys()]) if (/digest:\d{4}-W\d\d:done/.test(k)) db.delete(k);
    for (const k of [...sets.keys()]) if (/digest:/.test(k)) sets.delete(k);              // a new week, new items
    failFor = B;
    const n = emails.length;
    let r = await call("digest", { headers: AUTH });
    assert.strictEqual(r.statusCode, 502); assert.strictEqual(r.body.status, "partial");
    assert.strictEqual(r.body.sent, 1); assert.strictEqual(r.body.failed, 1); assert.strictEqual(emails.length, n + 1);
    failFor = null;
    r = await call("digest", { headers: AUTH });
    assert.strictEqual(r.body.status, "sent"); assert.strictEqual(r.body.sent, 1); assert.strictEqual(r.body.skipped, 1);
    assert.strictEqual(emails.length, n + 2); assert.deepStrictEqual(emails[emails.length - 1].to, [B]);
    assert.strictEqual((await call("digest", { headers: AUTH })).body.status, "already-sent");
    const id = [...db.entries()].find(([k, v]) => k.includes(":sub:") && v.includes(B))[0].split(":sub:")[1];   // B leaves
    await call("unsubscribe", { query: { t: new URL(/<(.+)>/.exec(emails[emails.length - 1].headers["List-Unsubscribe"])[1]).searchParams.get("t") } });
    assert.ok(!db.has([...db.keys()].find(k => k.endsWith(id)) || "none"));
  });

  await step("unsubscribe: forged -> 400; one click deletes the record", async () => {
    const t = unsubLink.searchParams.get("t");
    assert.strictEqual((await call("unsubscribe", { query: { t: t.slice(0, -2) + "xx" } })).statusCode, 400);
    const r = await call("unsubscribe", { query: { t } });
    assert.strictEqual(r.statusCode, 200); assert.match(r.body, /deleted/);
    assert.strictEqual([...db.keys()].filter(k => k.includes(":sub:")).length, 0);
    const conf = [...sets.entries()].find(([k]) => k.endsWith(":confirmed"));
    assert.strictEqual(conf[1].size, 0);
    assert.strictEqual((await call("unsubscribe", { method: "POST", query: { t } })).statusCode, 200);   // RFC 8058 POST, idempotent
  });

  await step("digest after unsubscribe (new week): nobody is emailed", async () => {
    for (const k of [...db.keys()]) if (/digest:\d{4}-W\d\d:done/.test(k)) db.delete(k);
    for (const k of [...sets.keys()]) if (/digest:/.test(k)) sets.delete(k);
    const n = emails.length;
    const r = await call("digest", { headers: AUTH });
    assert.strictEqual(r.statusCode, 200); assert.strictEqual(emails.length, n);
  });

  await step("google stays off until both client values are set", async () => {
    const r = await call("subscribe");
    assert.strictEqual(r.body.google, false);
    assert.strictEqual((await call("google")).statusCode, 503);
    process.env.GOOGLE_CLIENT_ID = "client-id";
    assert.strictEqual((await call("google")).statusCode, 503);   // secret still missing
    process.env.GOOGLE_CLIENT_SECRET = "client-secret";
    process.env.GOOGLE_TOKEN_URL = base + "/google/token";
    process.env.GOOGLE_USERINFO_URL = base + "/google/userinfo";
  });

  await step("google: start redirects with a signed state cookie", async () => {
    const r = await call("google");
    assert.strictEqual(r.statusCode, 302);
    const loc = new URL(r.headers.location);
    assert.strictEqual(loc.searchParams.get("client_id"), "client-id");
    assert.strictEqual(loc.searchParams.get("scope"), "openid email");
    assert.match(loc.searchParams.get("redirect_uri"), /\/api\/google\/$/);
    const cookie = /lsub_g=([^;]+)/.exec(r.headers["set-cookie"])[1];
    assert.strictEqual(cookie, loc.searchParams.get("state"));
    gstate = cookie;
  });

  await step("google: bad state, unverified email, then a verified address is confirmed", async () => {
    const state = gstate;
    assert.strictEqual((await call("google", { query: { code: "ok", state: "nope" }, headers: { cookie: "lsub_g=" + state } })).statusCode, 400);
    assert.strictEqual((await call("google", { query: { code: "unverified", state }, headers: { cookie: "lsub_g=" + state } })).statusCode, 400);
    const before = [...db.keys()].filter(k => k.includes(":sub:")).length;
    const n = emails.length;
    const r = await call("google", { query: { code: "ok", state }, headers: { cookie: "lsub_g=" + state } });
    assert.strictEqual(r.statusCode, 200); assert.match(String(r.body), /subscribed/);
    assert.strictEqual(emails.length, n + 1);
    assert.match(emails[emails.length - 1].text, /Unsubscribe/);
    const recs = [...db.entries()].filter(([k, v]) => k.includes(":sub:") && v.includes("person@example.org"));
    assert.strictEqual(recs.length, 1);
    assert.strictEqual(JSON.parse(recs[0][1]).status, "confirmed");
    assert.ok(recs.length >= 1);
    assert.ok([...db.keys()].filter(k => k.includes(":sub:")).length >= before);
    assert.strictEqual(googlePosts.at(-1).code, "ok");
    db.delete(recs[0][0]);
  });

  await step("no email address in any function log", async () => {
    assert.ok(!logs.some(l => l.includes("@")), logs.join("\n"));
  });

  process.stdout.write(results.join("\n") + "\n");
  process.stdout.write(`${results.filter(r => r.startsWith("PASS")).length} passed, ${results.filter(r => r.startsWith("FAIL")).length} failed. `);
  process.stdout.write(`${emails.length} emails captured by the fake Resend; none sent.\n`);
  server.close();
});
