/* ================================================================== GENEALOGY
   The tree is built from the sources, never hand-entered: every link carries the passage that
   establishes it, and people without one float unattached rather than being guessed into place.
   My corrections (merges, links, tiers, notes) are kept apart and survive every rebuild. */
const G = {view:'tree', layout:'all', focus:null, sel:null, closed:false, vb:null, data:null};
const G_TIER = {documented:'documented', told:'told', lore:'family lore', unconfirmed:'unconfirmed'};
const G_TREE_SVG = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="9" y="3" width="6" height="4.5" rx="1.2"/><rect x="3" y="16.5" width="6" height="4.5" rx="1.2"/><rect x="15" y="16.5" width="6" height="4.5" rx="1.2"/><path d="M12 7.5V12M6 16.5V12h12v4.5"/></svg>';
const G_CAST_SVG = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="9" cy="8" r="3.2"/><path d="M3 19.5c.6-3.3 3-5.2 6-5.2s5.4 1.9 6 5.2"/><circle cx="16.8" cy="9" r="2.6"/><path d="M16.5 14.4c2.4.2 4 1.8 4.5 4.6"/></svg>';
BUILDERS.genealogy = async function(el, rest, q={}){
  el.innerHTML='';
  head(el,{kicker:'Genealogy', title:'The family tree, from the evidence', lede:'Every link points at the words that establish it. Nothing is inferred from surnames, dates or photographs; anyone without evidence stays off the tree until something connects them.'});
  el.insertAdjacentHTML('beforeend', `<div class="card"><div class="row">
      <div class="seg" role="group" aria-label="View"><button type="button" data-gview="tree" aria-label="Tree" title="Tree">${G_TREE_SVG}</button><button type="button" data-gview="cast" aria-label="Cast: everyone, as a list" title="Cast">${G_CAST_SVG}</button></div>
      <span class="gshape"><label for="g-layout">Tree shape</label><select id="g-layout" style="max-width:190px"><option value="hour">Hourglass</option><option value="anc">Ancestors only</option><option value="desc">Descendants only</option><option value="all">Everyone</option></select></span>
      <select id="g-focus" style="max-width:220px" aria-label="Centre on"></select>
      <span class="spacer"></span>
      <button class="btn go sm" id="g-rebuild">Rebuild from sources</button><button class="btn ghost sm hidden" id="g-review">Review the rebuild</button>
      <button class="btn ghost sm" id="g-import">Import GEDCOM</button><input type="file" id="g-import-in" accept=".ged,.gedcom,text/plain" class="hidden">
      ${dlMenu('g-dl', [['pdf','PDF'],['png','PNG image'],['svg','SVG vector'],'-',['ged','GEDCOM · for other software']])}<button class="btn ghost sm" id="g-print">Print</button></div>
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
  const chart=()=>{ const s=treeSvg(true); if(!s) alertNote('No tree to export yet.'); return s; };
  bindDlMenu('g-dl', {
    pdf:async()=>{ const s=chart(); if(s) await svgToPdf(s,'family-tree.pdf'); },
    png:async()=>{ const s=chart(); if(s) await svgToPng(s,'family-tree.png'); },
    svg:()=>{ const s=chart(); if(s) download('family-tree.svg', new Blob([s],{type:'image/svg+xml'})); },
    ged:async()=>{ const t=await (await fetch('/api/engine/genealogy.ged',{headers:{'X-Lineage-Token':TOKEN}})).text(); download('lineage.ged', new Blob([t],{type:'text/plain'})); }});
  $('#g-print').onclick=()=>{ const s=treeSvg(true); if(s) printable('Family tree', `<h1>${esc(S.data.identity.display_title)}</h1><p><small>Family tree from the evidence · line style shows how sure each link is</small></p>${s}`); };
  await loadTree();
  if(q.review) reviewRebuild();
};
async function loadTree(){ G.data = await api('/api/engine/genealogy'); drawGenealogy(); }
function gName(id){ const p=G.data.people.find(x=>x.id===id); return p ? (p.name||id) : id.replace(/-/g,' '); }
function drawGenealogy(){
  const d=G.data;
  $$('[data-gview]').forEach(b=>b.setAttribute('aria-pressed', String(b.dataset.gview===G.view)));
  $('#g-review').classList.toggle('hidden', !d.pending || !!d.from_file);
  $('#g-rebuild').classList.toggle('hidden', !!d.from_file);
  $('#g-note').innerHTML = (d.applied?`Last rebuild applied ${esc(ago(d.applied))}${d.note?' · '+esc(d.note):''}.`:'No rebuild applied yet. "Rebuild from sources" reads the material and proposes a tree for you to review.')
    + (d.pending&&!d.from_file?' <b>A rebuild is waiting for your review.</b>':'') + (d.conflicts.length?` <span class="pill warn">${d.conflicts.length} contradiction${d.conflicts.length>1?'s':''} kept</span>`:'');
  if(d.from_file){ $('#g-note').innerHTML=`From the family tree file, <code>${esc(d.from_file)}</code>: ${d.people.length} people, ${d.links.length} links, each with its evidence. Click anyone to see their links, with the evidence for each, below the tree.`; }
  if(!d.people.length){ $('#g-focus').innerHTML='<option>No one yet</option>'; $('#g-focus').disabled=true; $('#g-body').innerHTML='<div class="card"><p class="empty">No people yet. They appear as sources are read; then "Rebuild from sources" links them with evidence.</p></div>'; return; }
  const linked = new Set(d.links.flatMap(l=>[l.a,l.b]));
  if(!G.focus || !d.people.some(p=>p.id===G.focus)) G.focus = (d.subject && linked.has(d.subject)) ? d.subject : ([...linked][0] || d.people[0].id);
  $('#g-focus').innerHTML = d.people.slice().sort((a,b)=>(a.name||'').localeCompare(b.name||'')).map(p=>`<option value="${esc(p.id)}" ${p.id===G.focus?'selected':''}>Centre on ${esc(p.name||p.id)}</option>`).join('');
  $('#g-layout').value=G.layout; $('#g-layout').disabled = G.view==='cast'; $('#g-focus').disabled = G.view==='cast';
  if(G.view==='cast') return drawCast();
  $('#g-body').innerHTML = `<div class="gcanvas" id="g-canvas"><div class="zoom" role="group" aria-label="Zoom"><button class="btn ghost sm" id="gz-in" aria-label="Zoom in" title="Zoom in">+</button><button class="btn ghost sm" id="gz-out" aria-label="Zoom out" title="Zoom out">−</button><button class="btn ghost sm" id="gz-fit" aria-label="Fit everyone in view" title="Fit">fit</button></div></div>
    <div class="legend">${Object.entries(G_TIER).map(([k,v])=>`<span><svg width="30" height="8"><line x1="0" y1="4" x2="30" y2="4" class="glink ${k}"/></svg>${esc(v)}</span>`).join('')}<span><svg width="30" height="8"><line x1="0" y1="4" x2="30" y2="4" class="glink mine"/></svg>my edit</span><span><svg width="18" height="12"><rect x="1" y="1" width="16" height="10" rx="3" fill="#F3EEE4" stroke="#C9BFAE" stroke-dasharray="3 2"/></svg>unknown parents</span></div>
    <div id="g-card"></div>`;
  const fresh = !G.vb;
  $('#g-canvas').insertAdjacentHTML('afterbegin', treeSvg(false));
  if(fresh && !G.fitAll){                         // open at reading size, centred on the focus person; "fit" shows everyone
    const c=$('#g-canvas'), f=G.lay.pos[G.focus], w=Math.max(c.clientWidth,320), h=Math.max(c.clientHeight,300);
    if(f && G.vb.w > w*1.15){ G.vb={x:f.x+G.lay.W/2-w/2, y:f.y+G.lay.H/2-h/2, w, h}; $('#g-canvas svg').setAttribute('viewBox', `${G.vb.x} ${G.vb.y} ${G.vb.w} ${G.vb.h}`); }
  }
  G.fitAll=false;
  bindPanZoom();
  $$('#g-canvas .gnode').forEach(n=>{ const pick=e=>{ e.stopPropagation(); if(!n.dataset.id || n.classList.contains('unknown')) return; selectPerson(n.dataset.id); };
    n.onclick=pick; n.onkeydown=e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); pick(e); } }; });
  if(!G.closed) selectPerson(G.sel && d.people.some(p=>p.id===G.sel) ? G.sel : G.focus, true);
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
  const W=188, H=46, GX=22, GY=86, pos={};
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
    // the portrait chip, drawn in the tree: round picture at the left, name and dates beside it
    const pic = p.photo && !(standalone && p.living) ? thumbSrc(p.photo) : null, tx = pic ? H+4 : 16, cid='gc-'+n.id.replace(/[^a-z0-9-]/gi,'');
    return `<g class="gnode${n.id===G.focus?' focus':''}${n.id===G.sel?' sel':''}${p.by==='me'?' mine':''}${p.article?' linked':''}" data-id="${esc(n.id)}" transform="translate(${n.x},${n.y})" tabindex="0"><rect width="${W}" height="${H}" rx="${H/2}"/>
      ${pic?`<clipPath id="${cid}"><circle cx="${H/2}" cy="${H/2}" r="${H/2-5}"/></clipPath><image href="${esc(pic)}" x="5" y="5" width="${H-10}" height="${H-10}" preserveAspectRatio="xMidYMid slice" clip-path="url(#${cid})"/>`:''}
      <text x="${tx}" y="21">${esc(trunc(p.name||n.id,pic?19:23))}</text><text x="${tx}" y="35" class="d">${esc(trunc(p.dates||'',pic?22:26))}</text><title>${esc(p.name||n.id)}${p.article?' · open in the Familypedia':''}</title></g>`; }).join('');
  const style = standalone ? `<style>svg{color-scheme:only light}.gnode rect{fill:#FFFDF8;stroke:#C9BFAE;stroke-width:1.2}.gnode.focus rect,.gnode.sel rect{stroke:#C96F4A;stroke-width:2.4}.gnode.sel rect{fill:#F6E4D4}.gnode.unknown rect{fill:#F3EEE4;stroke-dasharray:4 3}.gnode text{font-family:Helvetica,Arial,sans-serif;font-size:14px;font-weight:600;fill:#1C1A17;color:#1C1A17}.gnode text.d{font-size:12px;font-weight:500;fill:#3A352E;color:#3A352E}.glink{fill:none;stroke-width:1.6}.glink.documented{stroke:#3D3A35}.glink.told{stroke:#C96F4A}.glink.lore{stroke:#B07BB0;stroke-dasharray:6 4}.glink.unconfirmed{stroke:#B5AC9C;stroke-dasharray:2 4}.glink.mine{stroke:#4F7A54}.glink.spouse{stroke-width:2.4}</style>` : '';
  return `<svg xmlns="http://www.w3.org/2000/svg" ${standalone?`width="${Math.round(box.w)}" height="${Math.round(box.h)}"`:''} viewBox="${vb.x} ${vb.y} ${vb.w} ${vb.h}" role="img" aria-label="Family tree">${style}<rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" fill="${standalone?'#fff':'none'}"/>${links}${nodes}</svg>`;
}
function bindPanZoom(){
  const c=$('#g-canvas'), svg=$('#g-canvas svg');
  const apply=()=>svg.setAttribute('viewBox', `${G.vb.x} ${G.vb.y} ${G.vb.w} ${G.vb.h}`);
  const zoom=(f,cx=0.5,cy=0.5)=>{ const nw=G.vb.w*f, nh=G.vb.h*f; G.vb.x+= (G.vb.w-nw)*cx; G.vb.y+=(G.vb.h-nh)*cy; G.vb.w=nw; G.vb.h=nh; apply(); };
  c.onwheel=e=>{ e.preventDefault(); const r=c.getBoundingClientRect(); zoom(e.deltaY>0?1.12:1/1.12, (e.clientX-r.left)/r.width, (e.clientY-r.top)/r.height); };
  // A drag anywhere on the tree, a person included, pans it. It never starts a text selection
  // across the names, and a drag that ends on a person does not also open them.
  let drag=null, moved=false;
  c.onpointerdown=e=>{ if(e.target.closest('.zoom')) return; if(e.pointerType==='mouse' && e.button!==0) return;
    if(!e.target.closest('.gnode')) e.preventDefault();
    const s=window.getSelection&&window.getSelection(); if(s && s.rangeCount && !s.isCollapsed) s.removeAllRanges();
    drag={x:e.clientX,y:e.clientY,vx:G.vb.x,vy:G.vb.y,id:e.pointerId}; moved=false; };
  c.onpointermove=e=>{ if(!drag || e.pointerId!==drag.id) return;
    if(!moved){ if(Math.hypot(e.clientX-drag.x, e.clientY-drag.y)<4) return; moved=true; c.classList.add('drag'); try{ c.setPointerCapture(e.pointerId); }catch(_){} }
    const r=c.getBoundingClientRect(); const k=G.vb.w/r.width;
    G.vb.x=drag.vx-(e.clientX-drag.x)*k; G.vb.y=drag.vy-(e.clientY-drag.y)*k; apply(); };
  c.onpointerup=c.onpointercancel=()=>{ drag=null; c.classList.remove('drag'); };
  c.addEventListener('click', e=>{ if(moved){ moved=false; e.stopPropagation(); e.preventDefault(); } }, true);
  c.onselectstart=e=>e.preventDefault();
  $('#gz-in').onclick=()=>zoom(1/1.25); $('#gz-out').onclick=()=>zoom(1.25); $('#gz-fit').onclick=()=>{ G.vb=null; G.fitAll=true; drawGenealogy(); };
}
/* ---- the person card, under the tree: who this is, their links with how sure each is, what to do next.
   The evidence and my edits fold open beneath it. Closing it leaves the tree to itself until the next click. */
function selectPerson(id, quiet){
  const d=G.data, p=d.people.find(x=>x.id===id); if(!p) return;
  G.sel=id; G.closed=false;
  $$('#g-canvas .gnode').forEach(n=>n.classList.toggle('sel', n.dataset.id===id));
  const mine=d.links.filter(l=>l.a===id||l.b===id);
  const relOf=l=>l.rel==='parent' ? (l.a===id?'parent of':'child of') : l.rel+' of';
  const tierOf=l=>l.by==='me'?'mine':l.tier, tierName=l=>l.by==='me'?'my edit':(G_TIER[l.tier]||l.tier);
  const chip=other=>{ const o=d.people.find(x=>x.id===other); return entryChip(null, gName(other), 'person', '', o&&o.photo||null, `data-gpick="${esc(other)}" role="button" tabindex="0"`); };
  const inline=l=>{ const other=l.a===id?l.b:l.a, ev=(l.evidence||[])[0];
    return `<span class="grel" title="${esc(ev?((ev.quote?'“'+ev.quote+'” ':'')+(ev.cite||'')):'no evidence recorded')}">${esc(relOf(l))} ${chip(other)} <span class="gtier g-${esc(tierOf(l))}">${esc(tierName(l))}</span></span>`; };
  const say=l=>{ const other=l.a===id?l.b:l.a;
    return `<div class="gev">
      <div class="row" style="gap:6px"><span>${esc(relOf(l))} ${chip(other)}</span><span class="spacer"></span>
        <select data-gtier="${esc(l.id)}" style="padding:3px 6px;font-size:12px;width:auto" aria-label="How sure">${Object.entries(G_TIER).map(([k,v])=>`<option value="${k}" ${l.tier===k?'selected':''}>${esc(v)}</option>`).join('')}</select>
        <button class="btn ghost sm" data-gdel="${esc(l.id)}" title="Remove this link (recorded as my edit)">×</button></div>
      ${(l.evidence||[]).map(e=>`<p class="quote" style="font-size:13.4px;margin:5px 0">${e.quote?'“'+esc(e.quote)+'”':''} ${/^\[?S\d+ \d\d:/.test(e.cite||'')?`<a class="cite" data-cite="${esc(e.cite)}">${esc(e.cite)}</a>`:`<span class="derived">${esc(e.cite||'')}</span>`}</p>`).join('')||'<p class="derived">no evidence recorded</p>'}
      <span class="derived">${l.by==='me'?'my edit':'derived from the sources'}</span></div>`; };
  const merges=(d.merges||[]).filter(m=>m.keep===id);
  const art=p.article?`#familypedia/${encodeURIComponent(p.article)}`:null, ns=p.n_sources||0, srcLabel=`${ns} source${ns!==1?'s':''}`;
  const box=$('#g-card'); if(!box) return;
  box.innerHTML = `<section class="gcard" aria-label="${esc(p.name||p.id)}">
    <button class="gcard-x" id="gp-close" type="button" aria-label="Close" title="Close">×</button>
    ${p.photo?`<img class="portrait" src="${thumbSrc(p.photo)}" alt="">`:`<div class="portrait" aria-hidden="true">${esc((p.name||'?')[0])}</div>`}
    <div class="gcard-main">
      <h3>${esc(p.name||p.id)}</h3>
      <div class="gcard-dates">${esc(p.dates||'dates unknown')}${p.living?' · living':''}${(p.aliases||[]).length?' · also '+p.aliases.map(esc).join(', '):''}</div>
      <div class="gcard-rels">${mine.map(inline).join('')||'<span class="derived">No evidenced relationships. Nothing is guessed.</span>'}</div>
      <div class="gcard-acts"><button class="btn sm" id="gp-focus" type="button">Centre the tree here</button>
        ${art?`<a class="btn ghost sm" href="${art}" title="The sources are listed in the Familypedia article">${srcLabel}</a>`:`<span class="pill">${srcLabel}</span>`}
        ${p.has_story?(art?`<a class="btn ghost sm" href="${art}" title="The ${L.stories} that tell of ${esc(p.name||'')} are listed in the article">In a ${L.story}</a>`:`<span class="pill ok">In a ${L.story}</span>`):''}
        ${art?`<a class="btn ghost sm" href="${art}">Open Familypedia article</a>`:''}</div>
      <details class="gcard-more"><summary>Evidence and edits <span class="derived">${p.by==='me'?'edited by me':'derived'}</span></summary>
        ${mine.map(say).join('')||'<p class="empty" style="padding:6px 0">No evidenced relationships.</p>'}
        <h4 style="margin:14px 0 6px;font-size:13.5px">Edit <span class="derived">recorded as mine, kept across rebuilds</span></h4>
        <div class="row" style="gap:6px"><button class="btn ghost sm" id="gp-edit">Name and dates</button><button class="btn ghost sm" id="gp-link">Add a relationship</button><button class="btn ghost sm" id="gp-merge">Same person as…</button>
          ${merges.map(m=>`<button class="btn ghost sm" data-gsplit="${esc(m.merge)}">Split out ${esc(m.merge.replace(/-/g,' '))}</button>`).join('')}</div>
        <label style="margin-top:12px" for="gp-note">Note</label><textarea id="gp-note" rows="2" placeholder="What you know that the sources don't say">${esc(p.note||'')}</textarea>
        <div class="row" style="margin-top:6px"><button class="btn ghost sm" id="gp-note-save">Save note</button></div></details></div></section>`;
  if(G.moreOpen) $('.gcard-more',box).open=true;
  $('.gcard-more',box).ontoggle=e=>{ G.moreOpen=e.target.open; };
  $$('[data-gpick]',box).forEach(b=>{ b.onclick=e=>{ e.preventDefault(); selectPerson(b.dataset.gpick); }; b.onkeydown=e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); selectPerson(b.dataset.gpick); } }; });
  $$('[data-cite]',box).forEach(c=>c.onclick=e=>{ e.preventDefault(); openCitation(c.dataset.cite); });
  $$('[data-gtier]',box).forEach(s=>s.onchange=()=>gEdit({op:'link_tier', id:s.dataset.gtier, tier:s.value}));
  $$('[data-gdel]',box).forEach(b=>b.onclick=()=>{ if(b.dataset.armed!=='1'){ b.dataset.armed='1'; b.textContent='remove?'; return; } gEdit({op:'link_remove', id:b.dataset.gdel}); });
  $$('[data-gsplit]',box).forEach(b=>b.onclick=()=>gEdit({op:'split', merge:b.dataset.gsplit}));
  $('#gp-close').onclick=()=>{ G.closed=true; G.sel=null; box.innerHTML=''; $$('#g-canvas .gnode.sel').forEach(n=>n.classList.remove('sel')); };
  $('#gp-focus').onclick=()=>{ G.focus=id; G.vb=null; drawGenealogy(); $('#g-canvas').scrollIntoView({block:'nearest', behavior:'smooth'}); };
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
  if(!quiet) box.scrollIntoView({block:'nearest', behavior:'smooth'});
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
  $('#g-body').innerHTML = `<div class="cast">${people.map(p=>`<div class="card"><div>${entryChip(p.article, p.name||p.id, 'person', '', p.photo||null)}<div style="font-size:12.6px;color:var(--ink-3);margin:4px 0 0 4px">${esc(p.dates||'')}${p.id===subj?' · the subject':''}</div></div>
    <div class="row" style="gap:5px"><span class="pill">${p.n_sources||0} source${p.n_sources!==1?'s':''}</span><span class="pill ${nlinks(p.id)?'':'warn'}">${nlinks(p.id)?nlinks(p.id)+' link'+(nlinks(p.id)>1?'s':''):'unattached'}</span>${p.has_story?`<span class="pill ok">in a ${L.story}</span>`:''}</div>
    <div class="row" style="gap:6px"><button class="chiplink" data-gtree="${esc(p.id)}">In the tree</button></div></div>`).join('')}</div>`;
  $$('[data-gtree]').forEach(b=>b.onclick=()=>{ G.view='tree'; G.focus=b.dataset.gtree; G.sel=b.dataset.gtree; G.closed=false; G.vb=null; drawGenealogy(); });
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
