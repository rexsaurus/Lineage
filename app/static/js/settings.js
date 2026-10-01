/* ================================================================== SETTINGS (behind the gear)
   Four pages, each routed at #/settings/<section>, with their own section list. */
SECTION_BUILDERS.family = function(el){
  const s = settings(), D = S.data;
  el.innerHTML='';
  head(el,{kicker:'Family details', title:'The lineage', lede:'These names appear on nearly every surface: the header, Home, the Familypedia, the tree, invitations and the book\'s title page.'});
  const I = D.identity;
  el.insertAdjacentHTML('beforeend', `
  <div class="card"><div class="row"><h3>This lineage</h3><span class="spacer"></span>${I.title?'':'<span class="pill warn">untitled — give it a name</span>'}</div>
    <p class="sub">These names appear on nearly every surface: the header, the Familypedia, the tree, invitations and the book's title page.</p>
    <div class="grid three">
      <div><label>Family name</label><input type="text" data-setting="family_name" value="${esc(s.family_name)}" placeholder="the Calders"></div>
      <div><label>Lineage title</label><input type="text" id="set-title" value="${esc(D.state.title)}" placeholder="The Lake Was Always There"></div>
      <div><label>Subtitle <span style="color:var(--ink-3);font-weight:400">optional</span></label><input type="text" data-setting="subtitle" value="${esc(s.subtitle)}" placeholder="A Life of Ruth Calder"></div>
      <div><label>Subject, full name</label><input type="text" id="set-subject" value="${esc(D.state.subject)}" placeholder="Ruth Calder"></div>
      <div><label>…and in the prose</label><input type="text" data-setting="subject_short" value="${esc(s.subject_short)}" placeholder="Ruth"></div>
      <div><label>Covers</label><input type="text" id="set-covers" value="${esc(s.covers_override||'')}" placeholder="${esc(I.covers_auto||'filled in from the timeline')}">
        <span style="font-size:12px;color:var(--ink-3)">${I.covers_auto?'From the timeline: '+esc(I.covers_auto)+'. Type to override.':'Fills in once the project has a timeline.'}</span></div>
    </div>
    <div style="margin-top:12px"><label>Summary</label><textarea id="set-summary" rows="3" placeholder="What this collection is, whose stories it holds, and what it covers.">${esc(s.summary)}</textarea>
      <div class="row" style="margin-top:6px"><button class="btn ghost sm" id="set-draft">Draft this from the project</button><span style="font-size:12.5px;color:var(--ink-3)">A draft to edit, never saved until you do. Yours always wins.</span></div></div>
    <div id="id-stale"></div>
  </div>
  <div class="card" id="crest"><p class="empty">Loading…</p></div>`);
  bindSettingInputs(el);
  ['title','subject'].forEach(k=>$('#set-'+k).onchange=e=>saveSettings({[k]:e.target.value}));
  $('#set-covers').onchange=e=>saveSettings({covers_override:e.target.value});
  $('#set-summary').onchange=e=>saveSettings({summary:e.target.value});
  $('#set-draft').onclick=async()=>{ const r=await api('/api/identity/draft-summary',{method:'POST'});
    const ta=$('#set-summary'); if(ta.value.trim() && !confirmReplace()) return; ta.value=r.summary; ta.focus(); alertNote('Draft written below. Edit it, then click away to save it as yours.'); };
  drawStale(); drawCrest();
};

/* ------------------------------------------------------------------ the crest: Generate · Upload · None.
   Default is None and hidden. Every attempt is kept; whatever is shown says where it came from. */
const SURFACES = {header:'Header', familypedia:'Familypedia front page', title_page:"Book title page", exports:'Exports and charts', invitations:'Invitations'};
async function drawCrest(){
  const c = await api('/api/crest'); S.crest=c;
  const box=$('#crest'); const I=S.data.identity;
  const prov = c.provenance ? (c.provenance.kind==='generated' ? `Generated with ${esc(c.provenance.model||'')} from “${esc(c.provenance.prompt||'')}” (${esc(c.provenance.style||'')}), ${esc((c.provenance.date||'').slice(0,10))}. Not a historical arms.`
      : `Uploaded · ${esc(c.provenance.provenance||'')}${c.provenance.note?' — '+esc(c.provenance.note):''} · ${esc((c.provenance.date||'').slice(0,10))}. Original kept as ${esc(c.provenance.original||'')}.`) : '';
  box.innerHTML = `<div class="row"><h3>Family crest or symbol</h3><span class="spacer"></span><span class="pill">${c.mode==='none'?'none':c.mode}</span></div>
    <p class="sub">Optional. A mark for the header, the Familypedia and the title page. Off unless you turn it on.</p>
    <div class="row" role="radiogroup" aria-label="Crest" style="gap:6px">${[['none','None'],['generate','Generate'],['upload','Upload']].map(([v,l])=>`<label class="choice" style="padding:8px 14px" data-on="${c.mode===v?1:0}"><input type="radio" name="crest-mode" value="${v}" ${c.mode===v?'checked':''} style="margin-right:6px">${l}</label>`).join('')}</div>
    <div id="crest-panel" style="margin-top:14px"></div>
    ${c.current&&c.mode!=='none'?`<div class="grid two" style="margin-top:16px;align-items:start">
      <div><h4 style="margin:0 0 6px">Current</h4><img src="${fileUrl(c.current)}&v=${Date.now()}" style="width:140px;height:140px;object-fit:contain;border:1px solid var(--line);border-radius:10px;background:#fff">
        <p class="sub" style="font-size:12.4px;margin-top:6px">${prov}</p>
        <div class="row" style="gap:6px">${Object.entries({transparent:'Remove the background', mono:'One-colour version'}).map(([k,l])=>c.variants[k]?`<a class="chiplink" href="${fileUrl(c.variants[k])}" target="_blank" rel="noopener">${esc(l)} ✓</a>`:`<button class="btn ghost sm" data-variant="${k}">${esc(l)}</button>`).join('')}</div></div>
      <div><h4 style="margin:0 0 6px">Where it shows</h4>
        <label class="toggle"><input type="checkbox" id="crest-show" ${c.show?'checked':''}><div><b>Show the crest</b><span>Off by default.</span></div></label>
        ${Object.entries(SURFACES).map(([k,l])=>`<label class="toggle" style="padding:3px 0 3px 26px"><input type="checkbox" data-surface="${k}" ${c.surfaces[k]?'checked':''} ${c.show?'':'disabled'}><div>${esc(l)}</div></label>`).join('')}</div></div>
      <h4 style="margin:16px 0 6px">In context</h4>
      <div class="grid three">
        <div class="note" style="background:var(--ink);color:var(--paper);display:flex;gap:8px;align-items:center"><img src="/logo.svg" style="width:22px"><b style="font-family:var(--serif)">${esc(I.display_title)}</b><img src="${fileUrl(c.current)}" style="width:24px;height:24px;object-fit:contain;background:#fff;border-radius:4px"></div>
        <div class="note" style="text-align:center;background:#fff;border:1px solid var(--line)"><img src="${fileUrl(c.variants.mono||c.current)}" style="width:54px;height:54px;object-fit:contain"><div style="font-family:var(--serif);font-size:17px;margin-top:4px">${esc(I.display_title)}</div><div style="font-size:11px;color:var(--ink-3)">title page</div></div>
        <div class="note" style="display:flex;gap:10px;align-items:center"><img src="${fileUrl(c.current)}" style="width:40px;height:40px;object-fit:contain;background:#fff;border-radius:6px"><div><div class="kicker" style="margin:0">${esc(I.family_name||'the family')}</div><b style="font-family:var(--serif)">Familypedia</b></div></div></div>`:''}
    ${c.attempts.length?`<details style="margin-top:16px"><summary style="cursor:pointer;font-weight:600">Every attempt · ${c.attempts.length}</summary>
      <div class="grid four" style="margin-top:10px">${c.attempts.map(a=>`<div class="choice" style="padding:8px"><img src="${fileUrl(a.image)}" style="width:100%;aspect-ratio:1;object-fit:contain;background:#fff;border-radius:6px"><p style="font-size:11.5px;margin:4px 0">${esc(a.style)} · ${esc((a.date||'').slice(0,10))}</p><button class="btn ghost sm" data-choose="${esc(a.name)}">Use this</button></div>`).join('')}</div></details>`:''}`;
  $$('input[name=crest-mode]',box).forEach(r=>r.onchange=async()=>{ await saveSettings({crest_mode:r.value, ...(r.value==='none'?{crest_show:false}:{})}); drawCrest(); });
  const sh=$('#crest-show'); if(sh) sh.onchange=async()=>{ await saveSettings({crest_show:sh.checked}); drawCrest(); };
  $$('[data-surface]',box).forEach(cb=>cb.onchange=async()=>{ const s={...c.surfaces, [cb.dataset.surface]:cb.checked}; await saveSettings({crest_surfaces:s}); });
  $$('[data-variant]',box).forEach(b=>b.onclick=async()=>{ b.textContent='working…'; const r=await api('/api/crest/variant',{method:'POST',body:{kind:b.dataset.variant}}); if(r.error) alertNote(r.error); drawCrest(); });
  $$('[data-choose]',box).forEach(b=>b.onclick=async()=>{ await api('/api/crest/choose',{method:'POST',body:{name:b.dataset.choose}}); await saveSettings({}); drawCrest(); });
  const panel=$('#crest-panel');
  if(c.mode==='generate'){
    panel.innerHTML = c.openai ? `<div class="grid two"><div><label>What it should show</label><textarea id="cr-prompt" rows="3" placeholder="a lake, an ore boat, pine trees"></textarea>
        <div class="row" style="margin-top:6px"><button class="btn ghost sm" id="cr-fill">Fill from the project</button><span class="sub" style="margin:0;font-size:12.4px">A starting point from your places and themes. Edit it.</span></div></div>
      <div><label>Style</label><select id="cr-style">${Object.entries(c.styles).map(([k,v])=>`<option value="${k}" title="${esc(v)}">${esc(k)}</option>`).join('')}</select>
        <button class="btn go" id="cr-go" style="margin-top:10px">Draw four</button><p class="sub" id="cr-step" style="margin:6px 0 0;font-size:12.4px">Uses ${esc('gpt-image-1')} on your OpenAI key. Every attempt is kept.</p></div></div>
      <div class="grid four" id="cr-new" style="margin-top:12px"></div>
      <p class="sub" style="font-size:12.4px">A generated mark is a new design, not a family's historical coat of arms, and is labelled that way wherever it shows.</p>`
      : `<div class="note">Generating needs an OpenAI key. Add one in <a href="#/settings/connectors">Connectors</a>, or upload a mark instead.</div>`;
    const f=$('#cr-fill'); if(f) f.onclick=async()=>{ const r=await api('/api/crest/fill',{method:'POST'}); $('#cr-prompt').value=r.prompt; };
    const g=$('#cr-go'); if(g) g.onclick=async()=>{ const prompt=$('#cr-prompt').value.trim(); if(!prompt){ alertNote('Say what it should show first.'); return; }
      g.disabled=true; const r=await api('/api/crest/generate',{method:'POST',body:{prompt, style:$('#cr-style').value}}); if(r.error){ alertNote(r.error); g.disabled=false; return; }
      pollJob(r.job, st=>{ $('#cr-step').textContent=st; }, res=>{ g.disabled=false; $('#cr-step').textContent='Pick one, or draw again.';
        $('#cr-new').innerHTML=res.attempts.filter(a=>res.made.includes(a.name)).map(a=>`<div class="choice" style="padding:8px"><img src="${fileUrl(a.image)}" style="width:100%;aspect-ratio:1;object-fit:contain;background:#fff;border-radius:6px"><button class="btn sm" data-choose-new="${esc(a.name)}" style="margin-top:6px">Use this</button></div>`).join('');
        $$('[data-choose-new]').forEach(b=>b.onclick=async()=>{ await api('/api/crest/choose',{method:'POST',body:{name:b.dataset.chooseNew}}); await saveSettings({}); drawCrest(); }); },
        err=>{ g.disabled=false; $('#cr-step').textContent=err; }); };
  } else if(c.mode==='upload'){
    panel.innerHTML = `<div class="grid three"><div><label>File</label><input type="file" id="cu-file" accept=".png,.jpg,.jpeg,.svg,image/png,image/jpeg,image/svg+xml"></div>
      <div><label>Where it comes from</label><select id="cu-kind"><option value="heirloom">A family heirloom (photographed or scanned)</option><option value="design">A design we made</option><option value="commissioned">Commissioned from someone</option><option value="other">Other</option></select></div>
      <div><label>Note</label><input type="text" id="cu-note" placeholder="Grandpa's signet ring, scanned 2024"></div></div>
      <div class="row" style="margin-top:10px"><button class="btn go" id="cu-go">Upload</button><span class="sub" style="margin:0;font-size:12.4px">PNG, JPG or SVG. The original is kept untouched; background removal and a one-colour version are optional copies.</span></div>`;
    $('#cu-go').onclick=async()=>{ const f=$('#cu-file').files[0]; if(!f){ alertNote('Choose a file.'); return; }
      const fd=new FormData(); fd.append('file',f,f.name); fd.append('provenance',$('#cu-kind').value); fd.append('note',$('#cu-note').value);
      const r=await api('/api/crest/upload',{method:'POST',body:fd}); if(r.error){ alertNote(r.error); return; } await saveSettings({}); drawCrest(); };
  } else panel.innerHTML = '<p class="sub" style="margin:0">No crest. Nothing shows anywhere.</p>';
}

SECTION_BUILDERS.project = function(el){
  const s = settings(), D = S.data, has = n => D.previews.includes(n);
  el.innerHTML='';
  head(el,{kicker:'Project settings', title:'How the record is kept, and where it lives', lede:'Styles, templates, print, the project folder and Drive. Every control writes to the same settings; nothing here blocks any tab.'});
  el.insertAdjacentHTML('beforeend', `
  <div class="grid two">
    <div class="card"><h3>The book</h3><p class="sub">The printed edition.</p>
      <div class="grid two">
        <div><label>Trim size</label><select data-setting="trim">${options(D.trims.map(t=>[t,t.replace('x',' × ')+' in']), s.trim)}</select></div>
        <div><label>Printer</label><select data-setting="printer">${options([['kdp','Amazon KDP'],['ingramspark','IngramSpark'],['lulu','Lulu'],['blurb','Blurb']], s.printer)}</select></div>
      </div></div>
    <div class="card"><h3>How it reads</h3><p class="sub">The same choices as the gallery below, compact.</p>
      <div class="grid two">
        <div><label>Narrator style</label><select data-setting="narrative_style">${options(D.narrative_styles.map(n=>[n.id,n.name]), s.narrative_style)}</select></div>
        <div><label>Writing style · quotes</label><select data-setting="quote_density">${options(D.writing_options.quote_density, s.quote_density)}</select></div>
        <div style="grid-column:1/-1"><label>${esc(L.storyTemplate)}</label><select data-setting="chapter_template">${options(D.chapter_templates.map(t=>[t.id,L.templates[t.id]||t.name]), s.chapter_template)}</select></div>
      </div></div>
  </div>

  <!-- author-only surface: project repo, Drive folder, terminal command -->
  <div class="card author"><h3>Project repo</h3><p class="sub">The folder that holds this lineage. Lineage checks it exists and is a git repo, so every version can be pinned.</p>
    <div class="row"><input type="text" id="repo-path" value="${esc(D.project)}" style="flex:1;min-width:280px"><button class="btn" id="repo-verify">Verify</button></div>
    <div id="repo-out" style="margin-top:12px"></div></div>
  <div class="card author"><h3>Google Drive folder</h3><p class="sub">A Drive folder for sources and finished outputs, and the shared family folder. Paste its ID or URL.</p>
    <div class="row"><input type="text" id="drive-folder" value="${esc(s.drive_folder||'')}" placeholder="https://drive.google.com/drive/folders/…" style="flex:1;min-width:280px">
      <button class="btn" id="drive-verify">Verify</button>
      <span class="pill ${s.drive_verified===true?'ok':(s.drive_folder?'warn':'')}" id="drive-pill">${s.drive_verified===true?'verified':(s.drive_folder?'saved, unverified':'not set')}</span></div>
    <label class="toggle"><input type="checkbox" data-setting="sync_sources" ${s.sync_sources?'checked':''}><div><b>Sync sources · Drive → this computer</b><span>Copies new files from the folder (or its <code>sources</code> subfolder) into the project's <code>sources/</code>. Never deletes, never overwrites a file you already have.</span></div></label>
    <label class="toggle"><input type="checkbox" data-setting="sync_outputs" ${s.sync_outputs?'checked':''}><div><b>Sync outputs · this computer → Drive</b><span>Uploads what's in <code>output/</code> (draft PDFs, narration) to an <code>outputs</code> subfolder. Nothing on Drive is deleted.</span></div></label>
    <div class="row"><button class="btn ghost sm" id="drive-sync">Sync now</button><span id="drive-sync-out" style="font-size:13px;color:var(--ink-3)"></span></div></div>
  <div class="card author"><h3>Terminal</h3><p class="sub">What runs in the terminal drawer (Ctrl+\`). Default: <code>claude</code> in the project folder. Detected CLIs are in Connectors.</p>
    <div class="grid two"><div><label>Command</label><input type="text" data-setting="terminal_command" value="${esc(s.terminal_command||'')}" placeholder="claude"></div>
      <div><label>Working folder</label><input type="text" data-setting="terminal_cwd" value="${esc(s.terminal_cwd||'')}" placeholder="${esc(D.project)}"></div></div></div>

  <div class="card"><h3>Narration voice</h3><p class="sub" id="voice-sub">Loading voices…</p>
    <div class="row"><div style="flex:1;min-width:220px"><select id="voice"></select></div><button class="btn ghost" id="voice-play">Preview</button><audio id="voice-audio"></audio></div>
    <p class="sub" style="margin:8px 0 0;font-size:12.4px">The default for every ${L.story}; any ${L.story} can override it on the Stories tab.</p></div>
  <div class="card"><h3>${esc(L.storyTemplate)}s</h3><p class="sub">Real pages, rendered from the Typst template. Click one for a larger look and its sections.</p>
    <div class="grid four">${D.chapter_templates.map(t=>`<div class="choice" data-choice-for="chapter_template" data-id="${t.id}" data-on="${s.chapter_template===t.id?1:0}">
      ${has('tpl-'+t.id+'.png')?`<img class="thumb" src="/previews/tpl-${t.id}.png" alt="">`:`<div class="thumb" style="display:grid;place-items:center;color:var(--ink-3);font-size:12px">no preview yet</div>`}
      <h4>${esc(L.templates[t.id]||t.name)}</h4><p>${esc(t.blurb)}</p>
      <p style="margin-top:8px"><button class="btn ghost sm" data-preview="${t.id}">Larger preview</button></p></div>`).join('')}</div></div>
  <div class="card"><h3>Narrator style</h3><p class="sub">One invented example passage, in each voice, so the difference is visible. It isn't from your project.</p>
    <div class="grid two">${D.narrative_styles.map(n=>`<div class="choice" data-choice-for="narrative_style" data-id="${n.id}" data-on="${s.narrative_style===n.id?1:0}">
      <h4>${esc(n.name)}</h4><p>${esc(n.blurb)}</p><p class="voice">${esc(D.voice_samples[n.id])}</p></div>`).join('')}</div></div>
  <div class="card"><h3>Writing style</h3><p class="sub">How the prose sits on the page.</p>
    <div class="grid four">
      <div><label>Quote density</label><select data-setting="quote_density">${options(D.writing_options.quote_density, s.quote_density)}</select></div>
      <div><label>Section-break ornament</label><select data-setting="ornament">${options(D.writing_options.ornament, s.ornament)}</select></div>
      <div><label>${esc(L.Story)} opener</label><select data-setting="opener">${options(D.writing_options.opener, s.opener)}</select></div>
      <div><label>Bridges in drafts</label><label class="toggle" style="padding:6px 0"><input type="checkbox" data-setting="bridges_in_drafts" ${s.bridges_in_drafts?'checked':''}><div><b>Print highlighted</b><span>The final build refuses unapproved bridges either way.</span></div></label></div>
    </div></div>
  <div class="card"><h3>Photographs and illustrations</h3><p class="sub">The look for generated illustrations.</p>
    <div class="note" style="margin-bottom:14px"><b>Standing rule:</b> generated images are always captioned as illustrations ("as the family told it", "illustration") and listed apart from the real photographs. They never pass as records.</div>
    <div class="grid five">${D.photo_styles.map(p=>`<div class="choice" data-choice-for="photo_style" data-id="${p.id}" data-on="${s.photo_style===p.id?1:0}">
      ${has('photo-'+p.id+'.png')?`<img class="swatch" src="/previews/photo-${p.id}.png" alt="">`:''}<h4>${esc(p.name)}</h4><p>${esc(p.blurb)}</p></div>`).join('')}</div></div>
  <div class="card"><h3>Where things are</h3><p class="sub">Resolved paths on this machine.</p>
    <dl class="kv mono">${Object.entries(D.paths).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl></div>`);
  bindSettingInputs(el);
  loadVoices();
  $$('[data-choice-for]', el).forEach(c=>c.onclick=e=>{ if(e.target.closest('[data-preview]')) return; saveSettings({[c.dataset.choiceFor]: c.dataset.id}); });
  $$('[data-preview]', el).forEach(b=>b.onclick=()=>templatePreview(b.dataset.preview));
  $('#repo-verify').onclick = verifyRepo;
  $('#drive-verify').onclick = async ()=>{ const p=$('#drive-pill'); p.className='pill'; p.textContent='checking…';
    const r = await api('/api/drive/verify',{method:'POST', body:{folder:$('#drive-folder').value}});
    p.className='pill '+(r.ok===true?'ok':(r.ok===null?'warn':'bad')); p.textContent=r.detail; S.data.state.settings.drive_folder=$('#drive-folder').value; };
  $('#drive-sync').onclick = ()=>runJob('sync', st=>{$('#drive-sync-out').textContent=st;}, r=>{
    $('#drive-sync-out').textContent=`downloaded ${r.downloaded.length}, uploaded ${r.uploaded.length}, skipped ${r.skipped.length}`; }, err=>{$('#drive-sync-out').textContent=err;});
  verifyRepo();
};
function confirmReplace(){ const ta=$('#set-summary'); if(ta.dataset.ok==='1') return true; ta.dataset.ok='1'; alertNote('You already have a summary. Click "Draft" again to replace it with a fresh draft.'); return false; }
function templatePreview(id){
  const t=S.data.chapter_templates.find(x=>x.id===id);
  openModal(L.templates[id]||t.name, `<div class="grid two" style="align-items:start">
    ${S.data.previews.includes('tpl-'+id+'.png')?`<img src="/previews/tpl-${id}.png" style="width:100%;border:1px solid var(--line);border-radius:8px;background:#fff">`:'<div class="note">No preview yet: run <code>make previews</code> in app/.</div>'}
    <div><p>${esc(t.blurb)}</p><h3 style="margin:16px 0 6px;font-size:15px">Sections</h3><ol>${t.sections.map(x=>`<li>${esc(x)}</li>`).join('')}</ol>
    <button class="btn go" id="tpl-use">Use this template</button></div></div>`);
  $('#tpl-use').onclick=()=>{ saveSettings({chapter_template:id}); closeOverlay(); };
}
async function verifyRepo(){
  const out=$('#repo-out'); out.innerHTML='<span class="pill">checking…</span>';
  const path=$('#repo-path').value;
  const r = await api('/api/repo/verify',{method:'POST', body:{path}});
  if(!r.exists){ out.innerHTML='<span class="pill bad">folder does not exist</span>'; return; }
  if(r.is_dir===false){ out.innerHTML='<span class="pill bad">not a folder</span>'; return; }
  const useBtn = path!==S.data.project ? `<button class="btn ghost sm" id="repo-use">Use this folder as the project</button>` : '';
  if(r.git===false){ out.innerHTML=`<div class="row"><span class="pill warn">not a git repo</span><button class="btn sm" id="repo-init">git init</button>${useBtn}</div>`;
    $('#repo-init').onclick=async()=>{ await api('/api/repo/init',{method:'POST',body:{path}}); verifyRepo(); }; }
  else if(r.git===null){ out.innerHTML=`<span class="pill warn">${esc(r.detail)}</span> ${useBtn}`; }
  else out.innerHTML=`<div class="row"><span class="pill ok">git repo</span><span class="pill">${esc(r.branch)}</span>
      <span class="pill ${r.remote?'':'warn'}">${r.remote?'origin · '+esc(r.remote):'no remote'}</span>
      <span class="pill ${r.dirty?'warn':'ok'}">${r.dirty?r.dirty+' uncommitted change'+(r.dirty>1?'s':''):'clean'}</span>${useBtn}</div>`;
  const u=$('#repo-use'); if(u) u.onclick=async()=>{ const res=await api('/api/project',{method:'POST',body:{path}});
    if(res.ok){ S.data = await api('/api/bootstrap'); $('#proj').textContent=S.data.project; S.built={}; route(); alertNote('Project switched.'); } else alertNote(res.detail); };
}


async function loadVoices(){
  const r = await api('/api/voices'); S.voices=r.voices; const s=settings();
  $('#voice-sub').textContent = r.live ? 'Live from your ElevenLabs account.' : (r.voices.length ? 'Demo voices.' : 'No voices yet. Add an ElevenLabs key in Connectors to choose one and hear previews.');
  $('#voice').innerHTML = r.voices.map(v=>`<option value="${esc(v.voice_id)}" ${s.voice_id===v.voice_id?'selected':''}>${esc(v.name)}</option>`).join('');
  $('#voice').onchange=e=>saveSettings({voice_id:e.target.value, voice_name:e.target.selectedOptions[0].textContent});
  $('#voice-play').onclick=()=>{ const v=S.voices.find(x=>x.voice_id===$('#voice').value);
    if(!v||!v.preview_url){ alertNote(r.live?'This voice has no preview sample.':'Previews need an ElevenLabs key.'); return; }
    const a=$('#voice-audio'); a.src=v.preview_url; a.play(); };
}


/* ------------------------------------------------------------------ Connectors */
/* author-only surface: keys, OAuth, agent CLIs. */
SECTION_BUILDERS.connectors = async function(el){
  el.innerHTML='';
  head(el,{kicker:'Connectors', title:'Services and tools', lede:"Keys are checked against the real service and stored in ~/.lineage/config.json (chmod 600) on this machine. If a card isn't wired up, it says so."});
  el.insertAdjacentHTML('beforeend','<div class="grid three" id="conn"><div class="card">Loading…</div></div>');
  const c = await api('/api/connectors');
  const keyCard=(id)=>{ const P=S.data.providers[id], m=c.keys[id];
    return `<div class="card author"><h3>${esc(P.label)}</h3><p class="sub">Used for: ${esc(P.use)}</p>
      <div class="row" style="margin-bottom:8px"><span class="pill ${m?'ok':''}" id="pill-${id}">${m?'saved · '+esc(m):'not connected'}</span></div>
      <input type="password" id="in-${id}" placeholder="${m?'replace the key':'paste a key'}">
      <div class="row" style="margin-top:10px"><button class="btn sm" data-connect="${id}">${m?'Replace':'Connect'}</button>
      ${m?`<button class="btn ghost sm" data-recheck="${id}">Check again</button><button class="btn ghost sm" data-disconnect="${id}">Disconnect</button>`:''}</div></div>`; };
  const d=c.drive;
  $('#conn').innerHTML = `
    <div class="card author"><h3>Google Drive</h3><p class="sub">Used for: source and output sync, the shared family folder. Token stored in ~/.lineage/, never in the project.</p>
      <div class="row" style="margin-bottom:10px"><span class="pill ${d.connected?'ok':''}">${d.connected?(d.can_read_folder?'connected · can read the folder':'connected · device flow (files Lineage created only)'):'not connected'}</span></div>
      <details ${d.client_configured?'':'open'}><summary style="cursor:pointer;font-size:13px;color:var(--ink-2)">OAuth client ${d.client_configured?'(saved)':'— needed first'}</summary>
        <p class="sub" style="margin:8px 0">Create a <b>Desktop app</b> OAuth client in Google Cloud Console (APIs &amp; Services → Credentials) with the Drive API enabled, then paste it here.</p>
        <input type="text" id="g-id" placeholder="client ID"><div style="height:8px"></div><input type="password" id="g-secret" placeholder="client secret">
        <div class="row" style="margin-top:8px"><button class="btn ghost sm" id="g-save">Save client</button></div></details>
      <div class="row" style="margin-top:12px"><button class="btn sm" id="g-device" ${d.client_configured?'':'disabled'}>Connect (device code)</button>
        <button class="btn ghost sm" id="g-browser" ${d.client_configured?'':'disabled'}>Browser sign-in</button>${d.connected?'<button class="btn ghost sm" id="g-disc">Disconnect</button>':''}</div>
      <div id="g-out" class="note" style="margin-top:10px;display:none"></div>
      <p class="sub" style="margin:10px 0 0;font-size:12.4px">Device code only sees files Lineage itself created: fine for uploading outputs, not for reading an existing folder. Browser sign-in can read the folder.</p></div>
    <div class="card author"><h3>GitHub</h3><p class="sub">Used for: the lineage's repo.</p>
      <div class="row" style="margin-bottom:8px"><span class="pill ${c.gh.logged_in?'ok':(c.gh.installed?'warn':'')}">${c.gh.installed?(c.gh.logged_in?'gh CLI · '+esc(c.gh.account||'signed in'):'gh CLI found, not signed in'):'gh CLI not found'}</span>
      <span class="pill ${c.keys.github?'ok':''}" id="pill-github">${c.keys.github?'token · '+esc(c.keys.github):'no token'}</span></div>
      <input type="password" id="in-github" placeholder="a fine-grained token (optional if gh is signed in)">
      <div class="row" style="margin-top:10px"><button class="btn sm" data-connect="github">${c.keys.github?'Replace':'Save token'}</button>${c.keys.github?'<button class="btn ghost sm" data-disconnect="github">Disconnect</button>':''}
        <button class="btn ghost sm" id="gh-push">Push the lineage repo</button></div>
      <p class="sub" style="margin:10px 0 0;font-size:12.4px">Push runs <code>git push origin HEAD</code> in the project with your existing git credentials.</p></div>
    ${keyCard('anthropic')}${keyCard('openai')}${keyCard('elevenlabs')}
    <div class="card author" style="grid-column:span 2"><h3>Detected on this machine</h3><p class="sub">Agent CLIs on PATH. The one you pick runs in the terminal drawer.</p>
      ${c.clis.length?c.clis.map(x=>`<label class="toggle" style="padding:6px 0"><input type="radio" name="cli" value="${esc(x.command)}" ${c.terminal_command===x.command?'checked':''}><div><b>${esc(x.label)}</b> <span class="pill">${x.kind}</span><span>${esc(x.path)}</span></div></label>`).join(''):'<p class="sub">No agent CLI found on PATH.</p>'}</div>
    <div class="card"><h3>Grok</h3><p class="sub">xAI</p><span class="pill">not wired up</span><p class="sub" style="margin-top:10px">Nothing calls Grok yet. A placeholder, not a connection.</p></div>
    <div class="card"><h3>ChatGPT</h3><p class="sub">OpenAI's app</p><span class="pill">not wired up</span><p class="sub" style="margin-top:10px">Not connected to anything. The OpenAI key above (illustrations) is real; this card is not.</p></div>`;
  $$('[data-connect]', el).forEach(b=>b.onclick=()=>connectKey(b.dataset.connect));
  $$('[data-disconnect]', el).forEach(b=>b.onclick=async()=>{ await api('/api/key',{method:'POST',body:{provider:b.dataset.disconnect, remove:true}}); S.data.keys[b.dataset.disconnect]=''; SECTION_BUILDERS.connectors(el); });
  $$('[data-recheck]', el).forEach(b=>b.onclick=async()=>{ const p=$('#pill-'+b.dataset.recheck); p.className='pill'; p.textContent='checking…';
    const r=await api('/api/key/recheck',{method:'POST',body:{provider:b.dataset.recheck}}); p.className='pill '+(r.ok===true?'ok':(r.ok===null?'warn':'bad')); p.textContent=r.detail; });
  $$('input[name=cli]', el).forEach(r=>r.onchange=()=>{ saveSettings({terminal_command:r.value}); alertNote(`The terminal will run ${r.value}. Press Restart in the terminal drawer.`); });
  $('#g-save').onclick=async()=>{ await api('/api/google/client',{method:'POST',body:{client_id:$('#g-id').value, client_secret:$('#g-secret').value}}); SECTION_BUILDERS.connectors(el); };
  $('#g-device').onclick=googleDevice;
  $('#g-browser').onclick=async()=>{ const r=await api('/api/google/browser-url'); if(r.ok) location.href=r.url; else alertNote(r.detail); };
  const gd=$('#g-disc'); if(gd) gd.onclick=async()=>{ await api('/api/google/disconnect',{method:'POST'}); SECTION_BUILDERS.connectors(el); };
  $('#gh-push').onclick=async()=>{ $('#gh-push').textContent='pushing…'; const r=await api('/api/repo/push',{method:'POST'}); $('#gh-push').textContent='Push the lineage repo'; alertNote(r.detail); };
};
async function connectKey(provider){
  const input=$('#in-'+provider), pill=$('#pill-'+provider); pill.className='pill'; pill.textContent='checking…';
  const r=await api('/api/key',{method:'POST',body:{provider, key:input.value}});
  pill.className='pill '+(r.ok===true?'ok':(r.ok===null?'warn':'bad')); pill.textContent = r.ok===true ? (r.detail+' · '+r.masked) : r.detail;
  if(r.ok!==false){ S.data.keys[provider]=r.masked; input.value=''; } refreshAttention();
}
async function googleDevice(){
  const out=$('#g-out'); out.style.display='block'; out.textContent='asking Google…';
  const r=await api('/api/google/device/start',{method:'POST'}); if(!r.ok){ out.textContent=r.detail; return; }
  out.innerHTML=`Go to <a href="${esc(r.verification_url)}" target="_blank" rel="noopener">${esc(r.verification_url)}</a> and enter <b style="font-family:var(--mono);font-size:16px">${esc(r.user_code)}</b>. Waiting…`;
  const t=setInterval(async()=>{ const p=await api('/api/google/device/poll',{method:'POST'});
    if(p.state==='connected'){ clearInterval(t); alertNote('Google Drive connected.'); SECTION_BUILDERS.connectors($('#set-body')); }
    else if(!['authorization_pending','slow_down','pending'].includes(p.state)){ clearInterval(t); out.textContent='Stopped: '+p.state; } }, (r.interval||5)*1000);
}


/* ------------------------------------------------------------------ Contributors (owner-only management)
   Contributors are people who add material. The family is what the book is about. */
SECTION_BUILDERS.contributors = async function(el){
  el.innerHTML='';
  head(el,{kicker:'Contributors', title:'Who adds to the record', lede:"Contributors add recordings, photos and notes without ever seeing this dashboard. You're the only owner; nothing a contributor sends reaches the book until you've reviewed it."});
  el.insertAdjacentHTML('beforeend', `<div class="note" style="margin-bottom:16px">Invite links only work once the project is hosted. Until then a link is for testing on this computer: the server checks it, and it expires and can be revoked.</div>
    <div class="card"><h3>Add someone</h3><div class="grid four" style="margin-top:10px">
      <div><label>Name</label><input type="text" id="fm-name" placeholder="Aunt May"></div>
      <div><label>Relationship to the family</label><input type="text" id="fm-rel" placeholder="her younger sister"></div>
      <div><label>Email</label><input type="email" id="fm-email" placeholder="may@example.org"></div>
      <div><label>Role</label><select id="fm-role"><option value="contributor">Contributor — adds sources and notes</option><option value="reader">Reader — sees the book and Familypedia</option><option value="editor">Editor — annotates and tags anyone's sources</option></select></div></div>
      <div class="row" style="margin-top:12px"><button class="btn" id="fm-add">Add</button></div></div>
    <div class="card"><h3>Contributors</h3><div id="fm-table"><p class="empty">Loading…</p></div></div>
    <div class="card"><h3>Requests outstanding</h3><p class="sub">What you've asked each contributor (from Home → Request more), with the date and whether it's been answered.</p><div id="fm-asks"><p class="empty">Loading…</p></div></div>
    <div class="card"><h3>Shared folder</h3><p class="sub">Where contributors' files land once the project is hosted: the Drive folder from Project settings.</p><div id="fm-folder"></div></div>
    <div class="card"><h3>Review queue</h3><p class="sub">New contributions from contributors land here first: the file, its summary and suggested name. Accept, or ask a question.</p><div id="fm-queue"></div></div>`);
  $('#fm-add').onclick=async()=>{ const r=await api('/api/family/member',{method:'POST',body:{name:$('#fm-name').value, relationship:$('#fm-rel').value, email:$('#fm-email').value, role:$('#fm-role').value}});
    if(r.error){ alertNote(r.error); return; } ['fm-name','fm-rel','fm-email'].forEach(i=>$('#'+i).value=''); drawFamily(r); };
  drawFamily(await api('/api/family'));
  const df=settings().drive_folder; $('#fm-folder').innerHTML = df ? `<code style="font-size:12.5px">${esc(df)}</code> <span class="pill ${settings().drive_verified?'ok':'warn'}">${settings().drive_verified?'verified':'not verified'}</span>` : '<p class="empty">No Drive folder set. Add one in <a href="#/settings/project">Project settings</a>.</p>';
  const asks=await api('/api/engine/requests'); const box=$('#fm-asks');
  box.innerHTML = asks.length ? `<table><thead><tr><th>To</th><th>About</th><th>Asked</th><th>Status</th><th></th></tr></thead><tbody>${asks.slice().reverse().map(r=>`<tr><td>${esc(r.to_name||'not addressed')}</td><td>${esc(r.title)}</td><td style="white-space:nowrap">${esc(ago(r.made))}</td>
      <td><span class="pill ${r.status==='answered'?'ok':'warn'}">${esc(r.status)}</span></td><td class="links"><button data-rqtoggle="${esc(r.id)}" data-st="${r.status==='answered'?'asked':'answered'}">mark ${r.status==='answered'?'asked':'answered'}</button></td></tr>`).join('')}</tbody></table>` : '<p class="empty">Nothing asked yet. Use "Request more" on Home.</p>';
  $$('[data-rqtoggle]',box).forEach(b=>b.onclick=async()=>{ await api('/api/engine/request/mark',{method:'POST',body:{id:b.dataset.rqtoggle, status:b.dataset.st}}); SECTION_BUILDERS.contributors(el); });
};
function drawFamily(d){
  $('#fm-table').innerHTML = d.members.length ? `<table><thead><tr><th>Name</th><th>Relationship</th><th>Email</th><th>Role</th><th>Status</th><th>Added</th><th style="text-align:right">Contributed</th><th>Invite</th></tr></thead><tbody>
    ${d.members.map(m=>`<tr><td><strong>${esc(m.name)}</strong></td><td>${esc(m.relationship)}</td><td>${esc(m.email)}</td>
      <td><select data-role="${m.id}" style="padding:4px 8px;font-size:12.5px">${d.roles.map(r=>`<option ${m.role===r?'selected':''}>${r}</option>`).join('')}</select></td>
      <td><select data-status="${m.id}" style="padding:4px 8px;font-size:12.5px">${['invited','active','paused'].map(s=>`<option ${m.status===s?'selected':''}>${s}</option>`).join('')}</select></td>
      <td style="white-space:nowrap">${esc(m.added.slice(0,10))}</td><td class="num">${m.contributions}</td>
      <td class="links">${m.invite?`<button data-copy="${esc(m.invite.url)}">copy link</button>${m.email?`<a href="mailto:${esc(m.email)}?subject=${encodeURIComponent('Help with the family record')}&body=${encodeURIComponent('Add what you have here: '+m.invite.url)}">email</a>`:''}<button data-revoke="${m.id}">revoke</button><br><span style="font-size:11.5px;color:var(--ink-3)">expires ${esc(m.invite.expires.slice(0,10))}</span>`:`<button data-invite="${m.id}">make invite link</button>`}</td></tr>`).join('')}
    </tbody></table>` : '<p class="empty">No contributors yet. Add someone above: a relative, a family friend, anyone with material.</p>';
  $('#fm-queue').innerHTML = d.review_queue.length ? '' : '<p class="empty">Nothing waiting. Contributions appear here once contributors can add material (when the project is hosted).</p>';
  $$('[data-invite]').forEach(b=>b.onclick=async()=>drawFamily(await api('/api/family/invite',{method:'POST',body:{member:b.dataset.invite}})));
  $$('[data-revoke]').forEach(b=>b.onclick=async()=>drawFamily(await api('/api/family/revoke',{method:'POST',body:{member:b.dataset.revoke}})));
  $$('[data-copy]').forEach(b=>b.onclick=async()=>{ try{ await navigator.clipboard.writeText(b.dataset.copy); alertNote('Link copied.'); }catch(e){ prompt('Copy the link:', b.dataset.copy); } });
  $$('[data-role]').forEach(s=>s.onchange=async()=>drawFamily(await api('/api/family/member',{method:'POST',body:{id:s.dataset.role, role:s.value}})));
  $$('[data-status]').forEach(s=>s.onchange=async()=>drawFamily(await api('/api/family/member',{method:'POST',body:{id:s.dataset.status, status:s.value}})));
}

