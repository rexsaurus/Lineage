import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/db";
import { requireUser } from "@/lib/auth";
import { familyForReader } from "@/lib/families";
import { getSubscription } from "@/lib/subscriptions";
import { setDigestAction, unfollowAction } from "../../../sub-actions";
import { SubmitButton } from "@/components/SubmitButton";

export const metadata = { title: "Email updates" };

export default async function Updates({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const { id } = await params;
  const sp = await searchParams;
  const u = await requireUser(`/family/${id}/updates`);
  const db = await getDb();
  const r = await familyForReader(db, id, u);
  if (!r) notFound();
  const sub = await getSubscription(db, r.family.id, u.id);
  const live = sub && ["active", "past_due"].includes(sub.status);
  return (
    <div className="page">
      <h1>Email updates</h1>
      <p>About the {r.family.name} page: new photos, documents and relatives.</p>
      {sp.saved ? <p className="okmsg" role="status">Saved.</p> : null}
      {live ? (
        <>
          <form action={setDigestAction}>
            <input type="hidden" name="familyId" value={r.family.id} />
            <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
              <legend style={{ fontWeight: 600 }}>How often?</legend>
              {(["weekly", "monthly", "off"] as const).map(f => (
                <label key={f} style={{ fontWeight: 400, display: "flex", gap: 12, alignItems: "center", minHeight: 48 }}>
                  <input type="radio" name="freq" value={f} defaultChecked={sub!.digestFreq === f} style={{ width: 28, height: 28 }} />
                  {f === "weekly" ? "Once a week" : f === "monthly" ? "Once a month" : "Never"}
                </label>
              ))}
            </fieldset>
            <div style={{ marginTop: 16 }}><SubmitButton>Save</SubmitButton></div>
          </form>
          {sub!.kind === "follow" ? (
            <form action={unfollowAction} style={{ marginTop: 24 }}>
              <input type="hidden" name="familyId" value={r.family.id} />
              <button className="btn secondary" type="submit">Stop following this family</button>
            </form>
          ) : (
            <p className="small muted" style={{ marginTop: 24 }}>To cancel your subscription, reply to any update email and Rex will cancel it.</p>
          )}
        </>
      ) : (
        <>
          <p>You don&apos;t get email updates about this family yet.</p>
          <Link className="btn" href={`/f/${r.family.id}`}>Get updates</Link>
        </>
      )}
      <p style={{ marginTop: 24 }}><Link href={`/family/${r.family.id}`}>Back to the family page</Link></p>
    </div>
  );
}
