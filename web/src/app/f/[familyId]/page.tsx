import Link from "next/link";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { eq } from "drizzle-orm";
import { getDb } from "@/db";
import { users } from "@/db/schema";
import { subPriceDisplay } from "@/env";
import { currentUser } from "@/lib/auth";
import { familyForReader, getFamily } from "@/lib/families";
import { isRefCode, REF_COOKIE } from "@/lib/refs";
import { getSubscription } from "@/lib/subscriptions";
import { subscribeAction } from "../../sub-actions";
import { SubmitButton } from "@/components/SubmitButton";

export const metadata = { title: "Follow a family" };

// A family's subscribe page, reached from an archivist's referral link (/f/<id>?ref=<code>) or an invite. Shows only the
// family name and who shared it — nothing from the family page itself until they follow or subscribe.
export default async function FamilyLanding({ params, searchParams }: { params: Promise<{ familyId: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const { familyId } = await params;
  const sp = await searchParams;
  const db = await getDb();
  const fam = await getFamily(db, familyId);
  if (!fam || fam.isDemo) notFound();
  const viewer = await currentUser();
  const access = await familyForReader(db, fam.id, viewer);
  const sub = viewer ? await getSubscription(db, fam.id, viewer.id) : null;
  const code = sp.ref?.toLowerCase() || (await cookies()).get(REF_COOKIE)?.value;
  const [referrer] = isRefCode(code) ? await db.select({ name: users.name }).from(users).where(eq(users.refCode, code)).limit(1) : [];
  const price = subPriceDisplay();
  const from = referrer?.name?.trim().split(/\s+/)[0];

  return (
    <div className="page">
      <h1>The {fam.name.replace(/^the\s+/i, "")} family page</h1>
      <p>{from ? `${from} keeps the family's photos, letters and records on Lineage, and invited you to follow along.` : "A relative keeps the family's photos, letters and records on Lineage."}</p>
      {sp.left ? <p className="okmsg" role="status">You&apos;ve stopped following this family.</p> : null}
      {sp.sent ? (
        <div className="card" role="status">
          <h2 style={{ marginTop: 0 }}>Check your email</h2>
          <p>We&apos;ve sent you a link. Open it on this phone and you&apos;ll be back here to finish.</p>
        </div>
      ) : access && sub?.status !== "canceled" ? (
        <>
          <p className="okmsg">{access.access === "subscriber" ? "You're following this family." : "You're a member of this family."}</p>
          <Link className="btn" href={`/family/${fam.id}`}>Open the family page</Link>
        </>
      ) : (
        <section className="card" aria-labelledby="sub-h">
          <h2 id="sub-h" style={{ marginTop: 0 }}>{price ? `Subscribe — ${price}` : "Follow this family — free"}</h2>
          <p>See the family page, and get an email when new photos and papers are added: weekly, monthly, or never — you choose.</p>
          <form action={subscribeAction}>
            <input type="hidden" name="familyId" value={fam.id} />
            {viewer ? null : (
              <>
                <label htmlFor="email">Your email</label>
                <input id="email" name="email" type="email" inputMode="email" autoComplete="email" required />
                {sp.error ? <p className="error" role="alert">Please check your email address.</p> : null}
              </>
            )}
            <div style={{ marginTop: 20 }}>
              <SubmitButton>{price ? "Subscribe" : "Follow this family"}</SubmitButton>
            </div>
          </form>
          {price ? <p className="small muted">You&apos;ll pay securely with Stripe and can cancel any time. <Link href="/terms/subscribers">Subscriber terms</Link></p> : null}
        </section>
      )}
      <p className="small"><Link href="/privacy">Privacy</Link></p>
    </div>
  );
}
