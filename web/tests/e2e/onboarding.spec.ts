import { test, expect } from "@playwright/test";
import { checkSeniorFriendly, lastMail, linkIn, outbox, PDF, photoBuffer, signInByEmail } from "./helpers";

// The main flow (spec §3.1, §14 manual script, automated): scan → pay (test) → name the family → photo → family page,
// then invite a relative who joins and uploads, the follow-up email, privacy, and the admin counts.
test("archivist signs up at an event, uploads, invites; admin sees the counts", async ({ browser, page, context }, info) => {
  const tag = info.project.name;
  const src = `e2e-${tag}`;
  const email = `archivist-${tag}@example.org`;
  const t0 = Date.now();

  // 1. scan the QR
  await page.goto(`/?src=${src}`);
  expect((await context.cookies()).find(c => c.name === "lineage_src")?.value).toBe(src);
  await expect(page.getByRole("heading", { name: /Founding Archivist — TEST-PRICE/ })).toBeVisible();
  await checkSeniorFriendly(page);
  await page.getByRole("link", { name: "Start my family" }).click();

  // 2. email → test checkout → welcome (signed in on this device)
  await expect(page.getByText("Step 1 of 4")).toBeVisible();
  await checkSeniorFriendly(page);
  await page.getByLabel("Your email").fill(email);
  await page.getByRole("button", { name: "Continue to payment" }).click();
  await expect(page.getByRole("heading", { name: "Test checkout" })).toBeVisible();
  await page.getByRole("button", { name: "Pay (test)" }).click();

  // 3. name the family
  await expect(page.getByText("Step 2 of 4")).toBeVisible();
  await checkSeniorFriendly(page);
  await page.getByLabel("Family name").fill(`The ${tag} Family`);
  await page.getByLabel(/Your name/).fill("Pat Archivist");
  await page.getByRole("button", { name: "Create my family page" }).click();

  // 4. first record: a photo from the library (the camera input works the same way)
  await expect(page.getByText("Step 3 of 4")).toBeVisible();
  await checkSeniorFriendly(page);
  const photo = await photoBuffer(page);
  await page.getByTestId("library-input").setInputFiles({ name: "grandma.jpg", mimeType: "image/jpeg", buffer: photo });
  await page.getByLabel(/Caption/).fill("Grandma Rose, 1952");
  await page.getByRole("button", { name: "Add to my family page" }).click();

  // 5. the family page
  await expect(page.getByRole("heading", { name: `The ${tag} Family` })).toBeVisible();
  await expect(page.getByText(/You're family #\d+ in Lineage/)).toBeVisible();
  await expect(page.getByText("Grandma Rose, 1952")).toBeVisible();
  const img = page.getByRole("img", { name: "Grandma Rose, 1952" });
  await expect.poll(() => img.evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0)).toBe(true);
  const recordSrc = await img.getAttribute("src");
  const elapsed = (Date.now() - t0) / 1000;
  console.log(`[${tag}] scan → family page with 1 record: ${elapsed.toFixed(1)}s (automated; the ≤2:00 target is for a person)`);
  expect(elapsed).toBeLessThan(120);
  await checkSeniorFriendly(page);
  const familyUrl = page.url();
  const familyPath = new URL(familyUrl).pathname;

  // follow-up email after the first record (spec §7)
  const follow = await lastMail(email, "followup");
  expect(follow.subject).toBe(`Your The ${tag} Family page is live`);
  expect(follow.text).toContain(familyPath);
  // and the magic link for next time
  await lastMail(email, "magic-link");

  // 6. invite a relative by email
  await page.getByRole("link", { name: "Invite a relative" }).click();
  await expect(page.getByText("Step 4 of 4")).toBeVisible();
  const cousin = `cousin-${tag}@example.org`;
  await page.getByLabel("Their name").fill("Sam Cousin");
  await page.getByLabel("Their email").fill(cousin);
  await page.getByRole("button", { name: "Send the invitation" }).click();
  await expect(page.getByText("Invitation sent.")).toBeVisible();
  const invite = await lastMail(cousin, "invite");
  const inviteLink = linkIn(invite.text, "/invite/");

  // the cousin, on another phone: open → email → magic link → join → upload a PDF
  const c = await browser.newContext({ ...info.project.use });
  const cp = await c.newPage();
  await cp.goto(inviteLink);
  await expect(cp.getByRole("heading", { name: `Join the The ${tag} Family page` })).toBeVisible();
  await cp.getByRole("button", { name: "Email me a link to join" }).click();
  await expect(cp.getByRole("heading", { name: "Check your email" })).toBeVisible();
  await cp.goto(linkIn((await lastMail(cousin, "magic-link")).text, "/api/auth/callback"));
  await cp.getByRole("button", { name: /Join/ }).click();
  await expect(cp.getByRole("heading", { name: `The ${tag} Family` })).toBeVisible();
  await cp.getByRole("link", { name: "Add another" }).click();
  await cp.getByTestId("library-input").setInputFiles({ name: "letter.pdf", mimeType: "application/pdf", buffer: PDF });
  await cp.getByRole("button", { name: "Add to my family page" }).click();
  await expect(cp.getByRole("link", { name: "PDF" })).toBeVisible();
  // the same invite link can't be used by anyone else
  const used = await browser.newContext({ ...info.project.use });
  const up = await used.newPage();
  await up.goto(inviteLink);
  await expect(up.getByRole("heading", { name: "This invitation has been used" })).toBeVisible();
  await used.close();
  await c.close();

  // 7. privacy: a signed-out visitor is sent to sign in; a signed-in stranger gets 404, for the page and the file
  const anon = await browser.newContext({ ...info.project.use });
  const ap = await anon.newPage();
  await ap.goto(familyPath);
  await expect(ap).toHaveURL(/\/login\?next=/);
  expect((await ap.request.get(recordSrc!, { maxRedirects: 0 })).status()).toBe(404);
  await anon.close();
  const stranger = await signInByEmail(browser, `stranger-${tag}@example.org`, { ...info.project.use });
  const sres = await stranger.page.goto(familyPath);
  expect(sres?.status()).toBe(404);
  expect((await stranger.page.request.get(recordSrc!, { maxRedirects: 0 })).status()).toBe(404);
  await stranger.ctx.close();

  // 8. admin: counts by event, CSV
  const admin = await signInByEmail(browser, "rex@example.org", { ...info.project.use }, "/admin");
  await expect(admin.page.getByRole("heading", { name: "Admin" })).toBeVisible();
  const row = admin.page.getByRole("row", { name: new RegExp(`^${src}\\b`) });
  // event, families 1, archivists 1, records 2, invites 1, accepted 1, paid 1
  await expect(row).toHaveText(new RegExp(`${src}\\s*1\\s*1\\s*2\\s*1\\s*1\\s*1`));
  const csv = await (await admin.page.request.get("/api/admin/kpi.csv")).text();
  expect(csv.split("\n")[0]).toBe("date,families,archivists");
  expect(csv.split("\n")[1]).toMatch(/^\d{4}-\d{2}-\d{2},\d+,\d+$/);
  const byEvent = await (await admin.page.request.get("/api/admin/kpi-by-event.csv")).text();
  expect(byEvent).toContain(`,${src},1,1,2,1`);
  // the export token works for scripts; nothing works without auth
  const tok = await admin.page.request.get("/api/admin/kpi.csv", { headers: { Authorization: "Bearer e2e-kpi-token-e2e-kpi-token-123" } });
  expect(tok.status()).toBe(200);
  await admin.ctx.close();
  const anon2 = await browser.newContext();
  expect((await (await anon2.newPage()).request.get("/api/admin/kpi.csv")).status()).toBe(404);
  await anon2.close();

  expect(outbox().length).toBeGreaterThan(0);
});

test("landing and demo pages; noindex everywhere but /", async ({ page, request }) => {
  const landing = await request.get("/");
  expect(landing.headers()["x-robots-tag"]).toBeUndefined();
  const start = await request.get("/start");
  expect(start.headers()["x-robots-tag"]).toContain("noindex");
  await page.goto("/demo");
  await expect(page.getByText("Demo content").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Start your own" })).toBeVisible();
  await checkSeniorFriendly(page);
  await page.goto("/privacy");
  await expect(page.getByText("DRAFT — pending legal review")).toBeVisible();
  await checkSeniorFriendly(page);
});

test("upload limits: oversized and unsupported files get a plain-English message", async ({ browser }, info) => {
  const { ctx, page } = await signInByEmail(browser, `limits-${info.project.name}@example.org`, { ...info.project.use });
  await page.goto("/family/new");
  await page.getByLabel("Family name").fill("Limits");
  await page.getByRole("button", { name: "Create my family page" }).click();
  await page.getByTestId("library-input").setInputFiles({ name: "huge.pdf", mimeType: "application/pdf", buffer: Buffer.concat([Buffer.from("%PDF-"), Buffer.alloc(25 * 1024 * 1024)]) });
  await expect(page.locator("p.error[role=alert]")).toHaveText(/over 25 MB/);
  await page.getByTestId("library-input").setInputFiles({ name: "notes.pdf", mimeType: "application/pdf", buffer: Buffer.from("not really a pdf") });
  await page.getByRole("button", { name: "Add to my family page" }).click();
  await expect(page.locator("p.error[role=alert]")).toHaveText(/photo \(JPEG, PNG or HEIC\) or a PDF/);
  await ctx.close();
});
