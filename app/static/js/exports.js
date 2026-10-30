/* ================================================================== EXPORTS
   One Download menu for the chart pages (Genealogy, Timeline) and the writers behind it. Everything runs
   in the browser, so the published static site exports exactly as the local app does: the chart's SVG is
   drawn to a canvas, which gives the PNG, and a JPEG of it wrapped in a one-page PDF (no library). */
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
/* A single-page PDF holding one JPEG (an Image XObject with /DCTDecode). The page takes the chart's
   aspect at 72 dpi of its CSS size, so it opens at the size it was drawn and prints scaled to fit. */
function jpegPdf(jpeg, pxW, pxH, pageW, pageH){
  const enc=s=>{ const b=new Uint8Array(s.length); for(let i=0;i<s.length;i++) b[i]=s.charCodeAt(i)&255; return b; };
  const W=+pageW.toFixed(2), H=+pageH.toFixed(2), draw=`q ${W} 0 0 ${H} 0 0 cm /Im0 Do Q`;
  const parts=[], offs=[]; let len=0;
  const put=x=>{ const b=typeof x==='string'?enc(x):x; parts.push(b); len+=b.length; };
  const obj=(n, body)=>{ offs[n]=len; put(`${n} 0 obj\n${body}\nendobj\n`); };
  put('%PDF-1.4\n%\xE2\xE3\xCF\xD3\n');
  obj(1, '<< /Type /Catalog /Pages 2 0 R >>');
  obj(2, '<< /Type /Pages /Kids [3 0 R] /Count 1 >>');
  obj(3, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${W} ${H}] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`);
  offs[4]=len; put(`4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${pxW} /Height ${pxH} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.length} >>\nstream\n`);
  put(jpeg); put('\nendstream\nendobj\n');
  obj(5, `<< /Length ${draw.length} >>\nstream\n${draw}\nendstream`);
  const xref=len;
  put(`xref\n0 6\n0000000000 65535 f \n${[1,2,3,4,5].map(n=>String(offs[n]).padStart(10,'0')+' 00000 n \n').join('')}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
  return new Blob(parts,{type:'application/pdf'});
}
async function svgToPdf(svgText, name){
  const {canvas, w, h}=await svgToCanvas(svgText, 2);
  const b64=canvas.toDataURL('image/jpeg', 0.92).split(',')[1], bin=atob(b64), jpeg=new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++) jpeg[i]=bin.charCodeAt(i);
  // CSS px → points (0.75); a page is at most 200 inches a side (PDF's own limit), so huge charts shrink to fit
  const k=Math.min(0.75, 14400/w, 14400/h);
  download(name, jpegPdf(jpeg, canvas.width, canvas.height, w*k, h*k));
}
