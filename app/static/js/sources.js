/* ================================================================== SOURCES */
const KIND_LABEL={audio:'AUD',video:'VID',image:'IMG',pdf:'PDF',text:'TXT',other:'FILE'};
let srcPoll=null;
BUILDERS.sources = function(el, rest, q={}){
  S.srcQ = q;
  el.innerHTML='';
  head(el,{kicker:'Sources', title:'What the book is made from', lede:'Recordings, scans, letters, documents. Each file is scanned, named, summarized and indexed as it lands. Originals are never modified or renamed on disk.'});
  el.insertAdjacentHTML('beforeend', `
    <div class="drop" id="drop"><p style="font-size:16px;color:var(--ink)">Drop files here</p><p>audio · video · pdf · images · text — scanned in the background, ten at a time is fine</p>
      <div class="row" style="justify-content:center;margin-top:10px"><button class="btn ghost sm" id="pick">Choose files</button><button class="btn ghost sm" id="from-drive">Add from Drive folder</button><button class="btn ghost sm" id="scan-all">Scan unindexed files</button><button class="btn ghost sm" id="show-trash">Trash</button></div>
      <input id="picker" type="file" multiple class="hidden"></div>
    <div class="card"><div class="row" style="margin-bottom:12px">
      <input type="search" id="src-filter" placeholder="Search names, summaries, notes and the text inside" style="max-width:380px">
      <select id="src-sort" style="max-width:190px"><option value="name">Sort: name</option><option value="added">Sort: date added</option><option value="content">Sort: date of content</option><option value="bytes">Sort: size</option><option value="status">Sort: status</option></select>
      <label class="toggle" style="padding:0;margin:0"><input type="checkbox" id="src-group" checked><div><b>Group by kind</b></div></label>
      <span id="src-hfilter"></span><span class="spacer"></span><span class="pill" id="src-count"></span></div>
      <div class="row hidden" id="src-bulk" style="margin-bottom:10px;background:#F3EEE4;border-radius:9px;padding:8px 12px"><b id="src-nsel"></b>
        <button class="btn ghost sm" id="bulk-reingest">Re-ingest</button><button class="btn ghost sm" id="bulk-tag">Tag…</button><button class="btn ghost sm" id="bulk-del">Delete…</button><button class="btn ghost sm" id="bulk-clear">Clear selection</button></div>
      <div id="src-table"><p class="empty">Loading…</p></div></div>`);
  el.querySelector('.head').insertAdjacentHTML('beforeend','<div id="src-queue" style="margin-top:8px"></div>');
  S.sel = new Set();
  $('#bulk-clear').onclick=()=>{ S.sel.clear(); drawSources(); };
  $('#bulk-reingest').onclick=async()=>{ await api('/api/engine/source/bulk',{method:'POST',body:{action:'reingest', rids:[...S.sel]}}); alertNote(`Re-ingesting ${S.sel.size} source(s). Your edits are kept.`); S.sel.clear(); loadSources(); };
  $('#bulk-del').onclick=()=>confirmDelete([...S.sel]);
  $('#bulk-tag').onclick=bulkTag;
  const drop=$('#drop');
  drop.ondragover=e=>{e.preventDefault();drop.classList.add('over')}; drop.ondragleave=()=>drop.classList.remove('over');
  drop.ondrop=e=>{e.preventDefault();drop.classList.remove('over');upload(e.dataTransfer.files)};
  $('#pick').onclick=()=>$('#picker').click(); $('#picker').onchange=e=>upload(e.target.files);
  $('#scan-all').onclick=async()=>{ const r=await api('/api/engine/source/scan-all',{method:'POST'}); alertNote(r.started?`Scanning ${r.started} file(s).`:'Everything is already indexed.'); loadSources(); };
  $('#show-trash').onclick=showTrash;
  $('#from-drive').onclick=()=>{
    if(!settings().drive_folder){ alertNote('No Drive folder yet: set one in Settings → Project settings.'); return; }
    if(!settings().sync_sources){ alertNote('Turn on "Sync sources" in Settings → Project settings, then try again.'); return; }
    $('#from-drive').textContent='syncing…';
    runJob('sync', null, r=>{ $('#from-drive').textContent='Add from Drive folder'; alertNote(`Added ${r.downloaded.length} file(s) from Drive.`); loadSources(); },
      err=>{ $('#from-drive').textContent='Add from Drive folder'; alertNote(err); });
  };
  let t=null; $('#src-filter').oninput=()=>{ clearTimeout(t); t=setTimeout(drawSources,220); };
  ['src-sort','src-group'].forEach(id=>$('#'+id).oninput=drawSources);
  loadSources();
};
async function loadSources(){
  const r=await api('/api/engine/sources'); S.sources=r.sources; drawSources(); processing();
  if(S.srcQ && S.srcQ.open){ const x=S.sources.find(s=>s.rid===S.srcQ.open); S.srcQ.open=null; if(x) editSource(x.id); }
  const busy = S.sources.some(x=>Object.values(x.stages||{}).some(s=>s.state==='running') || (x.rid && !(x.stages||{}).index));
  clearTimeout(srcPoll); if(busy && S.tab==='sources') srcPoll=setTimeout(loadSources, 2000);
}
async function upload(files){
  const fd=new FormData(); [...files].forEach(f=>fd.append('file',f,f.name));
  $('#src-count').textContent='uploading…';
  const r=await api('/api/upload',{method:'POST',body:fd});
  const dup=(r.duplicates||[]).map(d=>`${d.name}: already here, added ${d.added.slice(0,10)}`).join(' · ');
  alertNote(`Added ${(r.saved||[]).length} file(s).${dup?' '+dup:''}`); loadSources();
}
const STAGE_LABEL={ingest:'Saved', extract:'Reading', understand:'Understanding', index:'Indexed', drive:'Drive'};
function stageLine(x){
  const order=['ingest','extract','understand','index'];
  const st=x.stages||{};
  if(!x.rid) return `<span class="pill">not ingested</span> <button class="btn sm" data-scan="${esc(x.id)}">Ingest</button>`;
  const failed=order.find(k=>st[k]&&st[k].state==='failed');
  if(failed) return `<span class="pill bad" title="${esc(st[failed].detail)}">${STAGE_LABEL[failed]} failed</span> <button class="btn sm" data-rescan="${esc(x.rid)}">Retry</button><br><span style="font-size:12px;color:#8E3B2A">${esc(st[failed].detail)}</span>`;
  const chips = order.map(k=>{ const v=st[k]; const cls=!v?'':(v.state==='done'?'ok':(v.state==='running'?'warn':''));
    return `<span class="pill ${cls}" style="padding:2px 7px">${v&&v.state==='running'?STAGE_LABEL[k]+'…':STAGE_LABEL[k]}</span>`; }).join('');
  const notes=[];
  if(st.extract&&st.extract.detail&&/can't read|not installed|no text layer/.test(st.extract.detail)) notes.push(st.extract.detail);
  if(st.understand&&/no Anthropic key/.test(st.understand.detail)) notes.push('Basic summary only: add an Anthropic key in Settings → Connectors, then Re-ingest.');
  return `<div class="row" style="gap:3px">${chips}</div>${notes.map(n=>`<div style="font-size:12px;color:#8A6418;margin-top:3px">${esc(n)}</div>`).join('')}`;
}
function processing(){
  const busy=(S.sources||[]).filter(x=>x.rid && ['extract','understand','index'].some(k=>!x.stages[k] || x.stages[k].state==='running'));
  const box=$('#src-queue'); if(!box) return;
  box.innerHTML = busy.length ? `<span class="pill warn">${busy.length} file${busy.length>1?'s':''} processing</span> <span style="font-size:12.5px;color:var(--ink-3)">${busy.map(x=>{ const k=['extract','understand','index'].find(k=>!x.stages[k]||x.stages[k].state==='running'); return esc(x.display_name)+': '+STAGE_LABEL[k]; }).join(' · ')}</span>` : '';
}
async function drawSources(){
  if(!S.sources) return;
  const q=($('#src-filter').value||'').trim(), sort=$('#src-sort').value, group=$('#src-group').checked;
  let rows=S.sources;
  const hq=S.srcQ||{};
  if(hq.filter==='pending') rows=rows.filter(x=>!x.rid || !((x.stages||{}).index && x.stages.index.state==='done'));
  if(hq.kind) rows=rows.filter(x=>x.kind===hq.kind);
  const fbox=$('#src-hfilter'); if(fbox) fbox.innerHTML = (hq.filter||hq.kind) ? `<span class="pill warn">${hq.filter==='pending'?'showing sources not yet ingested':'showing '+esc(hq.kind)+' sources only'}</span> <a href="#sources" class="btn ghost sm" style="text-decoration:none">Show all</a>` : '';
  if(q){ const r=await api('/api/engine/search?q='+encodeURIComponent(q)); const ids=new Set(r.hits.map(h=>h.id));
    const ql=q.toLowerCase(); rows=rows.filter(x=>ids.has(x.rid) || (x.name+' '+x.kind+' '+x.status).toLowerCase().includes(ql)); }
  rows=rows.slice().sort({name:(a,b)=>a.display_name.localeCompare(b.display_name), added:(a,b)=>b.added.localeCompare(a.added), content:(a,b)=>(a.content_date||'9999').localeCompare(b.content_date||'9999'), bytes:(a,b)=>b.bytes-a.bytes, status:(a,b)=>a.status.localeCompare(b.status)}[sort]);
  $('#src-count').textContent=`${rows.length} of ${S.sources.length}`;
  if(!S.sources.length){ $('#src-table').innerHTML='<p class="empty">No sources yet. Add a recording, a photo or a document to start.</p>'; return; }
  const order=['audio','video','text','pdf','image','other'];
  const groups = group ? order.map(k=>[k, rows.filter(r=>r.kind===k)]).filter(([,v])=>v.length) : [[null, rows]];
  const used = x => x.cited_in ? `<span class="pill ok">used in ${x.cited_in} ${x.cited_in>1?L.stories:L.story}</span>` : '';
  const bulk=$('#src-bulk'); bulk.classList.toggle('hidden', !S.sel.size); $('#src-nsel').textContent=`${S.sel.size} selected`;
  $('#src-table').innerHTML=`<table><thead><tr><th><input type="checkbox" id="sel-all" title="Select all shown"></th><th></th><th>Name</th><th>Kind</th><th>Added</th><th>Content</th><th style="text-align:right">Size · length</th><th>Summary</th><th>Status</th><th></th></tr></thead><tbody>
   ${groups.map(([k,list])=>(k?`<tr class="group"><td colspan="10">${esc(k)} · ${list.length}</td></tr>`:'')+list.map(x=>`<tr>
     <td>${x.rid?`<input type="checkbox" data-sel="${esc(x.rid)}" ${S.sel.has(x.rid)?'checked':''}>`:''}</td>
     <td>${x.thumb?`<img src="${fileUrl(x.thumb)}" style="width:44px;height:44px;object-fit:cover;border-radius:6px;border:1px solid var(--line);display:block">`:`<span class="icon ${x.kind}">${KIND_LABEL[x.kind]}</span>`}</td>
     <td><button class="linkish" data-edit="${esc(x.id)}">${esc(x.display_name)}</button>${x.renamed?' <span class="derived" title="Original: '+esc(x.name)+'">renamed</span>':''}${x.session?` <span class="pill">${esc(x.session)}</span>`:''}${x.added_by&&x.added_by!=='me'?`<br><span class="derived">added by ${esc(x.added_by)}</span>`:''}</td>
     <td style="white-space:nowrap">${esc(x.doc_kind||x.kind)}</td>
     <td style="white-space:nowrap">${esc(x.added.slice(0,10))}</td><td style="white-space:nowrap">${esc(x.content_date||'—')}</td>
     <td class="num">${fmtBytes(x.bytes)}${x.kind==='audio'||x.kind==='video'?'<br>'+fmtDur(x.duration):''}</td>
     <td style="max-width:280px;font-size:12.8px" title="${esc(x.summary)}">${x.summary?esc(x.summary.length>110?x.summary.slice(0,110)+'…':x.summary)+` <span class="derived">${x.summary_by==='me'?'mine':'derived'}</span>`:'<span style="color:var(--ink-3)">—</span>'}</td>
     <td><div class="row" style="gap:4px">${stageLine(x)}${x.in_drive?'<span class="pill ok">in Drive</span>':''}${x.transcribed?'<span class="pill ok">transcribed</span>':(x.transcription==='queued'?'<span class="pill warn">queued for transcription</span>':'')}${used(x)}</div></td>
     <td style="position:relative;white-space:nowrap"><button class="btn ghost sm" data-menu="${esc(x.id)}" aria-label="Actions">⋯</button></td></tr>`).join('')).join('')}
   </tbody></table>`;
  $$('[data-drawer]').forEach(b=>b.onclick=()=>openTranscript(b.dataset.drawer));
  $$('[data-edit]').forEach(b=>b.onclick=()=>editSource(b.dataset.edit));
  $$('[data-sel]').forEach(c=>c.onchange=()=>{ c.checked?S.sel.add(c.dataset.sel):S.sel.delete(c.dataset.sel); drawSources(); });
  const all=$('#sel-all'); all.checked = rows.length>0 && rows.every(x=>!x.rid||S.sel.has(x.rid));
  all.onchange=()=>{ rows.forEach(x=>{ if(x.rid) all.checked?S.sel.add(x.rid):S.sel.delete(x.rid); }); drawSources(); };
  $$('[data-menu]').forEach(b=>b.onclick=e=>{ e.stopPropagation(); openMenu(b, S.sources.find(s=>s.id===b.dataset.menu)); });
  $$('[data-reveal]').forEach(b=>b.onclick=async()=>{ const r=await api('/api/reveal',{method:'POST',body:{path:b.dataset.reveal}}); if(!r.ok) alertNote(r.detail||r.error); });
  $$('[data-rescan]').forEach(b=>b.onclick=async()=>{ await api('/api/engine/source/scan',{method:'POST',body:{rid:b.dataset.rescan}}); alertNote('Re-scanning. Your edits are kept.'); loadSources(); });
  $$('[data-scan]').forEach(b=>b.onclick=async()=>{ await api('/api/engine/source/scan',{method:'POST',body:{path:b.dataset.scan}}); loadSources(); });
  $$('[data-transcribe]').forEach(b=>b.onclick=async()=>{ const r=await api('/api/engine/source/transcribe',{method:'POST',body:{rid:b.dataset.transcribe}}); alertNote(r.error||'Transcription started. It runs once per file.'); loadSources(); });
  $$('[data-del]').forEach(b=>b.onclick=async()=>{
    if(b.dataset.armed!=='1'){ b.dataset.armed='1'; b.textContent='confirm: move to .trash'; b.style.color='#8E3B2A'; setTimeout(()=>{ if(b.isConnected){ b.dataset.armed=''; b.textContent='delete'; b.style.color=''; } },4000); return; }
    await api('/api/engine/source/trash',{method:'POST',body:{rid:b.dataset.del}}); alertNote('Moved to .trash. Restore it from Trash. The Drive copy, if any, is untouched.'); loadSources(); });
}
async function showTrash(){
  const r=await api('/api/engine/trash');
  openDrawer('Trash', r.trash.length ? `<p class="sub">Files here were moved to <code>.trash/</code> in the project. Nothing is ever hard-deleted, and Drive copies are untouched.</p>
    ${r.trash.map(t=>`<div class="row" style="padding:8px 0;border-top:1px solid var(--line)"><span style="flex:1">${esc(t.accepted_name||t.original_name)}</span><button class="btn ghost sm" data-restore="${esc(t.id)}">Restore</button><button class="btn ghost sm" data-purge="${esc(t.id)}" style="color:#8E3B2A">Delete permanently</button></div>`).join('')}` : '<p class="empty">The trash is empty.</p>');
  $$('[data-restore]').forEach(b=>b.onclick=async()=>{ await api('/api/engine/source/trash',{method:'POST',body:{rid:b.dataset.restore, restore:true}}); closeOverlay(); loadSources(); alertNote('Restored and back in the index.'); });
  $$('[data-purge]').forEach(b=>b.onclick=async()=>{
    if(b.dataset.armed!=='1'){ b.dataset.armed='1'; b.textContent='The file will be gone from this computer. Click again.'; return; }
    await api('/api/engine/source/purge',{method:'POST',body:{rid:b.dataset.purge}}); showTrash(); alertNote('Deleted permanently. The file is gone.'); });
}
async function editSource(path, focus){
  const x=S.sources.find(s=>s.id===path);
  if(!x.rid){ openDrawer(x.name, `<p>This file hasn't been scanned yet.</p><button class="btn" id="ed-scan">Scan it now</button>`);
    $('#ed-scan').onclick=async()=>{ await api('/api/engine/source/scan',{method:'POST',body:{path}}); closeOverlay(); loadSources(); }; return; }
  const m=await api('/api/engine/source/meta?rid='+encodeURIComponent(x.rid));
  const d=m.derived||{}; const by=f=>`<span class="derived">${m.by[f]==='me'?'mine':'derived'}</span>`;
  const conf=f=>d.confidence&&d.confidence[f]?` · ${esc(d.confidence[f])} confidence`:'';
  const list=v=>(v||[]).join('; ');
  openDrawer(m.accepted_name||m.original_name, `
    ${m.thumb?`<img src="${fileUrl(m.thumb)}" style="max-width:100%;border-radius:8px;border:1px solid var(--line);margin-bottom:12px">`:''}
    <label>Name</label>
    <div class="grid two" style="margin-bottom:6px"><div class="note" style="padding:8px 10px"><span class="derived">original</span><br>${esc(m.original_name)}</div>
      <div class="note" style="padding:8px 10px"><span class="derived">suggested · ${esc(d.suggested_name_basis||'')}</span><br>${esc(d.suggested_name||'—')}</div></div>
    <div class="row"><input type="text" id="ed-name" value="${esc(m.accepted_name||'')}" placeholder="keep the original name" style="flex:1"><button class="btn ghost sm" id="ed-accept">Accept suggestion</button></div>
    <p class="sub" style="margin:4px 0 14px;font-size:12.4px">The name you accept is metadata (and the Drive copy's name). The file on disk keeps its original name.</p>
    <label>Summary ${by('summary')}${conf('summary')}</label><textarea id="ed-summary" rows="3">${esc(m.summary||'')}</textarea>
    <div class="grid two" style="margin-top:10px">
      <div><label>Kind ${by('doc_kind')}</label><select id="ed-kind">${m.doc_kinds.map(k=>`<option ${m.doc_kind===k?'selected':''}>${k}</option>`).join('')}</select></div>
      <div><label>Date of content ${by('date_range')}${conf('date_range')}</label><input type="text" id="ed-date" value="${esc(m.date_range||'')}"></div>
      <div><label>People ${by('people')}${conf('people')}</label><input type="text" id="ed-people" value="${esc(list(m.people))}"></div>
      <div><label>Places ${by('places')}${conf('places')}</label><input type="text" id="ed-places" value="${esc(list(m.places))}"></div></div>
    <p class="sub" style="margin:6px 0 14px;font-size:12.4px">Derived by ${esc(d.method||'—')}. Nothing derived is presented as fact; anything you change here is marked as yours and wins over a re-scan.</p>
    <h4 style="margin:6px 0">Your notes <span class="derived">stated by me</span></h4>
    <div class="grid two">
      <div><label>What is this?</label><input type="text" id="ed-what" value="${esc((m.fields||{}).what||'')}" placeholder="Back of a photo, Mom's handwriting"></div>
      <div><label>Who is in it / by it?</label><input type="text" id="ed-who" value="${esc((m.fields||{}).who||'')}" placeholder="Aunt May, writing to Ruth"></div>
      <div><label>What is it about?</label><input type="text" id="ed-about" value="${esc((m.fields||{}).about||'')}" placeholder="The farm after Homer died"></div>
      <div><label>Where did it come from?</label><input type="text" id="ed-prov" value="${esc((m.fields||{}).provenance||'')}" placeholder="Aunt Ruth's album, scanned 2019"></div></div>
    <label style="margin-top:10px">Notes</label><textarea id="ed-notes" rows="3">${esc(m.notes||'')}</textarea>
    <label class="toggle"><input type="checkbox" id="ed-drive" ${m.store_in_drive?'checked':''} ${m.drive_connected?'':'disabled'}><div><b>Store in Google Drive</b><span>${m.drive_connected?'Uploads under a folder for its kind, with the accepted name.':'Connect Google Drive in Settings → Connectors. The file is fully usable locally either way.'}</span></div></label>
    <div class="row" style="margin:6px 0 16px"><button class="btn go" id="ed-save">Save</button><button class="btn ghost" id="ed-rescan">Save and re-scan</button></div>
    <details><summary style="cursor:pointer;font-weight:600">Extracted text · ${esc(m.text_source||'none')} ${by('text')}</summary>
      ${m.extract_note?`<p class="note" style="margin-top:8px">${esc(m.extract_note)}</p>`:''}
      ${m.vision?`<p class="sub" style="margin-top:8px"><b>Vision description (inferred):</b> ${esc(m.vision.text)}</p>`:''}
      <textarea id="ed-text" rows="10" style="margin-top:8px;font-family:var(--mono);font-size:12.4px">${esc(m.extracted_text||'')}</textarea>
      <div class="row" style="margin-top:6px"><button class="btn ghost sm" id="ed-text-save">Save my text</button><span class="sub" style="margin:0;font-size:12.4px">Paste a transcription here when there's no text layer.</span></div></details>
    <details style="margin-top:12px"><summary style="cursor:pointer;font-weight:600">History</summary>
      <ul style="font-size:13px">${(m.history||[]).map(h=>`<li>${esc(h.at.replace('T',' ').slice(0,16))} · ${esc(h.by)} · ${esc(h.event)}${h.fields?' ('+esc(h.fields.join(', '))+')':''}</li>`).join('')}</ul></details>
    <details style="margin-top:12px"><summary style="cursor:pointer;font-weight:600">Links to · ${(m.links_to||[]).length}</summary>
      <ul style="font-size:13px">${(m.links_to||[]).map(l=>`<li>${esc(l.type)} · ${esc(l.label)}</li>`).join('')}</ul></details>`);
  $('#ed-accept').onclick=()=>{ $('#ed-name').value=d.suggested_name||''; };
  if(focus==='name'){ $('#ed-name').focus(); $('#ed-name').select(); }
  const split=v=>v.split(/;\s*/).map(s=>s.trim()).filter(Boolean);
  const collect=()=>{ const p={rid:m.id, notes:$('#ed-notes').value, what:$('#ed-what').value, who:$('#ed-who').value, about:$('#ed-about').value, provenance:$('#ed-prov').value, store_in_drive:$('#ed-drive').checked};
    const cmp=(id,key,val,orig)=>{ if(JSON.stringify(val)!==JSON.stringify(orig)) p[key]=val; };
    cmp('ed-name','accepted_name',$('#ed-name').value.trim(), m.accepted_name||'');
    cmp('ed-summary','summary',$('#ed-summary').value, m.summary||'');
    cmp('ed-kind','doc_kind',$('#ed-kind').value, m.doc_kind);
    cmp('ed-date','date_range',$('#ed-date').value, m.date_range||'');
    cmp('ed-people','people',split($('#ed-people').value), m.people||[]);
    cmp('ed-places','places',split($('#ed-places').value), m.places||[]);
    return p; };
  $('#ed-save').onclick=async()=>{ await api('/api/engine/source/edit',{method:'POST',body:collect()}); closeOverlay(); loadSources(); alertNote('Saved. Your changes are marked as yours.'); };
  $('#ed-rescan').onclick=async()=>{ await api('/api/engine/source/edit',{method:'POST',body:{...collect(), rescan:true}}); closeOverlay(); loadSources(); };
  $('#ed-text-save').onclick=async()=>{ await api('/api/engine/source/edit',{method:'POST',body:{rid:m.id, text:$('#ed-text').value, rescan:true}}); alertNote('Your text is saved and the summary will be redone from it.'); };
}
function openMenu(btn, x){
  closeMenu();
  const items = [
    ['Open', ()=>api('/api/reveal',{method:'POST',body:{path:x.id}}).then(r=>{ if(!r.ok) alertNote(r.detail||r.error); })],
    ['Copy path', async()=>{ const pth=S.data.project+'/'+x.id; try{ await navigator.clipboard.writeText(pth); alertNote('Path copied.'); }catch(e){ alertNote(pth); } }],
    ...(x.drive_url?[['Open in Drive', ()=>window.open(x.drive_url,'_blank','noopener')]]:[]),
    ...(x.transcribed?[['Transcript', ()=>openTranscript(x.id)]]:[]),
    ['Rename', ()=>editSource(x.id, 'name')],
    ['Edit details', ()=>editSource(x.id)],
    [x.rid?'Re-ingest':'Ingest', async()=>{ await api('/api/engine/source/scan',{method:'POST',body:x.rid?{rid:x.rid}:{path:x.id}}); alertNote(x.rid?'Re-ingesting. Your edits are kept.':'Ingesting.'); loadSources(); }],
    ...(x.transcription==='queued'?[['Transcribe', async()=>{ const r=await api('/api/engine/source/transcribe',{method:'POST',body:{rid:x.rid}}); alertNote(r.error||'Transcription started. It runs once per file.'); loadSources(); }]]:[]),
    ...(x.rid?[['Delete…', ()=>confirmDelete([x.rid])]]:[]),
  ];
  const m=document.createElement('div'); m.id='row-menu';
  m.style.cssText='position:absolute;right:0;top:34px;z-index:30;background:var(--card);border:1px solid var(--line);border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.12);padding:5px;min-width:170px';
  m.innerHTML=items.map(([l],i)=>`<button data-mi="${i}" style="all:unset;display:block;cursor:pointer;padding:7px 11px;border-radius:7px;font-size:13.5px;width:calc(100% - 22px)${l.startsWith('Delete')?';color:#8E3B2A':''}">${esc(l)}</button>`).join('');
  btn.parentElement.appendChild(m);
  $$('[data-mi]', m).forEach(b=>{ b.onmouseenter=()=>b.style.background='#F0EADF'; b.onmouseleave=()=>b.style.background=''; b.onclick=e=>{ e.stopPropagation(); closeMenu(); items[+b.dataset.mi][1](); }; });
  setTimeout(()=>document.addEventListener('click', closeMenu, {once:true}), 0);
}
function closeMenu(){ const m=$('#row-menu'); if(m) m.remove(); }
async function confirmDelete(rids){
  const r=await api('/api/engine/source/consequences?rid='+encodeURIComponent(rids.join(',')));
  const cited=r.items.filter(i=>i.stories.length), drive=r.items.filter(i=>i.in_drive);
  openModal(rids.length>1?`Delete ${rids.length} sources?`:`Delete ${(r.items[0]||{}).name||'this source'}?`, `
    <p>The original${rids.length>1?'s move':' moves'} to <code>.trash/</code> in the project with ${rids.length>1?'their':'its'} details, and leave${rids.length>1?'':'s'} the index. You can restore from Trash.</p>
    ${cited.length?`<div class="note" style="margin-bottom:12px"><b>Cited:</b> ${cited.map(i=>`${esc(i.name)} is cited in ${i.stories.length} ${i.stories.length>1?L.stories:L.story} (${i.stories.map(s=>esc(s.title)).join(', ')})`).join('; ')}. Those ${L.stories} will be marked stale, not left with broken citations.</div>`:''}
    ${drive.length?`<label class="toggle"><input type="checkbox" id="del-drive"><div><b>Also delete the Google Drive cop${drive.length>1?'ies':'y'} (${drive.length})</b><span>Off by default: deleting here leaves Drive alone.</span></div></label>
      <label class="toggle hidden" id="del-drive-confirm-row"><input type="checkbox" id="del-drive-confirm"><div><b>Yes, delete from Drive too</b><span>This removes the Drive file for everyone who can see the folder.</span></div></label>`:''}
    <div class="row" style="margin-top:14px"><button class="btn go" id="del-go">${rids.length>1?`Delete ${rids.length} sources`:'Delete'}</button><button class="btn ghost" id="del-cancel">Cancel</button></div>`);
  const dd=$('#del-drive'); if(dd) dd.onchange=()=>$('#del-drive-confirm-row').classList.toggle('hidden', !dd.checked);
  $('#del-cancel').onclick=closeOverlay;
  $('#del-go').onclick=async()=>{
    const delDrive = !!(dd && dd.checked && $('#del-drive-confirm').checked);
    if(dd && dd.checked && !delDrive){ alertNote('Tick "Yes, delete from Drive too" to confirm, or untick the Drive option.'); return; }
    await api('/api/engine/source/bulk',{method:'POST',body:{action:'delete', rids, delete_drive:delDrive}});
    closeOverlay(); S.sel.clear(); loadSources();
    undoToast(`${rids.length>1?rids.length+' sources':'Source'} moved to .trash${delDrive?' (Drive copies deleted)':' (Drive untouched)'}.`, async()=>{
      for(const rid of rids) await api('/api/engine/source/trash',{method:'POST',body:{rid, restore:true}}); loadSources(); alertNote('Restored.'); });
  };
}
function undoToast(msg, undo){
  const n=document.createElement('div'); n.className='note';
  n.style.cssText='position:fixed;bottom:18px;left:50%;transform:translateX(-50%);z-index:60;box-shadow:0 6px 20px rgba(0,0,0,.15);display:flex;gap:12px;align-items:center';
  n.innerHTML=`<span>${esc(msg)}</span><button class="btn sm">Undo</button>`;
  n.querySelector('button').onclick=()=>{ n.remove(); undo(); };
  document.body.appendChild(n); setTimeout(()=>n.remove(), 12000);
}
async function bulkTag(){
  openModal(`Tag ${S.sel.size} source${S.sel.size>1?'s':''}`, `<p class="sub">Adds to each source's details, marked as yours.</p>
    <div class="grid three"><div><label>Person</label><input type="text" id="bt-person" placeholder="Aunt May"></div><div><label>Place</label><input type="text" id="bt-place" placeholder="Duluth, Minnesota"></div><div><label>Date or range</label><input type="text" id="bt-date" placeholder="1950–1955"></div></div>
    <div class="row" style="margin-top:14px"><button class="btn go" id="bt-go">Apply to ${S.sel.size}</button></div>`);
  $('#bt-go').onclick=async()=>{ await api('/api/engine/source/bulk',{method:'POST',body:{action:'tag', rids:[...S.sel], person:$('#bt-person').value.trim(), place:$('#bt-place').value.trim(), date:$('#bt-date').value.trim()}}); closeOverlay(); loadSources(); alertNote('Tagged.'); };
}
async function openTranscript(id, atSeconds=null){
  const d=await api('/api/engine/source?id='+encodeURIComponent(id));
  const media = d.kind==='audio'||d.kind==='video';
  openDrawer(id.split('/').pop(), d.transcribed ? `
    ${media?`<audio id="dr-audio" controls preload="metadata" src="${fileUrl(id)}" style="width:100%;margin-bottom:14px"></audio>`:''}
    <h4 style="margin:0 0 6px">Session ${esc(d.session)}</h4>
    <dl class="kv" style="margin-bottom:18px">${Object.entries(d.header).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>
    ${d.topics.length?`<h4 style="margin:0 0 6px">Topics</h4><div class="ts" style="margin-bottom:18px">${d.topics.map(t=>`<button data-t="${t.t}">${t.t}</button><span>${esc(t.title)}</span>`).join('')}</div>`:''}
    <h4 style="margin:0 0 6px">Jump to</h4>
    <div class="ts">${d.paragraphs.map(p=>`<button data-s="${p.seconds}">${p.t}</button><span class="${atSeconds===p.seconds?'hl':''}" ${atSeconds===p.seconds?'id="dr-hit"':''}><span class="spk">${esc(p.speaker)}</span> ${esc(p.text)}</span>`).join('')}</div>`
    : '<p>Not transcribed yet.</p>');
  const jump=sec=>{ const a=$('#dr-audio'); if(!a){ alertNote('Jumping needs the recording itself; this source is text.'); return; } a.currentTime=sec; a.play(); };
  $$('.drawer [data-s]').forEach(b=>b.onclick=()=>jump(+b.dataset.s));
  $$('.drawer [data-t]').forEach(b=>b.onclick=()=>{ const [h,m,s]=b.dataset.t.split(':').map(Number); jump(h*3600+m*60+s); });
  const hit=$('#dr-hit'); if(hit) hit.scrollIntoView({block:'center'});
}
/* open the transcript at a citation like "[S1 00:00:05]" */
async function openCitation(cite){
  const m = /\[?(S\d+) (\d\d):(\d\d):(\d\d)/.exec(cite||''); if(!m){ alertNote('No transcript line for this citation.'); return; }
  if(!S.sources){ const r=await api('/api/engine/sources'); S.sources=r.sources; }
  const src = S.sources.find(x=>x.session===m[1]);
  const secs = (+m[2])*3600+(+m[3])*60+(+m[4]);
  if(src) openTranscript(src.id, secs);
  else alertNote(`Session ${m[1]} has no recording in sources/ yet.`);
}

