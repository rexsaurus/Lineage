import { notFound } from "next/navigation";
import { env } from "@/env";
import { fakeConnect } from "@/lib/connect";

export const metadata = { title: "Test payout setup" };

// Development and tests only (CONNECT_DRIVER=fake): stands in for Stripe's Express onboarding.
export default async function FakeConnect({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  if (env().CONNECT_DRIVER !== "fake") notFound();
  const sp = await searchParams;
  if (!sp.account || !fakeConnect.accounts.has(sp.account)) notFound();
  return (
    <div className="page">
      <p className="badge">TEST MODE — no money moves</p>
      <h1>Test payout setup</h1>
      <p>This page stands in for Stripe&apos;s onboarding while Lineage is being tested.</p>
      <form action="/dev/fake-connect/done" method="post">
        <input type="hidden" name="account" value={sp.account} />
        <input type="hidden" name="return" value={sp.return || "/earnings"} />
        <button className="btn" type="submit">Finish setup (test)</button>
      </form>
    </div>
  );
}
