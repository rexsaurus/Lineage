// Upload checks (spec §3.1, §12, §14): sniff the real type from the bytes, enforce the size limit, and strip
// location and other metadata from photos before they are stored.
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

export type Sniffed = { mime: string; ext: string; kind: "photo" | "document" };

export function sniff(b: Buffer): Sniffed | null {
  if (b.length >= 3 && b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return { mime: "image/jpeg", ext: "jpg", kind: "photo" };
  if (b.length >= 8 && b.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]))) return { mime: "image/png", ext: "png", kind: "photo" };
  if (b.length >= 5 && b.subarray(0, 5).toString("latin1") === "%PDF-") return { mime: "application/pdf", ext: "pdf", kind: "document" };
  if (b.length >= 12 && b.subarray(0, 4).toString("latin1") === "RIFF" && b.subarray(8, 12).toString("latin1") === "WEBP") return { mime: "image/webp", ext: "webp", kind: "photo" };
  if (b.length >= 12 && b.subarray(4, 8).toString("latin1") === "ftyp") {
    const brand = b.subarray(8, 12).toString("latin1");
    if (["heic", "heix", "hevc", "hevx", "mif1", "msf1", "heim", "heis"].includes(brand)) return { mime: "image/heic", ext: "heic", kind: "photo" };
  }
  return null;
}

/** JPEG: drop APP1 (Exif, XMP — where GPS lives), APP13 (IPTC) and comments; keep everything needed to display. */
export function stripJpeg(b: Buffer): Buffer {
  if (!(b[0] === 0xff && b[1] === 0xd8)) return b;
  const out: Buffer[] = [b.subarray(0, 2)];
  let i = 2;
  while (i + 4 <= b.length) {
    if (b[i] !== 0xff) return b; // not a well-formed marker stream: leave untouched rather than corrupt it
    const marker = b[i + 1];
    if (marker === 0xda) {
      out.push(b.subarray(i)); // start of scan: the rest is image data
      return Buffer.concat(out);
    }
    if (marker === 0xd8 || (marker >= 0xd0 && marker <= 0xd7) || marker === 0x01) {
      out.push(b.subarray(i, i + 2));
      i += 2;
      continue;
    }
    const len = b.readUInt16BE(i + 2);
    const seg = b.subarray(i, i + 2 + len);
    const drop = marker === 0xe1 || marker === 0xed || marker === 0xfe;
    if (!drop) out.push(seg);
    i += 2 + len;
  }
  return Buffer.concat(out);
}

/** PNG: drop eXIf and text chunks. */
export function stripPng(b: Buffer): Buffer {
  const out: Buffer[] = [b.subarray(0, 8)];
  let i = 8;
  while (i + 12 <= b.length) {
    const len = b.readUInt32BE(i);
    const type = b.subarray(i + 4, i + 8).toString("latin1");
    const end = i + 12 + len;
    if (end > b.length) return b;
    if (!["eXIf", "tEXt", "iTXt", "zTXt"].includes(type)) out.push(b.subarray(i, end));
    i = end;
    if (type === "IEND") break;
  }
  return Buffer.concat(out);
}

export function stripMetadata(b: Buffer, mime: string): Buffer {
  if (mime === "image/jpeg") return stripJpeg(b);
  if (mime === "image/png") return stripPng(b);
  // HEIC and WebP are stored as received. The upload page converts photos to JPEG in the browser first (which also
  // drops location); see README "Known limits".
  return b;
}

export type UploadCheck = { ok: true; sniffed: Sniffed; body: Buffer } | { ok: false; message: string };

export function checkUpload(b: Buffer): UploadCheck {
  if (b.length === 0) return { ok: false, message: "That file looks empty. Please try another." };
  if (b.length > MAX_UPLOAD_BYTES) return { ok: false, message: "That file is over 25 MB. Please choose a smaller photo or document." };
  const s = sniff(b);
  if (!s) return { ok: false, message: "Please choose a photo (JPEG, PNG or HEIC) or a PDF document." };
  return { ok: true, sniffed: s, body: stripMetadata(b, s.mime) };
}
