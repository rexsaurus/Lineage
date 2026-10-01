/* ================================================================== TERMINAL DRAWER
   author-only surface: the terminal is a real shell on this machine. It lives in a drawer
   that opens from any tab (header button, or Ctrl+`), so the Genealogist is always one key away. */
const TERM = {term:null, fit:null, es:null, chain:Promise.resolve(), buf:'', timer:null, started:false};
const ACTIONS = [
  ['research','Search public records','Names, places and dates → archives'],
  ['genealogy','Build the genealogy','Records → a line of descent'],
  ['chapters', L.proposeStories,'Material → a proposed '+L.storyMap.toLowerCase()],
  ['generate','Write the stories','Cited prose, bridges held back'],
  ['podcast','Make a podcast episode','A spoken script in the chosen voice'],
];
function buildTerminalDrawer(el){
  el.innerHTML = `<div class="tmain">
      <div class="sessionbar"><span class="who">The Genealogist</span><code id="t-cmd"></code><span class="spacer"></span>
        <span class="pill" id="t-status">…</span>
        <button class="btn ghost sm" id="t-restart" title="Start the command again">Restart</button>
        <button class="btn ghost sm" id="t-stop" title="Send Ctrl-C (SIGINT)">Stop</button>
        <button class="btn ghost sm" id="t-clear" title="Clear the screen and the saved scrollback">Clear</button>
        <button class="btn ghost sm" id="t-size" title="Taller or shorter">Taller</button>
        <button class="btn ghost sm" id="t-hide" title="Hide the terminal (Ctrl+\`). It keeps running.">Hide</button></div>
      <div class="chips">${S.data.quick_prompts.map((q,i)=>`<button class="chip" data-i="${i}" title="${esc(q.prompt)}">${esc(q.label.replace('chapter map', L.storyMap.toLowerCase()).replace('chapter 1','the first '+L.story))}</button>`).join('')}</div>
      <div class="composer"><div style="flex:1"><textarea id="t-compose" rows="1" placeholder="Ask the Genealogist… (Enter to send, Shift+Enter for a new line)"></textarea>
        <div class="hint">Typed into the terminal below, followed by Return. The terminal is the truth.</div></div>
        <button class="btn go" id="t-send">Send</button></div>
      <div class="termwrap"><div id="term"></div></div>
    </div>
    <aside class="tside">
      <div class="card"><h3>Pipeline</h3><p class="sub">Each step is handed to the Genealogist, with the Lineage skills.</p>
        ${ACTIONS.map(([id,name,blurb])=>`<div class="action"><span class="name">${esc(name)}</span><button class="btn sm" data-run="${id}">Run</button>
          <span class="step" id="step-${id}">${esc(blurb)}</span><div class="mini"><i id="bar-${id}"></i></div></div>`).join('')}</div>
      <div class="card"><div class="row"><h3>Needs your approval</h3><span class="spacer"></span><button class="btn ghost sm" id="appr-refresh">Refresh</button></div>
        <p class="sub">Bridges, REVIEW notes and proposed decisions.</p><ul class="appr" id="appr"></ul></div>
    </aside>`;
  $$('[data-run]', el).forEach(b=>b.onclick=()=>runAction(b.dataset.run, b));
  $('#appr-refresh').onclick=loadApprovals; loadApprovals();
  $('#t-restart').onclick=startTerminal;
  $('#t-stop').onclick=()=>api('/api/term/stop',{method:'POST'});
  $('#t-clear').onclick=()=>api('/api/term/clear',{method:'POST'});
  $('#t-hide').onclick=()=>openDock(false);
  $('#t-size').onclick=()=>{ el.classList.toggle('tall'); $('#t-size').textContent=el.classList.contains('tall')?'Shorter':'Taller'; setTimeout(()=>{ try{ TERM.fit.fit(); sendResize(); }catch(e){} },50); };
  $('#t-send').onclick=sendCompose;
  $('#t-compose').onkeydown=e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendCompose(); } };
  $$('.chip', el).forEach(c=>c.onclick=()=>sendToTerminal(S.data.quick_prompts[+c.dataset.i].prompt));
  initTerminal();
}
function initTerminal(){
  if(typeof Terminal==='undefined'){ $('#term').innerHTML='<p style="color:#F7F3EC;padding:14px">xterm.js did not load (no internet?). The terminal needs the CDN once.</p>'; return; }
  const t = new Terminal({fontFamily:"'JetBrains Mono','SFMono-Regular',Menlo,Consolas,monospace", fontSize:13.2, lineHeight:1.18, cursorBlink:true, scrollback:10000,
    theme:{background:'#1C1A17', foreground:'#F7F3EC', cursor:'#C96F4A', cursorAccent:'#1C1A17', selectionBackground:'#5B544A',
      black:'#1C1A17', red:'#E07A5F', green:'#9DBF8F', yellow:'#E3B95F', blue:'#8FB3D9', magenta:'#C99BC9', cyan:'#86C5C0', white:'#E9E2D6',
      brightBlack:'#7C756A', brightRed:'#F09A80', brightGreen:'#B6D6A8', brightYellow:'#F0CF7F', brightBlue:'#A9C8E8', brightMagenta:'#DDB6DD', brightCyan:'#A3D8D3', brightWhite:'#FFFFFF'}});
  const fit = new FitAddon.FitAddon(); t.loadAddon(fit); t.open($('#term'));
  TERM.term=t; TERM.fit=fit;
  t.onData(d=>{ if(TERM.replaying) return; TERM.buf+=d; if(!TERM.timer) TERM.timer=setTimeout(flushKeys, 6); });   // replies to replayed queries are not input
  new ResizeObserver(()=>{ if(isDockOpen()){ try{ fit.fit(); sendResize(); }catch(e){} } }).observe($('#term'));
  openStream();
}
function flushKeys(){ const d=TERM.buf; TERM.buf=''; TERM.timer=null; if(d) TERM.chain = TERM.chain.then(()=>api('/api/term/input',{method:'POST',body:{data:d}})); }
let resizeTimer=null;
function sendResize(){ clearTimeout(resizeTimer); resizeTimer=setTimeout(()=>{ if(TERM.term) api('/api/term/resize',{method:'POST',body:{cols:TERM.term.cols, rows:TERM.term.rows}}); },120); }
const b64 = s => Uint8Array.from(atob(s), c=>c.charCodeAt(0));
function openStream(){
  if(TERM.es) TERM.es.close();
  const es = new EventSource('/api/term/stream?token='+encodeURIComponent(TOKEN)); TERM.es = es;
  es.addEventListener('hello', e=>{ const d=JSON.parse(e.data); TERM.term.reset();
    if(d.scrollback){ TERM.replaying=true; TERM.term.write(b64(d.scrollback), ()=>{ TERM.replaying=false; }); } setTermStatus(d); });
  es.addEventListener('data', e=>TERM.term.write(b64(e.data)));
  es.addEventListener('status', e=>setTermStatus(JSON.parse(e.data)));
  es.addEventListener('clear', ()=>TERM.term.clear());
}
function setTermStatus(d){
  S.data.terminal = d; const p=$('#t-status'); if(!p) return;
  const map={running:['ok','running'], exited:['warn','exited'], 'not configured':['bad','not configured'], 'not started':['','not started']};
  const [cls,label]=map[d.status]||['',d.status];
  p.className='pill '+cls; p.textContent=label; p.title=d.detail||'';
  $('#t-cmd').textContent = d.command ? `${d.command} · ${d.cwd||''}` : '';
  if(d.status==='not configured' && d.detail && TERM.term) TERM.term.write(`\r\n\x1b[33m${d.detail}\x1b[0m\r\n`);
}
async function startTerminal(){ const d = await api('/api/term/start',{method:'POST'}); setTermStatus(d); setTimeout(()=>{ TERM.fit && TERM.fit.fit(); sendResize(); },60); }
function onTermShown(){
  setTimeout(()=>{ try{ TERM.fit && TERM.fit.fit(); sendResize(); }catch(e){} TERM.term && TERM.term.focus(); }, 30);
  if(!TERM.started){ TERM.started=true; if(S.data.terminal.status!=='running') startTerminal(); }
}
async function sendToTerminal(text){
  if(!text.trim()) return;
  if(!isDockOpen()) openDock(true);
  if(S.data.terminal.status!=='running'){ await startTerminal(); await new Promise(r=>setTimeout(r,900)); }
  // Multi-line text goes in as a bracketed paste so it stays one message (agent CLIs support
  // it); a single line is typed plainly, which every shell understands. Return submits it.
  const body = text.includes('\n') ? '\x1b[200~'+text+'\x1b[201~' : text;
  TERM.chain = TERM.chain.then(()=>api('/api/term/input',{method:'POST',body:{data:body}}))
                         .then(()=>new Promise(r=>setTimeout(r,60)))
                         .then(()=>api('/api/term/input',{method:'POST',body:{data:'\r'}}));
  TERM.term && TERM.term.focus();
}
function sendCompose(){ const ta=$('#t-compose'); const v=ta.value; ta.value=''; sendToTerminal(v); }
async function loadApprovals(){
  const r = await api('/api/engine/approvals'); const ul=$('#appr'); if(!ul) return;
  ul.innerHTML = r.items.length ? r.items.slice(0,60).map(i=>`<li><span class="pill ${i.kind==='bridge'?'warn':(i.kind==='review'?'bad':'')}">${esc(i.kind)}</span> ${esc(i.text.replace('Chapter map',L.storyMap))}<br><code>${esc(i.where)}</code></li>`).join('')
    : '<li style="background:none;color:var(--ink-3);padding-left:0">Nothing waiting.</li>';
}
async function runAction(stage, btn){
  const step=$('#step-'+stage), bar=$('#bar-'+stage);
  if(!S.data.demo){
    // Real work: the Genealogist does it in the terminal, with the Lineage skills.
    const r = await api('/api/run/'+stage,{method:'POST'});
    if(r.terminal_prompt){ sendToTerminal(r.terminal_prompt); step.textContent='Sent to the Genealogist below. Follow it in the terminal.'; return; }
    if(r.error){ step.textContent='Error: '+r.error; return; }
  }
  btn.disabled=true;
  runJob(stage, (s,p)=>{ step.textContent=s; bar.style.width=p+'%'; }, r=>{
    btn.disabled=false; btn.textContent='Run again'; bar.style.width='100%';
    S.results[stage]=r; step.innerHTML=`Done · <a href="#" data-show="${stage}">view result</a>`;
    step.querySelector('[data-show]').onclick=e=>{e.preventDefault(); showResult(stage);};
    showResult(stage); loadApprovals();
  }, err=>{ btn.disabled=false; step.textContent='Error: '+err; });
}
function showResult(stage){
  const r=S.results[stage]; let title='', html='';
  if(stage==='research'){ title=`${r.records.length} records found`;
    const tone=c=>c.startsWith('documented')?'ok':(c.startsWith('contradicts')?'warn':'');
    html=`<p class="sub">PROTOTYPE results. Each would get a line in THE RECORDS.</p><table><thead><tr><th>Record</th><th>Where</th><th>What it shows</th><th>Verdict</th></tr></thead><tbody>${r.records.map(x=>`<tr><td><strong>${esc(x.title)}</strong></td><td>${esc(x.where)}</td><td>${esc(x.detail)}</td><td><span class="pill ${tone(x.confidence)}">${esc(x.confidence)}</span></td></tr>`).join('')}</tbody></table>`; }
  if(stage==='genealogy'){ title='Line of descent';
    html=`<p class="sub">PROTOTYPE. Green: witnessed. Sand: told. Clay: a record says so.</p><ul class="tree">${r.tree.map(p=>`<li class="${esc(p.tier)}"><div class="name">${esc(p.name)} <span class="meta">${esc(p.years)}</span></div><div class="meta">${esc(p.note||'')} · ${esc(p.tier)}</div></li>`).join('')}</ul>`; }
  if(stage==='chapters'){ title=`${r.chapters.length} ${L.stories} proposed`;
    html=`<p class="sub">PROTOTYPE ${L.storyMap.toLowerCase()}. Approve it, or ask the Genealogist to split, merge or reorder.</p><table><thead><tr><th>#</th><th>${esc(L.Story)}</th><th>Part</th><th>Years</th><th>Units</th><th>Words</th></tr></thead><tbody>${r.chapters.map(c=>`<tr><td>${c.n}</td><td><strong>${esc(c.title)}</strong><br><span style="color:var(--ink-3);font-size:13px">${esc(c.summary)}</span></td><td>${esc(c.part)}</td><td>${esc(c.years)}</td><td class="num">${c.units}</td><td class="num">${c.words.toLocaleString()}</td></tr>`).join('')}</tbody></table>
      <h3 style="margin:22px 0 8px">Preview, in the current narrator style</h3><div class="preview">${esc(r.preview).replace(/⟦BRIDGE: (.*?)⟧/g,(m,t)=>`<mark>BRIDGE · ${esc(t)} · approve or cut</mark>`)}</div>`; }
  if(stage==='generate'){ title=`${r.written} ${L.stories} drafted`; html=`<p>${esc(r.note.replace('chapter',L.story))}</p><div class="row"><span class="pill ok">${r.written} ${L.stories}</span><span class="pill warn">${r.bridges} bridges to approve</span></div>`; }
  if(stage==='podcast'){ title='Episode 1'; html=`<p>${esc(r.note)}</p><div class="row"><span class="pill ok">${esc(r.script)}</span>${r.audio?'<span class="pill ok">audio</span>':'<span class="pill warn">audio not rendered</span>'}</div><p><a href="#stories">Open in Stories</a></p>`; }
  openModal(title, html);
}

