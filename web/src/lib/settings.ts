import { eq } from "drizzle-orm";
import type { Db } from "@/db";
import { settings } from "@/db/schema";

export async function getSetting(db: Db, key: string): Promise<string | null> {
  const [r] = await db.select().from(settings).where(eq(settings.key, key)).limit(1);
  return r?.value ?? null;
}

export async function setSetting(db: Db, key: string, value: string) {
  await db.insert(settings).values({ key, value }).onConflictDoUpdate({ target: settings.key, set: { value } });
}

/** Spec §6 fallback: when on, /start sends people to the Stripe Payment Link instead of Checkout. */
export const PAYMENT_LINK_FALLBACK = "payment_link_fallback";
