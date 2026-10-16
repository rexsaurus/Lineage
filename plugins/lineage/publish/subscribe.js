/* Lineage: the weekly-digest Subscribe form. Published at /updates/subscribe.js by updates_page.py.
   Any page of the site can carry the form with two lines:
     <div data-lineage-subscribe></div>
     <script src="/updates/subscribe.js" defer></script>
   The form stays closed ("Subscriptions open soon") until /api/subscribe says it is configured. */
(function () {
  var CLOSED = "Subscriptions open soon — follow the RSS feed meanwhile.";
  var API = "/api/subscribe/";
  var CSS = ".lsub{border:1px solid var(--rule,var(--line,#d9d2c4));border-radius:8px;padding:16px 18px;margin:28px 0;max-width:100%;box-sizing:border-box}" +
    ".lsub h2,.lsub .lsub-h{font-weight:500;font-size:21px;margin:0 0 4px;border:0;padding:0}" +
    ".lsub p{margin:4px 0}.lsub .lsub-note,.lsub .lsub-rss{color:var(--muted,var(--ink2,#6b645b));font-size:16px}" +
    ".lsub form{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 4px}.lsub form[hidden]{display:none}" +
    ".lsub input[type=email]{flex:1 1 200px;min-width:0;font:inherit;font-size:17px;padding:8px 10px;border:1px solid var(--rule,var(--line,#d9d2c4));border-radius:6px;background:transparent;color:inherit}" +
    ".lsub button{font:inherit;font-size:17px;padding:8px 16px;border:0;border-radius:6px;background:var(--rubric,var(--accent,#b3261e));color:#fff;cursor:pointer}" +
    ".lsub button[disabled]{opacity:.6}.lsub .lsub-hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}" +
    ".lsub .lsub-msg:empty{display:none}.lsub label.lsub-l{position:absolute;left:-9999px}";
  var HTML = '<p class="lsub-h">Get the weekly digest</p>' +
    '<p class="lsub-note">New posts and changes to the site, in one email a week. Confirm by email; unsubscribe with one click.</p>' +
    '<form method="post" action="' + API + '" hidden><label class="lsub-l" for="lsub-email">Email address</label>' +
    '<input id="lsub-email" type="email" name="email" required autocomplete="email" placeholder="you@example.com" maxlength="254">' +
    '<span class="lsub-hp" aria-hidden="true"><input type="text" name="website" tabindex="-1" autocomplete="off"></span>' +
    '<button type="submit">Subscribe</button></form>' +
    '<p class="lsub-msg" role="status" aria-live="polite">' + CLOSED + '</p>' +
    '<p class="lsub-rss">or follow the <a href="/updates/feed.xml">RSS feed</a></p>';

  function setup(box, open) {
    var form = box.querySelector("form"), msg = box.querySelector(".lsub-msg");
    if (!form || !msg) return;
    if (!open) { form.hidden = true; msg.textContent = CLOSED; return; }
    form.hidden = false; msg.textContent = "";
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var btn = form.querySelector("button"), fd = new FormData(form);
      btn.disabled = true; msg.textContent = "Sending…";
      fetch(API, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ email: fd.get("email") || "", website: fd.get("website") || "" }) })
        .then(function (r) { return r.json().catch(function () { return { ok: false }; }).then(function (j) { j.status = r.status; return j; }); })
        .then(function (j) {
          if (j.status === 503 && j.open === false) { form.hidden = true; msg.textContent = CLOSED; return; }
          msg.textContent = j.message || (j.ok ? "Thank you. Check your inbox." : "Sorry, that didn't go through.");
          if (j.ok) form.reset();
        })
        .catch(function () { msg.textContent = "Sorry, that didn't go through. Please try again later."; })
        .then(function () { btn.disabled = false; });
    });
  }

  function init() {
    var boxes = document.querySelectorAll("[data-lineage-subscribe]");
    if (!boxes.length) return;
    if (!document.getElementById("lsub-css")) {
      var st = document.createElement("style"); st.id = "lsub-css"; st.textContent = CSS; document.head.appendChild(st);
    }
    for (var i = 0; i < boxes.length; i++) {
      boxes[i].classList.add("lsub");
      if (!boxes[i].querySelector("form")) boxes[i].innerHTML = HTML.replace(/lsub-email/g, "lsub-email-" + i);
    }
    fetch(API, { headers: { Accept: "application/json" }, cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : { open: false }; })
      .catch(function () { return { open: false }; })
      .then(function (j) { for (var k = 0; k < boxes.length; k++) setup(boxes[k], !!(j && j.open)); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
