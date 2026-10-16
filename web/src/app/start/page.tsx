import type { Metadata } from "next";
import { cookies } from "next/headers";
import { startAction } from "../actions";
import { SubmitButton } from "@/components/SubmitButton";
import { priceDisplay } from "@/env";
import { isSlug, normalizeSrc, SRC_COOKIE } from "@/lib/src";

export const metadata: Metadata = { title: "Start" };

export default async function Start({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  const src = isSlug(sp.src?.toLowerCase()) ? sp.src!.toLowerCase() : normalizeSrc((await cookies()).get(SRC_COOKIE)?.value);
  const price = priceDisplay();
  return (
    <div className="page">
      <p className="steps">Step 1 of 4</p>
      <h1>Your email</h1>
      <p>{price ? "Next you'll pay securely with Stripe. Your card details never reach Lineage." : "Your spot is free while the price is being set."}</p>
      <form action={startAction}>
        <input type="hidden" name="src" value={src} />
        <label htmlFor="email">Your email</label>
        <input id="email" name="email" type="email" inputMode="email" autoComplete="email" required autoFocus aria-describedby={sp.error ? "email-err" : "email-hint"} />
        {sp.error === "email" ? (
          <p id="email-err" className="error" role="alert">Please check your email address and try again.</p>
        ) : (
          <p id="email-hint" className="hint">We&apos;ll use it to send your family page and a sign-in link. No password needed.</p>
        )}
        <div style={{ marginTop: 20 }}>
          <SubmitButton>{price ? "Continue to payment" : "Reserve my spot"}</SubmitButton>
        </div>
      </form>
    </div>
  );
}
