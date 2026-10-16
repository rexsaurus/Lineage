import { describe, expect, it } from "vitest";
import { normalizeSrc, isSlug } from "@/lib/src";
import { makeSessionToken, readSessionToken } from "@/lib/session";
import { createMagicLink, consumeMagicLink, safeRedirect, MAGIC_TTL_MS } from "@/lib/magic";
import { normalizeEmail } from "@/lib/crypto";
import { parseEnv } from "@/env";
import { appendRow } from "../../scripts/append-kpi";
import { ctx } from "./setup";

describe("attribution (src)", () => {
  it("keeps valid slugs and maps missing/invalid ones to 'direct'", () => {
    expect(normalizeSrc("scchgs-writing-2026-10-20")).toBe("scchgs-writing-2026-10-20");
    expect(normalizeSrc("SMCGS-2026-10-17")).toBe("smcgs-2026-10-17");
    expect(normalizeSrc(undefined)).toBe("direct");
    expect(normalizeSrc("")).toBe("direct");
    expect(normalizeSrc("bad slug")).toBe("direct");
    expect(normalizeSrc("x".repeat(65))).toBe("direct");
    expect(normalizeSrc("<script>")).toBe("direct");
    expect(isSlug("a")).toBe(true);
  });
});

describe("sessions", () => {
  it("verifies, rejects tampering and expiry", () => {
    const t = makeSessionToken("11111111-1111-1111-1111-111111111111", 0);
    expect(readSessionToken(t, 1000)).toBe("11111111-1111-1111-1111-111111111111");
    expect(readSessionToken(t.slice(0, -2) + "xx", 1000)).toBeNull();
    const [body, sig] = t.split(".");
    const forged = Buffer.from(JSON.stringify({ uid: "someone-else", exp: 9e15 })).toString("base64url");
    expect(readSessionToken(`${forged}.${sig}`, 1000)).toBeNull();
    expect(readSessionToken(`${body}.${sig}`, 31 * 86400_000)).toBeNull();
  });
});

describe("magic links", () => {
  it("work once and expire after 15 minutes", async () => {
    const t0 = Date.now();
    const tok = await createMagicLink(ctx.db, "a@example.org", "/family/new", t0);
    expect(await consumeMagicLink(ctx.db, tok, t0 + 1000)).toEqual({ email: "a@example.org", redirectTo: "/family/new" });
    expect(await consumeMagicLink(ctx.db, tok, t0 + 2000)).toBeNull(); // second use rejected
    const late = await createMagicLink(ctx.db, "a@example.org", null, t0);
    expect(await consumeMagicLink(ctx.db, late, t0 + MAGIC_TTL_MS + 1)).toBeNull(); // expired
    expect(await consumeMagicLink(ctx.db, "not-a-token", t0)).toBeNull();
  });
  it("never redirects off-site", () => {
    expect(safeRedirect("/invite/abc")).toBe("/invite/abc");
    expect(safeRedirect("//evil.example")).toBeNull();
    expect(safeRedirect("https://evil.example")).toBeNull();
  });
});

describe("email normalisation", () => {
  it("lower-cases and validates", () => {
    expect(normalizeEmail("  Pat@Example.ORG ")).toBe("pat@example.org");
    expect(normalizeEmail("nope")).toBeNull();
  });
});

describe("environment", () => {
  it("defaults to no price and fake payments", () => {
    const e = parseEnv({});
    expect(e.PRICE_TBD).toBe(true);
    expect(e.PAYMENTS_DRIVER).toBe("fake");
  });
  it("refuses live Stripe keys unless explicitly allowed", () => {
    const base = { PAYMENTS_DRIVER: "stripe", STRIPE_WEBHOOK_SECRET: "whsec_x", STRIPE_PRICE_ID_FOUNDING: "price_x" };
    expect(() => parseEnv({ ...base, STRIPE_SECRET_KEY: "sk_live_abc" })).toThrow(/live Stripe key refused/);
    expect(() => parseEnv({ ...base, STRIPE_SECRET_KEY: "sk_test_abc" })).not.toThrow();
  });
  it("requires a price text before showing one, and a session secret in production", () => {
    expect(() => parseEnv({ PRICE_TBD: "false" })).toThrow(/PRICE_DISPLAY/);
    expect(() => parseEnv({ NODE_ENV: "production" })).toThrow(/SESSION_SECRET/);
  });
});

describe("append-kpi", () => {
  it("appends today's row once, never a duplicate date", () => {
    const fetched = "date,families,archivists\n2026-10-20,3,4\n";
    const one = appendRow("date,families,archivists\n2026-10-16,0,0\n", fetched);
    expect(one.added).toBe(true);
    expect(one.text).toBe("date,families,archivists\n2026-10-16,0,0\n2026-10-20,3,4\n");
    expect(appendRow(one.text, fetched).added).toBe(false);
    expect(appendRow("", "garbage").added).toBe(false);
  });
});
