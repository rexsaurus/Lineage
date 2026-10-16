// archive_open_book.js
// Saves an OPEN (freely downloadable) book from archive.org.
// Refuses lending-library / access-restricted items.
//
// Usage:  node archive_open_book.js <archive.org URL or identifier> [output directory]
// Needs:  Node 18+, and for the screenshot fallback: npm i playwright && npx playwright install chromium

const fs = require('fs');
const path = require('path');

const RESTRICTED_COLLECTIONS = ['inlibrary', 'printdisabled', 'lendinglibrary', 'browserlending'];

function toIdentifier(input) {
  const m = input.match(/archive\.org\/(?:details|download|embed)\/([^/?#]+)/);
  return m ? m[1] : input.trim();
}

async function getMetadata(id) {
  const res = await fetch(`https://archive.org/metadata/${id}`);
  if (!res.ok) throw new Error(`Metadata request failed: ${res.status}`);
  const data = await res.json();
  if (!data.metadata) throw new Error(`No item found for "${id}"`);
  return data;
}

// Every reason the item is not open; an empty list means it is safe to save.
function checkOpen(data) {
  const md = data.metadata;
  const collections = [].concat(md.collection || []);
  const reasons = [];
  if (String(md['access-restricted-item']) === 'true') reasons.push('marked access-restricted');
  if (data.is_dark) reasons.push('item is dark (not public)');
  const lending = collections.filter(c => RESTRICTED_COLLECTIONS.includes(c));
  if (lending.length) reasons.push(`in lending collection(s): ${lending.join(', ')}`);
  return reasons;
}

async function download(url, dest) {
  const res = await fetch(url, { redirect: 'follow' });
  if (!res.ok) throw new Error(`Download failed (${res.status}): ${url}`);
  const buf = Buffer.from(await res.arrayBuffer());

  // Make sure we actually got a PDF, not an HTML error/login page or an encrypted file.
  if (buf.subarray(0, 5).toString() !== '%PDF-') {
    const preview = buf.subarray(0, 200).toString().replace(/\s+/g, ' ');
    throw new Error(
      `Downloaded file is not a PDF (content-type: ${res.headers.get('content-type')}).\n` +
      `First bytes: ${preview}`
    );
  }
  fs.writeFileSync(dest, buf);
}

function pickPdf(files) {
  const usable = (files || []).filter(f =>
    /pdf/i.test(f.format || '') &&
    f.name.toLowerCase().endsWith('.pdf') &&
    !f.private &&
    !/encrypted|lcp/i.test(`${f.format} ${f.name}`)
  );
  const rank = f =>
    f.format === 'Text PDF' ? 0 :
    f.format === 'Image Container PDF' ? 1 :
    /additional/i.test(f.format) ? 3 : 2;
  return usable.sort((a, b) => rank(a) - rank(b))[0];
}

async function screenshotPages(id, pageCount, outDir) {
  const { chromium } = require('playwright');
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 1800 } });

  for (let n = 0; n < pageCount; n++) {
    await page.goto(`https://archive.org/details/${id}/page/n${n}/mode/1up`, { waitUntil: 'networkidle' });
    const img = page.locator('.BRpagecontainer.BRpage-visible img').first();
    await img.waitFor({ state: 'visible', timeout: 15000 });
    await page.waitForTimeout(800); // let the full-resolution image load
    await img.screenshot({ path: path.join(outDir, `${String(n + 1).padStart(4, '0')}.png`) });
    process.stdout.write(`\rPage ${n + 1}/${pageCount}`);
  }
  console.log();
  await browser.close();
}

(async () => {
  const arg = process.argv[2];
  if (!arg) {
    console.error('Usage: node archive_open_book.js <archive.org URL or identifier> [output directory]');
    process.exit(1);
  }
  const outRoot = process.argv[3] || '.';
  fs.mkdirSync(outRoot, { recursive: true });

  const id = toIdentifier(arg);
  const data = await getMetadata(id);
  const title = data.metadata.title || id;

  const reasons = checkOpen(data);
  if (reasons.length) {
    console.error(`"${title}" is not an open book (${reasons.join('; ')}). Skipping.`);
    process.exit(2);
  }

  // Preferred: download the PDF the archive already provides.
  const pdf = pickPdf(data.files);
  if (pdf) {
    const dest = path.join(outRoot, `${id}.pdf`);
    console.log(`"${title}" is open. Downloading ${pdf.name} (${pdf.format})...`);
    await download(`https://archive.org/download/${id}/${encodeURIComponent(pdf.name)}`, dest);
    console.log(`Saved ${dest}`);
    return;
  }

  // Fallback: open item with no PDF, so screenshot each page from the viewer.
  const pageCount = parseInt(data.metadata.imagecount, 10);
  if (!pageCount) throw new Error('No PDF and no page count found for this item.');
  const pagesDir = path.join(outRoot, `${id}-pages`);
  console.log(`"${title}" is open but has no PDF. Capturing ${pageCount} pages...`);
  await screenshotPages(id, pageCount, pagesDir);
  console.log(`Saved pages to ${pagesDir}/  (combine with: img2pdf ${pagesDir}/*.png -o ${path.join(outRoot, id + '.pdf')})`);
})().catch(err => {
  console.error(err.message);
  process.exit(1);
});
