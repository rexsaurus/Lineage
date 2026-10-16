import Stripe from "stripe";
import { env } from "@/env";

// Stripe Connect Express for archivist payouts: onboarding through Account Links, money moved with Transfers from the
// platform balance. Test mode only until Rex decides otherwise (live keys are refused by env.ts). The fake driver keeps
// accounts in memory and "onboards" through /dev/fake-connect.
export interface Connect {
  createAccount(a: { email: string; userId: string }): Promise<{ id: string }>;
  onboardingLink(a: { accountId: string; refreshUrl: string; returnUrl: string }): Promise<string>;
  getAccount(id: string): Promise<{ payoutsEnabled: boolean; detailsSubmitted: boolean } | null>;
  transfer(a: { amountCents: number; currency: string; destination: string; idempotencyKey: string; metadata: Record<string, string> }): Promise<{ id: string }>;
}

export class StripeConnect implements Connect {
  private stripe: Stripe;
  constructor(secretKey: string, client?: Stripe) {
    if (secretKey.startsWith("sk_live_") && !env().ALLOW_LIVE_STRIPE) throw new Error("live Stripe key refused (ALLOW_LIVE_STRIPE is not set)");
    this.stripe = client || new Stripe(secretKey);
  }
  async createAccount(a: { email: string; userId: string }) {
    const acct = await this.stripe.accounts.create({
      type: "express",
      email: a.email,
      capabilities: { transfers: { requested: true } },
      metadata: { user_id: a.userId },
    });
    return { id: acct.id };
  }
  async onboardingLink(a: { accountId: string; refreshUrl: string; returnUrl: string }) {
    const l = await this.stripe.accountLinks.create({ account: a.accountId, refresh_url: a.refreshUrl, return_url: a.returnUrl, type: "account_onboarding" });
    return l.url;
  }
  async getAccount(id: string) {
    try {
      const a = await this.stripe.accounts.retrieve(id);
      return { payoutsEnabled: !!a.payouts_enabled, detailsSubmitted: !!a.details_submitted };
    } catch {
      return null;
    }
  }
  async transfer(a: { amountCents: number; currency: string; destination: string; idempotencyKey: string; metadata: Record<string, string> }) {
    const t = await this.stripe.transfers.create(
      { amount: a.amountCents, currency: a.currency, destination: a.destination, metadata: a.metadata },
      { idempotencyKey: a.idempotencyKey },
    );
    return { id: t.id };
  }
}

type FakeAcct = { payoutsEnabled: boolean; detailsSubmitted: boolean };
const g = globalThis as unknown as { __fakeConnect?: { accounts: Map<string, FakeAcct>; transfers: Map<string, { id: string; amountCents: number; destination: string }> } };
export const fakeConnect = (g.__fakeConnect ??= { accounts: new Map(), transfers: new Map() });

export class FakeConnect implements Connect {
  async createAccount() {
    const id = `acct_fake_${Math.random().toString(36).slice(2, 12)}`;
    fakeConnect.accounts.set(id, { payoutsEnabled: false, detailsSubmitted: false });
    return { id };
  }
  async onboardingLink(a: { accountId: string; returnUrl: string }) {
    return `/dev/fake-connect?account=${encodeURIComponent(a.accountId)}&return=${encodeURIComponent(a.returnUrl)}`;
  }
  async getAccount(id: string) {
    return fakeConnect.accounts.get(id) || null;
  }
  async transfer(a: { amountCents: number; destination: string; idempotencyKey: string }) {
    const prior = fakeConnect.transfers.get(a.idempotencyKey);
    if (prior) return { id: prior.id };
    if (!fakeConnect.accounts.get(a.destination)?.payoutsEnabled) throw new Error("destination account can't receive transfers");
    const t = { id: `tr_fake_${Math.random().toString(36).slice(2, 12)}`, amountCents: a.amountCents, destination: a.destination };
    fakeConnect.transfers.set(a.idempotencyKey, t);
    return { id: t.id };
  }
}

let override: Connect | null = null;
export function setConnect(c: Connect | null) {
  override = c;
}
export function connectProvider(): Connect {
  if (override) return override;
  const e = env();
  return e.CONNECT_DRIVER === "stripe" ? new StripeConnect(e.STRIPE_SECRET_KEY!) : new FakeConnect();
}
