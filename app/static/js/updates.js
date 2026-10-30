/* ================================================================== UPDATES
   The family's news, newest first: the project's posts (posts/<slug>.md), the same posts the published site
   shows at /updates/. The daily research report lands here too (the daily-update macro writes it as a post).
   #updates lists them; #updates/<slug> opens one. */
const updDate = d => { const t = new Date(d+'T12:00:00'); return isNaN(t) ? d : t.toLocaleDateString('en-GB',{day:'numeric', month:'long', year:'numeric'}); };
BUILDERS.updates = async function(el, rest){
  el.innerHTML='';
  const d = await api('/api/engine/updates'), posts = d.posts||[];
  const slug = rest[0] && decodeURIComponent(rest[0]), p = slug && posts.find(x=>x.slug===slug);
  if(p){
    el.insertAdjacentHTML('beforeend', `<p class="upd-back"><a href="#updates">← All updates</a></p>
      <article class="card upd-post"><div class="kicker">${esc(updDate(p.date))}${p.author?' · '+esc(p.author):''}</div>
      <h2>${esc(p.title)}</h2>${p.image && !p.html.includes(p.image)?`<img class="upd-hero" src="${esc(p.image)}" alt="">`:''}<div class="upd-body">${p.html}</div></article>`);
    return;
  }
  head(el,{kicker:'Updates', title:'What’s new', lede:'Research news, newest first: what came in, what changed, and what is still open.'});
  const wk = posts.find(x=>/^weekly-/.test(x.slug));
  el.insertAdjacentHTML('beforeend', `<p class="upd-actions">${wk?`<a class="upd-btn" href="#updates/${encodeURIComponent(wk.slug)}">Weekly Update</a>`:''}
      <a class="upd-btn" href="#upd-subscribe">Subscribe</a></p>`);
  if(d.error) el.insertAdjacentHTML('beforeend', `<div class="note">${esc(d.error)}</div>`);
  if(!posts.length){ el.insertAdjacentHTML('beforeend','<p class="empty">No updates yet.</p>'); return; }
  el.insertAdjacentHTML('beforeend', `<div class="upd-list">${posts.map(x=>`<a class="card upd-item" href="#updates/${encodeURIComponent(x.slug)}">
      ${x.thumb?`<img src="${esc(x.thumb)}" alt="" loading="lazy">`:''}<div><div class="kicker">${esc(updDate(x.date))}</div>
      <h3>${esc(x.title)}</h3>${x.summary?`<p>${esc(x.summary)}</p>`:''}</div></a>`).join('')}</div>`);
  updSubscribe(el);
};
/* The weekly-digest form. The published site serves it at /updates/subscribe.js; the form stays closed until the
   site's /api/subscribe says subscriptions are configured. Locally the script is absent and the box stays empty. */
function updSubscribe(el){
  el.insertAdjacentHTML('beforeend','<div id="upd-subscribe" data-lineage-subscribe></div>');
  if(!document.getElementById('lsub-js')){
    const s=document.createElement('script'); s.id='lsub-js'; s.src='/updates/subscribe.js'; s.defer=true;
    s.onerror=()=>{ const b=document.getElementById('upd-subscribe'); if(b) b.remove(); };
    document.head.appendChild(s);
  } else if(window.LineageSubscribe) window.LineageSubscribe();
}
