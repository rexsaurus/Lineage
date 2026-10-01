/* ======================================================================================
   LABELS — the only place UI words for the book's pieces live. The engine and files keep
   their names (chapters/, data/chapters.csv); people see "stories". The printed book still
   has chapters, so "chapter" survives only where the book's own structure is meant.
   "Contributors" are people who add material; "family" and "relatives" are the subject.
   ====================================================================================== */
const L = {
  story:'story', Story:'Story', stories:'stories', Stories:'Stories',
  storyMap:'Story map', proposeStories:'Propose stories', storyTemplate:'Story template',
  generateRemaining:'Generate the remaining stories', storiesAbout:'Stories about',
  bookChapter:'Chapter', // the printed book's own numbering
  states:{'draft':'draft', 'in the book':'in the book', 'kept aside':'kept aside'},
  templates:{ancestor:'Ancestor story', 'life-stage':'Life stage', theme:'Theme across a life', album:'Photo album'},
  noStories:'No stories yet — add a source to start one.',
  contributor:'contributor', contributors:'contributors', Contributors:'Contributors',
};
/* Working surfaces only. Administration lives behind the gear (#/settings/<section>). */
const TABS = [['home','Home'], ['sources','Sources'], ['familypedia','Familypedia'], ['genealogy','Genealogy'], ['stories','Stories'], ['timeline','Timeline']];
const SETTINGS = [
  ['family','Family details','Title, family name, summary, subject, crest'],
  ['connectors','Connectors','Drive, GitHub, Anthropic, OpenAI, ElevenLabs, agent CLIs'],
  ['contributors','Contributors','People who add material, invites, review queue'],
  ['project','Project settings','Repo, Drive folder, styles, templates, print, paths'],
];
/* Old addresses still land somewhere sensible. */
const ALIASES = {settings:'/settings/family', connectors:'/settings/connectors', family:'/settings/contributors', contributors:'/settings/contributors',
  read:'stories', listen:'stories', transcribe:'home'};

const S = {data:null, tab:null, built:{}, results:{}, sources:null, voices:[], stories:null, wiki:null, article:null, attention:[], from:'home', q:{}};
const $ = (s,r=document)=>r.querySelector(s);
const $$ = (s,r=document)=>[...r.querySelectorAll(s)];
const esc = s => (s??"").toString().replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function api(path, {method='GET', body=null}={}){
  const opts = {method, headers:{'X-Lineage-Token':TOKEN}};
  if(body instanceof FormData) opts.body = body;
  else if(body!==null){ opts.body = JSON.stringify(body); opts.headers['Content-Type']='application/json'; }
  return (await fetch(path, opts)).json();
}
const fileUrl = rel => '/api/file?path='+encodeURIComponent(rel)+'&token='+encodeURIComponent(TOKEN);
const tokUrl = p => p+(p.includes('?')?'&':'?')+'token='+encodeURIComponent(TOKEN);
const settings = () => S.data.state.settings;
async function saveSettings(patch){
  const r = await api('/api/settings',{method:'POST', body:patch});
  S.data.state.settings = r.settings; S.data.state.title = r.title; S.data.state.subject = r.subject;
  if(r.identity){ S.data.identity = r.identity; drawIdentityHeader(); drawStale(); }
  syncMirrors(); return r;
}
/* the lineage's name flows everywhere by reference: header, browser title, Familypedia front page */
function drawIdentityHeader(){
  const id = S.data.identity;
  $('#lin-title').textContent = id.display_title;
  $('#lin-title').title = id.title ? '' : 'Name this lineage in Settings → Family details';
  document.title = id.title ? `${id.title} · Lineage` : 'Untitled lineage · Lineage';
  const c=$('#lin-crest'), on = id.crest && (id.crest_surfaces||{}).header;
  if(on){ c.src=fileUrl(id.crest)+'&v='+Date.now(); c.classList.remove('hidden'); } else c.classList.add('hidden');
}
function drawStale(){
  const box=$('#id-stale'); if(!box) return;
  const st=S.data.identity.stale||[];
  box.innerHTML = st.length ? `<div class="note" style="margin-top:12px">Out of date since the name or summary changed: ${st.map(x=>`<span class="pill warn">${esc(x)}</span>`).join(' ')} <button class="btn ghost sm" id="id-fresh">I've checked these</button></div>` : '';
  const f=$('#id-fresh'); if(f) f.onclick=async()=>{ S.data.identity = await api('/api/identity/fresh',{method:'POST',body:{}}); drawStale(); };
}
function fmtBytes(n){ if(n<1024) return n+' B'; if(n<1048576) return (n/1024).toFixed(0)+' KB'; if(n<1073741824) return (n/1048576).toFixed(1)+' MB'; return (n/1073741824).toFixed(2)+' GB'; }
function fmtDur(s){ if(s==null) return '—'; s=Math.round(s); const h=Math.floor(s/3600), m=Math.floor(s%3600/60), x=s%60; return (h?h+':'+String(m).padStart(2,'0'):m)+':'+String(x).padStart(2,'0'); }
function ago(iso){
  if(!iso) return ''; const s=(Date.now()-new Date(iso).getTime())/1000;
  if(s<60) return 'just now'; if(s<3600) return Math.round(s/60)+' min ago'; if(s<86400) return Math.round(s/3600)+' h ago';
  const d=Math.round(s/86400); if(d<14) return d+' day'+(d>1?'s':'')+' ago'; if(d<60) return Math.round(d/7)+' weeks ago';
  return new Date(iso).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'});
}
function head(el,{kicker,title,lede}){ el.insertAdjacentHTML('beforeend',`<div class="head"><div class="kicker">${esc(kicker)}</div><h2>${esc(title)}</h2>${lede?`<p class="lede">${esc(lede)}</p>`:''}</div>`); }
function options(list, cur){ return list.map(([v,l])=>`<option value="${esc(v)}" ${v===cur?'selected':''}>${esc(l)}</option>`).join(''); }
function alertNote(msg){ const n=document.createElement('div'); n.className='note'; n.style.cssText='position:fixed;bottom:18px;left:50%;transform:translateX(-50%);z-index:60;box-shadow:0 6px 20px rgba(0,0,0,.15);max-width:80vw'; n.textContent=msg; document.body.appendChild(n); setTimeout(()=>n.remove(),4500); }
async function copyText(t){ try{ await navigator.clipboard.writeText(t); alertNote('Copied.'); }catch(e){ openModal('Copy this', `<textarea rows="12" style="font-family:var(--mono);font-size:12.5px">${esc(t)}</textarea>`); } }
function download(name, blob){ const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name; document.body.appendChild(a); a.click(); setTimeout(()=>{ URL.revokeObjectURL(a.href); a.remove(); },500); }
/* SVG → PNG in the browser, for exports. */
function svgToPng(svgText, name, scale=2){
  const img=new Image(); const url=URL.createObjectURL(new Blob([svgText],{type:'image/svg+xml'}));
  img.onload=()=>{ const c=document.createElement('canvas'); c.width=img.width*scale; c.height=img.height*scale;
    const g=c.getContext('2d'); g.fillStyle='#fff'; g.fillRect(0,0,c.width,c.height); g.drawImage(img,0,0,c.width,c.height);
    c.toBlob(b=>download(name,b),'image/png'); URL.revokeObjectURL(url); };
  img.src=url;
}
/* A print-ready page in a new window; the person presses Print. */
function printable(title, bodyHtml){
  const w=window.open('','_blank'); if(!w){ alertNote('Allow pop-ups to open the printable page.'); return; }
  w.document.write(`<!doctype html><title>${esc(title)}</title><style>body{font-family:Georgia,serif;margin:40px;color:#1C1A17}h1{font-weight:600}h2{margin-top:26px}p,li{line-height:1.5}small{color:#7C756A}svg{max-width:100%;height:auto}@media print{button{display:none}}</style>
    <button onclick="print()" style="float:right;padding:8px 14px">Print</button>${bodyHtml}`);
  w.document.close();
}

/* ------------------------------------------------------------------ boot + routing (no wizard: every tab, any time) */
async function boot(){
  S.data = await api('/api/bootstrap');
  $('#proj').textContent = S.data.project;
  drawIdentityHeader();
  if(S.data.demo) document.body.insertAdjacentHTML('afterbegin','<div style="background:#B9872F;color:#fff;text-align:center;font-size:13px;padding:5px">Demo mode (--demo): pipeline results are invented sample content, not your project.</div>');
  $('#tabs').innerHTML = TABS.map(([id,label])=>`<a href="#${id}" data-tab="${id}">${esc(label)}</a>`).join('');
  $('#main').innerHTML = TABS.map(([id])=>`<section id="tab-${id}" class="page hidden"></section>`).join('') + `<section id="tab-settings" class="page hidden"></section>`;
  initGear(); initDock();
  window.addEventListener('hashchange', route);
  if(!location.hash) history.replaceState(null,'','#home');
  refreshAttention();
  route();
}
function parseHash(){
  let raw = decodeURIComponent(location.hash.replace(/^#/,''));
  const [path, qs=''] = raw.split('?');
  const q = Object.fromEntries(new URLSearchParams(qs));
  return {path, q};
}
const BUILDERS = {};
function route(){
  let {path, q} = parseHash();
  let [t, ...rest] = path.replace(/^\//,'').split('/');
  // old tabs → new homes
  if(path==='settings' || (t==='settings' && !rest.length)){ location.replace('#/settings/family'); return; }
  if(t!=='settings' && ALIASES[t]){
    const to = ALIASES[t];
    if(t==='transcribe') openDock(true);
    if(t==='read' && rest.length){ location.replace('#stories?read='+encodeURIComponent(rest[0])); return; }
    location.replace('#'+to); return;
  }
  if(t==='settings'){ return showSettings(rest[0]||'family'); }
  if(!TABS.some(([id])=>id===t)) t='home';
  S.from = location.hash || '#home';
  S.tab = t; S.q = q;
  $$('#tabs a').forEach(a=>a.setAttribute('aria-current', a.dataset.tab===t?'page':'false'));
  $('#tab-settings').classList.add('hidden');
  TABS.forEach(([x])=>$('#tab-'+x).classList.toggle('hidden', x!==t));
  const always = ['home','sources','stories','genealogy','timeline'];
  if(!S.built[t] || always.includes(t)){ BUILDERS[t]($('#tab-'+t), rest, q); S.built[t]=true; }
  else { syncMirrors(); if(t==='familypedia' && rest.length) openArticle(decodeURIComponent(rest[0])); }
  window.scrollTo(0,0);
}
function syncMirrors(){
  $$('[data-setting]').forEach(el=>{ const v = settings()[el.dataset.setting];
    if(el.tagName==='SELECT' && ![...el.options].some(o=>o.value===String(v??''))) return;
    if(el.type==='checkbox') el.checked = !!v; else if(document.activeElement!==el) el.value = v ?? ''; });
  $$('[data-choice-for]').forEach(c=>{ c.dataset.on = settings()[c.dataset.choiceFor]===c.dataset.id ? 1 : 0; });
}
function bindSettingInputs(root){
  $$('[data-setting]', root).forEach(el=>{ el.onchange = ()=>saveSettings({[el.dataset.setting]: el.type==='checkbox' ? el.checked : el.value}); });
}
async function runJob(stage, onStep, onDone, onError){
  const r = await api('/api/run/'+stage,{method:'POST'});
  if(r.terminal_prompt){ sendToTerminal(r.terminal_prompt); openDock(true); onError && onError('Sent to the Genealogist in the terminal.'); return; }
  if(!r.job){ onError && onError(r.error||'could not start'); return; }
  return pollJob(r.job, onStep, onDone, onError);
}
function pollJob(job, onStep, onDone, onError){
  return new Promise(resolve=>{ const t=setInterval(async()=>{ const j=await api('/api/job/'+job);
    onStep && onStep(j.step, j.progress);
    if(j.state==='done'){ clearInterval(t); onDone && onDone(j.result); resolve(j.result); }
    if(j.state==='error'||j.state==='unknown'){ clearInterval(t); onError && onError(j.step||'job lost'); resolve(null); } }, 400); });
}

/* ------------------------------------------------------------------ the settings gear */
const GEAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="3.2"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>';
const TERM_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M12 15h5"/></svg>';
function initGear(){
  const b=$('#gear');
  b.innerHTML = GEAR_SVG+'<span>Settings</span><i class="dot hidden" id="gear-dot"></i>';
  b.onclick = e=>{ e.stopPropagation(); const m=$('#gearmenu'); m ? closeGear() : openGear(); };
  b.onkeydown = e=>{ if(e.key==='ArrowDown'){ e.preventDefault(); openGear(); } };
}
function openGear(){
  closeGear();
  const att = new Set(S.attention.map(a=>a.section));
  const m=document.createElement('div'); m.id='gearmenu'; m.className='gearmenu'; m.setAttribute('role','menu');
  m.innerHTML = SETTINGS.map(([id,name,blurb])=>`<a role="menuitem" href="#/settings/${id}" tabindex="-1"><div>${esc(name)}<small>${esc(blurb)}</small></div>${att.has(id)?'<i class="att" title="Needs attention"></i>':''}</a>`).join('');
  $('#gearwrap').appendChild(m); $('#gear').setAttribute('aria-expanded','true');
  const items=$$('a',m); items[0].focus();
  m.onkeydown=e=>{ const i=items.indexOf(document.activeElement);
    if(e.key==='ArrowDown'){ e.preventDefault(); items[(i+1)%items.length].focus(); }
    if(e.key==='ArrowUp'){ e.preventDefault(); items[(i-1+items.length)%items.length].focus(); }
    if(e.key==='Escape'){ closeGear(); $('#gear').focus(); } };
  items.forEach(a=>a.onclick=()=>closeGear());
  setTimeout(()=>document.addEventListener('click', closeGear, {once:true}),0);
}
function closeGear(){ const m=$('#gearmenu'); if(m) m.remove(); $('#gear').setAttribute('aria-expanded','false'); }
async function refreshAttention(){
  S.attention = await api('/api/engine/attention');
  const dot=$('#gear-dot'); dot.classList.toggle('hidden', !S.attention.length);
  $('#gear').title = S.attention.length ? S.attention.map(a=>a.text).join('\n') : '';
  $('#gear').setAttribute('aria-label', 'Settings'+(S.attention.length?` (${S.attention.length} need${S.attention.length>1?'':'s'} attention)`:''));
}
function showSettings(section){
  if(!SETTINGS.some(([id])=>id===section)) section='family';
  TABS.forEach(([x])=>$('#tab-'+x).classList.add('hidden'));
  $$('#tabs a').forEach(a=>a.setAttribute('aria-current','false'));
  const el=$('#tab-settings'); el.classList.remove('hidden');
  const att = new Set(S.attention.map(a=>a.section));
  el.innerHTML = `<div class="setbar"><div><div class="kicker">Settings</div></div><span class="spacer"></span><button class="btn" id="set-done">Done</button></div>
    <div class="setwrap"><nav class="setnav" aria-label="Settings sections">${SETTINGS.map(([id,name])=>`<a href="#/settings/${id}" aria-current="${id===section?'page':'false'}">${esc(name)}${att.has(id)?'<i class="att" title="Needs attention"></i>':''}</a>`).join('')}</nav>
    <div id="set-body"></div></div>`;
  $('#set-done').onclick = leaveSettings;
  SECTION_BUILDERS[section]($('#set-body'));
  window.scrollTo(0,0);
}
function leaveSettings(){ location.hash = S.from && !S.from.startsWith('#/settings') ? S.from : '#home'; }
const SECTION_BUILDERS = {};

/* ------------------------------------------------------------------ dock: the mini player and the terminal drawer */
function initDock(){
  const t=$('#termbtn');
  t.innerHTML = TERM_SVG+'<span>Terminal</span><kbd>Ctrl `</kbd>';
  t.setAttribute('aria-label','Terminal (Ctrl+backquote)');
  t.onclick = ()=>openDock(!isDockOpen());
  document.addEventListener('keydown', e=>{ if(e.ctrlKey && (e.key==='`' || e.code==='Backquote')){ e.preventDefault(); openDock(!isDockOpen()); } });
  new ResizeObserver(()=>{ document.body.style.setProperty('--dockh', $('#dock').offsetHeight+'px'); document.body.classList.toggle('docked', $('#dock').offsetHeight>0); }).observe($('#dock'));
}
function isDockOpen(){ return !$('#tdrawer').classList.contains('hidden'); }
function openDock(open){
  const d=$('#tdrawer');
  if(open && !d.dataset.built){ buildTerminalDrawer(d); d.dataset.built='1'; }
  d.classList.toggle('hidden', !open); $('#termbtn').setAttribute('aria-expanded', String(open));
  if(open) onTermShown();
}
/* One player for the whole dashboard. */
function play(story){
  const p=$('#player'); p.classList.remove('hidden');
  p.innerHTML = `<span class="t" title="${esc(story.title)}">${esc(story.title)}</span><audio controls autoplay src="${fileUrl(story.audio)}"></audio>
    ${story.audio_stale?'<span class="pill warn" title="The story changed after this was recorded">audio is stale</span>':''}
    <a class="btn ghost sm" href="${fileUrl(story.audio)}" download>Download</a><button class="btn ghost sm" id="pl-close" aria-label="Close the player">×</button>`;
  $('#pl-close').onclick=()=>{ p.innerHTML=''; p.classList.add('hidden'); S.playing=null; $$('.story.playing').forEach(x=>x.classList.remove('playing')); };
  S.playing = story.id; $$('.story').forEach(x=>x.classList.toggle('playing', x.dataset.id===String(story.id)));
}

/* ------------------------------------------------------------------ overlays */
function closeOverlay(){ $('#overlay').innerHTML=''; }
function openDrawer(title, html){
  $('#overlay').innerHTML=`<div class="scrim"></div><aside class="drawer" role="dialog" aria-label="${esc(title)}"><header><h3>${esc(title)}</h3><span class="spacer"></span><button class="btn ghost sm" id="ov-close">Close</button></header><div class="body">${html}</div></aside>`;
  $('.scrim').onclick=closeOverlay; $('#ov-close').onclick=closeOverlay;
}
function openModal(title, html){
  $('#overlay').innerHTML=`<div class="scrim"></div><div class="modal" role="dialog" aria-label="${esc(title)}"><header><h3>${esc(title)}</h3><span class="spacer"></span><button class="btn ghost sm" id="ov-close">Close</button></header><div class="body">${html}</div></div>`;
  $('.scrim').onclick=closeOverlay; $('#ov-close').onclick=closeOverlay;
}
document.addEventListener('keydown',e=>{
  if(e.key!=='Escape') return;
  if($('#overlay').innerHTML){ closeOverlay(); return; }
  if($('#gearmenu')){ closeGear(); return; }
  if(location.hash.startsWith('#/settings') && !(document.activeElement && /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName))) leaveSettings();
});
