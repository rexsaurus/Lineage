import { subPriceDisplay } from "@/env";

export const metadata = { title: "Subscriber terms" };
export const dynamic = "force-dynamic";

export default function SubscriberTerms() {
  const price = subPriceDisplay();
  return (
    <div className="page">
      <p className="badge">DRAFT — pending legal review</p>
      <h1>Subscriber terms</h1>
      <h2>What you get</h2>
      <p>Following or subscribing to a family page lets you see what the family has shared there (not the items they keep private) and, if you want, get email updates when something is added.</p>
      <h2>Price</h2>
      <p>{price ? `A subscription is ${price}, charged by Stripe until you cancel.` : "Following a family is free. A paid subscription is not available yet; its price will be shown before you are ever asked to pay."}</p>
      <h2>Cancelling</h2>
      <p>You can stop the emails at any time from the link in any update. To cancel a paid subscription, reply to any update email.</p>
      <h2>Referrals</h2>
      <p>If you joined through a relative&apos;s link, that relative may earn a share of what you pay. It doesn&apos;t change your price.</p>
      <h2>Your information</h2>
      <p>See <a href="/privacy">Privacy</a>.</p>
    </div>
  );
}
