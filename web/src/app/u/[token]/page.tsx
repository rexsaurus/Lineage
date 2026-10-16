import { notFound } from "next/navigation";
import { readUnsubscribeToken } from "@/lib/digest";
import { unsubscribeAction } from "../../sub-actions";

export const metadata = { title: "Unsubscribe" };

// The unsubscribe link in every update email: one tap, no sign-in. (Mail apps' own one-click unsubscribe uses the
// List-Unsubscribe header → POST /api/unsubscribe/[token].)
export default async function Unsubscribe({ params, searchParams }: { params: Promise<{ token: string }>; searchParams: Promise<Record<string, string | undefined>> }) {
  const { token } = await params;
  const sp = await searchParams;
  if (!readUnsubscribeToken(decodeURIComponent(token))) notFound();
  if (sp.done) {
    return (
      <div className="page">
        <h1>You&apos;re unsubscribed</h1>
        <p>You won&apos;t get any more update emails about this family. You can turn them back on from the family page.</p>
      </div>
    );
  }
  return (
    <div className="page">
      <h1>Stop update emails?</h1>
      <form action={unsubscribeAction}>
        <input type="hidden" name="token" value={decodeURIComponent(token)} />
        <button className="btn" type="submit">Unsubscribe</button>
      </form>
    </div>
  );
}
