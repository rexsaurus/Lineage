import { notFound } from "next/navigation";
import { env } from "@/env";
import { fakeSessions } from "@/lib/payments";

export const metadata = { title: "Test checkout" };

// Development and tests only (PAYMENTS_DRIVER=fake): stands in for Stripe Checkout. 404 whenever real Stripe is set.
export default async function FakeCheckout({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  if (env().PAYMENTS_DRIVER !== "fake") notFound();
  const sp = await searchParams;
  const s = sp.session ? fakeSessions.get(sp.session) : undefined;
  if (!s) notFound();
  return (
    <div className="page">
      <p className="badge">TEST MODE — no money moves</p>
      <h1>Test checkout</h1>
      <p>This page stands in for Stripe while Lineage is being tested.</p>
      <form action="/dev/fake-checkout/pay" method="post">
        <input type="hidden" name="session" value={s.id} />
        <input type="hidden" name="success" value={sp.success || ""} />
        <button className="btn" type="submit">Pay (test)</button>
      </form>
      <a className="btn secondary" style={{ marginTop: 12 }} href={sp.cancel || "/"}>Cancel</a>
    </div>
  );
}
