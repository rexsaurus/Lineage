/* ================================================================== HOME
   Answers "what is in here, and what should I do next". It surfaces what the project already
   holds; it never writes prose of its own. An empty project gets one card: what to add first. */
S.home = {story:0, relative:0, allNeeds:false};
BUILDERS.home = async function(el){
  el.innerHTML = '<p class="empty">Loading…</p>';
  const h = await api(`/api/engine/home?story=${S.home.story}&relative=${S.home.relative}`);
  S.homeData = h;
  if(h.empty){
    el.innerHTML = `<div class="card" style="max-width:720px;margin:40px auto">
      <div class="kicker">${esc(S.data.identity.display_title)}</div><h2>Start with one thing</h2>
      <p class="lede">This project has nothing in it yet. Add a recording, a letter, a photograph or a document, and Lineage reads it, names it and indexes it.
        Stories, the Familypedia, the tree and the timeline grow from what you add.</p>
      <div class="row" style="margin-top:18px"><a class="btn go" href="#sources" style="text-decoration:none">Add a first source</a>
        <a class="btn ghost" href="#/settings/family" style="text-decoration:none">Name this lineage</a>
        <a class="btn ghost" href="#/settings/connectors" style="text-decoration:none">Connect a model</a></div></div>`;
    return;
  }
  el.innerHTML = `<div class="row" style="margin-bottom:16px"><div><div class="kicker">${esc(S.data.identity.family_name||'Home')}</div>
      <h2 style="margin:0">${esc(S.data.identity.display_title)}</h2></div><span class="spacer"></span>
      <span class="pill" title="${esc(h.updated||'')}">${h.updated?'Last updated '+esc(ago(h.updated)):'Nothing recorded yet'}</span></div>
    <div class="homegrid">
      <div class="card" id="h-story"></div>
      <div class="card" id="h-rel"></div>
      <div class="card" id="h-needs"></div>
      <div class="card" id="h-ask"></div>
      <div class="card" id="h-glance" style="grid-column:1/-1"></div>
      <div class="card" id="h-feed" style="grid-column:1/-1"></div>
    </div>`;
  drawHomeStory(h); drawHomeRelative(h); drawNeeds(h); drawAsk(h); drawGlance(h); drawFeed(h);
};
function drawHomeStory(h){
  const box=$('#h-story'), s=h.story;
  if(!s){ box.innerHTML = `<div class="kicker">Story of the day</div><p class="empty">No ${L.stories} drafted yet. ${L.Stories} come from transcribed recordings: add one in <a href="#sources">Sources</a>, then ask the Genealogist (Terminal) to propose the ${L.storyMap.toLowerCase()}.</p>`; return; }
  box.innerHTML = `<div class="row"><div class="kicker">Story of the day</div><span class="spacer"></span>
      ${s.of>1?`<button class="btn ghost sm" id="h-reroll" title="Another story">Another</button>`:''}</div>
    <div class="hero">${s.photo?`<img src="${fileUrl(s.photo)}" alt="">`:`<div class="ph">${esc(s.title[0])}</div>`}
      <div><h3>${esc(s.title)}</h3><div class="meta" style="color:var(--ink-3);font-size:13px">${esc(s.dates||'undated')} · ${s.reading_minutes} min read</div>
        <p class="open">${esc(s.opening)}</p>
        <div class="row"><a class="btn" href="#stories?read=${encodeURIComponent(s.id)}" style="text-decoration:none">Read</a>
          ${s.has_audio?`<button class="btn ghost" id="h-listen">Listen</button>`:`<a class="btn ghost" href="#stories?listen=${encodeURIComponent(s.id)}" style="text-decoration:none" title="No narration yet">Narrate…</a>`}</div></div></div>`;
  const r=$('#h-reroll'); if(r) r.onclick=async()=>{ S.home.story++; const n=await api(`/api/engine/home?story=${S.home.story}&relative=${S.home.relative}`); drawHomeStory(n); };
  const l=$('#h-listen'); if(l) l.onclick=()=>play({id:s.id, title:s.title, audio:s.audio});
}
function drawHomeRelative(h){
  const box=$('#h-rel'), p=h.relative;
  if(!p){ box.innerHTML = `<div class="kicker">Featured relative</div><p class="empty">No one in the Cast yet. People appear as sources are read.</p>`; return; }
  const subj = S.data.identity.subject_short || S.data.identity.subject || 'the subject';
  box.innerHTML = `<div class="row"><div class="kicker">Featured relative</div><span class="spacer"></span><button class="btn ghost sm" id="h-rel-next">Another</button></div>
    <div class="row" style="align-items:flex-start;gap:14px;margin-top:6px">${p.photo?`<img class="portrait" src="${fileUrl(p.photo)}" alt="">`:`<div class="portrait">${esc((p.name||'?')[0])}</div>`}
      <div style="flex:1;min-width:0"><h3 style="font-family:var(--serif);font-size:21px;margin:0">${esc(p.name)}</h3>
        <div style="font-size:13px;color:var(--ink-3)">${esc(p.dates||'dates unknown')} · ${p.relationship?esc(p.relationship)+' of '+esc(subj):'not yet traced to '+esc(subj)+' in the tree'}</div></div></div>
    ${p.line?`<p style="font-size:14px;margin:10px 0">${esc(p.line)}</p>`:''}
    <div class="row" style="gap:6px;margin:8px 0"><span class="pill">${p.counts.sources} source${p.counts.sources!==1?'s':''}</span><span class="pill">${p.counts.mentions} mention${p.counts.mentions!==1?'s':''}</span><span class="pill">${p.counts.photographs} photograph${p.counts.photographs!==1?'s':''}</span>
      ${p.nudge?`<span class="pill warn">no ${L.story} yet</span>`:''}</div>
    <div class="row">${p.article?`<a class="btn ghost sm" href="#familypedia/${encodeURIComponent(p.article)}" style="text-decoration:none">Familypedia</a>`:''}
      <a class="btn ghost sm" href="#genealogy?focus=${encodeURIComponent(p.id)}" style="text-decoration:none">In the tree</a>
      ${p.article?`<button class="btn ghost sm" id="h-rel-ask">Ask for more</button>`:''}</div>`;
  $('#h-rel-next').onclick=async()=>{ S.home.relative++; const n=await api(`/api/engine/home?story=${S.home.story}&relative=${S.home.relative}`); drawHomeRelative(n); };
  const a=$('#h-rel-ask'); if(a) a.onclick=()=>draftRequest({kind:'person', about:p.article});
}
function drawNeeds(h){
  const box=$('#h-needs'), items=h.needs, cap=S.home.allNeeds?items.length:6;
  box.innerHTML = `<div class="row"><h3>Needs you</h3><span class="spacer"></span>${items.length?`<span class="pill">${items.length}</span>`:''}</div>
    <p class="sub">One click each, ordered by what unblocks the most.</p>
    ${items.length?items.slice(0,cap).map((n,i)=>`<div class="need"><span>${esc(n.text)}</span><button class="btn sm" data-need="${i}">${esc(n.action)}</button></div>`).join('')
      :'<p class="empty">Nothing is waiting on you.</p>'}
    ${items.length>6?`<button class="btn ghost sm" id="h-needs-all" style="margin-top:8px">${S.home.allNeeds?'Show fewer':'Show all '+items.length}</button>`:''}`;
  $$('[data-need]',box).forEach(b=>b.onclick=async()=>{ const n=items[+b.dataset.need];
    if(n.op==='ingest-all'){ const r=await api('/api/engine/source/scan-all',{method:'POST'}); alertNote(r.started?`Ingesting ${r.started} file(s).`:'Everything is already ingested.'); location.hash='#sources'; return; }
    if(n.op==='question'){ await api('/api/engine/question',{method:'POST',body:{text:n.question, source:n.source}}); alertNote('Added to the question list.'); BUILDERS.home($('#tab-home')); return; }
    if(n.go) location.hash=n.go; });
  const all=$('#h-needs-all'); if(all) all.onclick=()=>{ S.home.allNeeds=!S.home.allNeeds; drawNeeds(h); };
}
/* ------------------------------------------------------------------ requests: asking for more */
function drawAsk(h){
  const box=$('#h-ask');
  const people=(S.wikiPeople||[]);
  box.innerHTML = `<h3>Request more</h3><p class="sub">Builds a question list from what the project already flags as open. Nothing is sent without you.</p>
    <label>Ask for more about…</label><div class="row" style="margin-bottom:10px"><select id="ask-person" style="flex:1"><option value="">choose a relative</option></select><button class="btn sm" id="ask-person-go">Draft</button></div>
    <div class="row" style="margin-bottom:10px"><button class="btn ghost sm" id="ask-source" style="flex:1">Ask for a missing source</button></div>
    ${h.members.length?`<label>Ask a ${L.contributor}</label><div class="row"><select id="ask-to" style="flex:1">${h.members.map(m=>`<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('')}</select>
      <select id="ask-what" style="flex:1"><option value="source">for missing sources</option></select><button class="btn sm" id="ask-to-go">Draft</button></div>`
      :`<p class="sub" style="font-size:12.6px">Add ${L.contributors} in <a href="#/settings/contributors">Settings → Contributors</a> to address a request to someone.</p>`}
    <div id="ask-list" style="margin-top:12px"></div>`;
  api('/api/engine/familypedia').then(r=>{ S.wiki=S.wiki||r.articles; const ppl=r.articles.filter(a=>a.type==='person');
    $('#ask-person').insertAdjacentHTML('beforeend', ppl.map(a=>`<option value="${esc(a.slug)}">${esc(a.title)}</option>`).join(''));
    const w=$('#ask-what'); if(w) w.insertAdjacentHTML('beforeend', ppl.map(a=>`<option value="${esc(a.slug)}">about ${esc(a.title)}</option>`).join('')); });
  $('#ask-person-go').onclick=()=>{ const v=$('#ask-person').value; if(!v){ alertNote('Choose a relative first.'); return; } draftRequest({kind:'person', about:v}); };
  $('#ask-source').onclick=()=>draftRequest({kind:'source'});
  const tg=$('#ask-to-go'); if(tg) tg.onclick=()=>{ const w=$('#ask-what').value; draftRequest(w==='source'?{kind:'source', to:$('#ask-to').value}:{kind:'person', about:w, to:$('#ask-to').value}); };
  drawRequests(h.requests);
}
function drawRequests(reqs){
  const box=$('#ask-list'); if(!box) return;
  const open=reqs.filter(r=>r.status==='asked');
  box.innerHTML = open.length ? `<h4 style="margin:0 0 4px;font-size:13px">Outstanding</h4>${open.map(r=>`<div class="need" style="font-size:13.2px"><span>You asked ${esc(r.to_name||'(not addressed)')} ${r.about?'about '+esc(r.about.replace(/-/g,' ')):'for '+esc(r.title.toLowerCase())} ${esc(ago(r.made))}</span>
      <button class="btn ghost sm" data-answered="${esc(r.id)}">Answered</button></div>`).join('')}` : '';
  $$('[data-answered]',box).forEach(b=>b.onclick=async()=>{ const all=await api('/api/engine/request/mark',{method:'POST',body:{id:b.dataset.answered, status:'answered'}}); drawRequests(all); });
}
async function draftRequest(spec){
  const d = await api('/api/engine/request/draft',{method:'POST',body:spec});
  if(d.error){ alertNote(d.error); return; }
  const intro = d.to_name ? `Hi ${d.to_name},\n\nFor the family record, could you help with any of these?\n\n` : 'For the family record, could you help with any of these?\n\n';
  const text = intro + (d.questions.length ? d.questions.map((q,i)=>`${i+1}. ${q}`).join('\n') : '(nothing is flagged as open here yet)') + '\n\nAnything at all helps: a sentence, a photo, a name.\n';
  openModal(d.title + (d.to_name?` · to ${d.to_name}`:''), `
    <p class="sub">Assembled from open questions, timeline gaps, unconfirmed links and missing photographs. Edit before you send it.</p>
    <textarea id="rq-text" rows="${Math.min(22, d.questions.length+8)}" style="font-size:14px;line-height:1.5">${esc(text)}</textarea>
    <div class="row" style="margin-top:12px"><button class="btn" id="rq-copy">Copy</button>
      ${d.to_email?`<a class="btn ghost" id="rq-mail" style="text-decoration:none">Open in email</a>`:`<a class="btn ghost" id="rq-mail" style="text-decoration:none">Open in email</a>`}
      <span class="spacer"></span><button class="btn go" id="rq-save">Save as asked</button></div>
    <p class="sub" style="margin-top:8px;font-size:12.4px">"Save as asked" records it with today's date${d.to_name?` on ${esc(d.to_name)}'s page`:''}, so Home can remind you what's outstanding. Lineage never sends it for you.</p>`);
  const mail=()=>`mailto:${encodeURIComponent(d.to_email||'')}?subject=${encodeURIComponent(d.title+' — for the family record')}&body=${encodeURIComponent($('#rq-text').value)}`;
  $('#rq-mail').onclick=e=>{ e.currentTarget.href=mail(); };
  $('#rq-copy').onclick=()=>copyText($('#rq-text').value);
  $('#rq-save').onclick=async()=>{ await api('/api/engine/request/save',{method:'POST',body:{...d, text:$('#rq-text').value}}); closeOverlay(); alertNote('Saved as asked.'); if(S.tab==='home') BUILDERS.home($('#tab-home')); };
}
function drawGlance(h){
  const g=h.glance, n=v=>(v??0).toLocaleString();
  const tiles=[[g.sources,'sources','#sources'],[g.people,'people','#genealogy?view=cast'],[g.stories,L.stories,'#stories'],[g.photographs,'photographs','#sources?kind=image'],
    [g.records,'records','#familypedia'],[g.events,'timeline events','#timeline'],[g.words,'words written','#stories'],[g.audio_minutes,'audio minutes','#stories?filter=audio']];
  $('#h-glance').innerHTML = `<div class="row"><h3>The lineage at a glance</h3><span class="spacer"></span>
      ${g.range?`<span class="pill">covers ${g.range[0]}–${g.range[1]}</span>`:''}${g.pages?`<a class="pill" href="${fileUrl('output/book-draft.pdf')}" target="_blank" rel="noopener">draft · ${g.pages} pages</a>`:'<span class="pill">no draft built yet</span>'}</div>
    <div class="glance" style="margin-top:10px">${tiles.map(([v,l,href])=>`<a href="${href}"><b>${n(v)}</b><span>${esc(l)}</span></a>`).join('')}</div>`;
}
function drawFeed(h){
  $('#h-feed').innerHTML = `<h3>Recently</h3><ul class="feed" style="margin-top:8px">${h.activity.length?h.activity.map(a=>`<li><time datetime="${esc(a.at)}" title="${esc(a.at)}">${esc(ago(a.at))}</time><a href="${esc(a.go||'#home')}">${esc(a.text)}</a>${a.by&&a.by!=='me'?`<span class="derived" style="margin-left:auto">${esc(a.by)}</span>`:''}</li>`).join('')
    :'<li><span class="empty" style="padding:0">Nothing yet.</span></li>'}</ul>`;
}
