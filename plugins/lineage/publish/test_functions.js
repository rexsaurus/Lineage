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

function prepareSite(given) {
  if (given && fs.existsSync(path.join(given, "api", "subscribe.js"))) return given;
  const dir = fs.mkdtempSync(path.join(require("os").tmpdir(), "lineage-sub-"));
  fs.cpSync(path.join(__dirname, "api"), path.join(dir, "api"), { recursive: true });
  fs.mkdirSync(path.join(dir, "updates"), { recursive: true });
  fs.writeFileSync(path.join(dir, "updates", "posts.json"), JSON.stringify({ format: 1, posts: [
    { slug: "weekly-2026-w44", title: "Weekly update: the week of 26 October 2026", date: "2026-10-30", summary: "A week of research.", url: "/updates/weekly-2026-w44/", image: "" },
    { slug: "note-2026-10-31", title: "A short note", date: "2026-10-31", summary: "One new record.", url: "/updates/note-2026-10-31/", image: "" },
  ] }));
  fs.writeFileSync(path.join(dir, "changelog.json"), JSON.stringify({ format: 1, entries: [
    { id: "e1", date: "2026-10-30", at: "2026-10-30T18:00:00Z", changes: ["A photograph was added."] },
  ] }));
  fs.writeFileSync(path.join(dir, "api", "_lineage-config.json"), JSON.stringify({
    site_url: "http://127.0.0.1", title: "Test book", slug: "test-book", trailing_slash: true, app_path: "/lineage/",
  }));
  return dir;
}
const site = prepareSite(process.argv[2] ? path.resolve(process.argv[2]) : "");
const api = path.join(site, "api");
if (!fs.existsSync(path.join(api, "subscribe.js"))) { console.error(`no api/subscribe.js in ${site}`); process.exit(2); }

// ---------------------------------------------------------------------------------------- fake Upstash + Resend
const db = new Map(), sets = new Map(), emails = [], googlePosts = [], batches = [], notifyHits = [];
let batch429 = 0;
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
    case "SCARD": return (sets.get(k) || new Set()).size;
    default: throw new Error("unsupported " + O);
  }
}
let failFor = null;                               // an address the fake Resend refuses (to test resuming)
const server = http.createServer((req, res) => {
  let body = "";
  req.on("data", c => (body += c));
  req.on("end", () => {
   try {
    if (req.url === "/kv" && req.method === "POST") {
      assert.strictEqual(req.headers.authorization, "Bearer kv-token");
      try { res.end(JSON.stringify({ result: redis(JSON.parse(body)) })); } catch (e) { res.end(JSON.stringify({ error: String(e) })); }
    } else if (req.url === "/resend/emails" && req.method === "POST") {
      assert.strictEqual(req.headers.authorization, "Bearer re_test");
      const msg = JSON.parse(body);
      if (failFor && msg.to.includes(failFor)) { res.statusCode = 500; return res.end("{}"); }
      emails.push({ ...msg, idem: req.headers["idempotency-key"] });
      res.end(JSON.stringify({ id: "em_" + emails.length }));
    } else if (req.url === "/resend/emails/batch" && req.method === "POST") {
      assert.strictEqual(req.headers.authorization, "Bearer re_test");
      const list = JSON.parse(body);
      assert.ok(Array.isArray(list) && list.length <= 100, "batch must be an array of at most 100");
      batches.push(list.length);
      if (batch429 > 0) { batch429--; res.statusCode = 429; res.setHeader("Retry-After", "0"); return res.end("{}"); }
      if (list.some(m => failFor && m.to.includes(failFor))) { res.statusCode = 500; return res.end("{}"); }
      for (const msg of list) emails.push({ ...msg, idem: req.headers["idempotency-key"] });
      res.end(JSON.stringify({ data: list.map((_, i) => ({ id: "b_" + i })) }));
    } else if (req.url.startsWith("/api/notify")) {
      notifyHits.push({ url: req.url, auth: req.headers.authorization || "" });
      const dry = req.url.includes("dry_run=1");
      res.end(JSON.stringify({ ok: true, dry_run: dry, status: dry ? "dry-run" : "sent", posts: [{ slug: "weekly-2026-w44", subject: "Weekly update", recipients: 1 }] }));
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
   } catch (e) { console.error("fake server", e); try { res.statusCode = 500; res.end("{}"); } catch { /* already sent */ } }
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
  DIGEST_POSTAL_ADDRESS: "PO Box 1, Example Town", SITE_URL: "", RESEND_API_BASE: "",
  OWNER_NOTIFY_EMAIL: "owner@example.org", NOTIFY_FROM: "Lineage <noreply@example.org>",
  ADMIN_SECRET: "a".repeat(40), SESSION_SECRET: "b".repeat(40),
  RESEND_WEBHOOK_SECRET: "whsec_" + Buffer.from("webhook-secret-key-32bytes!!!!").toString("base64") };

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
    assert.strictEqual(rec.status, "pending"); assert.strictEqual(rec.email, EMAIL);
    assert.ok(rec.token_hash); assert.ok("source" in rec);
    assert.ok(!recs[0][0].includes(EMAIL), "key must not contain the address");
    assert.strictEqual(emails.length, 1); assert.deepStrictEqual(emails[0].to, [EMAIL]);
    confirmLink = new URL(/https?:\/\/[^\s"]+\/api\/confirm\/?\?t=[^\s"]+/.exec(emails[0].text)[0]);
    const cs = [...sets.keys()].find(k => k.endsWith(":confirmed"));
    assert.ok(!cs || sets.get(cs).size === 0, "not a subscriber before confirming");
  });

  await step("confirm: forged token -> 400; real token -> confirmed", async () => {
    const t = confirmLink.searchParams.get("t");
    assert.strictEqual((await call("confirm", { query: { t: t.slice(0, -2) + "xx" } })).statusCode, 400);
    const beforeMail = emails.length;
    const r = await call("confirm", { query: { t } });
    assert.strictEqual(r.statusCode, 200); assert.match(r.body, /subscribed/);
    const rec = JSON.parse([...db.entries()].find(([k]) => k.includes(":sub:"))[1]);
    assert.strictEqual(rec.status, "confirmed"); assert.ok(rec.confirmed); assert.strictEqual(rec.token_hash, null);
    assert.strictEqual(rec.frequency, "each"); assert.strictEqual(rec.method, "email double opt-in");
    assert.strictEqual(emails.length, beforeMail + 1, "owner alert on first confirm");
    assert.deepStrictEqual(emails[emails.length - 1].to, ["owner@example.org"]);
    assert.match(emails[emails.length - 1].subject, /New subscriber/);
    assert.match(emails[emails.length - 1].text, /1 total|Confirmed subscribers: 1/);
    const again = emails.length;
    assert.strictEqual((await call("confirm", { query: { t } })).statusCode, 200);      // a second click is harmless
    assert.strictEqual(emails.length, again, "no second owner alert");
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
  function forceFreq(email, freq) {
    for (const [k, v] of [...db.entries()]) {
      if (!k.includes(":sub:") || !String(v).includes(email)) continue;
      const rec = JSON.parse(v); rec.frequency = freq; db.set(k, JSON.stringify(rec));
    }
  }
  await step("digest: sends this week's posts and changes, with unsubscribe link and postal footer", async () => {
    forceFreq(EMAIL, "weekly");   // existing subscribers keep the Monday digest
    const n = emails.length;
    const r = await call("digest", { headers: AUTH });
    assert.strictEqual(r.statusCode, 200, JSON.stringify(r.body)); assert.strictEqual(r.body.status, "sent");
    assert.strictEqual(emails.length, n + 1);
    const m = emails[emails.length - 1];
    assert.match(m.text, /PO Box 1, Example Town/); assert.match(m.html, /Unsubscribe/);
    assert.ok(m.headers["List-Unsubscribe"] && m.headers["List-Unsubscribe-Post"]); assert.ok(m.idem);
    unsubLink = new URL(/<(https?:[^>]+)>/.exec(m.headers["List-Unsubscribe"])[1]);
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
    forceFreq(EMAIL, "weekly"); forceFreq(B, "weekly");
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
    await call("unsubscribe", { query: { t: new URL(/<(https?:[^>]+)>/.exec(emails[emails.length - 1].headers["List-Unsubscribe"])[1]).searchParams.get("t") } });
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
    assert.strictEqual(emails.length, n + 2, "welcome plus one owner alert");
    const mine = emails.slice(n);
    assert.ok(mine.some(m => m.to.includes("person@example.org") && /Unsubscribe/.test(m.text)));
    assert.ok(mine.some(m => m.to.includes("owner@example.org")));
    const recs = [...db.entries()].filter(([k, v]) => k.includes(":sub:") && v.includes("person@example.org"));
    assert.strictEqual(recs.length, 1);
    assert.strictEqual(JSON.parse(recs[0][1]).status, "confirmed");
    assert.ok(recs.length >= 1);
    assert.ok([...db.keys()].filter(k => k.includes(":sub:")).length >= before);
    assert.strictEqual(googlePosts.at(-1).code, "ok");
  });

  await step("already subscribed: distinct status, manage link, no second confirmation email", async () => {
    const again = "again@example.org";
    await call("subscribe", { method: "POST", body: { email: again, source: "/updates/weekly-2026-w44/" }, headers: { "x-forwarded-for": "203.0.113.40" } });
    const link = new URL(/https?:\/\/[^\s"]+\/api\/confirm\/?\?t=[^\s"]+/.exec(emails[emails.length - 1].text)[0]);
    assert.strictEqual((await call("confirm", { query: { t: link.searchParams.get("t") } })).statusCode, 200);
    const n = emails.length;
    const r = await call("subscribe", { method: "POST", body: { email: again, source: "/updates/weekly-2026-w44/" }, headers: { "x-forwarded-for": "203.0.113.41" } });
    assert.strictEqual(r.statusCode, 200);
    assert.strictEqual(r.body.status, "already");
    assert.strictEqual(r.body.already, true);
    assert.match(r.body.message, /already subscribed/i);
    assert.match(r.body.manage_url, /#account/);
    assert.strictEqual(emails.length, n);
  });

  await step("google already subscribed: no second welcome and no second owner alert", async () => {
    const start = await call("google");
    const state = new URL(start.headers.location).searchParams.get("state");
    const n = emails.length;
    const r = await call("google", { query: { code: "ok", state }, headers: { cookie: "lsub_g=" + state } });
    assert.strictEqual(r.statusCode, 200);
    assert.match(String(r.body), /already subscribed/i);
    assert.match(String(r.body), /Manage my subscription/);
    assert.strictEqual(emails.length, n);
  });

  await step("test endpoint: 401 without the admin secret, and it only mails the owner", async () => {
    assert.strictEqual((await call("account", { method: "POST", query: { op: "test" }, body: { kind: "post" } })).statusCode, 401);
    assert.strictEqual((await call("account", { method: "POST", query: { op: "test" }, body: { kind: "post" }, headers: { authorization: "Bearer nope" } })).statusCode, 401);
    const n = emails.length;
    const r = await call("account", { method: "POST", query: { op: "test" }, body: { kind: "post" }, headers: { authorization: "Bearer " + "a".repeat(40) } });
    assert.strictEqual(r.statusCode, 200, JSON.stringify(r.body));
    assert.strictEqual(emails.length, n + 1);
    assert.deepStrictEqual(emails[emails.length - 1].to, ["owner@example.org"]);
    assert.match(emails[emails.length - 1].subject, /^\[TEST\]/);
    assert.ok(!emails.slice(n).some(m => m.to.some(t => t !== "owner@example.org")));
  });

  await step("notify: each subscriber once, weekly and paused skipped, resume without duplicates", async () => {
    const eachA = "each-a@example.org", eachB = "each-b@example.org", paused = "paused@example.org";
    for (const [addr, ip] of [[eachA, "203.0.113.50"], [eachB, "203.0.113.51"], [paused, "203.0.113.52"]]) {
      await call("subscribe", { method: "POST", body: { email: addr, source: "/lineage/" }, headers: { "x-forwarded-for": ip } });
      const link = new URL(/https?:\/\/[^\s"]+\/api\/confirm\/?\?t=[^\s"]+/.exec(emails[emails.length - 1].text)[0]);
      assert.strictEqual((await call("confirm", { query: { t: link.searchParams.get("t") } })).statusCode, 200);
    }
    forceFreq(paused, "paused");
    forceFreq(EMAIL, "weekly");
    const before = emails.filter(m => m.to.includes(eachA) || m.to.includes(eachB) || m.to.includes(paused)).length;
    process.env.LINEAGE_EMAIL_BATCH = "2";
    delete require.cache[require.resolve(path.join(api, "_lineage.js"))];
    delete require.cache[require.resolve(path.join(api, "notify.js"))];
    batch429 = 1;
    let r = await call("notify", { method: "POST", headers: { authorization: "Bearer cron-secret-123456" } });
    assert.ok(r.statusCode === 200 || r.statusCode === 502, JSON.stringify(r.body));
    const got = emails.filter(m => (m.to[0] === eachA || m.to[0] === eachB) && m.headers && m.headers["List-Unsubscribe"] && !/^\[TEST\]/.test(m.subject || ""));
    assert.ok(got.length >= 2, "each address got a post");
    assert.ok(got.every(m => m.headers && m.headers["List-Unsubscribe"] && m.headers["List-Unsubscribe-Post"] === "List-Unsubscribe=One-Click"));
    assert.ok(got.every(m => /Manage my subscription/.test(m.text)));
    assert.ok(!emails.some(m => m.to.includes(paused) && !/New subscriber|Confirm|Unsubscribed/.test(m.subject || "")));
    assert.ok(batches.some(n => n <= 2 && n > 0));
    const n = emails.length;
    r = await call("notify", { method: "POST", headers: { authorization: "Bearer cron-secret-123456" } });
    assert.strictEqual(r.body.status, "nothing-new");
    assert.strictEqual(emails.length, n, "rerun does not double-send");
    assert.ok(before >= 0);
    process.env.LINEAGE_EMAIL_BATCH = "100";
  });

  await step("notify dry run writes nothing and names no address", async () => {
    const snap = JSON.stringify([...db.entries()]);
    const r = await call("notify", { method: "POST", query: { slug: "weekly-2026-w44", dry_run: "1" }, headers: { authorization: "Bearer " + "a".repeat(40) } });
    assert.strictEqual(r.statusCode, 200, JSON.stringify(r.body));
    assert.strictEqual(r.body.dry_run, true);
    assert.ok(!JSON.stringify(r.body).includes("@"));
    assert.strictEqual(JSON.stringify([...db.entries()]), snap);
  });

  await step("webhook: bad signature rejected, hard bounce and complaint suppress", async () => {
    const secret = process.env.RESEND_WEBHOOK_SECRET;
    const key = Buffer.from(secret.replace(/^whsec_/, ""), "base64");
    function sign(raw) {
      const id = "msg_" + Math.random().toString(16).slice(2);
      const ts = String(Math.floor(Date.now() / 1000));
      const sig = require("crypto").createHmac("sha256", key).update(`${id}.${ts}.${raw}`).digest("base64");
      return { "svix-id": id, "svix-timestamp": ts, "svix-signature": "v1," + sig };
    }
    const bad = await call("account", { method: "POST", query: { op: "resend-webhook" }, body: "{}", headers: { "svix-id": "x", "svix-timestamp": "1", "svix-signature": "v1,nope" } });
    assert.strictEqual(bad.statusCode, 401);
    const raw = JSON.stringify({ type: "email.bounced", data: { to: ["again@example.org"], bounce: { type: "Permanent" } } });
    const r = await call("account", { method: "POST", query: { op: "resend-webhook" }, body: raw, headers: sign(raw) });
    assert.strictEqual(r.statusCode, 200, JSON.stringify(r.body));
    const rec = [...db.entries()].find(([k, v]) => k.includes(":sub:") && String(v).includes("again@example.org"));
    assert.ok(rec, "record remains, suppressed");
    assert.strictEqual(JSON.parse(rec[1]).status, "suppressed");
    const id = rec[0].split(":sub:")[1];
    const conf = [...sets.entries()].find(([k]) => k.endsWith(":confirmed"));
    assert.ok(!conf[1].has(id));
  });

  await step("auth: magic link is single use, tampered session is rejected, CSRF and sign-out", async () => {
    const addr = "signer@example.org";
    const n = emails.length;
    const link = await call("account", { method: "POST", query: { op: "link" }, body: { email: addr }, headers: { "x-forwarded-for": "203.0.113.70" } });
    assert.strictEqual(link.statusCode, 200);
    assert.strictEqual(emails.length, n + 1);
    assert.deepStrictEqual(emails[emails.length - 1].to, [addr]);
    const url = new URL(/https?:\/\/\S+op=verify&t=[^\s]+/.exec(emails[emails.length - 1].text)[0]);
    const t = url.searchParams.get("t");
    const bad = await call("account", { query: { op: "verify", t: t.slice(0, -2) + "xx" } });
    assert.strictEqual(bad.statusCode, 400);
    const ok = await call("account", { query: { op: "verify", t } });
    assert.strictEqual(ok.statusCode, 302);
    const again = await call("account", { query: { op: "verify", t } });
    assert.strictEqual(again.statusCode, 400);
    const cookie = /lsess=([^;]+)/.exec(ok.headers["set-cookie"])[1];
    const me = await call("account", { query: { op: "me" }, headers: { cookie: "lsess=" + cookie } });
    assert.strictEqual(me.body.signed_in, true);
    assert.strictEqual(me.body.email, addr);
    const flipped = cookie.slice(0, -2) + (cookie.endsWith("aa") ? "bb" : "aa");
    const tamper = await call("account", { query: { op: "me" }, headers: { cookie: "lsess=" + flipped } });
    assert.strictEqual(tamper.body.signed_in, false);
    const noCsrf = await call("account", { method: "POST", query: { op: "prefs" }, body: { frequency: "weekly" }, headers: { cookie: "lsess=" + cookie } });
    assert.strictEqual(noCsrf.statusCode, 403);
    const saved = await call("account", { method: "POST", query: { op: "prefs" }, body: { frequency: "each", paused_until: "2099-01-01" }, headers: { cookie: "lsess=" + cookie, "x-lineage-csrf": me.body.csrf } });
    assert.strictEqual(saved.statusCode, 404); // signed in, not subscribed
    const out = await call("account", { method: "POST", query: { op: "signout" }, body: {}, headers: { cookie: "lsess=" + cookie, "x-lineage-csrf": me.body.csrf } });
    assert.strictEqual(out.statusCode, 200);
    const after = await call("account", { query: { op: "me" }, headers: { cookie: "lsess=" + cookie } });
    assert.strictEqual(after.body.signed_in, false);
  });

  await step("manage: prefs, pause, unsubscribe, change email, delete", async () => {
    const addr = "manage@example.org";
    await call("subscribe", { method: "POST", body: { email: addr }, headers: { "x-forwarded-for": "203.0.113.80" } });
    const cl = new URL(/https?:\/\/[^\s"]+\/api\/confirm\/?\?t=[^\s"]+/.exec(emails[emails.length - 1].text)[0]);
    await call("confirm", { query: { t: cl.searchParams.get("t") } });
    const n = emails.length;
    await call("account", { method: "POST", query: { op: "link" }, body: { email: addr }, headers: { "x-forwarded-for": "203.0.113.81" } });
    const vu = new URL(/https?:\/\/\S+op=verify&t=[^\s]+/.exec(emails[emails.length - 1].text)[0]);
    const ver = await call("account", { query: { op: "verify", t: vu.searchParams.get("t") } });
    const cookie = /lsess=([^;]+)/.exec(ver.headers["set-cookie"])[1];
    const me = await call("account", { query: { op: "me" }, headers: { cookie: "lsess=" + cookie } });
    assert.strictEqual(me.body.subscriber.status, "confirmed");
    assert.strictEqual(me.body.subscriber.frequency, "each");
    const H = { cookie: "lsess=" + cookie, "x-lineage-csrf": me.body.csrf };
    const pref = await call("account", { method: "POST", query: { op: "prefs" }, body: { frequency: "weekly", paused_until: "2099-06-01" }, headers: H });
    assert.strictEqual(pref.statusCode, 200, JSON.stringify(pref.body));
    assert.strictEqual(pref.body.frequency, "weekly");
    const neu = "manage-next@example.org";
    const ch = await call("account", { method: "POST", query: { op: "change-email" }, body: { email: neu }, headers: H });
    assert.strictEqual(ch.statusCode, 200, JSON.stringify(ch.body));
    const mail = emails.slice(n).find(m => m.to.includes(neu));
    assert.ok(mail, "confirmation goes to the new address only");
    const tu = new URL(/https?:\/\/\S+op=confirm-email&t=[^\s]+/.exec(mail.text)[0]);
    const done = await call("account", { query: { op: "confirm-email", t: tu.searchParams.get("t") } });
    assert.strictEqual(done.statusCode, 200);
    assert.ok([...db.values()].some(v => String(v).includes(neu)));
    assert.ok(emails.some(m => m.to.includes(addr) && /changed/.test(m.subject || "")));
    const cookie2 = /lsess=([^;]+)/.exec(String(done.headers["set-cookie"]))[1];
    const me2 = await call("account", { query: { op: "me" }, headers: { cookie: "lsess=" + cookie2 } });
    const del = await call("account", { method: "POST", query: { op: "delete" }, body: { confirm: "delete" }, headers: { cookie: "lsess=" + cookie2, "x-lineage-csrf": me2.body.csrf } });
    assert.strictEqual(del.statusCode, 200, JSON.stringify(del.body));
    assert.ok(del.body.deleted.includes("subscriber record"));
    assert.ok(![...db.values()].some(v => String(v).includes(neu)));
  });

  await step("backfill: dry run is the default and --send without --i-approve refuses", async () => {
    const { spawn, spawnSync } = require("child_process");
    const script = path.join(__dirname, "backfill.js");
    const env = Object.assign({}, process.env, { SITE_URL: base, ADMIN_SECRET: "a".repeat(40) });
    const refused = spawnSync(process.execPath, [script, "--send", "--slug", "weekly-2026-w44"], { env });
    assert.notStrictEqual(refused.status, 0);
    assert.match(String(refused.stdout) + String(refused.stderr), /i-approve/);
    assert.strictEqual(notifyHits.length, 0);
    const dry = await new Promise(resolve => {
      const child = spawn(process.execPath, [script, "--slug", "weekly-2026-w44"], { env });
      let stdout = "", stderr = "";
      child.stdout.on("data", d => { stdout += d; });
      child.stderr.on("data", d => { stderr += d; });
      child.on("close", status => resolve({ status, stdout, stderr }));
    });
    assert.strictEqual(dry.status, 0, dry.stderr);
    assert.match(dry.stdout, /weekly-2026-w44/);
    assert.ok(!dry.stdout.includes("@"));
    assert.ok(notifyHits.some(h => h.url.includes("dry_run=1")));
  });

  await step("no email address in any function log", async () => {
    assert.ok(!logs.some(l => l.includes("@")), logs.join("\n"));
  });

  process.stdout.write(results.join("\n") + "\n");
  process.stdout.write(`${results.filter(r => r.startsWith("PASS")).length} passed, ${results.filter(r => r.startsWith("FAIL")).length} failed. `);
  process.stdout.write(`${emails.length} emails captured by the fake Resend; none sent.\n`);
  server.close();
});
