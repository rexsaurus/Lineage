/* ================================================================== EXPORTS
   One Download menu for the chart pages (Genealogy, Timeline) and the writers behind it. Everything runs
   in the browser, so the published static site exports exactly as the local app does: the chart's SVG is
   drawn to a canvas, which gives the PNG, and a JPEG of it split across Letter pages in a PDF (no library). */
const DL_ICON = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true"><path d="M12 4v11M7 10.5l5 5 5-5M5 19.5h14"/></svg>';
/* items: [[key, label], …] with '-' for a rule. */
function dlMenu(id, items){
  return `<div class="dl" id="${id}"><button class="btn ghost sm dl-btn" type="button" aria-haspopup="menu" aria-expanded="false">${DL_ICON}<span>Download</span><span aria-hidden="true" class="dl-caret">▾</span></button>
    <div class="dl-menu hidden" role="menu">${items.map(it=>it==='-'?'<hr role="separator">':`<button type="button" role="menuitem" data-dl="${esc(it[0])}" tabindex="-1">${esc(it[1])}</button>`).join('')}</div></div>`;
}
function bindDlMenu(id, handlers){
  const box=document.getElementById(id); if(!box) return;
  const btn=$('.dl-btn',box), menu=$('.dl-menu',box), items=$$('[data-dl]',menu);
  const close=()=>{ menu.classList.add('hidden'); btn.setAttribute('aria-expanded','false'); document.removeEventListener('click', outside); };
  const outside=e=>{ if(!box.contains(e.target)) close(); };
  const open=()=>{ menu.classList.remove('hidden'); btn.setAttribute('aria-expanded','true'); items[0].focus(); setTimeout(()=>document.addEventListener('click', outside),0); };
  btn.onclick=()=>menu.classList.contains('hidden') ? open() : close();
  btn.onkeydown=e=>{ if(e.key==='ArrowDown'){ e.preventDefault(); open(); } };
  menu.onkeydown=e=>{ const i=items.indexOf(document.activeElement);
    if(e.key==='ArrowDown'){ e.preventDefault(); items[(i+1)%items.length].focus(); }
    if(e.key==='ArrowUp'){ e.preventDefault(); items[(i-1+items.length)%items.length].focus(); }
    if(e.key==='Escape'){ e.stopPropagation(); close(); btn.focus(); }
    if(e.key==='Tab') close(); };
  items.forEach(b=>b.onclick=async()=>{ close(); const f=handlers[b.dataset.dl]; if(!f) return;
    try{ await f(); }catch(err){ alertNote('That download did not work: '+(err&&err.message||err)); } });
}
/* SVG text → canvas on a white ground. The scale drops for very large charts: browsers refuse canvases
   much past 16k pixels a side or ~16 million pixels (Safari), and a blank file is worse than a smaller one. */
function svgToCanvas(svgText, scale=2){
  return new Promise((resolve, reject)=>{
    const img=new Image(), url=URL.createObjectURL(new Blob([svgText],{type:'image/svg+xml'}));
    img.onload=()=>{ const w=img.width||1, h=img.height||1;
      const k=Math.max(0.25, Math.min(scale, 16000/w, 16000/h, Math.sqrt(16e6/(w*h))));
      const c=document.createElement('canvas'); c.width=Math.round(w*k); c.height=Math.round(h*k);
      const g=c.getContext('2d'); g.fillStyle='#fff'; g.fillRect(0,0,c.width,c.height); g.drawImage(img,0,0,c.width,c.height);
      URL.revokeObjectURL(url); resolve({canvas:c, w, h}); };
    img.onerror=()=>{ URL.revokeObjectURL(url); reject(new Error('the chart could not be drawn')); };
    img.src=url;
  });
}
async function svgToPng(svgText, name, scale=2){
  const {canvas}=await svgToCanvas(svgText, scale);
  canvas.toBlob(b=>download(name,b),'image/png');
}
/* A PDF of Letter pages, each holding one JPEG slice (an Image XObject with /DCTDecode). No library.
   pages: [{jpeg, pxW, pxH, w, h}] where w, h are the slice's size on the page in points. */
function jpegPdf(pages, pageW, pageH, margin){
  const enc=s=>{ const b=new Uint8Array(s.length); for(let i=0;i<s.length;i++) b[i]=s.charCodeAt(i)&255; return b; };
  const parts=[], offs=[]; let len=0;
  const put=x=>{ const b=typeof x==='string'?enc(x):x; parts.push(b); len+=b.length; };
  const obj=(n, body)=>{ offs[n]=len; put(`${n} 0 obj\n${body}\nendobj\n`); };
  const n=pages.length, pageObj=i=>3+i*3;          // each page: page, image, contents
  put('%PDF-1.4\n%\xE2\xE3\xCF\xD3\n');
  obj(1, '<< /Type /Catalog /Pages 2 0 R >>');
  obj(2, `<< /Type /Pages /Kids [${pages.map((_,i)=>pageObj(i)+' 0 R').join(' ')}] /Count ${n} >>`);
  pages.forEach((pg,i)=>{
    const o=pageObj(i), w=+pg.w.toFixed(2), h=+pg.h.toFixed(2), y=+(pageH-margin-h).toFixed(2);
    const draw=`q ${w} 0 0 ${h} ${margin} ${y} cm /Im0 Do Q`;
    obj(o, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageW} ${pageH}] /Resources << /XObject << /Im0 ${o+1} 0 R >> >> /Contents ${o+2} 0 R >>`);
    offs[o+1]=len; put(`${o+1} 0 obj\n<< /Type /XObject /Subtype /Image /Width ${pg.pxW} /Height ${pg.pxH} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${pg.jpeg.length} >>\nstream\n`);
    put(pg.jpeg); put('\nendstream\nendobj\n');
    obj(o+2, `<< /Length ${draw.length} >>\nstream\n${draw}\nendstream`);
  });
  const total=3+n*3, xref=len;
  put(`xref\n0 ${total}\n0000000000 65535 f \n${Array.from({length:total-1},(_,k)=>String(offs[k+1]).padStart(10,'0')+' 00000 n \n').join('')}trailer\n<< /Size ${total} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  return new Blob(parts,{type:'application/pdf'});
}
const canvasJpeg = c => { const bin=atob(c.toDataURL('image/jpeg', 0.92).split(',')[1]), b=new Uint8Array(bin.length); for(let i=0;i<bin.length;i++) b[i]=bin.charCodeAt(i); return b; };
/* The chart across Letter pages: portrait for a tall chart (the timeline), landscape for a wide one (a tree).
   It fills the width inside half-inch margins and runs onto as many pages as its height needs. */
async function svgToPdf(svgText, name){
  const {canvas, w, h}=await svgToCanvas(svgText, 2);
  const land = w > h, pageW = land ? 792 : 612, pageH = land ? 612 : 792, margin = 36;
  const boxW = pageW-2*margin, boxH = pageH-2*margin;
  const k = Math.min(boxW/w, 1.5);                         // points per CSS px; never blown up past 150%
  const sliceCss = boxH/k, pxPerCss = canvas.width/w, sliceH = Math.max(1, Math.floor(sliceCss*pxPerCss));
  const pages=[];
  for(let y=0; y<canvas.height; y+=sliceH){
    const hh=Math.min(sliceH, canvas.height-y), c=document.createElement('canvas'); c.width=canvas.width; c.height=hh;
    const g=c.getContext('2d'); g.fillStyle='#fff'; g.fillRect(0,0,c.width,hh); g.drawImage(canvas, 0, y, canvas.width, hh, 0, 0, canvas.width, hh);
    pages.push({jpeg:canvasJpeg(c), pxW:c.width, pxH:hh, w:w*k, h:hh/pxPerCss*k});
  }
  download(name, jpegPdf(pages, pageW, pageH, margin));
}
