"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

const MAX = 25 * 1024 * 1024;
const LONG_EDGE = 2400;
const DIRECT_LIMIT = 4 * 1024 * 1024; // larger files go straight to storage when the server offers a signed URL

/** Re-draws a photo at most 2400px on its long edge as JPEG. The re-encode also drops location and other metadata.
 * Returns null when the browser can't decode the file (e.g. HEIC outside Safari), and the original is sent instead. */
async function resize(file: File): Promise<Blob | null> {
  if (!file.type.startsWith("image/")) return null;
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, LONG_EDGE / Math.max(bmp.width, bmp.height));
    const w = Math.round(bmp.width * scale), h = Math.round(bmp.height * scale);
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    c.getContext("2d")!.drawImage(bmp, 0, 0, w, h);
    return await new Promise(res => c.toBlob(b => res(b), "image/jpeg", 0.88));
  } catch {
    return null;
  }
}

function send(url: string, method: string, body: XMLHttpRequestBodyInit, onProgress: (p: number) => void, headers: Record<string, string> = {}) {
  return new Promise<{ status: number; text: string }>((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open(method, url);
    for (const [k, v] of Object.entries(headers)) x.setRequestHeader(k, v);
    x.upload.onprogress = e => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    x.onload = () => resolve({ status: x.status, text: x.responseText });
    x.onerror = () => reject(new Error("network"));
    x.send(body);
  });
}

export function UploadForm({ familyId }: { familyId: string }) {
  const router = useRouter();
  const camera = useRef<HTMLInputElement>(null);
  const library = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [caption, setCaption] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState("");

  function pick(f: File | undefined) {
    setError("");
    if (!f) return;
    if (f.size > MAX) {
      setError("That file is over 25 MB. Please choose a smaller photo or document.");
      return;
    }
    setFile(f);
  }

  async function upload() {
    if (!file) return;
    setError("");
    setProgress(0);
    try {
      const small = await resize(file);
      const blob: Blob = small || file;
      const name = small ? "photo.jpg" : file.name;
      let res: { status: number; text: string };
      if (blob.size > DIRECT_LIMIT) {
        const sign = await fetch("/api/upload/sign", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ familyId, type: blob.type || "application/octet-stream", size: blob.size }) });
        if (sign.ok) {
          const { url, key } = await sign.json();
          const put = await send(url, "PUT", blob, setProgress, { "Content-Type": blob.type || "application/octet-stream" });
          if (put.status >= 300) throw new Error("storage");
          res = await fetch("/api/upload/complete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ familyId, key, caption }) }).then(async r => ({ status: r.status, text: await r.text() }));
        } else {
          res = await viaServer();
        }
      } else {
        res = await viaServer();
      }
      async function viaServer() {
        const fd = new FormData();
        fd.set("familyId", familyId);
        fd.set("caption", caption);
        fd.set("file", blob, name);
        return send("/api/upload", "POST", fd, setProgress);
      }
      const j = JSON.parse(res.text || "{}");
      if (res.status >= 300 || !j.ok) throw new Error(j.message || "upload");
      router.push(`/family/${familyId}`);
      router.refresh();
    } catch (e) {
      setProgress(null);
      const msg = e instanceof Error && e.message && !["upload", "network", "storage"].includes(e.message) ? e.message : "";
      setError(msg || "The upload didn't finish. Please check your connection and try again.");
    }
  }

  return (
    <div>
      <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={e => pick(e.target.files?.[0])} data-testid="camera-input" />
      <input ref={library} type="file" accept="image/*,application/pdf" hidden onChange={e => pick(e.target.files?.[0])} data-testid="library-input" />
      {!file ? (
        <>
          <button type="button" className="btn" onClick={() => camera.current?.click()}>Take a photo</button>
          <button type="button" className="btn secondary" style={{ marginTop: 12 }} onClick={() => library.current?.click()}>Choose a photo or document</button>
        </>
      ) : (
        <div className="card">
          <p><strong>Ready to add:</strong> {file.name}</p>
          <label htmlFor="caption">Caption <span className="muted small">(optional)</span></label>
          <input id="caption" value={caption} maxLength={200} onChange={e => setCaption(e.target.value)} placeholder="e.g. Grandma Rose, 1952" />
          {progress !== null ? (
            <>
              <label htmlFor="up-progress">Uploading… {progress}%</label>
              <progress id="up-progress" className="progress" value={progress} max={100} />
            </>
          ) : (
            <>
              <button type="button" className="btn" style={{ marginTop: 20 }} onClick={upload}>Add to my family page</button>
              <button type="button" className="btn secondary" style={{ marginTop: 12 }} onClick={() => setFile(null)}>Choose a different file</button>
            </>
          )}
        </div>
      )}
      {error ? <p className="error" role="alert" style={{ marginTop: 16 }}>{error}</p> : null}
    </div>
  );
}
