import fs from "node:fs";
import path from "node:path";
import { expect, type Page, type Browser, type BrowserContext } from "@playwright/test";

const OUTBOX = path.join(".data/e2e/outbox");

type Mail = { to: string; subject: string; text: string; kind: string; at: string };

export function outbox(): Mail[] {
  if (!fs.existsSync(OUTBOX)) return [];
  return fs
    .readdirSync(OUTBOX)
    .sort()
    .map(f => JSON.parse(fs.readFileSync(path.join(OUTBOX, f), "utf8")) as Mail);
}

export async function lastMail(to: string, kind: string): Promise<Mail> {
  for (let i = 0; i < 40; i++) {
    const m = outbox().filter(x => x.to === to && x.kind === kind).at(-1);
    if (m) return m;
    await new Promise(r => setTimeout(r, 250));
  }
  throw new Error(`no ${kind} email to ${to}`);
}

export function linkIn(text: string, pathPart: string): string {
  const m = text.match(new RegExp(`https?://\\S*${pathPart.replace(/[/?]/g, c => "\\" + c)}\\S*`));
  if (!m) throw new Error(`no ${pathPart} link in email`);
  return m[0];
}

/** A real, decodable image for upload tests (a screenshot of a page). */
export async function photoBuffer(page: Page): Promise<Buffer> {
  return page.screenshot({ type: "jpeg", quality: 80 });
}

export const PDF = Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n");

/** Sign a fresh context in through the magic-link email. */
export async function signInByEmail(browser: Browser, email: string, use: object, next?: string): Promise<{ ctx: BrowserContext; page: Page }> {
  const ctx = await browser.newContext(use);
  const page = await ctx.newPage();
  await page.goto(`/login${next ? `?next=${encodeURIComponent(next)}` : ""}`);
  await page.getByLabel("Your email").fill(email);
  await page.getByRole("button", { name: /sign-in link|link/i }).click();
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
  const mail = await lastMail(email, "magic-link");
  await page.goto(linkIn(mail.text, "/api/auth/callback"));
  return { ctx, page };
}

/** Spec §11 checks on the current page. */
export async function checkSeniorFriendly(page: Page) {
  const r = await page.evaluate(() => {
    const body = parseFloat(getComputedStyle(document.body).fontSize);
    const small = [...document.querySelectorAll<HTMLElement>("a.btn, button.btn")]
      .filter(b => b.offsetParent !== null)
      .map(b => b.getBoundingClientRect().height)
      .filter(h => h < 48);
    const noHScroll = document.documentElement.scrollWidth <= window.innerWidth + 1;
    const unlabelled = [...document.querySelectorAll<HTMLInputElement>("input:not([type=hidden]):not([hidden])")]
      .filter(i => i.offsetParent !== null && !i.labels?.length && !i.getAttribute("aria-label")).length;
    return { body, small, noHScroll, unlabelled };
  });
  expect(r.body).toBeGreaterThanOrEqual(18);
  expect(r.small, "buttons shorter than 48px").toEqual([]);
  expect(r.noHScroll, "no horizontal scrolling").toBe(true);
  expect(r.unlabelled, "inputs without labels").toBe(0);
}
