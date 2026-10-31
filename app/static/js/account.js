/* Sign in and Manage my subscription. The account API lives at /api/account/.
   When that API answers 503 the Sign in control stays hidden. Subscribe itself stays the header button
   and the form on the Updates tab. */
const GMARK = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23EA4335' d='M24 9.5c3.5 0 6.6 1.2 9 3.5l6.7-6.7C35.6 2.4 30.2 0 24 0 14.6 0 6.6 5.4 2.6 13.2l7.8 6C12.3 13.6 17.7 9.5 24 9.5z'/%3E%3Cpath fill='%234285F4' d='M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z'/%3E%3Cpath fill='%23FBBC05' d='M10.4 28.8A14.5 14.5 0 0 1 9.5 24c0-1.7.3-3.3.9-4.8l-7.8-6A24 24 0 0 0 0 24c0 3.9.9 7.5 2.6 10.8z'/%3E%3Cpath fill='%2334A853' d='M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.9 2.3-8.4 2.3-6.3 0-11.7-4.1-13.6-9.8l-7.8 6C6.6 42.6 14.6 48 24 48z'/%3E%3C/svg%3E";
const ACCT = { me: null };

function acctSource() {
  const s = (location.pathname || "/") + (location.search || "");
  return /^\/[A-Za-z0-9/_.#?=&%-]{0,200}$/.test(s) ? s : "/";
}
async function acctFetch(op, { method = "GET", body = null, csrf = false } = {}) {
  const headers = { Accept: "application/json" };
  if (body) headers["Content-Type"] = "application/json";
  if (csrf && ACCT.me && ACCT.me.csrf) headers["X-Lineage-CSRF"] = ACCT.me.csrf;
  const r = await fetch("/api/account/?op=" + encodeURIComponent(op), { method, headers, body: body ? JSON.stringify(body) : undefined, cache: "no-store" });
  const j = await r.json().catch(() => ({}));
  j._status = r.status;
  return j;
}

function acctDialog() {
  let root = document.getElementById("lsign");
  if (root) { root.hidden = false; root.querySelector("input")?.focus(); return; }
  root = document.createElement("div");
  root.id = "lsign";
  root.className = "lsub-modal";
  root.innerHTML = `<button type="button" class="lsub-backdrop" aria-label="Close sign in"></button>
    <div class="lsub-dialog lsign" role="dialog" aria-modal="true" aria-labelledby="lsign-h">
      <button type="button" class="lsub-x" aria-label="Close">×</button>
      <p class="lsub-h" id="lsign-h">Sign in</p>
      <p class="lsub-note">Use Google, or get a one-time link by email. The link expires in 15 minutes.</p>
      <p><a class="lsi-google" href="/api/google/?mode=signin&amp;source=${encodeURIComponent(acctSource())}">Continue with Google</a></p>
      <form id="lsign-form">
        <label class="lsub-l" for="lsign-email">Email address</label>
        <input id="lsign-email" type="email" required autocomplete="email" placeholder="you@example.com" maxlength="254">
        <button type="submit">Email me a sign-in link</button>
      </form>
      <p class="lsub-msg" id="lsign-msg" role="status"></p>
    </div>`;
  if (!document.getElementById("lsign-css")) {
    const st = document.createElement("style");
    st.id = "lsign-css";
    st.textContent = ".lsign .lsi-google{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;min-height:44px;box-sizing:border-box;padding:8px 16px;border-radius:9px;background:#8E1A14;color:#fff;font-weight:600;text-decoration:none}" +
      ".lsign .lsi-google:hover{background:#73140F;color:#fff}" +
      ".lsign .lsi-google:focus-visible{outline:2px solid #1A1814;outline-offset:2px}" +
      ".lsign .lsi-google::before{content:\"\";flex:none;width:18px;height:18px;background:url(\"" + GMARK + "\") center/18px 18px no-repeat}" +
      ".lsign form{display:flex;flex-direction:column;gap:8px;margin-top:12px}.lsign input{min-height:44px;font:inherit;padding:8px 10px;border:1px solid var(--line,#DED8CA);border-radius:9px}" +
      ".lsign button[type=submit]{min-height:44px;border:0;border-radius:9px;background:#1A1814;color:#F7F3EC;font:inherit;cursor:pointer}";
    document.head.appendChild(st);
  }
  document.body.appendChild(root);
  root.querySelector(".lsub-backdrop").onclick = () => { root.hidden = true; };
  root.querySelector(".lsub-x").onclick = () => { root.hidden = true; };
  root.querySelector("#lsign-form").onsubmit = async (ev) => {
    ev.preventDefault();
    const msg = root.querySelector("#lsign-msg");
    const btn = root.querySelector("button[type=submit]");
    btn.disabled = true;
    msg.textContent = "Sending…";
    try {
      const j = await acctFetch("link", { method: "POST", body: { email: root.querySelector("#lsign-email").value } });
      msg.textContent = j.message || (j.ok ? "If that address can sign in, a link is on its way." : "Sorry, that did not go through.");
    } catch { msg.textContent = "Sorry, that did not go through."; }
    btn.disabled = false;
  };
  root.querySelector("#lsign-email").focus();
}

function drawAccount() {
  const sign = document.getElementById("hdr-sign");
  const box = document.getElementById("hdr-acct");
  if (!sign || !box) return;
  const me = ACCT.me;
  if (!me || me._status === 503 || me.open === false) { sign.classList.add("hidden"); box.classList.add("hidden"); return; }
  if (!me.signed_in) {
    box.classList.add("hidden");
    sign.classList.remove("hidden");
    sign.onclick = () => acctDialog();
    return;
  }
  sign.classList.add("hidden");
  box.classList.remove("hidden");
  const initial = (me.email || "?").trim().charAt(0).toUpperCase();
  box.innerHTML = `<button type="button" class="hacct-btn" id="hacct-btn" aria-haspopup="menu" aria-expanded="false" aria-label="Account menu for ${esc(me.email)}">${esc(initial)}</button>
    <div class="hacct-menu hidden" id="hacct-menu" role="menu">
      <div class="hacct-email">${esc(me.email)}</div>
      <a role="menuitem" href="#account">Manage my subscription</a>
      <button type="button" role="menuitem" id="hacct-out">Sign out</button>
    </div>`;
  const btn = box.querySelector("#hacct-btn");
  const menu = box.querySelector("#hacct-menu");
  btn.onclick = () => {
    const open = menu.classList.toggle("hidden");
    btn.setAttribute("aria-expanded", open ? "false" : "true");
  };
  box.querySelector("#hacct-out").onclick = async () => {
    await acctFetch("signout", { method: "POST", body: {}, csrf: true });
    ACCT.me = { open: true, signed_in: false };
    drawAccount();
    if (S.tab === "account" && typeof BUILDERS.account === "function") BUILDERS.account(document.getElementById("tab-account"));
  };
}

async function lineageAccount() {
  try { ACCT.me = await acctFetch("me"); }
  catch { ACCT.me = { _status: 503, open: false }; }
  drawAccount();
}

function freqRadios(cur) {
  return ["each", "Each new update", "weekly", "Monday digest", "paused", "Paused"].reduce((html, x, i, a) => {
    if (i % 2) return html;
    const v = a[i], label = a[i + 1];
    return html + `<label style="display:flex;gap:8px;align-items:center;min-height:44px"><input type="radio" name="acct-freq" value="${v}" ${cur === v ? "checked" : ""}> ${esc(label)}</label>`;
  }, "");
}

BUILDERS.account = async function (el) {
  el.innerHTML = '<p class="empty">Loading…</p>';
  if (!ACCT.me) {
    try { ACCT.me = await acctFetch("me"); } catch { ACCT.me = { _status: 503 }; }
  }
  const me = ACCT.me;
  if (!me || me._status === 503 || me.open === false) {
    el.innerHTML = '<div class="card" style="max-width:640px"><h2>Manage my subscription</h2><p>Sign-in is not open on this site yet.</p></div>';
    return;
  }
  if (!me.signed_in) {
    el.innerHTML = '<div class="card" style="max-width:640px"><h2>Manage my subscription</h2><p>Sign in to see or change a subscription.</p><p><button class="btn go" id="acct-signin" type="button" style="min-height:44px">Sign in</button></p></div>';
    el.querySelector("#acct-signin").onclick = () => acctDialog();
    return;
  }
  const sub = me.subscriber || { status: "none" };
  const status = sub.status === "confirmed" ? `Subscribed${sub.since ? " since " + esc(sub.since.slice(0, 10)) : ""}${sub.method ? " (" + esc(sub.method) + ")" : ""}` : sub.status === "pending" ? "Pending confirmation" : sub.status === "paused" ? "Paused" : "Not subscribed";
  const owner = me.owner ? `<p><strong>${me.confirmed_count == null ? "" : esc(String(me.confirmed_count)) + " confirmed subscribers."}</strong></p>
    <p><button class="btn" id="acct-test" type="button" style="min-height:44px">Send me a test email</button> <span id="acct-test-msg"></span></p>` : "";
  el.innerHTML = `<div class="card" style="max-width:640px"><h2>Manage my subscription</h2>
    <p>${status}</p>
    ${sub.status === "none" ? '<p><a class="btn go" href="#home?to=subscribe" id="acct-sub" style="min-height:44px;display:inline-flex;align-items:center">Subscribe</a></p>' : ""}
    <fieldset style="border:0;padding:0;margin:12px 0"><legend>How often</legend>${freqRadios(sub.frequency || "each")}</fieldset>
    <p><label>Pause until <input id="acct-until" type="date" value="${esc(sub.paused_until || "")}"></label></p>
    <p><button class="btn" id="acct-save" type="button" style="min-height:44px">Save</button> <span id="acct-save-msg"></span></p>
    <p><label>New email <input id="acct-new" type="email" autocomplete="email" maxlength="254"></label></p>
    <p><button class="btn ghost" id="acct-change" type="button" style="min-height:44px">Send a confirmation to the new address</button></p>
    <p><button class="btn ghost" id="acct-unsub" type="button" style="min-height:44px">Unsubscribe</button></p>
    <p><button class="btn ghost" id="acct-del" type="button" style="min-height:44px">Delete my data</button></p>
    ${owner}
    <p id="acct-msg" role="status"></p>
  </div>`;
  const msg = el.querySelector("#acct-msg");
  const subBtn = el.querySelector("#acct-sub");
  if (subBtn) subBtn.onclick = (e) => { if (window.LineageSubscribe) { e.preventDefault(); window.LineageSubscribe.open(subBtn); } };
  el.querySelector("#acct-save").onclick = async () => {
    const frequency = (el.querySelector("input[name=acct-freq]:checked") || {}).value || "each";
    const paused_until = el.querySelector("#acct-until").value || "";
    const j = await acctFetch("prefs", { method: "POST", body: { frequency, paused_until }, csrf: true });
    el.querySelector("#acct-save-msg").textContent = j.ok ? "Saved." : (j.message || "Not saved.");
    if (j.ok) { ACCT.me = await acctFetch("me"); }
  };
  el.querySelector("#acct-change").onclick = async () => {
    const j = await acctFetch("change-email", { method: "POST", body: { email: el.querySelector("#acct-new").value }, csrf: true });
    msg.textContent = j.message || (j.ok ? "Check the new inbox." : "Not sent.");
  };
  el.querySelector("#acct-unsub").onclick = async () => {
    if (!confirm("Unsubscribe? The address is deleted and the emails stop.")) return;
    const j = await acctFetch("unsubscribe", { method: "POST", body: {}, csrf: true });
    msg.textContent = j.ok ? "You are unsubscribed." : (j.message || "Not done.");
    ACCT.me = await acctFetch("me");
    BUILDERS.account(el);
  };
  el.querySelector("#acct-del").onclick = async () => {
    if (!confirm("Delete my subscription data? This cannot be undone.")) return;
    const j = await acctFetch("delete", { method: "POST", body: { confirm: "delete" }, csrf: true });
    msg.textContent = j.ok ? ("Deleted: " + (j.deleted || []).join(", ")) : (j.message || "Not deleted.");
    ACCT.me = { open: true, signed_in: false };
    drawAccount();
    BUILDERS.account(el);
  };
  const test = el.querySelector("#acct-test");
  if (test) test.onclick = async () => {
    const j = await acctFetch("test", { method: "POST", body: { kind: "post" }, csrf: true });
    el.querySelector("#acct-test-msg").textContent = j.ok ? "Sent to you only." : (j.message || "Not sent.");
  };
};
