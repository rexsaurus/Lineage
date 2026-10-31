/* Lineage: the weekly-digest Subscribe form. Published at /updates/subscribe.js by updates_page.py.
   Any page of the site can carry the form with two lines:
     <div data-lineage-subscribe></div>
     <script src="/updates/subscribe.js" defer></script>
   A Subscribe link (href="#subscribe", "#upd-subscribe", or "#home?to=subscribe") opens this form in a
   dialog. Without JavaScript the link still scrolls to the form on the page.
   The form stays closed until /api/subscribe says it is configured. Google sign-in appears only when
   that response says google is on. */
(function () {
  var CLOSED = "Subscriptions are not open yet. Follow the RSS feed meanwhile.";
  var API = "/api/subscribe/";
  var CSS = ".lsub{border:1px solid var(--rule,var(--line,#d9d2c4));border-radius:8px;padding:16px 18px;margin:28px 0;max-width:100%;box-sizing:border-box}" +
    ".lsub h2,.lsub .lsub-h{font-weight:500;font-size:21px;margin:0 0 4px;border:0;padding:0}" +
    ".lsub p{margin:4px 0}.lsub .lsub-note,.lsub .lsub-rss{color:var(--muted,var(--ink2,#6b645b));font-size:16px}" +
    ".lsub form{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 4px}.lsub form[hidden]{display:none}" +
    ".lsub input[type=email]{flex:1 1 160px;min-width:0;width:100%;font:inherit;font-size:17px;padding:8px 10px;border:1px solid var(--rule,var(--line,#d9d2c4));border-radius:6px;background:transparent;color:inherit;box-sizing:border-box}" +
    ".lsub button{font:inherit;font-size:17px;padding:8px 16px;border:0;border-radius:6px;background:var(--rubric,var(--accent,#b3261e));color:#fff;cursor:pointer;text-decoration:none;display:inline-block;text-align:center;box-sizing:border-box}" +
    ".lsub button[disabled]{opacity:.6}.lsub .lsub-hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}" +
    ".lsub .lsub-msg:empty{display:none}.lsub label.lsub-l{position:absolute;left:-9999px}" +
    ".lsub a{color:var(--rubric,var(--accent,#b3261e))}" +
    /* Continue with Google is the secondary action: page-surface fill, 1px border, the text colour of the page,
       and the Google G. It used to share the red primary fill, and a host page's link colour could land on it. */
    ".lsub a.lsub-google{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;min-height:44px;box-sizing:border-box;padding:8px 16px;font:inherit;font-size:17px;font-weight:500;line-height:1.2;text-align:center;text-decoration:none;cursor:pointer;border-radius:6px;background:transparent;color:inherit;border:1px solid var(--muted,var(--ink2,currentColor))}" +
    ".lsub a.lsub-google:hover{background:rgba(127,127,127,.12);color:inherit}" +
    ".lsub a.lsub-google::before{content:\"\";flex:none;width:18px;height:18px;background:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23EA4335' d='M24 9.5c3.5 0 6.6 1.2 9 3.5l6.7-6.7C35.6 2.4 30.2 0 24 0 14.6 0 6.6 5.4 2.6 13.2l7.8 6C12.3 13.6 17.7 9.5 24 9.5z'/%3E%3Cpath fill='%234285F4' d='M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z'/%3E%3Cpath fill='%23FBBC05' d='M10.4 28.8A14.5 14.5 0 0 1 9.5 24c0-1.7.3-3.3.9-4.8l-7.8-6A24 24 0 0 0 0 24c0 3.9.9 7.5 2.6 10.8z'/%3E%3Cpath fill='%2334A853' d='M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.9 2.3-8.4 2.3-6.3 0-11.7-4.1-13.6-9.8l-7.8 6C6.6 42.6 14.6 48 24 48z'/%3E%3C/svg%3E\") center/18px 18px no-repeat}" +
    ".lsub-or{margin:8px 0 4px;color:var(--muted,var(--ink-3,#6b645b));font-size:15px}" +
    ".lsub-modal{position:fixed;inset:0;z-index:400;display:flex;align-items:flex-end;justify-content:center}" +
    ".lsub-backdrop{position:absolute;inset:0;background:rgba(21,19,15,.55);border:0;padding:0;margin:0;cursor:pointer}" +
    ".lsub-dialog{position:relative;z-index:1;width:100%;max-width:520px;max-height:min(92dvh,100%);overflow:auto;box-sizing:border-box;background:var(--paper,var(--card,#f8f5ee));color:var(--ink,#1d1a17);border-radius:16px 16px 0 0;padding:18px 16px 24px;box-shadow:0 20px 60px rgba(0,0,0,.28)}" +
    ".lsub-dialog .lsub{border:0;padding:0;margin:0}" +
    ".lsub-x{position:absolute;top:8px;right:8px;width:40px;height:40px;border:0;border-radius:8px;background:transparent;color:inherit;font:inherit;font-size:26px;line-height:1;cursor:pointer}" +
    ".lsub-x:hover{background:rgba(0,0,0,.06)}.lsub-x:focus-visible,.lsub button:focus-visible,.lsub a.lsub-google:focus-visible,.lsub input:focus-visible{outline:2px solid currentColor;outline-offset:2px}" +
    "@media (min-width:700px){.lsub-modal{align-items:center;padding:24px}.lsub-dialog{border-radius:12px;padding:26px 24px 28px}}" +
    "@media (max-width:480px){.lsub form{flex-direction:column}.lsub form button{width:100%}}";
  var HTML = '<p class="lsub-h" id="lsub-title">Get the weekly digest</p>' +
    '<p class="lsub-note">New posts and changes to the site, in one email a week. Confirm by email. Unsubscribe with one click.</p>' +
    '<form method="post" action="' + API + '" hidden><label class="lsub-l" for="lsub-email">Email address</label>' +
    '<input id="lsub-email" type="email" name="email" required autocomplete="email" placeholder="you@example.com" maxlength="254">' +
    '<span class="lsub-hp" aria-hidden="true"><input type="text" name="website" tabindex="-1" autocomplete="off"></span>' +
    '<button type="submit">Subscribe</button></form>' +
    '<p class="lsub-msg" role="status" aria-live="polite">' + CLOSED + '</p>' +
    '<p class="lsub-rss">or follow the <a href="/updates/feed.xml">RSS feed</a></p>';

  var modal = null, lastFocus = null, locked = null;

  function setup(box, open, googleUrl) {
    var form = box.querySelector("form"), msg = box.querySelector(".lsub-msg");
    if (!form || !msg) return;
    var row = box.querySelector(".lsub-google-row");
    if (!open) {
      form.hidden = true; msg.textContent = CLOSED;
      if (row) row.hidden = true;
      return;
    }
    form.hidden = false; msg.textContent = "";
    if (googleUrl) {
      if (!row) {
        row = document.createElement("p");
        row.className = "lsub-google-row";
        row.innerHTML = '<span class="lsub-or">or</span><br><a class="lsub-google" href="' + googleUrl.replace(/"/g, "") + '">Continue with Google</a>';
        form.insertAdjacentElement("afterend", row);
      }
      row.hidden = false;
      var a = row.querySelector("a"); if (a) a.href = googleUrl;
    } else if (row) row.hidden = true;
    if (form.dataset.ready) return;
    form.dataset.ready = "1";
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var btn = form.querySelector("button"), fd = new FormData(form);
      btn.disabled = true; msg.textContent = "Sending…";
      fetch(API, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ email: fd.get("email") || "", website: fd.get("website") || "" }) })
        .then(function (r) { return r.json().catch(function () { return { ok: false }; }).then(function (j) { j.status = r.status; return j; }); })
        .then(function (j) {
          if (j.status === 503 && j.open === false) { form.hidden = true; msg.textContent = j.message || CLOSED; return; }
          msg.textContent = j.message || (j.ok ? "Thank you. Check your inbox." : "Sorry, that didn't go through.");
          if (j.ok) form.reset();
        })
        .catch(function () { msg.textContent = "Sorry, that didn't go through. Please try again later."; })
        .then(function () { btn.disabled = false; });
    });
  }

  function boxes() { return document.querySelectorAll("[data-lineage-subscribe]"); }

  function paint(j) {
    var list = boxes();
    var open = !!(j && j.open), url = open && j.google && j.google_url ? j.google_url : "";
    for (var k = 0; k < list.length; k++) setup(list[k], open, url);
  }

  function ask() {
    return fetch(API, { headers: { Accept: "application/json" }, cache: "no-store" })
      .then(function (r) { return r.json().catch(function () { return { open: false }; }); })
      .catch(function () { return { open: false }; })
      .then(paint);
  }

  function init() {
    var list = boxes();
    if (!list.length) return;
    if (!document.getElementById("lsub-css")) {
      var st = document.createElement("style"); st.id = "lsub-css"; st.textContent = CSS; document.head.appendChild(st);
    }
    for (var i = 0; i < list.length; i++) {
      list[i].classList.add("lsub");
      if (!list[i].querySelector("form")) list[i].innerHTML = HTML.replace(/lsub-email/g, "lsub-email-" + i).replace('id="lsub-title"', 'id="lsub-title-' + i + '"');
    }
    ask();
  }

  function focusables(root) {
    return Array.prototype.filter.call(root.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]):not([tabindex="-1"]), textarea, select'), function (el) {
      return el.getClientRects().length > 0;
    });
  }

  function lockScroll() {
    locked = { y: window.scrollY || 0, top: document.body.style.top, position: document.body.style.position, width: document.body.style.width, left: document.body.style.left, right: document.body.style.right };
    document.body.style.position = "fixed";
    document.body.style.top = "-" + locked.y + "px";
    document.body.style.left = "0";
    document.body.style.right = "0";
    document.body.style.width = "100%";
  }
  function unlockScroll() {
    if (!locked) return;
    document.body.style.position = locked.position;
    document.body.style.top = locked.top;
    document.body.style.width = locked.width;
    document.body.style.left = locked.left;
    document.body.style.right = locked.right;
    window.scrollTo(0, locked.y);
    locked = null;
  }

  function closeModal() {
    if (!modal) return;
    var box = modal.box, slot = modal.slot, back = modal.trigger;
    if (box && slot && slot.isConnected) slot.appendChild(box);
    modal.root.remove();
    modal = null;
    unlockScroll();
    if (back && back.focus) back.focus();
  }

  function onKey(e) {
    if (!modal) return;
    if (e.key === "Escape") { e.preventDefault(); closeModal(); return; }
    if (e.key !== "Tab") return;
    var f = focusables(modal.dialog);
    if (!f.length) { e.preventDefault(); return; }
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    else if (!modal.dialog.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
  }

  function openModal(trigger) {
    init();
    var list = boxes();
    if (!list.length) return;
    if (modal) closeModal();
    var box = list[0], slot = box.parentNode;
    var root = document.createElement("div");
    root.className = "lsub-modal";
    root.innerHTML = '<button type="button" class="lsub-backdrop" tabindex="-1" aria-label="Close subscribe"></button>' +
      '<div class="lsub-dialog" role="dialog" aria-modal="true" aria-labelledby="' + (box.querySelector(".lsub-h") ? box.querySelector(".lsub-h").id : "lsub-title") + '">' +
      '<button type="button" class="lsub-x" aria-label="Close">×</button></div>';
    var dialog = root.querySelector(".lsub-dialog");
    dialog.appendChild(box);
    document.body.appendChild(root);
    lockScroll();
    modal = { root: root, dialog: dialog, box: box, slot: slot, trigger: trigger || document.activeElement };
    root.querySelector(".lsub-backdrop").addEventListener("click", closeModal);
    root.querySelector(".lsub-x").addEventListener("click", closeModal);
    var field = box.querySelector("input[type=email]");
    var start = (field && !field.closest("form").hidden) ? field : root.querySelector(".lsub-x");
    start.focus();
  }

  function isSubscribeLink(a) {
    if (!a || !a.getAttribute) return false;
    var href = a.getAttribute("href") || "";
    return a.id === "hdr-sub" || href === "#subscribe" || href === "#upd-subscribe" || href === "#home?to=subscribe";
  }

  if (!window.__lsubBound) {
    window.__lsubBound = true;
    document.addEventListener("click", function (e) {
      var a = e.target && e.target.closest ? e.target.closest("a") : null;
      if (!isSubscribeLink(a)) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
      e.preventDefault();
      openModal(a);
    });
    document.addEventListener("keydown", onKey, true);
  }

  window.LineageSubscribe = init;
  window.LineageSubscribe.open = openModal;
  window.LineageSubscribe.close = closeModal;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
