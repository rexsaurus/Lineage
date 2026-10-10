/* ================================================================== FAMILYPEDIA
   An article for every subject the material names: person · place · event · vessel ·
   organization · object · publication · occupation · theme. Same structure and the same
   evidence rules for every type. Views: Articles (browse, A–Z, most material, needs more,
   search), Map, Records, Photographs. Tagging (picker, suggestions, bulk) is shared with
   Sources and the Timeline. */
const TYPE_ICON={person:'☺', place:'⌖', event:'◷', vessel:'⛵', organization:'⚑', object:'◆', publication:'❡', occupation:'⚒', theme:'❖'};
const TIER_TITLES={witnessed:'What was witnessed', told:'What was told', lore:'Family lore', documented:'What the records show'};
const FP={meta:null, list:null, view:'articles', type:'', sort:'az', letter:'', q:'', hits:null, shown:200, sel:new Set()};

BUILDERS.familypedia = async function(el, rest, q={}){
  el.innerHTML='';
  head(el,{kicker:'Familypedia', title:'Everything the material names', lede:"People, places, events, ships, regiments, objects, papers, trades and themes. Built only from this project's own material: every sentence points at its source, and stubs show where the next recording or record should go."});
  el.insertAdjacentHTML('beforeend', `<div class="row fp-views" role="tablist" style="margin:0 0 14px">
      ${[['articles','Articles'],['map','Map'],['records','Records'],['photos','Photographs']].map(([v,l])=>`<a class="chiplink" role="tab" data-view="${v}" href="#familypedia?view=${v}">${l}</a>`).join('')}
      <span class="spacer"></span><button class="btn ghost sm" id="fp-new">New subject…</button></div>
    <div id="fp-body"><p class="empty">Loading…</p></div>`);
  $('#fp-new').onclick=()=>openPicker({title:'New subject', newOnly:true, onPick:s=>{ location.hash='familypedia/'+encodeURIComponent(s.slug); }});
  await loadFamilypedia();
  if(rest && rest.length) return showArticle(decodeURIComponent(rest[0]));
  showView(q.view||'articles', q);
};
async function loadFamilypedia(force=false){
  if(FP.list && !force) return;
  const [m, r] = await Promise.all([api('/api/engine/familypedia/meta'), api('/api/engine/familypedia')]);
  FP.meta=m; FP.list=r.articles; S.wiki=r.articles; FP.bySlug=new Map(r.articles.map(a=>[a.slug,a])); try{ const st=await api('/api/engine/stories'); FP.stories=Object.fromEntries((st.stories||[]).map(x=>[x.id,x])); }catch(e){ FP.stories={}; } buildLinker(m.links);
}
function setView(v){ FP.view=v; $$('.fp-views [data-view]').forEach(a=>a.setAttribute('aria-current', a.dataset.view===v?'page':'false')); }
function showView(v, q={}){
  setView(v);
  if(v==='map') return drawMapView(q.focus);
  if(v==='records') return drawCatalogue('records');
  if(v==='photos') return drawCatalogue('photos');
  if(q.type) FP.type=q.type; if(q.sort) FP.sort=q.sort;
  drawBrowse();
}

/* ------------------------------------------------------------------ links: [[Name]], [[Name|label]] and known names */
let LINKER=null;
function buildLinker(rows){
  const by=new Map(); rows.forEach(([name,slug,type])=>{ const k=name.toLowerCase(); if(!by.has(k)) by.set(k,[]); by.get(k).push({slug,type,name}); });
  // automatic links only for proper names: capitalised, not bare numbers or phrases like “his father”
  // a lone word that only names a stub person (a surname off a roster) is too likely to be someone else
  const auto=rows.filter(([n,,t,stub])=>t!=='event' && n.length>=4 && /^[A-Z][^]*[A-Za-z]/.test(n) && !/^\d+$/.test(n) && !(t==='person' && stub && !/\s/.test(n.trim()))).map(r=>r[0]);
  const uniq=[...new Set(auto)].sort((a,b)=>b.length-a.length).slice(0,4000);
  const rx = uniq.length ? new RegExp('(^|[^\\w])('+uniq.map(n=>esc(n).replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|')+')(?![\\w])','g') : null;
  LINKER={by, rx};
}
function resolveName(name){ if(!LINKER) return null; const c=LINKER.by.get(String(name).trim().toLowerCase()); return c&&c.length?c[0]:null; }
function unesc(s){ return s.replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&amp;/g,'&'); }
function wikiLink(text, opts={}){
  // Never rewrites the words: explicit [[links]] resolve across types; known names become links once each.
  if(!LINKER) return esc(text);
  const used=new Set(opts.skip?[opts.skip]:[]);
  const parts=[]; let last=0; const src=String(text??'');
  src.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,(m,name,label,off)=>{ parts.push({t:src.slice(last,off)}); parts.push({link:name,label:label||name}); last=off+m.length; return m; });
  parts.push({t:src.slice(last)});
  return parts.map(p=>{
    if(p.link){ const a=resolveName(p.link); if(a) used.add(a.slug);
      return a?`<a class="wl" href="#familypedia/${encodeURIComponent(a.slug)}">${esc(p.label)}</a>`:`<span class="wl missing" title="No article named “${esc(p.link)}” yet">${esc(p.label)}</span>`; }
    const html=esc(p.t); if(!LINKER.rx || opts.noAuto) return html;
    return html.replace(LINKER.rx,(m,pre,name)=>{ const a=resolveName(unesc(name)); if(!a||used.has(a.slug)) return m; used.add(a.slug);
      return `${pre}<a class="wl" href="#familypedia/${encodeURIComponent(a.slug)}">${name}</a>`; });
  }).join('');
}
/* The portrait chip: the one way an entry is shown in any list (Rex, 2026-10-10: "use those everywhere as the
   default"). Its picture is the person's chosen portrait or the entry's first photograph; else the type's icon. */
const thumbSrc = rel => { const u=fileUrl(rel); return window.thumbOf ? window.thumbOf(u) : u; };
function entryChip(slug, title, type, note, pic, attrs=''){
  const a = FP.bySlug && slug ? FP.bySlug.get(slug) : null;
  if(pic===undefined) pic = a && a.portrait ? a.portrait.thumb : null;
  type = type || (a && a.type) || '';
  const href = slug ? `href="#familypedia/${encodeURIComponent(slug)}"` : '';
  return `<a class="pchip${pic?'':' noimg'}" ${href} ${attrs} title="${esc(title)}">${pic?`<img src="${thumbSrc(pic)}" alt="" loading="lazy">`:''}<span>${esc(title)}</span></a>${note?` <span class="derived">${esc(note)}</span>`:''}`;
}
const artLink = (slug,title,type,note) => entryChip(slug,title,type,note);
function storyChip(id, title){
  const st = (FP.stories||{})[id], pic = st && st.photo;
  return `<a class="pchip${pic?'':' noimg'}" href="#stories?read=${encodeURIComponent(id)}" title="${esc(title)}">${pic?`<img src="${thumbSrc(pic)}" alt="" loading="lazy">`:''}<span>${esc(title)}</span></a>`;
}
const typeLabel = t => ((FP.meta&&FP.meta.types.find(x=>x.type===t))||{}).label||t;
const typeSingular = t => ((FP.meta&&FP.meta.types.find(x=>x.type===t))||{}).singular||t;

/* ------------------------------------------------------------------ browse */
function drawBrowse(){
  const types=FP.meta.types, counts={}; FP.list.forEach(a=>counts[a.type]=(counts[a.type]||0)+1);
  $('#fp-body').innerHTML=`<div class="wiki"><nav class="card" style="padding:14px" aria-label="Browse the Familypedia">
      <input type="search" id="wk-q" placeholder="Search every article" value="${esc(FP.q)}">
      <div class="row" style="gap:6px;margin:10px 0"><button class="btn ghost sm" id="wk-random">Random article</button></div>
      <h5>Show</h5><ul>
        <li><a href="#" data-sort="az" aria-current="${FP.sort==='az'}">A–Z</a></li>
        <li><a href="#" data-sort="most" aria-current="${FP.sort==='most'}">Most material</a></li>
        <li><a href="#" data-sort="needs" aria-current="${FP.sort==='needs'}">Needs more (stubs) · ${FP.list.filter(a=>a.stub).length}</a></li></ul>
      <h5>By type</h5><ul><li><a href="#" data-type="" aria-current="${!FP.type}">Everything · ${FP.list.length}</a></li>
        ${types.filter(t=>counts[t.type]).map(t=>`<li><a href="#" data-type="${t.type}" aria-current="${FP.type===t.type}">${esc(t.label)} · ${counts[t.type]}</a></li>`).join('')}</ul>
      <p class="derived" style="margin:6px 0 0">No articles yet: ${types.filter(t=>!counts[t.type]).map(t=>esc(t.singular)).join(', ')||'none'}.</p></nav>
    <div id="wk-article"></div></div>`;
  $('#wk-random').onclick=()=>{ const l=FP.list; if(l.length) location.hash='familypedia/'+encodeURIComponent(l[Math.floor(Math.random()*l.length)].slug); };
  $$('[data-sort]').forEach(a=>a.onclick=e=>{ e.preventDefault(); FP.sort=a.dataset.sort; FP.letter=''; FP.shown=200; drawBrowse(); });
  $$('[data-type]').forEach(a=>a.onclick=e=>{ e.preventDefault(); FP.type=a.dataset.type; FP.letter=''; FP.shown=200; drawBrowse(); });
  let t; $('#wk-q').oninput=e=>{ clearTimeout(t); t=setTimeout(async()=>{ FP.q=e.target.value.trim(); await runSearch(); },220); };
  if(FP.q) runSearch(); else drawListing();
}
async function runSearch(){
  if(!FP.q){ FP.hits=null; return drawListing(); }
  const r=await api('/api/engine/familypedia/search?q='+encodeURIComponent(FP.q)+(FP.type?'&types='+FP.type:''));
  FP.hits=r.hits;
  $('#wk-article').innerHTML=`<div class="card"><h3>${r.hits.length} result${r.hits.length!==1?'s':''} for “${esc(FP.q)}”${FP.type?` in ${esc(typeLabel(FP.type))}`:''}</h3>
    <p class="sub">Searches titles, other names, leads, notes, story units, timeline events, records and the passages of the recordings. Pick a type on the left to filter.</p>
    ${r.hits.map(h=>`<div class="fp-hit">${artLink(h.slug,h.title,h.type)} <span class="pill">${esc(typeSingular(h.type))}</span>${h.stub?' <span class="derived">stub</span>':''}
      ${h.snippet?`<div class="sub" style="margin:2px 0 0;font-size:13px">…${esc(h.snippet)}…</div>`:''}</div>`).join('')||'<p class="empty">Nothing matches. Try another name, or create the subject with “New subject…”.</p>'}</div>`;
}
function drawListing(){
  let list=FP.list.filter(a=>!FP.type||a.type===FP.type);
  if(FP.sort==='needs') list=list.filter(a=>a.stub);
  if(FP.sort==='most') list=list.slice().sort((a,b)=>b.score-a.score);
  else list=list.slice().sort((a,b)=>a.title.replace(/^[^A-Za-z0-9]+/,'').localeCompare(b.title.replace(/^[^A-Za-z0-9]+/,'')));
  const initial = a => { const m=a.title.match(/[A-Za-z0-9]/); const c=m?m[0].toUpperCase():'#'; return /[A-Z]/.test(c)?c:'#'; };
  const letters=[...new Set(list.map(initial))].sort((x,y)=>x==='#'?-1:y==='#'?1:x.localeCompare(y));
  if(FP.sort!=='most' && FP.letter) list=list.filter(a=>initial(a)===FP.letter);
  const I=S.data.identity;
  const n = t => FP.list.filter(a=>a.type===t).length;
  const intro = !FP.type && FP.sort==='az' && !FP.letter ? `<div class="card"><div class="kicker">${esc(I.family_name||'the family')}</div><h2>${esc(I.display_title)}</h2>
      ${I.summary?`<p class="lede mine">${wikiLink(I.summary)}</p>`:`<p class="empty">No summary yet. Write one, or draft it from the project, in Settings → Family details.</p>`}
      <p class="sub" style="margin-top:8px">${FP.list.length} articles · ${FP.list.filter(a=>a.stub).length} stubs${FP.list.length?' · ':''}${FP.meta.types.filter(t=>n(t.type)).map(t=>`${n(t.type)} ${esc(t.label.toLowerCase())}`).join(' · ')}</p></div>` : '';
  const title = FP.sort==='needs' ? 'Needs more' : FP.sort==='most' ? 'Most material' : 'A–Z';
  $('#wk-article').innerHTML = intro + `<div class="card"><div class="row"><h3 style="margin:0">${title}${FP.type?' · '+esc(typeLabel(FP.type)):''}</h3><span class="spacer"></span><span class="sub" style="margin:0">${list.length} article${list.length!==1?'s':''}</span></div>
    ${FP.sort==='needs'?'<p class="sub" style="margin-top:6px">Stubs: named in the material, little said yet. Each is a question for the next recording or a record to look for.</p>':''}
    ${FP.sort!=='most'?`<div class="row fp-az" style="gap:3px;margin:10px 0">${letters.map(l=>`<button class="btn ghost sm" data-letter="${esc(l)}" aria-pressed="${FP.letter===l}">${esc(l)}</button>`).join('')}${FP.letter?'<button class="btn ghost sm" data-letter="">all</button>':''}</div>`:''}
    <ul class="fp-list chips">${list.slice(0,FP.shown).map(a=>`<li>${artLink(a.slug,a.title,a.type)}${a.kind?` <span class="derived">${esc(a.kind)}</span>`:''}${a.stub?' <span class="derived">stub</span>':''}
      <span class="fp-counts">${[a.stories&&`${a.stories} ${a.stories>1?L.stories:L.story}`, a.mentions&&`${a.mentions} passage${a.mentions>1?'s':''}`, a.records&&`${a.records} record${a.records>1?'s':''}`, a.photos&&`${a.photos} image${a.photos>1?'s':''}`, a.events.length&&`${a.events.length} event${a.events.length>1?'s':''}`].filter(Boolean).join(' · ')}</span></li>`).join('')}</ul>
    ${list.length>FP.shown?`<button class="btn ghost sm" id="fp-more">Show ${Math.min(400,list.length-FP.shown)} more</button>`:''}</div>`;
  $$('[data-letter]').forEach(b=>b.onclick=()=>{ FP.letter=b.dataset.letter; FP.shown=200; drawListing(); });
  const more=$('#fp-more'); if(more) more.onclick=()=>{ FP.shown+=400; drawListing(); };
}

/* ------------------------------------------------------------------ one article */
async function openArticle(slug){ await loadFamilypedia(); return showArticle(slug); }
async function showArticle(slug){
  setView('articles');
  if(!$('#wk-article')) drawBrowse();
  const box=$('#wk-article'); box.innerHTML='<div class="card"><p class="empty">Loading…</p></div>';
  const a = await api('/api/engine/article?slug='+encodeURIComponent(slug));
  if(a.error){ box.innerHTML=`<div class="card"><p class="empty">${esc(a.error)}</p></div>`; return; }
  S.article=a;
  if(a.wiki) return drawWikiArticle(a);
  const chip = c => c ? (/^https?:/.test(c)?`<a class="cite" href="${esc(c)}" target="_blank" rel="noopener">source ↗</a>`:`<a class="cite" data-cite="${esc(c)}">${esc(c)}</a>`) : '';
  // a person's picture is never an illustration; other subjects may lead with one, marked
  const lead = a.photos.find(p=>p.portrait && p.thumb) || a.photos.find(p=>p.thumb && !p.illustration) || a.photos.find(p=>p.chapter_cover && p.thumb) || (a.type==='person' ? null : a.photos.find(p=>p.thumb));
  const ibv = v => v.slug?artLink(v.slug,v.text,null,v.note):(v.record?`<a class="wl" href="#familypedia?view=records&focus=${encodeURIComponent(v.record)}">${esc(v.text)}</a>`:wikiLink(v.text,{skip:a.slug}));
  const sec = (title, body, extra='') => body ? `<section class="tier"><div class="row"><h4>${title}</h4><span class="spacer"></span>${extra}</div>${body}</section>` : '';
  const rec = r => `<tr><td>${esc(r.type)}</td><td>${r.url?`<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>`:esc(r.title)}${r.description&&r.description!==r.title?`<div class="sub" style="margin:2px 0 0;font-size:12.6px">${esc(r.description.slice(0,240))}</div>`:''}</td>
    <td>${esc(r.archive||'—')}</td><td class="mono">${esc(r.number||'')}</td><td>${esc(r.date||'')}</td><td>${r.retrieved?esc(r.retrieved):'<span class="derived">no retrieval date</span>'}</td></tr>`;
  const photo = p => !p.thumb ? '' : `<figure class="fp-photo">${`<img src="${fileUrl(p.thumb)}" alt="${esc(p.caption)}">`}
    <figcaption>${esc(p.caption)}${p.illustration?' <span class="pill warn" title="Generated: not a photograph of the real scene">illustration</span>':''}<br><span class="derived">${esc(p.provenance||p.origin||'')}</span>${p.date?`<br><span class="derived">${esc(p.date)}${p.date_basis?' · '+esc(p.date_basis):''}</span>`:''}</figcaption></figure>`;
  const related = a.related.map(g=>`<div class="fp-rel"><h5>${esc(g.group)} · ${g.count}</h5>${g.items.map(i=>artLink(i.slug,i.title,i.type,i.note)).join(' ')}${g.count>g.items.length?` <span class="derived">and ${g.count-g.items.length} more</span>`:''}</div>`).join('');
  const tiers = Object.entries(a.tiers).filter(([,v])=>v.length).map(([k,v])=>sec(`<span class="tierdot t-${k}"></span>${TIER_TITLES[k]} · ${v.length}`,
      `<ul class="fp-tier">${v.slice(0,40).map(i=>`<li>${i.slug?artLink(i.slug,i.text):wikiLink(i.text,{skip:a.slug})} ${i.date?`<span style="color:var(--ink-3)">${esc(i.date)}</span>`:''}${i.archive?` <span class="derived">${esc(i.archive)}</span>`:''}${(i.cite||'').split(/;\s*/).map(chip).join('')}${i.id&&i.kind==='event'?` <a class="chiplink" href="#timeline?focus=${encodeURIComponent(i.id)}">timeline</a>`:''}</li>`).join('')}</ul>${v.length>40?`<p class="derived">and ${v.length-40} more</p>`:''}`)).join('');
  const outLinks = [
    a.events.length?`<a class="chiplink" href="#timeline?focus=${encodeURIComponent(a.events[0].id)}">On the timeline · ${a.events.length}</a>`:'',
    a.type==='person'?`<a class="chiplink" href="#genealogy?focus=${encodeURIComponent(a.genealogy||a.slug)}">In the tree</a>`:'',
    a.coords||a.routes.length?`<a class="chiplink" href="#familypedia?view=map&focus=${encodeURIComponent(a.slug)}">On the map</a>`:'',
    ...a.stories.slice(0,4).map(s=>storyChip(s.id, s.title))].filter(Boolean).join('');
  box.innerHTML = `<article class="card article">
    <aside class="infobox">${lead&&lead.thumb?`<img src="${fileUrl(lead.thumb)}" alt="${esc(lead.caption)}" style="width:100%;border-radius:8px;margin-bottom:6px">${lead.illustration?'<span class="pill warn">illustration, not a photograph</span>':''}`:''}
      <dl class="kv ib"><dt>article</dt><dd>${esc(a.type_label)}${a.kind?` · ${esc(a.kind)}`:''}</dd>
      ${a.infobox.map(r=>`<dt>${esc(r.label.toLowerCase())}</dt><dd>${r.values.length?r.values.slice(0,12).map(ibv).join(r.values.length>3?'<br>':', ')+(r.values.length>12?` <span class="derived">+${r.values.length-12}</span>`:'')+` <span class="derived" title="${esc(r.basis)}">${r.by==='me'?'mine':'derived'}</span>`:'<span class="derived">not in the material</span>'}</dd>`).join('')}
      <dt>material</dt><dd>${[a.stories.length&&`${a.stories.length} ${a.stories.length>1?L.stories:L.story}`, a.passages.length&&`${a.passages.length} passage${a.passages.length>1?'s':''}`, a.records.length&&`${a.records.length} record${a.records.length>1?'s':''}`, a.photos.length&&`${a.photos.length} image${a.photos.length>1?'s':''}`, a.sources.length&&`${a.sources.length} source${a.sources.length>1?'s':''}`].filter(Boolean).join(' · ')||'one mention'}</dd></dl>
      <button class="btn ghost sm" id="wk-ibedit" style="margin-top:10px">Edit details</button>
      <p class="derived" style="margin:10px 0 0">No generated faces stand in for a real person. Images appear here when the material holds one or one is tagged.</p></aside>
    <div class="kicker">${esc(a.type_label)}${a.stub?' · stub':''}${a.aliases.length?' · also '+a.aliases.slice(0,4).map(esc).join(', '):''}</div><h2>${esc(a.title)}</h2>
    <p class="${a.lead_by==='me'?'mine':''}" id="wk-lead">${wikiLink(a.lead,{skip:a.slug})} <span class="derived">${a.lead_by==='me'?'written by me':'derived from the material'}</span> <button class="btn ghost sm" id="wk-edit">Edit</button></p>
    ${outLinks?`<div class="row" style="gap:6px;margin:6px 0 4px">${outLinks}</div>`:''}
    ${(a.conflicts||[]).length?`<div class="note" style="margin:10px 0;background:#FFFBF1;border:1px solid #E3D2AB"><b>The sources disagree.</b> ${a.conflicts.map(c=>esc(c)).join(' · ')} <span class="derived">both versions are kept</span></div>`:''}
    ${(a.event_passages||[]).length?sec('The passages this rests on', a.event_passages.map(x=>`<p class="quote">“${wikiLink(x.text)}”<br><span class="who">${esc(x.speaker||'')}</span>${chip(x.cite)}</p>`).join('')):''}
    ${(a.before||[]).length||(a.after||[]).length?`<div class="tier grid two" style="margin-top:12px"><div><h4>Before</h4>${(a.before||[]).map(e=>`<p style="margin:3px 0">${e.slug?artLink(e.slug,e.title):esc(e.title)} <span style="color:var(--ink-3)">${esc(e.date)}</span></p>`).join('')||'<p class="empty" style="padding:0">nothing earlier</p>'}</div>
      <div><h4>After</h4>${(a.after||[]).map(e=>`<p style="margin:3px 0">${e.slug?artLink(e.slug,e.title):esc(e.title)} <span style="color:var(--ink-3)">${esc(e.date)}</span></p>`).join('')||'<p class="empty" style="padding:0">nothing later</p>'}</div></div>`:''}
    ${tiers}
    ${sec(`In their words · ${a.passages.length} passage${a.passages.length!==1?'s':''}`, a.passages.slice(0,60).map(m=>`<p class="quote">“${wikiLink(m.text,{skip:a.slug})}”<br><span class="who">${esc(m.speaker)}</span>${chip(m.cite)}${m.source?` <a class="chiplink" href="#" data-listen="${esc(m.source)}" data-t="${esc(m.t)}">listen</a>`:''}</p>`).join('')+(a.passages.length>60?`<p class="derived">and ${a.passages.length-60} more</p>`:''))}
    ${sec(`${esc(L.storiesAbout)} ${esc(a.title)}`, a.stories.map(s=>`<a class="wl" href="#stories?read=${encodeURIComponent(s.id)}">${esc(s.title)}</a>${s.state?` <span class="derived">${esc(s.state)}</span>`:''}`).join(' · '))}
    ${sec(`Sources · ${a.sources.length}`, a.sources.length&&`<div class="fp-srcs">${a.sources.map(x=>`<a class="fp-src" href="#sources" data-src="${esc(x.id)}">${x.thumb?`<img src="${fileUrl(x.thumb)}" alt="">`:`<span class="icon ${esc(x.kind)}">${esc((typeof KIND_LABEL!=='undefined'&&KIND_LABEL[x.kind])||x.kind)}</span>`}<span>${esc(x.name)}<br><span class="derived">${esc(x.why)}</span></span></a>`).join('')}</div>`)}
    ${(a.book_sources||[]).length?sec(`Sources from the book · ${a.book_sources.reduce((n,g)=>n+g.items.length,0)}`, a.book_sources.map(g=>`<details class="fp-book-src"${a.book_sources.length===1?' open':''}><summary><a class="wl" href="#stories?read=${encodeURIComponent(g.story)}">${esc(g.title)}</a> <span class="derived">${g.items.length} source${g.items.length!==1?'s':''}, as listed at the chapter's end</span></summary><ol>${g.items.map(x=>`<li>${esc(x.text)}${(x.urls||[]).map((u,k)=>` <a href="${esc(u)}" target="_blank" rel="noopener">${(x.urls.length>1?'link '+(k+1):'link')}</a>`).join('')}</li>`).join('')}</ol></details>`).join('')):''}
    ${sec(`Records · ${a.records.length}`, a.records.length&&`<table class="fp-rec"><thead><tr><th>Type</th><th>Record</th><th>Archive</th><th>Number</th><th>Date</th><th>Retrieved</th></tr></thead><tbody>${a.records.slice(0,80).map(rec).join('')}</tbody></table>${a.records.length>80?`<p class="derived">and ${a.records.length-80} more in <a href="#familypedia?view=records">Records</a></p>`:''}`)}
    ${sec(`Photographs and illustrations · ${a.photos.filter(p=>p.thumb).length}`, a.photos.some(p=>p.thumb)&&`<div class="fp-photos">${a.photos.filter(p=>p.thumb).map(photo).join('')}</div>`)}
    ${sec('Related articles', related)}
    ${sec('Story units', a.units.map(u=>`<span class="chiplink" title="${esc(u.id)}">${esc(u.id)} · ${esc(u.title)}</span>`).join(' '))}
    <section class="tier"><h4>Notes <span class="derived">stated by me</span></h4><textarea id="wk-notes" rows="3" placeholder="What you know that the material doesn't say. [[Links]] work here. Your notes outrank anything derived.">${esc(a.notes)}</textarea>
      <div class="row" style="margin-top:6px"><button class="btn ghost sm" id="wk-notes-save">Save notes</button></div></section>
    ${a.open_questions.length?sec('Open questions', `<ul>${a.open_questions.map(q=>`<li>${wikiLink(q.text,{skip:a.slug})} <span class="derived">${esc(q.from)}</span></li>`).join('')}</ul>`, a.type==='person'?`<button class="btn ghost sm" id="wk-ask">Ask for more about ${esc(a.title)}</button>`:''):''}
    ${sec(`What links here · ${a.backlinks.length}`, a.backlinks.map(b=>artLink(b.slug,b.title,b.type)).join(' '))}
    <details class="tier fp-beyond" style="margin-top:18px" ${a.beyond.items.length?'open':''}><summary>Beyond the family <span class="derived">public background, kept apart from what the family knows</span></summary>
      ${a.beyond.items.map((b,i)=>`<p>${esc(b.text)} ${b.url?`<a href="${esc(b.url)}" target="_blank" rel="noopener">${esc(b.title||b.url)}</a>`:''} <span class="derived">${b.retrieved?'retrieved '+esc(b.retrieved):'no retrieval date'}</span> <button class="btn ghost sm" data-bdel="${i}">remove</button></p>`).join('')||'<p class="sub">Nothing added.</p>'}
      ${a.beyond.suggestions.length?`<p class="sub" style="margin:10px 0 4px">From this project's context sheets (already sourced):</p><ul>${a.beyond.suggestions.map(s=>`<li style="font-size:13px">${esc(s.text)} <span class="derived">${esc(s.file)}</span></li>`).join('')}</ul>`:''}
      <div class="grid three" style="margin-top:8px"><input type="text" id="bf-text" placeholder="What the source says (one sentence)"><input type="url" id="bf-url" placeholder="https://… link"><input type="text" id="bf-ret" placeholder="retrieved YYYY-MM-DD" value="${new Date().toISOString().slice(0,10)}"></div>
      <div class="row" style="margin-top:6px"><button class="btn ghost sm" id="bf-add">Add background</button><span class="sub" style="margin:0;font-size:12.4px">Public background is about the world, never about a private person.</span></div></details>
    ${a.history.length?`<details class="tier"><summary>History</summary><ul style="font-size:13px">${a.history.map(h=>`<li>${esc((h.at||'').replace('T',' ').slice(0,16))} · ${esc(h.by)} · ${esc((h.fields||[]).join(', '))}</li>`).join('')}</ul></details>`:''}
  </article>`;
  $$('#wk-article [data-cite]').forEach(c=>c.onclick=e=>{ e.preventDefault(); openCitation(c.dataset.cite); });
  $$('#wk-article [data-listen]').forEach(c=>c.onclick=e=>{ e.preventDefault(); const [h,m,s]=c.dataset.t.split(':').map(Number); openTranscript(c.dataset.listen, h*3600+m*60+s); });
  $$('#wk-article [data-src]').forEach(c=>c.onclick=e=>{ e.preventDefault(); const id=c.dataset.src; if(id.startsWith('audio/')) openTranscript(id); else { location.hash='sources'; setTimeout(()=>editSource(id),500); } });
  const ask=$('#wk-ask'); if(ask) ask.onclick=()=>draftRequest({kind:'person', about:a.slug});
  const save = async patch => { const r=await api('/api/engine/article',{method:'POST',body:{slug:a.slug, ...patch}}); if(r.error){ alertNote(r.error); return false; } return true; };
  $('#wk-notes-save').onclick=async()=>{ if(await save({notes:$('#wk-notes').value})) alertNote('Notes saved, marked as yours.'); };
  $('#wk-edit').onclick=()=>{ const p=$('#wk-lead'); p.innerHTML=`<textarea id="wk-lead-in" rows="4">${esc(a.lead)}</textarea><div class="row" style="margin-top:6px"><button class="btn sm" id="wk-lead-save">Save</button><button class="btn ghost sm" id="wk-lead-reset">Use the derived lead</button></div>`;
    $('#wk-lead-save').onclick=async()=>{ if(await save({lead:$('#wk-lead-in').value})) showArticle(a.slug); };
    $('#wk-lead-reset').onclick=async()=>{ if(await save({lead:''})) showArticle(a.slug); }; };
  $('#wk-ibedit').onclick=()=>editDetails(a, save);
  $('#bf-add').onclick=async()=>{ const text=$('#bf-text').value.trim(), url=$('#bf-url').value.trim(); if(!text||!url){ alertNote('Background needs a sentence and its link.'); return; }
    if(await save({beyond:[...a.beyond.items,{text,url,retrieved:$('#bf-ret').value.trim(),by:'me'}]})) showArticle(a.slug); };
  $$('[data-bdel]').forEach(b=>b.onclick=async()=>{ const items=a.beyond.items.filter((_,i)=>i!==+b.dataset.bdel); if(await save({beyond:items})) showArticle(a.slug); });
  window.scrollTo(0,0);
}
function editDetails(a, save){
  const types=FP.meta.types;
  openDrawer('Edit details: '+a.title, `<p class="sub">Your values are marked as yours and win over anything derived. Leave a field blank to use the derived value.</p>
    <div class="grid two"><div><label>Type</label><select id="ed-type">${types.map(t=>`<option value="${t.type}" ${t.type===a.type?'selected':''}>${esc(t.singular)}</option>`).join('')}</select></div>
      <div><label>Kind (what sort of ${esc(a.type_label)})</label><input type="text" id="ed-kind" value="${esc(a.kind||'')}" placeholder="whaleship, mill town, regiment…"></div></div>
    <label style="margin-top:10px">Other names <span class="derived">separate with ;</span></label><input type="text" id="ed-aliases" value="${esc(a.aliases.join('; '))}">
    <label style="margin-top:10px">Same subject as <span class="derived">slugs of duplicate articles to fold into this one; separate with ;</span></label><input type="text" id="ed-same" placeholder="ship-hannibal">
    <h4 style="margin:16px 0 6px">Infobox</h4>
    ${a.infobox.map(r=>`<label>${esc(r.label)} <span class="derived">${r.by==='me'?'mine':esc(r.basis||'')}</span></label><input type="text" data-ib="${esc(r.label)}" value="${r.by==='me'?esc(r.values.map(v=>v.text).join('; ')):''}" placeholder="${esc(r.values.map(v=>v.text).slice(0,3).join('; ')||'not in the material')}">`).join('')}
    ${a.type==='place'?`<h4 style="margin:16px 0 6px">Coordinates</h4><div class="grid three"><input type="text" id="ed-lat" placeholder="lat" value="${a.coords&&a.coords.by==='me'?a.coords.lat:''}"><input type="text" id="ed-lon" placeholder="lon" value="${a.coords&&a.coords.by==='me'?a.coords.lon:''}">
      <select id="ed-basis"><option value="approximate">approximate (drawn dashed)</option><option value="recorded">recorded in a source</option></select></div><input type="text" id="ed-csrc" placeholder="where the coordinates come from" style="margin-top:6px">`:''}
    <div class="row" style="margin-top:16px"><button class="btn go" id="ed-save">Save</button></div>`);
  $('#ed-save').onclick=async()=>{
    const split=v=>v.split(/;\s*/).map(s=>s.trim()).filter(Boolean);
    const infobox={}; $$('[data-ib]').forEach(i=>{ if(i.value.trim()) infobox[i.dataset.ib]=i.value.trim(); });
    const patch={type:$('#ed-type').value, kind:$('#ed-kind').value.trim(), aliases:split($('#ed-aliases').value), infobox};
    const same=split($('#ed-same').value); if(same.length) patch.same_as=same;
    if($('#ed-lat') && $('#ed-lat').value.trim()) patch.coords={lat:$('#ed-lat').value.trim(), lon:$('#ed-lon').value.trim(), basis:$('#ed-basis').value, source:$('#ed-csrc').value.trim()||'stated by me'};
    if(await save(patch)){ closeOverlay(); await loadFamilypedia(true); showArticle(a.slug); }
  };
}

/* ------------------------------------------------------------------ map */
async function drawMapView(focus){
  $('#fp-body').innerHTML='<div class="card"><p class="empty">Drawing the map…</p></div>';
  const m=await api('/api/engine/familypedia/map'+(focus?'?focus='+encodeURIComponent(focus):''));
  const ft=focus?((FP.list.find(a=>a.slug===focus)||{}).title||focus):'';
  $('#fp-body').innerHTML=`<div class="card"><div class="row"><h3 style="margin:0">Map${focus?` · ${artLink(focus,ft)}`:''}</h3><span class="spacer"></span>
      ${focus?'<a class="btn ghost sm" href="#familypedia?view=map" style="text-decoration:none">All places</a>':''}</div>
    <p class="sub" style="margin-top:6px">Built from the coordinates the records give. Nothing is placed by guesswork.</p>
    ${m.svg?`<div class="fp-mapwrap">${m.svg}</div>`:'<p class="empty">No coordinates in the material yet. They come from track or route files (lat, lon), the knowledge graph, or coordinates you give a place.</p>'}
    <div class="row fp-legend"><span><i class="lg rec"></i>recorded position</span><span><i class="lg open"></i>recorded, subject not aboard</span><span><i class="lg dash"></i>route between recorded positions (approximate)</span><span><i class="lg approx"></i>approximate place</span><span><b class="gapt">not recorded</b> a leg no record covers</span></div>
    ${m.land?`<p class="derived">Coastlines: ${esc(m.land)} (Natural Earth, public domain). No map tiles are fetched.</p>`:'<p class="derived">No coastline file in the project (facts/records/_raw/geo/*.geojson), so only the points are drawn.</p>'}</div>
    <div class="grid two"><div class="card"><h3>Routes · ${m.tracks.length}</h3>${m.tracks.map(t=>`<p style="margin:4px 0">${t.subjects.map(s=>artLink(s.slug,s.title)).join(' ')||'<span class="pill warn">not attached</span>'} <span class="derived">${esc(t.file)} · ${t.points} positions</span></p>`).join('')||'<p class="empty">None.</p>'}
      ${m.unattached_routes.length?`<p class="note">Routes whose subject is ambiguous (more than one match, or none): ${m.unattached_routes.map(esc).join(', ')}. Name the subject in data/familypedia/routes.json.</p>`:''}</div>
    <div class="card"><h3>Places not on the map · ${m.not_on_map.length}</h3><p class="sub">No coordinates in the records. Add them on the place's article (marked approximate) if you know them.</p>
      <p style="font-size:13px">${m.not_on_map.slice(0,300).map(t=>{ const a=resolveName(t); return a?artLink(a.slug,t):esc(t); }).join(' ')}</p></div></div>`;
}

/* ------------------------------------------------------------------ records and photographs: browse and bulk tag */
async function drawCatalogue(what){
  FP.sel=new Set();
  $('#fp-body').innerHTML='<div class="card"><p class="empty">Loading…</p></div>';
  const r=await api('/api/engine/familypedia/catalogue?what='+what); const items=r.items;
  const types=[...new Set(items.map(i=>i.type||'image'))].sort();
  const focus=(S.q||{}).focus;
  $('#fp-body').innerHTML=`<div class="card"><div class="row"><h3 style="margin:0">${what==='records'?'Records':'Photographs and illustrations'} · ${items.length}</h3><span class="spacer"></span>
      <input type="search" id="cat-q" placeholder="Filter" style="max-width:260px">${what==='records'?`<select id="cat-type" style="max-width:200px"><option value="">every type</option>${types.map(t=>`<option>${esc(t)}</option>`).join('')}</select>`:''}</div>
    <p class="sub" style="margin-top:6px">${what==='records'?'Every record the project knows: the catalogue, research sources and the knowledge graph, typed, with archive, number, link and retrieval date.':'Photographs from the photo index and image sources. Generated illustrations are marked, with their provenance.'} Select several and tag them to any article.</p>
    <div class="row hidden" id="cat-bulk" style="margin:8px 0;background:#F3EEE4;border-radius:9px;padding:8px 12px"><b id="cat-n"></b><button class="btn ghost sm" id="cat-tag">Tag to a subject…</button><button class="btn ghost sm" id="cat-clear">Clear selection</button></div>
    <div id="cat-list"></div></div>`;
  const draw=()=>{
    const q=($('#cat-q').value||'').toLowerCase(), ty=$('#cat-type')?$('#cat-type').value:'';
    const list=items.filter(i=>(!ty||i.type===ty) && (!q || JSON.stringify(i).toLowerCase().includes(q)));
    const subj = i => i.subjects.map(s=>artLink(s.slug,s.title,s.type)).join(' ')||'<span class="derived">untagged</span>';
    $('#cat-list').innerHTML = what==='records'
      ? `<table class="fp-rec"><thead><tr><th></th><th>Type</th><th>Record</th><th>Archive</th><th>Number</th><th>Retrieved</th><th>About</th></tr></thead><tbody>${list.slice(0,600).map(i=>`<tr id="rec-${esc(i.id)}" class="${focus===i.id?'hl':''}"><td><input type="checkbox" data-csel="${esc(i.id)}" ${FP.sel.has(i.id)?'checked':''}></td><td>${esc(i.type)}</td>
          <td>${i.url?`<a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a>`:esc(i.title)}</td><td>${esc(i.archive||'—')}</td><td class="mono">${esc(i.number||'')}</td><td>${esc(i.retrieved||'—')}</td><td style="font-size:12.8px">${subj(i)} <button class="btn ghost sm" data-ctag="${esc(i.id)}">tags</button></td></tr>`).join('')}</tbody></table>${list.length>600?`<p class="derived">Showing 600 of ${list.length}; filter to narrow.</p>`:''}`
      : `<div class="fp-photos">${list.map(p=>`<figure class="fp-photo sel"><label><input type="checkbox" data-csel="${esc(p.id)}" ${FP.sel.has(p.id)?'checked':''}> select</label>${p.thumb?`<img src="${fileUrl(p.thumb)}" alt="">`:''}
          <figcaption>${esc(p.id)} · ${esc(p.caption)}${p.illustration?' <span class="pill warn">illustration</span>':''}<br><span class="derived">${esc(p.provenance||'')}</span><br>${subj(p)} <button class="btn ghost sm" data-ctag="${esc(p.id)}">tags</button></figcaption></figure>`).join('')||'<p class="empty">None yet.</p>'}</div>`;
    $$('[data-csel]').forEach(c=>c.onchange=()=>{ c.checked?FP.sel.add(c.dataset.csel):FP.sel.delete(c.dataset.csel); bulk(); });
    $$('[data-ctag]').forEach(b=>b.onclick=()=>openTagPanel((what==='records'?'record:':'photo:')+b.dataset.ctag, ()=>drawCatalogue(what)));
    if(focus){ const row=document.getElementById('rec-'+focus); if(row) row.scrollIntoView({block:'center'}); }
  };
  const bulk=()=>{ $('#cat-bulk').classList.toggle('hidden',!FP.sel.size); $('#cat-n').textContent=`${FP.sel.size} selected`; };
  $('#cat-q').oninput=draw; if($('#cat-type')) $('#cat-type').onchange=draw;
  $('#cat-clear').onclick=()=>{ FP.sel.clear(); draw(); bulk(); };
  $('#cat-tag').onclick=()=>bulkTagTo([...FP.sel].map(id=>(what==='records'?'record:':'photo:')+id), ()=>drawCatalogue(what));
  draw(); bulk();
}

/* ------------------------------------------------------------------ the tagger: picker, suggestions, bulk (shared with Sources and Timeline) */
async function ensureFP(){ if(!FP.meta) await loadFamilypedia(); }
function openPicker({title='Choose a subject', onPick, newOnly=false}){
  const types=(FP.meta||{types:[]}).types;
  openModal(title, `${newOnly?'':`<input type="search" id="pk-q" placeholder="Search people, places, ships, regiments, objects…"><div id="pk-res" class="fp-picker"><p class="empty">Loading…</p></div>`}
    <details ${newOnly?'open':''} style="margin-top:12px"><summary style="cursor:pointer;font-weight:600">New subject…</summary>
      <div class="grid two" style="margin-top:8px"><input type="text" id="pk-title" placeholder="Name, as the material gives it"><select id="pk-type">${types.map(t=>`<option value="${t.type}">${esc(t.singular)}</option>`).join('')}</select></div>
      <div class="row" style="margin-top:8px"><button class="btn go sm" id="pk-create">Create</button><span class="sub" style="margin:0;font-size:12.4px">Created as a stub, marked as yours. It fills in as material is tagged to it.</span></div></details>`);
  const draw=async()=>{ const r=await api('/api/engine/familypedia/picker?q='+encodeURIComponent($('#pk-q').value||''));
    $('#pk-res').innerHTML=r.groups.map(g=>`<h5>${esc(g.label)} · ${g.count}</h5>${g.items.map(i=>`<button class="linkish fp-pick" data-slug="${esc(i.slug)}" data-title="${esc(i.title)}" data-type="${g.type}">${esc(i.title)}${i.kind?` <span class="derived">${esc(i.kind)}</span>`:''}${i.stub?' <span class="derived">stub</span>':''}</button>`).join('')}`).join('')||'<p class="empty">No subject by that name. Create it below.</p>';
    $$('.fp-pick').forEach(b=>b.onclick=()=>{ closeOverlay(); onPick({slug:b.dataset.slug, title:b.dataset.title, type:b.dataset.type}); }); };
  if(!newOnly){ let t; $('#pk-q').oninput=()=>{ clearTimeout(t); t=setTimeout(draw,160); }; $('#pk-q').focus(); draw(); }
  $('#pk-create').onclick=async()=>{ const title=$('#pk-title').value.trim(), type=$('#pk-type').value; if(!title){ alertNote('Give the subject a name.'); return; }
    const r=await api('/api/engine/familypedia/subject',{method:'POST',body:{title, type}}); if(r.error){ alertNote(r.error); return; }
    await loadFamilypedia(true); closeOverlay(); onPick({slug:r.slug, title, type}); };
}
async function bulkTagTo(targets, done){
  await ensureFP();
  openPicker({title:`Tag ${targets.length} item${targets.length>1?'s':''} to…`, onPick:async s=>{
    const r=await api('/api/engine/tags',{method:'POST',body:{targets, subject:s.slug, state:'accepted'}});
    if(r.error){ alertNote(r.error); return; } alertNote(`Tagged ${targets.length} to ${s.title}.`); await loadFamilypedia(true); done&&done(); }});
}
async function openTagPanel(target, done){
  await ensureFP();
  const r=await api('/api/engine/tags?target='+encodeURIComponent(target));
  openDrawer('Subjects', tagPanelHtml(r));
  bindTagPanel(target, ()=>openTagPanel(target, done), done);
}
function tagPanelHtml(r){
  const st={accepted:'ok', unsure:'warn', rejected:'bad', suggested:''};
  return `<p class="sub">Tag this to any article: a person, place, ship, regiment, object, paper, trade or theme. Suggestions come only from names written in the item, each with the words that name it; nothing is tagged until you accept it. No faces are recognized and no names guessed.</p>
    <div class="row" style="margin-bottom:10px"><button class="btn sm" id="tg-add">Tag to a subject…</button></div>
    <h5>Tags · ${r.tags.length}</h5>${r.tags.map(t=>`<div class="fp-tag"><span class="pill ${st[t.state]||''}">${esc(t.state)}</span> ${t.missing?esc(t.subject):artLink(t.subject,t.title,t.type)} <span class="derived">${esc(t.by)}${t.evidence?' · '+esc(t.evidence):''}</span>
      <span class="spacer"></span>${t.state!=='accepted'?`<button class="btn ghost sm" data-tset="${esc(t.subject)}" data-state="accepted">accept</button>`:''}${t.state!=='unsure'?`<button class="btn ghost sm" data-tset="${esc(t.subject)}" data-state="unsure">unsure</button>`:''}${t.state!=='rejected'?`<button class="btn ghost sm" data-tset="${esc(t.subject)}" data-state="rejected">reject</button>`:''}</div>`).join('')||'<p class="empty" style="padding:6px 0">None yet.</p>'}
    <h5 style="margin-top:14px">Suggested from the text · ${r.suggestions.length}</h5>${r.suggestions.map(t=>`<div class="fp-tag">${artLink(t.subject,t.title,t.type)} <span class="derived">${esc(t.evidence)}</span><span class="spacer"></span>
      <button class="btn ghost sm" data-tset="${esc(t.subject)}" data-state="accepted" data-ev="${esc(t.evidence)}">accept</button><button class="btn ghost sm" data-tset="${esc(t.subject)}" data-state="rejected" data-ev="${esc(t.evidence)}">not this</button></div>`).join('')||'<p class="empty" style="padding:6px 0">No known names in the text.</p>'}`;
}
function bindTagPanel(target, redraw, done){
  $('#tg-add').onclick=()=>openPicker({title:'Tag to…', onPick:async s=>{ await api('/api/engine/tags',{method:'POST',body:{targets:[target], subject:s.slug, state:'accepted'}}); await loadFamilypedia(true); redraw(); done&&done(); }});
  $$('[data-tset]').forEach(b=>b.onclick=async()=>{ await api('/api/engine/tags',{method:'POST',body:{targets:[target], subject:b.dataset.tset, state:b.dataset.state, evidence:b.dataset.ev||''}}); await loadFamilypedia(true); redraw(); done&&done(); });
}

/* Recording citations such as "[S5 01:25:44]" written into prose become small chips, so a reader never sees raw
   bracket codes in a sentence (Rex, 2026-10-10). Text that is already a citation chip on its own is left alone. */
(function(){
  const RE=/\s*\[(S\d+) (\d{1,2}:\d{2}:\d{2})\]/g, SKIP=new Set(['SCRIPT','STYLE','TEXTAREA','INPUT','CODE','PRE']);
  const fix=root=>{
    const w=document.createTreeWalker(root, NodeFilter.SHOW_TEXT), hits=[];
    for(let n=w.nextNode(); n; n=w.nextNode()){
      const p=n.parentElement; if(!p || SKIP.has(p.tagName) || p.closest('.ts-chip,[contenteditable="true"]')) continue;
      if(!n.nodeValue.includes('[S')) continue; RE.lastIndex=0; if(!RE.test(n.nodeValue)) continue;
      if(p.textContent.trim().replace(RE,'')==='') continue;          // already a chip of its own
      hits.push(n);
    }
    for(const n of hits){
      const f=document.createDocumentFragment(); let last=0, m; const s=n.nodeValue; RE.lastIndex=0;
      while((m=RE.exec(s))){ f.append(s.slice(last,m.index)); const c=document.createElement('span'); c.className='ts-chip';
        c.title=`Recording ${m[1]} at ${m[2]}`; c.textContent=`${m[1]} ${m[2]}`; f.append(' ',c); last=RE.lastIndex; }
      f.append(s.slice(last)); n.replaceWith(f);
    }
  };
  let queued=false;
  new MutationObserver(()=>{ if(queued) return; queued=true; requestAnimationFrame(()=>{ queued=false; fix(document.body); }); })
    .observe(document.documentElement,{childList:true,subtree:true});
})();


/* A curated encyclopedia article (data/wiki/<name>.md): infobox, lead, sections and numbered references, in place of
   the derived page (Rex, 2026-10-10: "full Wikipedia entries for each family member … sources linked at the bottom"). */
function drawWikiArticle(a){
  const box=$('#wk-article');
  const html=a.wiki.replace(/src="lineage-file:([^"]+)"/g,(m,p)=>`src="${fileUrl(p)}"`);
  const outLinks=[
    a.events.length?`<a class="chiplink" href="#timeline?focus=${encodeURIComponent(a.events[0].id)}">On the timeline · ${a.events.length}</a>`:'',
    `<a class="chiplink" href="#genealogy?focus=${encodeURIComponent(a.genealogy||a.slug)}">In the tree</a>`,
    // only the chapter about this person; the article's own "In The Book of Daniel" section lists the rest
    ...a.stories.filter(s=>[a.title, a.wiki_title].includes(s.title)).map(s=>storyChip(s.id, s.title))].filter(Boolean).join('');
  const photos=a.photos.filter(p=>p.thumb);
  box.innerHTML=`<article class="card article wiki-article">
    <div class="kicker">${esc(a.type_label)} · encyclopedia article</div><h2 class="wtitle">${esc(a.wiki_title||a.title)}</h2>
    ${outLinks?`<div class="row" style="gap:6px;margin:4px 0 12px">${outLinks}</div>`:''}
    ${html}
    ${photos.length?`<section class="tier" style="clear:both"><h4>Photographs and illustrations · ${photos.length}</h4><div class="fp-photos">${photos.map(p=>`<figure class="fp-photo"><img src="${fileUrl(p.thumb)}" alt="${esc(p.caption)}" loading="lazy"><figcaption>${esc(p.caption)}${p.illustration?' <span class="pill warn">illustration</span>':''}</figcaption></figure>`).join('')}</div></section>`:''}
    ${a.backlinks.length?`<section class="tier"><h4>What links here · ${a.backlinks.length}</h4>${a.backlinks.map(b=>artLink(b.slug,b.title,b.type)).join(' ')}</section>`:''}
  </article>`;
  $$('#wk-article .wiki a[href^="#ref-"], #wk-article .wiki a[href^="#cite-"], #wk-article .wtoc a, #wk-article .wiki a[href="#references"]').forEach(x=>x.onclick=e=>{
    e.preventDefault(); const t=document.getElementById(x.getAttribute('href').slice(1)); if(t) t.scrollIntoView({behavior:'smooth', block:'center'}); });
  window.scrollTo(0,0);
}
