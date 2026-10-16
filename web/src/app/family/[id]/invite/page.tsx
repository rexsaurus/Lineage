import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/db";
import { env } from "@/env";
import { requireUser } from "@/lib/auth";
import { familyForViewer } from "@/lib/families";
import { inviteByToken } from "@/lib/invites";
import { inviteAction, inviteLinkAction } from "../../../actions";
import { SubmitButton } from "@/components/SubmitButton";
import { ShareLink } from "@/components/ShareLink";

export const metadata = { title: "Invite a relative" };

export default async function Invite({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const { id } = await params;
  const sp = await searchParams;
  const u = await requireUser(`/family/${id}/invite`);
  const db = await getDb();
  const f = await familyForViewer(db, id, u);
  if (!f) notFound();
  // show a link only for an invite this family created
  const inv = sp.t ? await inviteByToken(db, sp.t) : null;
  const link = inv && inv.invite.familyId === f.id && inv.usable ? new URL(`/invite/${inv.invite.token}`, env().APP_URL).toString() : null;
  return (
    <div className="page">
      <p className="steps">Step 4 of 4</p>
      <h1>Invite a relative</h1>
      {sp.sent ? <p className="okmsg" role="status">Invitation sent.</p> : null}
      <form action={inviteAction}>
        <input type="hidden" name="familyId" value={f.id} />
        <label htmlFor="name">Their name</label>
        <input id="name" name="name" maxLength={80} autoComplete="off" />
        <label htmlFor="email">Their email</label>
        <input id="email" name="email" type="email" inputMode="email" autoComplete="off" required />
        {sp.error === "email" ? <p className="error" role="alert">Please check the email address.</p> : null}
        <div style={{ marginTop: 20 }}><SubmitButton>Send the invitation</SubmitButton></div>
      </form>

      <h2>Or send a link by text</h2>
      {link ? (
        <ShareLink url={link} familyName={f.name} />
      ) : (
        <form action={inviteLinkAction}>
          <input type="hidden" name="familyId" value={f.id} />
          <SubmitButton>Make an invitation link</SubmitButton>
        </form>
      )}
      <p className="small muted">Each link lets one person join.</p>
      <p style={{ marginTop: 24 }}><Link href={`/family/${f.id}`}>Back to the {f.name} page</Link></p>
    </div>
  );
}
