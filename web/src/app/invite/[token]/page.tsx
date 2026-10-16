import { notFound } from "next/navigation";
import { getDb } from "@/db";
import { currentUser } from "@/lib/auth";
import { inviteByToken } from "@/lib/invites";
import { memberRole } from "@/lib/families";
import { acceptInviteAction, loginAction } from "../../actions";
import { SubmitButton } from "@/components/SubmitButton";

export const metadata = { title: "You're invited" };

export default async function AcceptInvite({ params, searchParams }: { params: Promise<{ token: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const { token } = await params;
  const sp = await searchParams;
  const db = await getDb();
  const inv = await inviteByToken(db, token);
  if (!inv) notFound();
  const u = await currentUser();
  const already = u ? await memberRole(db, inv.invite.familyId, u.id) : null;
  const from = inv.inviterName || inv.inviterEmail || "A relative";
  if (!inv.usable && !already) {
    return (
      <div className="page">
        <h1>This invitation has been used</h1>
        <p>Each invitation link lets one person join. Ask {from} to send you a new one.</p>
      </div>
    );
  }
  return (
    <div className="page">
      <h1>Join the {inv.familyName} page</h1>
      <p>{from} invited you to see the family&apos;s photos and papers on Lineage, and to add your own.</p>
      {sp.error ? <p className="error" role="alert">This invitation has already been used. Ask for a new one.</p> : null}
      {u ? (
        <form action={acceptInviteAction}>
          <input type="hidden" name="token" value={token} />
          <SubmitButton>{already ? "Open the family page" : `Join ${inv.familyName}`}</SubmitButton>
        </form>
      ) : (
        <form action={loginAction}>
          <input type="hidden" name="next" value={`/invite/${token}`} />
          <label htmlFor="email">Your email</label>
          <input id="email" name="email" type="email" inputMode="email" autoComplete="email" required defaultValue={inv.invite.email || ""} />
          <p className="hint">We&apos;ll email you a link to join. No password needed.</p>
          <div style={{ marginTop: 20 }}><SubmitButton>Email me a link to join</SubmitButton></div>
        </form>
      )}
    </div>
  );
}
