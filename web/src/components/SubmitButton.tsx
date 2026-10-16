"use client";
import { useFormStatus } from "react-dom";

export function SubmitButton({ children, pending }: { children: React.ReactNode; pending?: string }) {
  const { pending: busy } = useFormStatus();
  return (
    <button className="btn" type="submit" disabled={busy} aria-busy={busy}>
      {busy ? pending || "One moment…" : children}
    </button>
  );
}
