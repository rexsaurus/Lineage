/* ================================================================== PHOTO VIEWER
   One viewer for every photograph on the site: the homepage gallery, all photographs, Familypedia articles and their
   profile photos, updates, story illustrations, timeline entries. Nothing links to an image file; a click on any
   picture the photo registry knows (/api/engine/photos) opens it here, full size, with its facts.
   An original and its restoration are one photograph: the viewer shows the restoration and carries the flip.
   Navigation cards (person chips, story cards) keep their links; a picture inside them is not a photograph to open. */
const PV = { reg:null, by:null, loading:null };
const PV_SKIP = '.pv, .pchip, .fp-person, .hstory, .upd-item, .story .mark, #src-table, .settings, [data-no-viewer]';
const PV_KIND = { portrait:'portrait', group:'group photograph', document:'document', place:'place', illustration:'illustration' };
const pvKey = s => { s = String(s||''); try { const u = new URL(s, location.href); const q = u.searchParams.get('path'); s = q || (u.origin===location.origin ? u.pathname : u.href); } catch(e){}
  return s.split('?')[0].replace(/^\/+/, '').replace(/^files\//, '').replace(/^work\/lineage-assets\//, ''); };
function pvLoad(){
  if(PV.reg) return Promise.resolve(PV.reg);
  return PV.loading = PV.loading || api('/api/engine/photos').catch(()=>({photos:[]})).then(r=>{
    PV.reg = r; PV.by = new Map();
    for(const p of r.photos||[]){
      for(const a of (p.paths||[]).concat(p.ids||[])) if(!PV.by.has(pvKey(a))) PV.by.set(pvKey(a), p);
      for(const a of p.paths||[]){ const u = fileUrl(a); PV.by.set(u, p); PV.by.set(pvKey(u), p); if(window.thumbOf) PV.by.set(window.thumbOf(u), p); }
    }
    pvMark(document);
    return r;
  });
}
const pvFind = x => x && PV.by ? (PV.by.get(x) || PV.by.get(pvKey(x)) || null) : null;
const pvOf = img => pvFind(img.dataset.photo) || pvFind(img.dataset.full) || pvFind(img.getAttribute('src'));
const pvSrc = p => fileUrl(p.image);
/* the registry entry for a path or id (grids use it to show one tile per photograph) */
const photoFor = x => pvFind(x);

// every known photograph is a button: focusable, and announced as one
function pvMark(root){
  if(!PV.by || !root.querySelectorAll) return;
  const imgs = root.tagName==='IMG' ? [root] : root.querySelectorAll('img');
  imgs.forEach(i=>{ if(i.dataset.pv || i.closest(PV_SKIP)) return; const p = pvOf(i); if(!p) return;
    i.dataset.pv = '1'; i.classList.add('pv-open'); if(!i.closest('a,button')){ i.tabIndex = 0; i.setAttribute('role','button'); }
    if(!i.alt) i.alt = p.title; });
}
new MutationObserver(ms=>{ if(!PV.by) return; for(const m of ms) for(const n of m.addedNodes) if(n.nodeType===1) pvMark(n); })
  .observe(document.documentElement, { childList:true, subtree:true });

function pvSet(img){
  const scope = img.closest('[data-photo-set], .fp-photos, .hgal, .upd-body, .upd-post, .infobox, article, section, .card, main') || document;
  const seen = new Set(), out = [];
  scope.querySelectorAll('img').forEach(i=>{ if(i.closest(PV_SKIP)) return; const p = pvOf(i); if(p && !seen.has(p.id)){ seen.add(p.id); out.push(p); } });
  return out;
}
function pvClick(e){
  const img = e.target.closest && e.target.closest('img'); if(!img || img.closest(PV_SKIP)) return;
  const p = pvOf(img); if(!p) return;
  e.preventDefault(); e.stopPropagation();
  const set = pvSet(img); openPhotoViewer(p, set.length ? set : [p], img);
}
document.addEventListener('click', pvClick, true);
document.addEventListener('keydown', e=>{ if(e.key==='Enter' && e.target.tagName==='IMG' && e.target.dataset.pv) pvClick(e); }, true);
pvLoad();

function pvBadge(p){
  if(p.illustration) return '<span class="pv-badge b-illus">Illustration</span>';
  if(p.isLowRes && p.backfillState==='not_located') return '<span class="pv-badge b-low">Low resolution</span>';
  return p.restored ? '<span class="pv-badge b-rest"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1l1.6 4.4L14 7l-4.4 1.6L8 13l-1.6-4.4L2 7l4.4-1.6z"/></svg>Restored</span>'
    : '<span class="pv-badge b-orig">Original</span>';
}
const pvTagLink = t => `<a class="pv-pill" href="#familypedia/${encodeURIComponent(t.slug)}">${esc(t.title)}</a>`;

function openPhotoViewer(p, set, origin){
  set = set && set.length ? set : [p];
  let i = Math.max(0, set.findIndex(x=>x.id===p.id)), orig = false;
  const back = origin || document.activeElement;
  const host = document.createElement('div'); host.className = 'pv'; document.body.appendChild(host);
  document.body.classList.add('pv-on');
  const close = () => { host.remove(); document.body.classList.remove('pv-on'); document.removeEventListener('keydown', key, true); if(back && back.focus) back.focus(); };
  const go = d => { if(i+d<0 || i+d>=set.length) return; i += d; orig = false; draw(); };
  const key = e => {
    if(!document.body.contains(host)) return;
    if(e.key==='Escape'){ e.preventDefault(); if(host.querySelector('.pv-tags')) { host.querySelector('.pv-tags').remove(); host.querySelector('.pv-more').focus(); } else close(); return; }
    if(/INPUT|TEXTAREA|SELECT/.test((document.activeElement||{}).tagName||'')) return;
    if(e.key==='ArrowLeft'){ e.preventDefault(); go(-1); } else if(e.key==='ArrowRight'){ e.preventDefault(); go(1); }
    else if(e.key==='Tab'){ const f = [...host.querySelectorAll('a[href],button:not([disabled]),[tabindex="0"]')].filter(x=>x.offsetParent!==null);
      if(!f.length) return; const a = f[0], z = f[f.length-1];
      if(e.shiftKey && document.activeElement===a){ e.preventDefault(); z.focus(); } else if(!e.shiftKey && document.activeElement===z){ e.preventDefault(); a.focus(); }
      else if(!host.contains(document.activeElement)){ e.preventDefault(); a.focus(); } }
  };
  document.addEventListener('keydown', key, true);
  function draw(){
    const x = set[i], src = fileUrl(orig && x.original ? x.original : x.image);
    const tags = [...x.tags.people, ...x.tags.places, ...x.tags.other], more = tags.length - 3;
    const s = x.source;
    host.innerHTML = `<div class="pv-scrim"></div>
    <div class="pv-box" role="dialog" aria-modal="true" aria-labelledby="pv-title">
      <div class="pv-stage">
        <div class="pv-img"><img src="${esc(src)}" alt="${esc(x.title)}"></div>
        <div class="pv-under">${x.width?`<span class="pv-res">Full-resolution image · ${x.width} × ${x.height}</span>`:''}
          ${x.restored&&x.original?`<span class="pv-flip" role="group" aria-label="Rendering"><button class="${orig?'':'on'}" data-r="0" aria-pressed="${!orig}">Restored</button><button class="${orig?'on':''}" data-r="1" aria-pressed="${orig}">Original scan</button></span><span class="pv-kept">digitally restored · both kept</span>`:''}</div>
      </div>
      <aside class="pv-facts">
        <button class="pv-x" aria-label="Close">×</button>
        ${pvBadge(x)}
        <h2 id="pv-title">${esc(x.title)}</h2>
        <p class="pv-sub">${[x.date, PV_KIND[x.kind]].filter(Boolean).map(esc).join(' · ')}</p>
        ${x.description?`<p class="pv-desc">${esc(x.description)}</p>`:''}
        ${x.isLowRes?`<p class="pv-low">${x.backfillState==='not_located'?'The full-resolution scan has not been found. This is the best copy on file.':'This is a small copy; the full-resolution scan is being looked for.'}</p>`:''}
        <dl class="pv-kv">${x.date?`<dt>Date</dt><dd>${esc(x.date)}</dd>`:''}${x.place?`<dt>Place</dt><dd>${esc(x.place)}</dd>`:''}
          ${s?`<dt>Source</dt><dd>${esc(s.institution||'')}${s.reference?`${s.institution?'<br>':''}${s.url?`<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.reference)}</a>`:esc(s.reference)}`:s.url?`${s.institution?'<br>':''}<a href="${esc(s.url)}" target="_blank" rel="noopener">Catalogue record</a>`:''}</dd>`:''}</dl>
        ${tags.length?`<h5>People and places</h5><div class="pv-pills">${tags.slice(0,3).map(pvTagLink).join('')}${more>0?`<button class="pv-pill pv-more">+ ${more} more</button>`:''}</div>`:''}
        ${x.appears.length?`<h5>Appears in</h5><ul class="pv-in">${x.appears.map(a=>`<li><a href="${esc(a.href)}">${esc(a.title)}${a.kind==='article'?' — Familypedia':''}</a></li>`).join('')}</ul>`:''}
      </aside>
      <footer class="pv-foot">
        <button class="pv-nav" data-d="-1" ${i?'':'disabled'} aria-label="Previous photograph">‹ Previous</button>
        <span class="pv-pos">${i+1} of ${set.length}</span>
        <button class="pv-nav" data-d="1" ${i<set.length-1?'':'disabled'} aria-label="Next photograph">Next ›</button>
        <span class="spacer"></span>
        <a class="pv-btn" href="${esc(src)}" target="_blank" rel="noopener">Open full size</a>
        <button class="pv-btn pv-dl">Download</button>
      </footer>
    </div>`;
    host.querySelector('.pv-scrim').onclick = close;
    host.querySelector('.pv-x').onclick = close;
    host.querySelectorAll('.pv-nav').forEach(b=>b.onclick=()=>go(+b.dataset.d));
    host.querySelectorAll('.pv-flip button').forEach(b=>b.onclick=()=>{ orig = b.dataset.r==='1'; draw(); host.querySelector(`.pv-flip [data-r="${b.dataset.r}"]`).focus(); });
    host.querySelectorAll('.pv-in a, .pv-pills a').forEach(a=>a.addEventListener('click', ()=>{ host.remove(); document.body.classList.remove('pv-on'); document.removeEventListener('keydown', key, true); }));
    const m = host.querySelector('.pv-more'); if(m) m.onclick = () => pvTags(host, x);
    host.querySelector('.pv-dl').onclick = () => pvDownload(src, x.title);
    host.querySelector('.pv-x').focus();
  }
  draw();
}
function pvTags(host, x, done){
  const grp = [['People', x.tags.people], ['Places', x.tags.places], ['Units and organisations', x.tags.other]].filter(g=>g[1].length);
  const box = document.createElement('div'); box.className = 'pv-tags'; box.setAttribute('role','dialog'); box.setAttribute('aria-label','Everyone and everywhere in this photograph');
  box.innerHTML = `<div class="row"><h4>In this photograph</h4><span class="spacer"></span><button class="pv-x" aria-label="Close the list">×</button></div>
    ${grp.map(([h, l])=>`<h5>${h} · ${l.length}</h5><div class="pv-pills">${l.map(pvTagLink).join('')}</div>`).join('')}`;
  host.querySelector('.pv-box').appendChild(box);
  box.querySelector('.pv-x').onclick = done || (() => { box.remove(); host.querySelector('.pv-more').focus(); });
  box.querySelectorAll('a').forEach(a=>a.addEventListener('click', ()=>{ host.remove(); document.body.classList.remove('pv-on'); if(done) done(); }));
  box.querySelector('.pv-x').focus();
}
async function pvDownload(src, title){
  const ext = (String(src).split('?')[0].match(/\.(jpe?g|png|gif|webp|tiff?)$/i)||['','jpg'])[1].toLowerCase();
  const name = (String(title).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,80) || 'photograph') + '.' + ext;
  const a = document.createElement('a'); a.download = name;
  try { const r = await fetch(src, {mode:'cors'}); if(!r.ok) throw 0; a.href = URL.createObjectURL(await r.blob()); }
  catch(e){ a.href = src; }
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>{ if(a.href.startsWith('blob:')) URL.revokeObjectURL(a.href); }, 4000);
}

/* ------------------------------------------------------------------ one tile per photograph */
// rows (catalogue or article photos) -> [{p: the registry entry or null, row}], the first row of each photograph only
function onePerPhoto(rows, path = r => r.thumb){
  const seen = new Set(), out = [];
  for(const r of rows){ const p = photoFor(r.id) || photoFor(path(r)); const k = p ? p.id : 'row:'+(r.id||path(r));
    if(seen.has(k)) continue; seen.add(k); out.push({p, row:r}); }
  return out;
}
function pvBadgeSmall(p){ return p ? pvBadge(p).replace('pv-badge', 'pv-badge on-img') : ''; }
// a figure for an article: the photograph's own title and date, never its file
function photoFigure(p, row){
  const title = p ? p.title : (row.caption||''), src = p ? p.image : row.thumb;
  return `<figure class="fp-photo"><div class="pv-frame"><img src="${fileUrl(src)}" data-photo="${esc(src)}" alt="${esc(title)}" loading="lazy">${pvBadgeSmall(p)}</div>
    <figcaption>${esc(title)}${p&&p.date?`<br><span class="derived">${esc(p.date)}</span>`:''}</figcaption></figure>`;
}
// a card for All photographs
function photoCard(p, sel){
  const tags = [...p.tags.people, ...p.tags.places, ...p.tags.other];
  const where = [p.date||'undated', p.isLowRes&&p.backfillState==='not_located' ? 'full scan not yet located' : (p.source&&p.source.institution)||''].filter(Boolean).join(' · ');
  return `<figure class="ph-card${sel&&sel.has(p.id)?' on':''}" data-pid="${esc(p.id)}">
    ${sel?`<label class="ph-sel"><input type="checkbox" data-psel="${esc(p.id)}" ${sel.has(p.id)?'checked':''}> select</label>`:''}
    <div class="ph-img"><img src="${fileUrl(p.image)}" data-photo="${esc(p.image)}" alt="${esc(p.title)}" loading="lazy">${pvBadgeSmall(p)}</div>
    <figcaption><b>${esc(p.title)}</b><span class="ph-where">${esc(where)}</span>
      ${tags.length?`<span class="pv-pills">${tags.slice(0,2).map(pvTagLink).join('')}${tags.length>2?`<button class="pv-pill pv-more" data-ptags="${esc(p.id)}" aria-label="Everyone and everywhere in this photograph">+${tags.length-2}</button>`:''}</span>`:''}</figcaption></figure>`;
}
// the tag list on its own, from a card's +N
function photoTagsModal(p, back){
  const host = document.createElement('div'); host.className = 'pv pv-solo'; document.body.appendChild(host);
  host.innerHTML = '<div class="pv-scrim"></div><div class="pv-box pv-small"></div>';
  const close = () => { host.remove(); document.removeEventListener('keydown', key, true); if(back) back.focus(); };
  const key = e => { if(e.key==='Escape'){ e.preventDefault(); close(); } };
  document.addEventListener('keydown', key, true);
  host.querySelector('.pv-scrim').onclick = close;
  pvTags(host, p, close);
}
