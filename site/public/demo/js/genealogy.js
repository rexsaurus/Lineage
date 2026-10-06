/* ================================================================== GENEALOGY
   The tree is built from the sources, never hand-entered: every link carries the passage that
   establishes it, and people without one float unattached rather than being guessed into place.
   My corrections (merges, links, tiers, notes) are kept apart and survive every rebuild. */
const G = {view:'tree', layout:'all', focus:null, sel:null, vb:null, data:null};
const G_TIER = {documented:'documented', told:'told', lore:'family lore', unconfirmed:'unconfirmed'};
BUILDERS.genealogy = async function(el, rest, q={}){
  el.innerHTML='';
  head(el,{kicker:'Genealogy', title:'The family tree, from the evidence', lede:'Every link points at the words that establish it. Nothing is inferred from surnames, dates or photographs; anyone without evidence floats unattached until something connects them.'});
  el.insertAdjacentHTML('beforeend', `<div class="card"><div class="row">
      <div class="row" role="tablist" style="gap:4px"><button class="btn sm" data-gview="tree" role="tab">Tree</button><button class="btn ghost sm" data-gview="cast" role="tab">Cast</button></div>
      <select id="g-layout" style="max-width:190px" aria-label="Layout"><option value="all">Everyone connected</option><option value="desc">Descendants</option><option value="anc">Ancestors</option><option value="hour">Hourglass</option></select>
      <select id="g-focus" style="max-width:220px" aria-label="Centre on"></select>
      <span class="spacer"></span>
      <button class="btn go sm" id="g-rebuild">Rebuild from sources</button><button class="btn ghost sm hidden" id="g-review">Review the rebuild</button>
      <button class="btn ghost sm" id="g-import">Import GEDCOM</button><input type="file" id="g-import-in" accept=".ged,.gedcom,text/plain" class="hidden">
      <button class="btn ghost sm" id="g-ged">GEDCOM</button><button class="btn ghost sm" id="g-svg">SVG</button><button class="btn ghost sm" id="g-png">PNG</button><button class="btn ghost sm" id="g-print">Print chart</button></div>
      <p class="sub" id="g-note" style="margin:10px 0 0"></p></div>
    <div id="g-body"><p class="empty">Loading…</p></div>`);
  G.view = q.view==='cast' ? 'cast' : 'tree';
  if(q.focus) G.focus = q.focus;
  $$('[data-gview]').forEach(b=>b.onclick=()=>{ G.view=b.dataset.gview; drawGenealogy(); });
  $('#g-layout').onchange=e=>{ G.layout=e.target.value; G.vb=null; drawGenealogy(); };
  $('#g-focus').onchange=e=>{ G.focus=e.target.value; G.vb=null; drawGenealogy(); };
  $('#g-rebuild').onclick=rebuildTree;
  $('#g-review').onclick=reviewRebuild;
  $('#g-import').onclick=()=>$('#g-import-in').click();
  $('#g-import-in').onchange=async e=>{ const f=e.target.files[0]; if(!f) return; const text=await f.text();
    G.data=await api('/api/engine/genealogy/import',{method:'POST',body:{text, filename:f.name}}); alertNote('Imported. Everything from the file is marked unconfirmed, with the file as its origin.'); drawGenealogy(); };
  $('#g-ged').onclick=async()=>{ const t=await (await fetch('/api/engine/genealogy.ged',{headers:{'X-Lineage-Token':TOKEN}})).text(); download('lineage.ged', new Blob([t],{type:'text/plain'})); };
  $('#g-svg').onclick=()=>{ const s=treeSvg(true); if(s) download('family-tree.svg', new Blob([s],{type:'image/svg+xml'})); };
  $('#g-png').onclick=()=>{ const s=treeSvg(true); if(s) svgToPng(s,'family-tree.png'); };
  $('#g-print').onclick=()=>{ const s=treeSvg(true); if(s) printable('Family tree', `<h1>${esc(S.data.identity.display_title)}</h1><p><small>Family tree from the evidence · line style shows how sure each link is</small></p>${s}`); };
  await loadTree();
  if(q.review) reviewRebuild();
};
async function loadTree(){ G.data = await api('/api/engine/genealogy'); drawGenealogy(); }
function gName(id){ const p=G.data.people.find(x=>x.id===id); return p ? (p.name||id) : id.replace(/-/g,' '); }
function drawGenealogy(){
  const d=G.data;
  $$('[data-gview]').forEach(b=>{ b.className='btn sm'+(b.dataset.gview===G.view?'':' ghost'); b.setAttribute('aria-selected', b.dataset.gview===G.view); });
  $('#g-review').classList.toggle('hidden', !d.pending);
  $('#g-note').innerHTML = (d.applied?`Last rebuild applied ${esc(ago(d.applied))}${d.note?' · '+esc(d.note):''}.`:'No rebuild applied yet. "Rebuild from sources" reads the material and proposes a tree for you to review.')
    + (d.pending?' <b>A rebuild is waiting for your review.</b>':'') + (d.conflicts.length?` <span class="pill warn">${d.conflicts.length} contradiction${d.conflicts.length>1?'s':''} kept</span>`:'');
  if(!d.people.length){ $('#g-focus').innerHTML='<option>No one yet</option>'; $('#g-focus').disabled=true; $('#g-body').innerHTML='<div class="card"><p class="empty">No people yet. They appear as sources are read; then "Rebuild from sources" links them with evidence.</p></div>'; return; }
  const linked = new Set(d.links.flatMap(l=>[l.a,l.b]));
  if(!G.focus || !d.people.some(p=>p.id===G.focus)) G.focus = (d.subject && linked.has(d.subject)) ? d.subject : ([...linked][0] || d.people[0].id);
  $('#g-focus').innerHTML = d.people.slice().sort((a,b)=>(a.name||'').localeCompare(b.name||'')).map(p=>`<option value="${esc(p.id)}" ${p.id===G.focus?'selected':''}>Centre on ${esc(p.name||p.id)}</option>`).join('');
  $('#g-layout').value=G.layout; $('#g-layout').disabled = G.view==='cast'; $('#g-focus').disabled = G.view==='cast';
  if(G.view==='cast') return drawCast();
  $('#g-body').innerHTML = `<div class="gwrap"><div>
      <div class="gcanvas" id="g-canvas"><div class="zoom"><button class="btn ghost sm" id="gz-in" aria-label="Zoom in">+</button><button class="btn ghost sm" id="gz-out" aria-label="Zoom out">−</button><button class="btn ghost sm" id="gz-fit" aria-label="Fit">fit</button></div></div>
      <div class="legend">${Object.entries(G_TIER).map(([k,v])=>`<span><svg width="30" height="8"><line x1="0" y1="4" x2="30" y2="4" class="glink ${k}"/></svg>${esc(v)}</span>`).join('')}<span><svg width="30" height="8"><line x1="0" y1="4" x2="30" y2="4" class="glink mine"/></svg>my edit</span><span><svg width="18" height="12"><rect x="1" y="1" width="16" height="10" rx="3" fill="#F3EEE4" stroke="#C9BFAE" stroke-dasharray="3 2"/></svg>unknown parents</span></div>
      <div id="g-float"></div></div>
    <aside class="card" id="g-side" style="margin:0;position:sticky;top:84px;max-height:calc(100vh - 110px);overflow-y:auto"></aside></div>`;
  $('#g-canvas').insertAdjacentHTML('afterbegin', treeSvg(false));
  bindPanZoom();
  const lay=G.lay, floating=d.people.filter(p=>!lay.nodes.some(n=>n.id===p.id));
  $('#g-float').innerHTML = floating.length ? `<div class="card" style="margin-top:12px"><h3>Not in this view · ${floating.length}</h3><p class="sub">${G.layout==='all'?'No evidenced link to the people above yet. Nothing is guessed; add a source, or state a link yourself.':'Outside this layout. Switch to "Everyone connected", or centre on someone else.'}</p>
    <div class="float">${floating.map(p=>`<button class="chiplink" data-gpick="${esc(p.id)}">${esc(p.name||p.id)}${linked.has(p.id)?'':' · unattached'}</button>`).join('')}</div></div>` : '';
  $$('[data-gpick]').forEach(b=>b.onclick=()=>selectPerson(b.dataset.gpick));
  $$('#g-canvas .gnode').forEach(n=>n.onclick=e=>{ e.stopPropagation(); if(n.dataset.id && !n.classList.contains('unknown')) selectPerson(n.dataset.id); });
  selectPerson(G.sel && d.people.some(p=>p.id===G.sel) ? G.sel : G.focus, true);
}
/* ---- layout: generations from the focus person; parents above, children below, spouses beside */
function layoutTree(){
  const d=G.data, up={}, down={}, side={};
  d.links.forEach(l=>{ if(l.rel==='parent'){ (up[l.b]=up[l.b]||[]).push(l.a); (down[l.a]=down[l.a]||[]).push(l.b); }
    else { (side[l.a]=side[l.a]||[]).push(l.b); (side[l.b]=side[l.b]||[]).push(l.a); } });
  const gen={[G.focus]:0}, order=[G.focus], q=[G.focus];
  const allow = {all:['u','d','s'], desc:['d','s'], anc:['u','s'], hour:['u','d','s']}[G.layout];
  while(q.length){ const c=q.shift();
    const steps=[...(allow.includes('u')?(up[c]||[]).map(n=>[n,-1,'u']):[]), ...(allow.includes('d')?(down[c]||[]).map(n=>[n,1,'d']):[]), ...(side[c]||[]).map(n=>[n,0,'s'])];
    for(const [n,dg,k] of steps){
      if(gen[n]!==undefined) continue;
      if(G.layout==='hour' && ((gen[c]<0 && k==='d') || (gen[c]>0 && k==='u'))) continue;   // hourglass: no cousins
      if(k==='s' && G.layout!=='all' && c!==G.focus && !(G.layout==='anc'?gen[c]<0:gen[c]>0)) continue;
      gen[n]=gen[c]+dg; order.push(n); q.push(n); } }
  // unknown parents above the focus and ancestors who have none
  const unknown=[];
  if(G.layout!=='desc') order.filter(id=>gen[id]<=0 && !(up[id]||[]).length && (G.layout!=='all' || id===G.focus)).forEach(id=>{ const u='?'+id; gen[u]=gen[id]-1; unknown.push({id:u, child:id}); order.push(u); });
  const gens={}; order.forEach(id=>{ (gens[gen[id]]=gens[gen[id]]||[]).push(id); });
  const keys=Object.keys(gens).map(Number).sort((a,b)=>a-b);
  const W=156, H=48, GX=28, GY=96, pos={};
  keys.forEach((g,gi)=>{
    let row=gens[g];
    if(gi>0){ const prev=gens[keys[gi-1]]; const bc=id=>{ const ps=(up[id]||[]).filter(p=>prev.includes(p)); const ix=ps.map(p=>prev.indexOf(p)); return ix.length?ix.reduce((a,b)=>a+b,0)/ix.length:(prev.indexOf('?'+id)>=0?prev.indexOf('?'+id):row.indexOf(id)); };
      row=row.slice().sort((a,b)=>bc(a)-bc(b)); }
    if(gi===0 && keys.length>1){ const next=gens[keys[1]]; const bc=id=>{ const cs=(down[id]||[]).concat(id.startsWith('?')?[id.slice(1)]:[]).filter(c=>next.includes(c)); return cs.length?cs.map(c=>next.indexOf(c)).reduce((a,b)=>a+b,0)/cs.length:99; }; row=row.slice().sort((a,b)=>bc(a)-bc(b)); }
    const seated=[]; row.forEach(id=>{ if(seated.includes(id)) return; seated.push(id); (side[id]||[]).forEach(sp=>{ if(row.includes(sp) && !seated.includes(sp) && G.data.links.some(l=>l.rel==='spouse'&&((l.a===id&&l.b===sp)||(l.b===id&&l.a===sp)))) seated.push(sp); }); });
    gens[g]=seated;
    const width=seated.length*W+(seated.length-1)*GX;
    seated.forEach((id,i)=>{ pos[id]={x:-width/2+i*(W+GX), y:gi*(H+GY)}; });
  });
  const nodes=order.map(id=>({id, ...pos[id], unknown:id.startsWith('?')}));
  return {nodes, pos, W, H, unknown};
}
function treeSvg(standalone){
  const d=G.data; if(!d || !d.people.length) return '';
  const lay=layoutTree(); G.lay=lay; const {pos,W,H}=lay;
  const xs=lay.nodes.map(n=>n.x), ys=lay.nodes.map(n=>n.y);
  const box={x:Math.min(...xs)-40, y:Math.min(...ys)-40, w:Math.max(...xs)-Math.min(...xs)+W+80, h:Math.max(...ys)-Math.min(...ys)+H+80};
  if(!G.vb || standalone) { if(!standalone) G.vb={...box}; }
  const vb = standalone ? box : G.vb;
  const cls = l => `glink ${l.by==='me'?'mine':esc(l.tier)}${l.rel==='spouse'?' spouse':''}`;
  let links='';
  d.links.forEach(l=>{ const a=pos[l.a], b=pos[l.b]; if(!a||!b) return;
    const title=`<title>${esc(gName(l.a))} ${l.rel==='parent'?'parent of':l.rel+' of'} ${esc(gName(l.b))} · ${esc(G_TIER[l.tier]||l.tier)}${(l.evidence||[]).length?' · '+esc(l.evidence[0].cite||''):''}</title>`;
    if(l.rel==='parent'){ const x1=a.x+W/2, y1=a.y+H, x2=b.x+W/2, y2=b.y, my=(y1+y2)/2;
      links+=`<path class="${cls(l)}" d="M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}">${title}</path>`; }
    else if(l.rel==='spouse'){ const [p,q]=a.x<b.x?[a,b]:[b,a]; links+=`<path class="${cls(l)}" d="M${p.x+W},${p.y+H/2} L${q.x},${q.y+H/2}">${title}</path>`; }
    else { const y=Math.min(a.y,b.y)-14; links+=`<path class="${cls(l)}" d="M${a.x+W/2},${a.y} V${y} H${b.x+W/2} V${b.y}" style="stroke-width:1.1">${title}</path>`; } });
  lay.unknown.forEach(u=>{ const a=pos[u.id], b=pos[u.child]; links+=`<path class="glink unconfirmed" d="M${a.x+W/2},${a.y+H} L${b.x+W/2},${b.y}"/>`; });
  const trunc=(s,n)=>s.length>n?s.slice(0,n-1)+'…':s;
  const nodes=lay.nodes.map(n=>{ if(n.unknown) return `<g class="gnode unknown" data-id="${esc(n.id)}" transform="translate(${n.x},${n.y})"><rect width="${W}" height="${H}" rx="9"/><text x="${W/2}" y="${H/2+4}" text-anchor="middle" class="d">parents unknown</text></g>`;
    let p=d.people.find(x=>x.id===n.id)||{name:n.id};
    if(standalone && p.living) p={name:'Living person', dates:''};      // living people stay out of exports
    return `<g class="gnode${n.id===G.focus?' focus':''}${n.id===G.sel?' sel':''}${p.by==='me'?' mine':''}" data-id="${esc(n.id)}" transform="translate(${n.x},${n.y})" tabindex="0"><rect width="${W}" height="${H}" rx="9"/>
      <text x="12" y="20">${esc(trunc(p.name||n.id,21))}</text><text x="12" y="36" class="d">${esc(trunc(p.dates||'dates unknown',24))}</text><title>${esc(p.name||n.id)}</title></g>`; }).join('');
  const style = standalone ? `<style>.gnode rect{fill:#FFFDF8;stroke:#C9BFAE;stroke-width:1.2}.gnode.focus rect{stroke:#C96F4A;stroke-width:2.4}.gnode.unknown rect{fill:#F3EEE4;stroke-dasharray:4 3}.gnode text{font-family:Helvetica,Arial,sans-serif;font-size:12.5px;fill:#1C1A17}.gnode text.d{font-size:11px;fill:#7C756A}.glink{fill:none;stroke-width:1.6}.glink.documented{stroke:#3D3A35}.glink.told{stroke:#C96F4A}.glink.lore{stroke:#B07BB0;stroke-dasharray:6 4}.glink.unconfirmed{stroke:#B5AC9C;stroke-dasharray:2 4}.glink.mine{stroke:#4F7A54}.glink.spouse{stroke-width:2.4}</style>` : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" ${standalone?`width="${Math.round(box.w)}" height="${Math.round(box.h)}"`:''} viewBox="${vb.x} ${vb.y} ${vb.w} ${vb.h}" role="img" aria-label="Family tree">${style}<rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" fill="${standalone?'#fff':'none'}"/>${links}${nodes}</svg>`;
}
function bindPanZoom(){
  const c=$('#g-canvas'), svg=$('#g-canvas svg');
  const apply=()=>svg.setAttribute('viewBox', `${G.vb.x} ${G.vb.y} ${G.vb.w} ${G.vb.h}`);
  const zoom=(f,cx=0.5,cy=0.5)=>{ const nw=G.vb.w*f, nh=G.vb.h*f; G.vb.x+= (G.vb.w-nw)*cx; G.vb.y+=(G.vb.h-nh)*cy; G.vb.w=nw; G.vb.h=nh; apply(); };
  c.onwheel=e=>{ e.preventDefault(); const r=c.getBoundingClientRect(); zoom(e.deltaY>0?1.12:1/1.12, (e.clientX-r.left)/r.width, (e.clientY-r.top)/r.height); };
  let drag=null;
  c.onpointerdown=e=>{ if(e.target.closest('.gnode,.zoom')) return; drag={x:e.clientX,y:e.clientY,vx:G.vb.x,vy:G.vb.y}; c.classList.add('drag'); c.setPointerCapture(e.pointerId); };
  c.onpointermove=e=>{ if(!drag) return; const r=c.getBoundingClientRect(); const k=G.vb.w/r.width;
    G.vb.x=drag.vx-(e.clientX-drag.x)*k; G.vb.y=drag.vy-(e.clientY-drag.y)*k; apply(); };
  c.onpointerup=()=>{ drag=null; c.classList.remove('drag'); };
  $('#gz-in').onclick=()=>zoom(1/1.25); $('#gz-out').onclick=()=>zoom(1.25); $('#gz-fit').onclick=()=>{ G.vb=null; drawGenealogy(); };
}
/* ---- the side panel: who this is, every link with its evidence, and my edits */
function selectPerson(id, quiet){
  G.sel=id; const d=G.data, p=d.people.find(x=>x.id===id); if(!p) return;
  $$('#g-canvas .gnode').forEach(n=>n.classList.toggle('sel', n.dataset.id===id));
  const mine=d.links.filter(l=>l.a===id||l.b===id);
  const say=l=>{ const other=l.a===id?l.b:l.a;
    const rel = l.rel==='parent' ? (l.a===id?'parent of':'child of') : l.rel+' of';
    return `<div style="border-top:1px solid var(--line);padding:8px 0">
      <div class="row" style="gap:6px"><span>${esc(rel)} <button class="linkish" data-gpick="${esc(other)}">${esc(gName(other))}</button></span><span class="spacer"></span>
        <select data-gtier="${esc(l.id)}" style="padding:3px 6px;font-size:12px;width:auto" aria-label="How sure">${Object.entries(G_TIER).map(([k,v])=>`<option value="${k}" ${l.tier===k?'selected':''}>${esc(v)}</option>`).join('')}</select>
        <button class="btn ghost sm" data-gdel="${esc(l.id)}" title="Remove this link (recorded as my edit)">×</button></div>
      ${(l.evidence||[]).map(e=>`<p class="quote" style="font-size:13.4px;margin:5px 0">${e.quote?'“'+esc(e.quote)+'”':''} ${/^\[?S\d+ \d\d:/.test(e.cite||'')?`<a class="cite" data-cite="${esc(e.cite)}">${esc(e.cite)}</a>`:`<span class="derived">${esc(e.cite||'')}</span>`}</p>`).join('')||'<p class="derived">no evidence recorded</p>'}
      <span class="derived">${l.by==='me'?'my edit':'derived from the sources'}</span></div>`; };
  const merges=(d.merges||[]).filter(m=>m.keep===id);
  $('#g-side').innerHTML = `<div class="row" style="align-items:flex-start;gap:12px">${p.photo?`<img class="portrait" style="width:64px;height:64px" src="${fileUrl(p.photo)}" alt="">`:`<div class="portrait" style="width:64px;height:64px;font-size:26px">${esc((p.name||'?')[0])}</div>`}
      <div style="flex:1;min-width:0"><h3 style="font-family:var(--serif);font-size:20px">${esc(p.name||p.id)}</h3><div style="font-size:13px;color:var(--ink-3)">${esc(p.dates||'dates unknown')}${p.living?' · living':''}</div>
      ${(p.aliases||[]).length?`<div style="font-size:12.4px;color:var(--ink-3)">also ${p.aliases.map(esc).join(', ')}</div>`:''}<span class="derived">${p.by==='me'?'edited by me':'derived'}</span></div></div>
    <div class="row" style="gap:6px;margin:10px 0">${p.article?`<a class="chiplink" href="#familypedia/${encodeURIComponent(p.article)}">Familypedia</a>`:''}<button class="chiplink" id="gp-focus">Centre the tree here</button>
      <span class="pill">${p.n_sources||0} source${p.n_sources!==1?'s':''}</span>${p.has_story?`<span class="pill ok">in a ${L.story}</span>`:''}</div>
    <h4 style="margin:12px 0 2px;font-size:13.5px">Relationships · ${mine.length}</h4>${mine.map(say).join('')||'<p class="empty" style="padding:6px 0">No evidenced relationships. Nothing is guessed.</p>'}
    <h4 style="margin:14px 0 6px;font-size:13.5px">Edit <span class="derived">recorded as mine, kept across rebuilds</span></h4>
    <div class="row" style="gap:6px"><button class="btn ghost sm" id="gp-edit">Name and dates</button><button class="btn ghost sm" id="gp-link">Add a relationship</button><button class="btn ghost sm" id="gp-merge">Same person as…</button>
      ${merges.map(m=>`<button class="btn ghost sm" data-gsplit="${esc(m.merge)}">Split out ${esc(m.merge.replace(/-/g,' '))}</button>`).join('')}</div>
    <label style="margin-top:12px">Note</label><textarea id="gp-note" rows="2" placeholder="What you know that the sources don't say">${esc(p.note||'')}</textarea>
    <div class="row" style="margin-top:6px"><button class="btn ghost sm" id="gp-note-save">Save note</button></div>`;
  $$('#g-side [data-gpick]').forEach(b=>b.onclick=()=>selectPerson(b.dataset.gpick));
  $$('#g-side [data-cite]').forEach(c=>c.onclick=e=>{ e.preventDefault(); openCitation(c.dataset.cite); });
  $$('#g-side [data-gtier]').forEach(s=>s.onchange=()=>gEdit({op:'link_tier', id:s.dataset.gtier, tier:s.value}));
  $$('#g-side [data-gdel]').forEach(b=>b.onclick=()=>{ if(b.dataset.armed!=='1'){ b.dataset.armed='1'; b.textContent='remove?'; return; } gEdit({op:'link_remove', id:b.dataset.gdel}); });
  $$('#g-side [data-gsplit]').forEach(b=>b.onclick=()=>gEdit({op:'split', merge:b.dataset.gsplit}));
  $('#gp-focus').onclick=()=>{ G.focus=id; G.vb=null; drawGenealogy(); };
  $('#gp-note-save').onclick=()=>gEdit({op:'note', id, note:$('#gp-note').value}, 'Note saved.');
  $('#gp-edit').onclick=()=>{ openModal('Name and dates', `<div class="grid two"><div><label>Name</label><input type="text" id="ge-name" value="${esc(p.name||'')}"></div><div><label>Dates</label><input type="text" id="ge-dates" value="${esc(p.dates||'')}" placeholder="b. about 1840 – d. 1911"></div></div>
      <label class="toggle"><input type="checkbox" id="ge-living" ${p.living?'checked':''}><div><b>Living</b><span>Living people are left out of exports and printed charts.</span></div></label>
      <div class="row"><button class="btn go" id="ge-save">Save</button></div>`);
    $('#ge-save').onclick=()=>{ closeOverlay(); gEdit({op:'person', id, name:$('#ge-name').value, dates:$('#ge-dates').value, living:$('#ge-living').checked}); }; };
  const others=d.people.filter(x=>x.id!==id).sort((a,b)=>(a.name||'').localeCompare(b.name||''));
  $('#gp-link').onclick=()=>{ openModal(`A relationship for ${p.name}`, `<div class="grid three"><div><label>${esc(p.name)} is the…</label><select id="gl-rel"><option value="parent">parent of</option><option value="child">child of</option><option value="spouse">spouse of</option><option value="sibling">sibling of</option></select></div>
      <div><label>…of</label><input type="text" id="gl-other" list="gl-people" placeholder="a name"><datalist id="gl-people">${others.map(o=>`<option value="${esc(o.name||o.id)}">`).join('')}</datalist></div>
      <div><label>How sure</label><select id="gl-tier">${Object.entries(G_TIER).map(([k,v])=>`<option value="${k}" ${k==='told'?'selected':''}>${esc(v)}</option>`).join('')}</select></div></div>
      <label style="margin-top:10px">What establishes it</label><textarea id="gl-ev" rows="2" placeholder="Mom always said… / the 1910 census lists…"></textarea>
      <p class="sub" style="font-size:12.4px">Stated by you and marked as yours. A rebuild never overwrites it.</p><div class="row"><button class="btn go" id="gl-save">Add</button></div>`);
    $('#gl-save').onclick=()=>{ const rel=$('#gl-rel').value, o=$('#gl-other').value.trim(); if(!o){ alertNote('Name the other person.'); return; }
      const ev=$('#gl-ev').value.trim(); if(!ev){ alertNote('Say what establishes it: no evidence, no link.'); return; }
      const oid=(others.find(x=>(x.name||x.id)===o)||{}).id || o;
      const body = rel==='child' ? {op:'link', a:oid, b:id, rel:'parent'} : {op:'link', a:id, b:oid, rel};
      closeOverlay(); gEdit({...body, tier:$('#gl-tier').value, evidence:ev}); }; };
  $('#gp-merge').onclick=()=>{ openModal(`${p.name} is the same person as…`, `<p class="sub">Merging keeps the other name as an alias and moves their links here. You can split them again.</p>
      <select id="gm-other">${others.map(o=>`<option value="${esc(o.id)}">${esc(o.name||o.id)}</option>`).join('')}</select>
      <div class="row" style="margin-top:12px"><button class="btn go" id="gm-go">Merge into ${esc(p.name)}</button></div>`);
    $('#gm-go').onclick=()=>{ closeOverlay(); gEdit({op:'merge', keep:id, merge:$('#gm-other').value}); }; };
  if(!quiet) $('#g-side').scrollTop=0;
}
async function gEdit(body, msg){
  const r=await api('/api/engine/genealogy/edit',{method:'POST',body});
  if(r.error){ alertNote(r.error); return; }
  G.data=r; drawGenealogy(); if(msg) alertNote(msg);
}
function drawCast(){
  const d=G.data, subj=d.subject;
  const people=d.people.slice().sort((a,b)=>(b.n_sources||0)-(a.n_sources||0) || (a.name||'').localeCompare(b.name||''));
  const nlinks=id=>d.links.filter(l=>l.a===id||l.b===id).length;
  $('#g-body').innerHTML = `<div class="cast">${people.map(p=>`<div class="card"><div class="row" style="gap:10px">${p.photo?`<img class="portrait" style="width:52px;height:52px" src="${fileUrl(p.photo)}" alt="">`:`<div class="portrait" style="width:52px;height:52px;font-size:22px">${esc((p.name||'?')[0])}</div>`}
      <div style="min-width:0"><b style="font-family:var(--serif);font-size:16.5px">${esc(p.name||p.id)}</b><div style="font-size:12.6px;color:var(--ink-3)">${esc(p.dates||'dates unknown')}${p.id===subj?' · the subject':''}</div></div></div>
    <div class="row" style="gap:5px"><span class="pill">${p.n_sources||0} source${p.n_sources!==1?'s':''}</span><span class="pill ${nlinks(p.id)?'':'warn'}">${nlinks(p.id)?nlinks(p.id)+' link'+(nlinks(p.id)>1?'s':''):'unattached'}</span>${p.has_story?`<span class="pill ok">in a ${L.story}</span>`:''}</div>
    <div class="row" style="gap:6px">${p.article?`<a class="chiplink" href="#familypedia/${encodeURIComponent(p.article)}">Familypedia</a>`:''}<button class="chiplink" data-gtree="${esc(p.id)}">In the tree</button></div></div>`).join('')}</div>`;
  $$('[data-gtree]').forEach(b=>b.onclick=()=>{ G.view='tree'; G.focus=b.dataset.gtree; G.sel=b.dataset.gtree; G.vb=null; drawGenealogy(); });
}
/* ---- rebuild with review: nothing changes until I approve it */
async function rebuildTree(){
  const b=$('#g-rebuild'); b.disabled=true; b.textContent='reading the sources…';
  const r=await api('/api/engine/genealogy/rebuild',{method:'POST'});
  pollJob(r.job, st=>{ b.textContent=st.length>30?'reading the sources…':st; }, async()=>{ b.disabled=false; b.textContent='Rebuild from sources'; await loadTree(); reviewRebuild(); },
    err=>{ b.disabled=false; b.textContent='Rebuild from sources'; alertNote(err); });
}
async function reviewRebuild(){
  const d=await api('/api/engine/genealogy/review');
  if(!d.pending){ alertNote('No rebuild is waiting.'); return; }
  const lk=l=>`${esc(gName(l.a))} <b>${l.rel==='parent'?'parent of':esc(l.rel)+' of'}</b> ${esc(gName(l.b))} <span class="tierdot t-${esc(l.tier)}"></span><span class="derived">${esc(G_TIER[l.tier]||l.tier)}</span>
    ${(l.evidence||[]).map(e=>`<div class="quote" style="font-size:13px;margin:4px 0">“${esc(e.quote)}” <span class="derived">${esc(e.cite)}</span></div>`).join('')}`;
  openModal('Review the rebuild', `<p class="sub">${esc(d.note||'')} · proposed ${esc(ago(d.made))}. Tick what to accept; the rest is left out. Your own edits are untouched either way.</p>
    ${d.contradictions.length?`<div class="note" style="margin-bottom:12px;background:#FFFBF1;border:1px solid #E3D2AB"><b>${d.contradictions.length} contradiction${d.contradictions.length>1?'s':''}:</b> these disagree with the current tree. Both versions are kept as a conflict; nothing is resolved silently.<ul>${d.contradictions.map(c=>`<li>now: ${lk(c.old)}<br>proposed: ${lk(c.new)}</li>`).join('')}</ul></div>`:''}
    <h4>New people · ${d.new_people.length}</h4><p>${d.new_people.map(p=>esc(p.name||p.id)).join(' · ')||'<span class="empty">none</span>'}</p>
    <h4>New relationships · ${d.new_links.length}</h4>${d.new_links.map(l=>`<label class="toggle" style="border-top:1px solid var(--line)"><input type="checkbox" data-acc="${esc(l.id)}" checked><div>${lk(l)}</div></label>`).join('')||'<p class="empty">none</p>'}
    ${d.changed_links.length?`<h4>Changed certainty · ${d.changed_links.length}</h4>${d.changed_links.map(c=>`<label class="toggle"><input type="checkbox" data-acc="${esc(c.new.id)}" checked><div>${lk(c.new)}<br><span class="derived">was ${esc(c.old.tier)}</span></div></label>`).join('')}`:''}
    ${d.gone_links.length?`<h4>No longer found · ${d.gone_links.length}</h4><p class="sub">Kept in the tree; remove them yourself if they're wrong.</p>${d.gone_links.map(l=>`<p>${lk(l)}</p>`).join('')}`:''}
    <div class="row" style="margin-top:14px"><button class="btn go" id="rv-apply">Apply what's ticked</button><button class="btn ghost" id="rv-later">Later</button></div>`);
  $('#rv-later').onclick=closeOverlay;
  $('#rv-apply').onclick=async()=>{ const accept=$$('[data-acc]').filter(c=>c.checked).map(c=>c.dataset.acc);
    G.data=await api('/api/engine/genealogy/apply',{method:'POST',body:{accept}}); closeOverlay(); drawGenealogy(); alertNote(`Applied ${accept.length} relationship${accept.length!==1?'s':''}.`); };
}
