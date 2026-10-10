/* ================================================================== STORIES
   Every story, oldest first, readable and listenable from the same row. The files are chapters/
   on disk; people see stories. Narration never reads an unapproved bridge. */
function eraOf(y){ if(y==null) return 'Not yet dated'; if(y<1900) return 'Before 1900'; return (Math.floor(y/10)*10)+'s'; }
BUILDERS.stories = async function(el, rest, q={}){
  el.innerHTML='';
  head(el,{kicker:L.Stories, title:`The ${L.stories}`, lede:`Every ${L.story}, oldest first. Read it as book pages or listen to it; ${L.stories} in the book also show where they sit as chapters.`});
  el.insertAdjacentHTML('beforeend', `<div class="card"><div class="row">
      <select id="rd-order" style="max-width:200px" aria-label="Order"><option value="chrono">Chronological</option><option value="book">Book order</option><option value="recent">Recently written</option><option value="longest">Longest</option></select>
      <select id="rd-state" style="max-width:180px" aria-label="State"><option value="">Every state</option>${Object.values(L.states).map(s=>`<option>${esc(s)}</option>`).join('')}</select>
      <select id="rd-filter" style="max-width:220px" aria-label="Filter"><option value="">No filter</option><option value="bridges">Has bridges to approve</option><option value="stale">Stale since a source changed</option><option value="audio">Has audio</option><option value="noaudio">No audio yet</option><option value="audiostale">Audio is stale</option></select>
      <span class="spacer"></span>
      <button class="btn ghost sm" id="rd-narrate-all">Narrate all…</button>
      <a class="btn ghost sm" id="rd-zip" href="${tokUrl('/api/engine/audio.zip')}">Download audio</a>
      <a class="btn ghost sm" id="rd-pdf" target="_blank" rel="noopener" href="${fileUrl('output/book-draft.pdf')}">Draft PDF</a></div>
      <div class="row" style="margin-top:10px"><span class="sub" style="margin:0" id="rd-voice-line"></span><span class="spacer"></span>
        <button class="btn sm" id="rd-generate">${esc(L.generateRemaining)}</button></div></div>
    <div id="rd-list"><p class="empty">Loading…</p></div>`);
  if(q.filter) $('#rd-filter').value = q.filter==='bridges'?'bridges':(q.filter==='stale'?'stale':(q.filter==='audio'?'audio':''));
  const [r, v] = await Promise.all([api('/api/engine/stories'), api('/api/voices')]);
  S.stories = r.stories; S.voices = v.voices || [];
  $('#rd-voice-line').innerHTML = S.voices.length ? `Narrator: <b>${esc(settings().voice_name||'not chosen')}</b> · change it in <a href="#/settings/project">Project settings</a>, or per ${L.story} below.` : `Narration needs an ElevenLabs key in <a href="#/settings/connectors">Settings → Connectors</a>.`;
  ['rd-order','rd-state','rd-filter'].forEach(id=>$('#'+id).oninput=drawStories);
  $('#rd-narrate-all').onclick=narrateAll;
  $('#rd-generate').onclick=generateRemaining;
  drawStories();
  if(q.read) readStory(q.read);
  if(q.listen){ const s=S.stories.find(x=>x.id===String(q.listen)); if(s && s.has_audio) play(s); else if(s) narrate(s.id); }
};
async function reloadStories(){ const r=await api('/api/engine/stories'); S.stories=r.stories; drawStories(); }
function drawStories(){
  let list = S.stories.slice();
  const st=$('#rd-state').value, f=$('#rd-filter').value, order=$('#rd-order').value;
  if(st) list=list.filter(s=>s.state===st);
  const filters={bridges:s=>s.bridges>0, stale:s=>!!s.stale, audio:s=>s.has_audio, noaudio:s=>s.exists&&!s.has_audio, audiostale:s=>s.has_audio&&s.audio_stale};
  if(f) list=list.filter(filters[f]);
  const sorters={chrono:(a,b)=>(a.year??1e9)-(b.year??1e9), book:(a,b)=>(+a.id)-(+b.id), recent:(a,b)=>(b.mtime||0)-(a.mtime||0), longest:(a,b)=>b.words-a.words};
  list.sort(sorters[order]);
  if(!list.length){ $('#rd-list').innerHTML=`<div class="card"><p class="empty">${esc(S.stories.length?'Nothing matches these filters.':L.noStories)}</p></div>`; return; }
  const voices = S.voices.map(v=>[v.voice_id, v.name]);
  let era=null, html='';
  list.forEach(s=>{
    const e = order==='chrono' ? eraOf(s.year) : null;
    if(e && e!==era){ html+=`<div class="era">${esc(e)}</div>`; era=e; }
    const audioPill = s.has_audio ? `<span class="pill ${s.audio_stale?'warn':'ok'}" title="${esc(s.audio_voice||'')} · ${esc((s.audio_made||'').slice(0,10))}">${s.audio_stale?'audio is stale':'audio · '+fmtDur(s.audio_duration)}</span>` : '';
    html+=`<div class="story${S.playing===s.id?' playing':''}" data-id="${esc(s.id)}">${s.photo?`<img class="mark mark-photo" src="${fileUrl(s.photo)}" alt="" loading="lazy">`:''}
      <div><h4>${esc(s.title)}</h4><div class="meta">${esc(s.dates||'undated')}${s.summary?' · '+esc(s.summary):''}</div>
        <div class="chipsrow">${s.exists?`<span class="pill">${s.words.toLocaleString()} words</span><span class="pill">${s.reading_minutes} min read</span>`:'<span class="pill warn">no draft yet</span>'}
        ${s.stale?`<span class="pill bad" title="${esc(s.stale.reason)}">stale</span>`:''}${s.photos?`<span class="pill">${s.photos} photo${s.photos!==1?'s':''}</span>`:''}${s.bridges?`<span class="pill warn">${s.bridges} bridge${s.bridges!==1?'s':''} to approve</span>`:''}
        ${audioPill}<span class="pill ${s.state==='in the book'?'ok':''}">${esc(s.state==='in the book'?s.book_position.replace('Chapter',L.bookChapter):L.states[s.state])}</span></div></div>
      <div class="actions">
        ${s.exists?`<button class="btn sm" data-read="${esc(s.id)}">Read</button>`:`<button class="btn sm" data-gen="${esc(s.id)}">Generate</button>`}
        ${s.has_audio?`<button class="btn ghost sm" data-listen="${esc(s.id)}">Listen</button>`:''}
        ${s.exists?`<button class="btn ghost sm" data-narrate="${esc(s.id)}" ${s.bridges?`title="Approve ${s.bridges} bridge(s) first: an unapproved bridge is never narrated"`:''}>${s.has_audio?'Re-narrate':'Narrate'}</button>`:''}
        ${s.exists&&voices.length?`<select data-voice="${esc(s.id)}" aria-label="Voice for this ${L.story}"><option value="">default voice</option>${options(voices, s.voice_override||'')}</select>`:''}
        <select data-state="${esc(s.id)}" aria-label="State">${Object.entries(L.states).map(([v,l])=>`<option value="${esc(v)}" ${s.state===v?'selected':''}>${esc(l)}</option>`).join('')}</select></div></div>`;
  });
  $('#rd-list').innerHTML = `<div class="card" style="padding:4px 22px">${html}</div>`;
  $$('[data-read]').forEach(b=>b.onclick=()=>readStory(b.dataset.read));
  $$('[data-listen]').forEach(b=>b.onclick=()=>play(S.stories.find(s=>s.id===b.dataset.listen)));
  $$('[data-narrate]').forEach(b=>b.onclick=()=>narrate(b.dataset.narrate, b));
  $$('[data-gen]').forEach(b=>b.onclick=()=>generateOne(b.dataset.gen));
  $$('[data-voice]').forEach(sel=>sel.onchange=async()=>{ await api('/api/engine/story/voice',{method:'POST',body:{id:sel.dataset.voice, voice_id:sel.value}}); alertNote(sel.value?'This '+L.story+' will use its own voice next time it is narrated.':'Back to the default voice.'); });
  $$('[data-state]').forEach(sel=>sel.onchange=async()=>{ await api('/api/engine/story/state',{method:'POST',body:{id:sel.dataset.state, state:sel.value}}); reloadStories(); });
}
async function narrate(id, btn){
  const s=S.stories.find(x=>x.id===String(id));
  const r=await api('/api/engine/story/narrate',{method:'POST',body:{id}});
  if(r.blocked){ alertNote(r.blocked); return; }
  if(r.error){ alertNote(r.error); return; }
  if(btn){ btn.disabled=true; btn.textContent='recording…'; }
  pollJob(r.job, st=>{ if(btn) btn.textContent=st.length>24?'recording…':st; },
    async res=>{ alertNote(`Narrated: ${s.title} (${fmtDur(res.duration)}).`); await reloadStories(); play(S.stories.find(x=>x.id===String(id))); },
    err=>{ if(btn){ btn.disabled=false; btn.textContent='Narrate'; } alertNote(err); });
}
async function narrateAll(){
  const todo=S.stories.filter(s=>s.exists && (!s.has_audio || s.audio_stale));
  if(!todo.length){ alertNote('Every drafted '+L.story+' already has current audio.'); return; }
  openModal('Narrate all', '<p class="empty">Counting characters…</p>');
  const rows=[]; for(const s of todo){ const r=await api('/api/engine/story/script?id='+encodeURIComponent(s.id)); rows.push({s, chars:r.chars||0, blocked:r.blocked}); }
  const ok=rows.filter(x=>!x.blocked), chars=ok.reduce((a,x)=>a+x.chars,0);
  $('.modal .body').innerHTML = `<p>${ok.length} ${ok.length===1?L.story:L.stories} to record · <b>${chars.toLocaleString()} characters</b>.</p>
    <p class="sub">ElevenLabs bills ${esc('eleven_multilingual_v2')} at about one credit per character, so this is roughly ${chars.toLocaleString()} credits. Check your plan for what a credit costs you.</p>
    ${rows.filter(x=>x.blocked).length?`<div class="note" style="margin-bottom:12px">Skipped, bridges not yet approved: ${rows.filter(x=>x.blocked).map(x=>esc(x.s.title)).join(', ')}</div>`:''}
    <ul>${ok.map(x=>`<li>${esc(x.s.title)} · ${x.chars.toLocaleString()} chars${x.s.audio_stale?' · replaces stale audio':''}</li>`).join('')}</ul>
    <div class="row" style="margin-top:12px"><button class="btn go" id="na-go" ${ok.length?'':'disabled'}>Record ${ok.length}</button><span id="na-step" class="sub" style="margin:0"></span></div>`;
  $('#na-go').onclick=async()=>{ $('#na-go').disabled=true;
    for(const [i,x] of ok.entries()){ $('#na-step').textContent=`${i+1} of ${ok.length}: ${x.s.title}`;
      const r=await api('/api/engine/story/narrate',{method:'POST',body:{id:x.s.id}});
      if(r.job) await pollJob(r.job); else if(r.error){ $('#na-step').textContent=r.error; return; } }
    $('#na-step').textContent='Done.'; reloadStories(); };
}
function generateRemaining(){
  const missing=S.stories.filter(s=>!s.exists);
  const prompt = missing.length
    ? `Using the Lineage skills, generate the ${L.stories} that have no draft yet, one at a time, following the approved story map and the style guide. Hold every bridge for my approval. Missing: ${missing.map(s=>`${s.id} "${s.title}"`).join('; ')}.`
    : `Using the Lineage skills, check the story map for ${L.stories} that still need drafting and tell me what's left. Don't write anything yet.`;
  sendToTerminal(prompt); alertNote('Handed to the Genealogist in the terminal.');
}
function generateOne(id){
  const s=S.stories.find(x=>x.id===String(id));
  sendToTerminal(`Using the Lineage skills, generate ${L.story} ${s.id} "${s.title}" only, from its units in the approved story map, following the style guide. Hold every bridge for my approval, then tell me when it's ready to preview.`);
  alertNote('Handed to the Genealogist in the terminal.');
}
/* What a story rests on: each paragraph's citation chips, and each image with its provenance and a toolbar. */
function citeChip(c){
  if(/^\[S\d+ /.test(c)) return `<a class="cite" data-cite="${esc(c)}" title="Open the recording here">${esc(c)}</a>`;
  if(/^R\d+$/.test(c)) return `<a class="cite rec" href="#familypedia?view=records&focus=${encodeURIComponent(c)}" onclick="closeOverlay()" title="Open the record">${esc(c)}</a>`;
  if(/^https?:/.test(c)) return `<a class="cite" href="${esc(c)}" target="_blank" rel="noopener">source ↗</a>`;
  return `<span class="cite plain">${esc(c)}</span>`;
}
function storyApparatusHtml(ap){
  const n=ap.paragraphs.length, ni=ap.images.length;
  return `<div class="apparatus"><div class="row ap-tabs" role="tablist"><button class="btn ghost sm" data-ap="cites" aria-pressed="true">Citations · ${n}</button><button class="btn ghost sm" data-ap="images" aria-pressed="false">Images · ${ni}</button><span class="spacer"></span><span class="derived">every paragraph, and where it comes from</span></div>
    <div class="ap-pane" data-pane="cites">${ap.paragraphs.map((p,i)=>`<div class="ap-cite"><span class="ap-n">¶${i+1}</span><span class="ap-x">${esc(p.excerpt)||'<span class="derived">(no text)</span>'}</span><span class="ap-chips">${p.cites.map(citeChip).join('')}${p.note?`<span class="cite plain" title="cited as written">${esc(p.note)}</span>`:''}${!p.cites.length&&!p.note?'<span class="pill bad">no citation</span>':''}</span></div>`).join('')||'<p class="empty">No cited paragraphs.</p>'}</div>
    <div class="ap-pane hidden" data-pane="images">${ap.images.map((m,i)=>`<div class="ap-img">${m.exists?`<img src="${fileUrl(m.path)}" alt="">`:''}
      <div><b>${esc(m.caption)}</b> ${m.illustration?'<span class="pill warn" title="Generated or drawn: never presented as a photograph">illustration</span>':''}${m.placeholder?' <span class="pill">placeholder</span>':''}
        <div class="derived" style="margin:3px 0">${[m.id, m.date&&('date: '+m.date+(m.date_basis?' ('+m.date_basis+')':'')), m.people&&('people: '+m.people+(m.people_basis?' ('+m.people_basis+')':'')), m.location&&('place: '+m.location), m.holder&&('held by '+m.holder)].filter(Boolean).map(esc).join(' · ')||'no provenance recorded'}</div>
        <div class="row ap-tools" role="toolbar" aria-label="Image tools"><a class="btn ghost sm" href="${fileUrl(m.path)}" target="_blank" rel="noopener">Open</a>${m.id?`<button class="btn ghost sm" data-imgtag="${esc(m.id)}">Tag…</button>`:''}<button class="btn ghost sm" data-imgcopy="${esc(m.path)}">Copy reference</button>${m.id?`<a class="btn ghost sm" href="#familypedia?view=photos" onclick="closeOverlay()">In Photographs</a>`:''}</div></div></div>`).join('')||'<p class="empty">No images in this story.</p>'}</div></div>`;
}
function bindStoryApparatus(ap){
  $$('.apparatus [data-ap]').forEach(b=>b.onclick=()=>{ $$('.apparatus [data-ap]').forEach(x=>x.setAttribute('aria-pressed', String(x===b))); $$('.apparatus .ap-pane').forEach(p=>p.classList.toggle('hidden', p.dataset.pane!==b.dataset.ap)); });
  $$('.apparatus [data-cite]').forEach(c=>c.onclick=e=>{ e.preventDefault(); closeOverlay(); openCitation(c.dataset.cite); });
  $$('.apparatus [data-imgtag]').forEach(b=>b.onclick=()=>openTagPanel('photo:'+b.dataset.imgtag));
  $$('.apparatus [data-imgcopy]').forEach(b=>b.onclick=()=>copyText(`#plate("/${b.dataset.imgcopy}")`));
}
async function readStory(id){
  if(!S.stories){ const r=await api('/api/engine/stories'); S.stories=r.stories; }
  const order = S.stories.slice().sort((a,b)=>(a.year??1e9)-(b.year??1e9)).filter(s=>s.exists);
  const i = order.findIndex(s=>s.id===String(id)); const s = order[i];
  if(!s){ alertNote('This '+L.story+' has no draft yet.'); return; }
  openModal(s.title, `<div class="row" style="margin-bottom:14px"><span class="pill">${esc(s.dates||'undated')}</span><span class="pill">${s.words.toLocaleString()} words</span>
      <span class="pill">${s.citations} cited paragraph${s.citations!==1?'s':''}</span>${s.bridges?`<span class="pill warn">${s.bridges} bridge${s.bridges!==1?'s':''}</span>`:''}
      <span class="pill ${s.state==='in the book'?'ok':''}">${esc(s.book_position)}</span><span class="spacer"></span>
      ${i>0?`<button class="btn ghost sm" data-nav="${esc(order[i-1].id)}">← ${esc(order[i-1].title)}</button>`:''}
      ${i<order.length-1?`<button class="btn ghost sm" data-nav="${esc(order[i+1].id)}">${esc(order[i+1].title)} →</button>`:''}</div>
    ${s.has_audio?`<div class="row" style="margin-bottom:14px"><audio controls src="${fileUrl(s.audio)}" style="flex:1"></audio>${s.audio_stale?'<span class="pill warn">audio is stale</span>':''}</div>`:''}
    <div class="pages" id="rd-pages"><p class="empty">Setting the pages…</p></div>`);
  $$('[data-nav]').forEach(b=>b.onclick=()=>readStory(b.dataset.nav));
  api('/api/engine/story/apparatus?id='+encodeURIComponent(s.id)).then(ap=>{ const box=$('#rd-pages'); if(!box||ap.error) return;
    box.insertAdjacentHTML('beforebegin', storyApparatusHtml(ap)); bindStoryApparatus(ap); });
  Promise.all([api('/api/engine/familypedia/story?id='+encodeURIComponent(s.id)), ensureFP()]).then(([r])=>{ const box=$('#rd-pages'); if(!box||!r.subjects.length) return;
    box.insertAdjacentHTML('beforebegin', `<div class="row fp-instory" style="gap:5px;margin:-4px 0 14px"><span class="derived">In this ${esc(L.story)}:</span>${r.subjects.map(x=>entryChip(x.slug, x.title, x.type, '', undefined, 'onclick="closeOverlay()"')).join(' ')}</div>`); });
  const r = await api('/api/engine/story/render',{method:'POST',body:{id:s.id}});
  pollJob(r.job, null, res=>{ const box=$('#rd-pages'); if(box) box.innerHTML = res.pages.map(p=>`<img src="${fileUrl(p)}&v=${Date.now()}" alt="page">`).join(''); },
    err=>{ const box=$('#rd-pages'); if(box) box.innerHTML=`<div class="note">Couldn't set this ${L.story} as pages: ${esc(err)}</div>`; });
}
