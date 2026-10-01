/* ================================================================== FAMILYPEDIA */
const TYPE_LABEL={person:'People', place:'Places', event:'Events', object:'Objects', organization:'Organizations', theme:'Themes'};
BUILDERS.familypedia = async function(el, rest){
  el.innerHTML='';
  head(el,{kicker:'Familypedia', title:'The family, as an encyclopedia', lede:"Built only from this project's own material. Every sentence points at its source; stubs show where the next recording should go."});
  el.insertAdjacentHTML('beforeend', `<div class="wiki"><nav class="card" style="padding:14px">
      <input type="search" id="wk-q" placeholder="Search the Familypedia">
      <div class="row" style="margin:10px 0"><button class="btn ghost sm" id="wk-random">Random article</button><button class="btn ghost sm" id="wk-needs">Needs more</button></div>
      <div id="wk-list"><p class="empty">Loading…</p></div></nav>
    <div id="wk-article"></div></div>`);
  const r = await api('/api/engine/familypedia'); S.wiki = r.articles;
  $('#wk-q').oninput = drawWikiList; drawWikiList();
  $('#wk-random').onclick = ()=>{ if(S.wiki.length) location.hash='familypedia/'+S.wiki[Math.floor(Math.random()*S.wiki.length)].slug; };
  $('#wk-needs').onclick = ()=>{ $('#wk-q').value=''; drawWikiList(true); };
  if(rest && rest.length) openArticle(decodeURIComponent(rest[0]));
  else if(!S.wiki.length) $('#wk-article').innerHTML = `<div class="card"><p class="empty">No articles yet. They appear as soon as the project has story units or a timeline: add a source and transcribe it.</p></div>`;
  else drawWikiHome();
};
function drawWikiList(needsOnly=false){
  const q=($('#wk-q').value||'').toLowerCase();
  const list = S.wiki.filter(a=>(!q || a.title.toLowerCase().includes(q)) && (!needsOnly || a.stub));
  const byType = {}; list.forEach(a=>(byType[a.type]=byType[a.type]||[]).push(a));
  $('#wk-list').innerHTML = (needsOnly?'<h5>Needs more (ask about these next)</h5>':'') + (Object.keys(TYPE_LABEL).filter(t=>byType[t]).map(t=>`<h5>${TYPE_LABEL[t]} · ${byType[t].length}</h5><ul>${byType[t].map(a=>`<li><a href="#familypedia/${encodeURIComponent(a.slug)}" aria-current="${S.article&&S.article.slug===a.slug}">${esc(a.title)}${a.stub?' <span class="derived">stub</span>':''}</a></li>`).join('')}</ul>`).join('') || '<p class="empty">Nothing matches.</p>');
}
function drawWikiHome(){
  const az = {}; S.wiki.forEach(a=>{ const k=a.title[0].toUpperCase(); (az[k]=az[k]||[]).push(a); });
  const I=S.data.identity;
  $('#wk-article').innerHTML = `<div class="card"><div class="kicker">${esc(I.family_name||'the family')}</div><h2>${esc(I.display_title)}</h2>
    ${I.summary?`<p class="lede mine">${wikiLink(I.summary)}</p>`:`<p class="empty">No summary yet. Write one, or draft it from the project, in Settings → Family details.</p>`}
    ${I.covers?`<p class="sub" style="margin-top:8px">${esc(I.covers)}</p>`:''}</div>
    <div class="card"><h3>A–Z</h3><p class="sub">${S.wiki.length} articles · ${S.wiki.filter(a=>a.stub).length} stubs</p>
    ${Object.keys(az).sort().map(k=>`<p style="margin:6px 0"><b style="font-family:var(--serif);font-size:18px;margin-right:8px">${k}</b>${az[k].map(a=>`<a class="wl" href="#familypedia/${encodeURIComponent(a.slug)}">${esc(a.title)}</a>`).join(' · ')}</p>`).join('')}</div>`;
}
function wikiLink(text){
  // [[wiki-links]] laid over the text: known article titles become links. Never rewrites the words.
  if(!S.wiki) return esc(text);
  let html = esc(text);
  const titles = S.wiki.filter(a=>a.type!=='event').map(a=>a.title).sort((a,b)=>b.length-a.length);
  const seen = new Set();
  titles.forEach(t=>{ const k=esc(t.split(',')[0]); if(k.length<4 || seen.has(k)) return; seen.add(k);
    const a=S.wiki.find(x=>x.title===t);
    html = html.replace(new RegExp('(^|[^\\w>])('+k.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')(?![\\w<])'), `$1<a class="wl" href="#familypedia/${encodeURIComponent(a.slug)}">$2</a>`); });
  return html;
}
async function openArticle(slug){
  if(!S.wiki){ return; }
  const a = await api('/api/engine/article?slug='+encodeURIComponent(slug));
  if(a.error){ $('#wk-article').innerHTML=`<div class="card"><p class="empty">${esc(a.error)}</p></div>`; return; }
  S.article = a; drawWikiList();
  const tierLabels = {witnessed:'What was witnessed', told:'What was told', lore:'Family lore', documented:'What the records show'};
  const chip = c => c ? `<a class="cite" data-cite="${esc(c)}">${esc(c)}</a>` : '';
  $('#wk-article').innerHTML = `<article class="card article">
    <aside class="infobox"><div class="ph">${esc(a.title[0])}</div>
      <dl class="kv"><dt>type</dt><dd>${esc(a.type)}</dd><dt>dates</dt><dd>${esc(a.infobox.dates)}</dd>
      ${a.infobox.places.length?`<dt>places</dt><dd>${a.infobox.places.map(p=>wikiLink(p)).join('<br>')}</dd>`:''}
      ${a.infobox_extra?`<dt>date</dt><dd>${esc(a.infobox_extra.date)}${a.infobox_extra.precision?` <span class="derived">${esc(a.infobox_extra.precision)}</span>`:''}</dd>
        ${a.infobox_extra.place?`<dt>place</dt><dd>${wikiLink(a.infobox_extra.place)}</dd>`:''}
        ${a.infobox_extra.people.length?`<dt>people</dt><dd>${a.infobox_extra.people.map(x=>wikiLink(x)).join('<br>')}</dd>`:''}
        <dt>kind</dt><dd>${esc(a.infobox_extra.type)}</dd>`:''}
      ${a.event?`<dt>tier</dt><dd><span class="tierdot t-${esc(a.event.tier)}"></span>${esc(a.event.tier)}${a.event.confidence?' · '+esc(a.event.confidence)+' confidence':''}</dd>`:''}
      <dt>material</dt><dd>${a.units.length} unit${a.units.length!==1?'s':''} · ${a.events.length} event${a.events.length!==1?'s':''} · ${a.mentions.length} mention${a.mentions.length!==1?'s':''}</dd></dl>
      <p class="derived" style="margin:10px 0 0">No generated faces, ever. A photo appears here once one is tagged.</p></aside>
    <div class="kicker">${esc(a.type)}${a.stub?' · stub':''}</div><h2>${esc(a.title)}</h2>
    <p class="${a.lead_by==='me'?'mine':''}" id="wk-lead">${wikiLink(a.lead)} <span class="derived">${a.lead_by==='me'?'written by me':'derived'}</span> <button class="btn ghost sm" id="wk-edit">Edit</button></p>
    ${a.event?`<div class="row" style="gap:6px;margin:6px 0 4px"><a class="chiplink" href="#timeline?focus=${encodeURIComponent(a.event.id)}">On the timeline</a>${a.event.story_id?`<a class="chiplink" href="#stories?read=${encodeURIComponent(a.event.story_id)}">${esc(a.event.story)}</a>`:''}</div>`:''}
    ${a.type==='person'?`<div class="row" style="gap:6px;margin:6px 0 4px"><a class="chiplink" href="#genealogy?focus=${encodeURIComponent(a.slug)}">In the tree</a><a class="chiplink" href="#timeline?person=${encodeURIComponent(a.title)}">On the timeline</a></div>`:''}
    ${(a.conflicts||[]).length?`<div class="note" style="margin:10px 0;background:#FFFBF1;border:1px solid #E3D2AB"><b>The sources disagree.</b> ${a.conflicts.map(c=>esc(c)).join(' · ')} <span class="derived">both versions are kept</span></div>`:''}
    ${(a.passages||[]).length?`<div class="tier"><h4>The passages this rests on</h4>${a.passages.map(x=>`<p class="quote">“${wikiLink(x.text)}”<br><span style="font-family:var(--sans);font-size:12.5px;color:var(--ink-3)">${esc(x.speaker||'')}</span>${chip(x.cite)}</p>`).join('')}</div>`:''}
    ${(a.before||[]).length||(a.after||[]).length?`<div class="tier grid two" style="margin-top:12px"><div><h4>Before</h4>${(a.before||[]).map(e=>`<p style="margin:3px 0">${e.slug?`<a class="wl" href="#familypedia/${encodeURIComponent(e.slug)}">${esc(e.title)}</a>`:esc(e.title)} <span style="color:var(--ink-3)">${esc(e.date)}</span></p>`).join('')||'<p class="empty" style="padding:0">nothing earlier</p>'}</div>
      <div><h4>After</h4>${(a.after||[]).map(e=>`<p style="margin:3px 0">${e.slug?`<a class="wl" href="#familypedia/${encodeURIComponent(e.slug)}">${esc(e.title)}</a>`:esc(e.title)} <span style="color:var(--ink-3)">${esc(e.date)}</span></p>`).join('')||'<p class="empty" style="padding:0">nothing later</p>'}</div></div>`:''}
    ${Object.entries(a.tiers).filter(([,v])=>v.length).map(([k,v])=>`<div class="tier"><h4>${tierLabels[k]}</h4>${v.map(i=>`<p style="margin:3px 0">${wikiLink(i.text)} <span style="color:var(--ink-3)">${esc(i.date)}</span>${(i.cite||'').split(/;\s*/).map(chip).join('')}</p>`).join('')}</div>`).join('')}
    ${a.mentions.length?`<div class="tier"><h4>In their words · ${a.mentions.length} mention${a.mentions.length!==1?'s':''}</h4>${a.mentions.map(m=>`<p class="quote">“${wikiLink(m.text)}”<br><span style="font-family:var(--sans);font-size:12.5px;color:var(--ink-3)">${esc(m.speaker)}</span>${chip(m.cite)}</p>`).join('')}</div>`:''}
    ${a.stories.length?`<div class="tier"><h4>${esc(L.storiesAbout)} ${esc(a.title)}</h4>${a.stories.map(s=>`<a class="wl" href="#stories?read=${encodeURIComponent(s.id)}">${esc(s.title)}</a>`).join(' · ')}</div>`:''}
    <div class="tier"><h4>Notes <span class="derived">stated by me</span></h4><textarea id="wk-notes" rows="3" placeholder="What you know that the recordings don't say. Your notes outrank anything derived.">${esc(a.notes)}</textarea>
      <div class="row" style="margin-top:6px"><button class="btn ghost sm" id="wk-notes-save">Save notes</button></div></div>
    ${a.open_questions.length?`<div class="tier"><div class="row"><h4>Open questions</h4><span class="spacer"></span>${a.type==='person'?`<button class="btn ghost sm" id="wk-ask">Ask for more about ${esc(a.title)}</button>`:''}</div><ul>${a.open_questions.map(q=>`<li>${esc(q)}</li>`).join('')}</ul></div>`:''}
    ${a.backlinks.length?`<div class="tier"><h4>What links here</h4>${a.backlinks.map(b=>wikiLink(b)).join(' · ')}</div>`:''}
    <details class="tier" style="margin-top:18px"><summary style="cursor:pointer;font-weight:600">Beyond the family</summary>
      <p class="sub" style="margin-top:6px">Public background (encyclopedias, with link and retrieval date) is kept apart from family knowledge and is off by default for private individuals. <span class="pill">not wired up yet</span></p></details>
  </article>`;
  $$('#wk-article [data-cite]').forEach(c=>c.onclick=e=>{ e.preventDefault(); openCitation(c.dataset.cite); });
  const ask=$('#wk-ask'); if(ask) ask.onclick=()=>draftRequest({kind:'person', about:a.slug});
  $('#wk-notes-save').onclick=async()=>{ await api('/api/engine/article',{method:'POST',body:{slug:a.slug, notes:$('#wk-notes').value}}); alertNote('Notes saved, marked as yours.'); };
  $('#wk-edit').onclick=()=>{ const p=$('#wk-lead'); p.innerHTML=`<textarea id="wk-lead-in" rows="3">${esc(a.lead)}</textarea><div class="row" style="margin-top:6px"><button class="btn sm" id="wk-lead-save">Save</button></div>`;
    $('#wk-lead-save').onclick=async()=>{ await api('/api/engine/article',{method:'POST',body:{slug:a.slug, lead:$('#wk-lead-in').value}}); openArticle(a.slug); }; };
  window.scrollTo(0,0);
}

