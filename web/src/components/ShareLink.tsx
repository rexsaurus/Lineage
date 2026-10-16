"use client";
import { useState } from "react";

export function ShareLink({ url, familyName }: { url: string; familyName: string }) {
  const [msg, setMsg] = useState("");
  const canShare = typeof navigator !== "undefined" && "share" in navigator;
  return (
    <div>
      <label htmlFor="invite-link">Invitation link</label>
      <input id="invite-link" readOnly value={url} onFocus={e => e.currentTarget.select()} />
      <button type="button" className="btn" style={{ marginTop: 12 }}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(url);
            setMsg("Link copied. Paste it into a text message.");
          } catch {
            setMsg("Press and hold the link above to copy it.");
          }
        }}>
        Copy invite link
      </button>
      {canShare ? (
        <button type="button" className="btn secondary" style={{ marginTop: 12 }}
          onClick={() => navigator.share({ title: `${familyName} on Lineage`, text: `Join the ${familyName} family page on Lineage:`, url }).catch(() => {})}>
          Share…
        </button>
      ) : null}
      {msg ? <p className="okmsg" role="status">{msg}</p> : null}
    </div>
  );
}
