/* ================================================================== TIMELINE
   A vertical spine, oldest at the top, with decade bands, a year rail that doubles as a minimap,
   gap cards where nothing is recorded, and conflict cards where the sources disagree.
   Every card carries its tier and its citations; nothing here is inferred for display. */
const TIER_LABEL={documented:'documented', witnessed:'witnessed', told:'told', lore:'family lore', unconfirmed:'unconfirmed'};
BUILDERS.timeline = async function(el, rest, q={}){
  el.innerHTML='';
  head(el,{kicker:'Timeline', title:'What happened, and when', lede:'Every dated event in the material, with how sure it is and where it comes from. Gaps show where the next question should go.'});
  el.insertAdjacentHTML('beforeend', `<div class="card"><div class="row">
      <input type="search" id="tl-q" placeholder="Search events, people, places" style="max-width:280px" value="${esc(q.q||'')}">
      <select id="tl-person" style="max-width:200px" aria-label="Person"><option value="">Everyone</option></select>
      <select id="tl-type" style="max-width:160px" aria-label="Kind"><option value="">Every kind</option></select>
      <select id="tl-tier" style="max-width:160px" aria-label="Tier"><option value="">Every tier</option>${Object.entries(TIER_LABEL).map(([k,v])=>`<option value="${k}">${esc(v)}</option>`).join('')}</select>
      <label class="toggle" style="padding:0;margin:0"><input type="checkbox" id="tl-hl"><div><b>Highlights</b></div></label>
      <label class="toggle" style="padding:0;margin:0"><input type="checkbox" id="tl-conf" ${q.filter==='conflicts'?'checked':''}><div><b>Conflicts</b></div></label>
      <span class="spacer"></span><button class="btn ghost sm" id="tl-undated">Undated</button>
      <button class="btn ghost sm" id="tl-svg">SVG</button><button class="btn ghost sm" id="tl-png">PNG</button><button class="btn ghost sm" id="tl-print">Printable appendix</button></div>
      <div class="legend">${Object.entries(TIER_LABEL).map(([k,v])=>`<span><span class="tierdot t-${k}"></span>${esc(v)}</span>`).join('')}<span>★ highlight</span></div></div>
    <div class="tl"><nav class="tlrail" id="tl-rail" aria-label="Years"></nav><div class="spine" id="tl-spine"><p class="empty">Loading…</p></div></div>`);
  const d = await api('/api/engine/timeline'); S.timeline = d;
  const people=[...new Set(d.events.flatMap(e=>e.people))].sort(), types=[...new Set(d.events.map(e=>e.type))].sort();
  $('#tl-person').insertAdjacentHTML('beforeend', people.map(p=>`<option ${q.person===p?'selected':''}>${esc(p)}</option>`).join(''));
  $('#tl-type').insertAdjacentHTML('beforeend', types.map(t=>`<option>${esc(t)}</option>`).join(''));
  let t=null; $('#tl-q').oninput=()=>{ clearTimeout(t); t=setTimeout(drawTimeline,200); };
  ['tl-person','tl-type','tl-tier','tl-hl','tl-conf'].forEach(id=>$('#'+id).oninput=drawTimeline);
  $('#tl-undated').onclick=showUndated;
  $('#tl-svg').onclick=async()=>{ const svg=await (await fetch('/api/engine/timeline.svg',{headers:{'X-Lineage-Token':TOKEN}})).text(); download('timeline.svg', new Blob([svg],{type:'image/svg+xml'})); };
  $('#tl-png').onclick=async()=>{ const svg=await (await fetch('/api/engine/timeline.svg',{headers:{'X-Lineage-Token':TOKEN}})).text(); svgToPng(svg,'timeline.png'); };
  $('#tl-print').onclick=printTimeline;
  $('#tl-undated').textContent = `Undated · ${d.undated.length}`;
  drawTimeline();
  if(q.focus) setTimeout(()=>{ const c=document.getElementById('ev-'+q.focus); if(c){ c.scrollIntoView({block:'center'}); c.style.boxShadow='0 0 0 3px rgba(201,111,74,.35)'; } },60);
};
function tlFiltered(){
  const d=S.timeline, q=($('#tl-q').value||'').toLowerCase(), person=$('#tl-person').value, type=$('#tl-type').value, tier=$('#tl-tier').value;
  return d.events.filter(e=>(!q || (e.title+' '+e.people.join(' ')+' '+e.place+' '+e.quote).toLowerCase().includes(q))
    && (!person || e.people.includes(person)) && (!type || e.type===type) && (!tier || e.tier===tier)
    && (!$('#tl-hl').checked || e.highlight) && (!$('#tl-conf').checked || e.conflict));
}
function evCard(e){
  const pl = p => e.person_slugs[p] ? `<a class="chiplink" href="#familypedia/${encodeURIComponent(e.person_slugs[p])}">${esc(p)}</a>` : `<span class="chiplink">${esc(p)}</span>`;
  return `<div class="ev tc-${esc(e.tier)}${e.highlight?' hl':''}${e.conflict?' conf':''}" id="ev-${esc(e.id)}">
    <button class="star${e.starred?' on':''}" data-star="${esc(e.id)}" aria-label="${e.starred?'Unstar':'Star'} this event" aria-pressed="${e.starred}">${e.starred?'★':'☆'}</button>
    ${e.photo?`<img class="ph" src="${fileUrl(e.photo)}" alt="">`:''}
    <div class="when"><span class="tierdot t-${esc(e.tier)}" title="${esc(TIER_LABEL[e.tier]||e.tier)}"></span>${esc(e.date)}${e.derived?` <span class="derived" title="${esc(e.summary)}">${esc(e.precision||'approximate')}</span>`:''} · ${esc(TIER_LABEL[e.tier]||e.tier)}${e.confidence?' · '+esc(e.confidence)+' confidence':''}</div>
    <h4>${e.slug?`<a class="wl" href="#familypedia/${encodeURIComponent(e.slug)}">${esc(e.title)}</a>`:esc(e.title)}</h4>
    ${e.quote?`<p class="quote" style="font-size:14px;margin:4px 0">“${esc(e.quote)}”</p>`:''}
    ${e.conflict?`<div class="note" style="padding:7px 10px;margin:6px 0;font-size:12.8px;background:#FBF4E4"><b>The sources disagree:</b> ${esc(e.conflict)}</div>`:''}
    <div class="tags">${e.people.map(pl).join('')}${e.place?(e.place_slug?`<a class="chiplink" href="#familypedia/${encodeURIComponent(e.place_slug)}">⌖ ${esc(e.place)}</a>`:`<span class="chiplink">⌖ ${esc(e.place)}</span>`):''}
      ${e.cites.map(c=>`<a class="cite" data-cite="${esc(c)}">${esc(c)}</a>`).join('')}
      ${e.story_id&&e.story?`<a class="chiplink" href="#stories?read=${encodeURIComponent(e.story_id)}">${esc(L.Story)}: ${esc(e.story)}</a>`:''}</div></div>`;
}
function drawTimeline(){
  const d=S.timeline, list=tlFiltered(), spine=$('#tl-spine');
  if(!d.events.length && !d.undated.length){ spine.innerHTML='<div class="card"><p class="empty">No events yet. The timeline is built from transcripts and records: ask the Genealogist (Terminal) to build it once there is material.</p></div>'; $('#tl-rail').innerHTML=''; return; }
  if(!list.length){ spine.innerHTML='<p class="empty">Nothing matches these filters.</p>'; $('#tl-rail').innerHTML=''; return; }
  const filtered = list.length!==d.events.length;
  const gapAfter = Object.fromEntries(d.gaps.map(g=>[g.after,g]));
  let band=null, html='';
  const counts={};
  list.forEach(e=>{ const b=Math.floor(e.year/10)*10; counts[b]=(counts[b]||0)+1;
    if(b!==band){ band=b; const life = d.subject_birth && b>=Math.floor(d.subject_birth/10)*10 ? ` <span class="derived">${esc(d.subject_short)} ${Math.max(0,b-d.subject_birth)}–${b+9-d.subject_birth}</span>` : '';
      html+=`<div class="band" id="band-${b}">${b}s${life}</div>`; }
    html+=evCard(e);
    const g=gapAfter[e.id];
    if(g && !filtered) html+=`<div class="gap"><span style="flex:1">Nothing recorded between <b>${g.from}</b> and <b>${g.to}</b>.</span><button class="btn ghost sm" data-gapq="${g.from}-${g.to}">Add to questions</button></div>`;
  });
  spine.innerHTML=html;
  const max=Math.max(...Object.values(counts));
  $('#tl-rail').innerHTML=Object.keys(counts).map(b=>`<a href="#band-${b}" data-band="${b}">${b}s <i style="width:${Math.max(4,Math.round(30*counts[b]/max))}px"></i></a>`).join('');
  $$('#tl-rail a').forEach(a=>a.onclick=e=>{ e.preventDefault(); document.getElementById('band-'+a.dataset.band).scrollIntoView({behavior:'smooth'}); });
  $$('[data-cite]',spine).forEach(c=>c.onclick=e=>{ e.preventDefault(); openCitation(c.dataset.cite); });
  $$('[data-star]',spine).forEach(b=>b.onclick=async()=>{ const e=d.events.find(x=>x.id===b.dataset.star); e.starred=!e.starred; e.highlight=e.starred||e.highlight;
    await api('/api/engine/timeline/star',{method:'POST',body:{id:e.id, star:e.starred}}); drawTimeline(); });
  $$('[data-gapq]',spine).forEach(b=>b.onclick=async()=>{ const [a,z]=b.dataset.gapq.split('-');
    await api('/api/engine/question',{method:'POST',body:{text:`What happened between ${a} and ${z}?`, source:`timeline gap ${a}–${z}`}}); b.textContent='Added'; b.disabled=true; });
  // the rail follows the scroll
  const io=new IntersectionObserver(es=>es.forEach(x=>{ if(x.isIntersecting){ $$('#tl-rail a').forEach(a=>a.classList.toggle('on', 'band-'+a.dataset.band===x.target.id)); } }),{rootMargin:'-80px 0px -70% 0px'});
  $$('.band',spine).forEach(b=>io.observe(b));
}
function showUndated(){
  const u=S.timeline.undated;
  openDrawer(`Undated · ${u.length}`, u.length ? `<p class="sub">Events the material mentions without a date. They stay off the spine until something dates them.</p>${u.map(evCard).join('')}` : '<p class="empty">Everything is dated.</p>');
  $$('.drawer [data-cite]').forEach(c=>c.onclick=e=>{ e.preventDefault(); openCitation(c.dataset.cite); });
  $$('.drawer .star').forEach(b=>b.remove());
}
function printTimeline(){
  const d=S.timeline, I=S.data.identity;
  printable(`Timeline · ${I.display_title}`, `<h1>Timeline</h1><p><small>${esc(I.display_title)}${I.covers?' · '+esc(I.covers):''}</small></p>
    ${d.events.map(e=>`<p><b>${esc(e.date)}</b> — ${esc(e.title)}${e.place?', '+esc(e.place):''} <small>(${esc(TIER_LABEL[e.tier]||e.tier)}; ${esc(e.cites.join('; '))})</small>${e.conflict?`<br><small>Sources disagree: ${esc(e.conflict)}</small>`:''}</p>`).join('')}
    ${d.undated.length?`<h2>Undated</h2>${d.undated.map(e=>`<p>${esc(e.title)} <small>(${esc(e.cites.join('; '))})</small></p>`).join('')}`:''}
    <p><small>Tiers: documented (a record says so), witnessed, told, family lore, unconfirmed.</small></p>`);
}
