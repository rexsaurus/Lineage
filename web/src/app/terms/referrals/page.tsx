import { minPayoutCents, refundHoldDays, revShareBps } from "@/env";

export const metadata = { title: "Referral program terms" };
// the numbers are read from the environment at request time, never baked in at build time
export const dynamic = "force-dynamic";

// DRAFT, pending legal review. Every number shown comes from the app's settings; where Rex hasn't decided, it says so.
export default function ReferralTerms() {
  const bps = revShareBps();
  const hold = refundHoldDays();
  const min = minPayoutCents();
  return (
    <div className="page">
      <p className="badge">DRAFT — pending legal review</p>
      <h1>Referral program terms</h1>
      {bps === null ? <p className="card"><strong>The earnings program is not yet open.</strong> These terms describe how it is planned to work; nothing is earned or paid until it opens.</p> : null}
      <h2>What you earn</h2>
      <p>When a relative subscribes to a family page you keep, through your link, you earn {bps === null ? "a share (to be announced)" : `${bps / 100}%`} of each payment they make, after any sales tax, for as long as they stay subscribed. Free followers don&apos;t earn anything. You can&apos;t earn from your own subscription.</p>
      <h2>When it becomes yours</h2>
      <p>{hold === null ? "Each earning waits for a hold period (to be announced) in case the payment is refunded." : `Each earning waits ${hold} day${hold === 1 ? "" : "s"} after the payment, in case it is refunded.`} If a payment is refunded or disputed, the earning from it is cancelled; if it was already paid to you, it is taken off your next payout.</p>
      <h2>How you&apos;re paid</h2>
      <p>Payouts go through Stripe, to the bank account you give Stripe. Stripe may ask for identity and tax information before it can pay you. Payouts are approved by Lineage{min ? ` once your available balance reaches the minimum` : ""}.</p>
      <h2>Taxes</h2>
      <p>You are responsible for any taxes on what you earn.</p>
      <h2>Changes</h2>
      <p>These terms may change; changes will be posted here and won&apos;t reduce what you have already earned.</p>
    </div>
  );
}
