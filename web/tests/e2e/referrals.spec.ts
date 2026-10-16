import { test, expect } from "@playwright/test";
import { checkSeniorFriendly, PDF, photoBuffer, signInByEmail } from "./helpers";

// Archivist shares their link → a relative subscribes (fake Stripe) → the archivist's dashboard shows the earning →
// the archivist sets up payouts (fake Connect) → the admin approves the payout → it shows as paid.
test("referral: share link → relative subscribes → earning → payout", async ({ browser }, info) => {
  const tag = info.project.name;
  const use = { ...info.project.use };

  // the archivist, with a family, one shared photo and one private document
  const arch = await signInByEmail(browser, `ref-arch-${tag}@example.org`, use);
  await arch.page.goto("/family/new");
  await arch.page.getByLabel("Family name").fill(`The Ref ${tag} Family`);
  await arch.page.getByLabel(/Your name/).fill("Pat Keeper");
  await arch.page.getByRole("button", { name: "Create my family page" }).click();
  await arch.page.getByTestId("library-input").setInputFiles({ name: "photo.jpg", mimeType: "image/jpeg", buffer: await photoBuffer(arch.page) });
  await arch.page.getByLabel(/Caption/).fill("Shared photo");
  await arch.page.getByRole("button", { name: "Add to my family page" }).click();
  await expect(arch.page.getByText("Shared photo")).toBeVisible();
  await arch.page.getByRole("link", { name: "Add another" }).click();
  await arch.page.getByTestId("library-input").setInputFiles({ name: "will.pdf", mimeType: "application/pdf", buffer: PDF });
  await arch.page.getByLabel(/Caption/).fill("Private will");
  await arch.page.getByLabel(/Only for family members/).check();
  await arch.page.getByRole("button", { name: "Add to my family page" }).click();
  await expect(arch.page.getByText("Private will")).toBeVisible();

  // their referral link and QR
  await arch.page.getByRole("link", { name: /Your link, QR code and earnings/ }).click();
  await expect(arch.page.getByRole("heading", { name: "Your link and earnings" })).toBeVisible();
  await expect(arch.page.getByRole("img", { name: /QR code for your/ })).toBeVisible();
  const link = await arch.page.getByLabel("Your link for this family").inputValue();
  expect(link).toMatch(/\/f\/[0-9a-f-]{36}\?ref=[a-z2-9]{8}$/);
  await checkSeniorFriendly(arch.page);

  // a relative opens the link on their own phone and subscribes
  const relCtx = await browser.newContext(use);
  const rel = await relCtx.newPage();
  await rel.goto(link);
  expect((await relCtx.cookies()).find(c => c.name === "lineage_ref")?.value).toBe(link.split("ref=")[1]);
  await expect(rel.getByText(/Pat keeps the family's photos/)).toBeVisible();
  await expect(rel.getByRole("heading", { name: "Subscribe — TEST-SUB-PRICE" })).toBeVisible();
  await checkSeniorFriendly(rel);
  await rel.getByLabel("Your email").fill(`ref-rel-${tag}@example.org`);
  await rel.getByRole("button", { name: "Subscribe" }).click();
  await expect(rel.getByRole("heading", { name: "Test checkout" })).toBeVisible();
  await rel.getByRole("button", { name: "Pay (test)" }).click();
  await expect(rel.getByText("Thank you for subscribing.")).toBeVisible();
  // read-only, and the private record is not there
  await expect(rel.getByText("Shared photo")).toBeVisible();
  await expect(rel.getByText("Private will")).toHaveCount(0);
  await expect(rel.getByRole("link", { name: "Add another" })).toHaveCount(0);
  await expect(rel.getByRole("link", { name: "Invite a relative" })).toHaveCount(0);
  // email update preferences
  await rel.getByRole("link", { name: "Email updates" }).click();
  await rel.getByLabel("Once a month").check();
  await rel.getByRole("button", { name: "Save" }).click();
  await expect(rel.getByText("Saved.")).toBeVisible();
  await relCtx.close();

  // the archivist sees the referral and the earning (20% of the fake $10.00 = $2.00; no hold in this test)
  await arch.page.goto("/earnings");
  await expect(arch.page.getByRole("row", { name: /Followed or subscribed\s*1/ })).toBeVisible();
  await expect(arch.page.getByRole("row", { name: /Paying subscribers\s*1/ })).toBeVisible();
  await expect(arch.page.getByRole("row", { name: /USD/ })).toContainText("$2.00");

  // "Get paid": Stripe Connect onboarding (fake)
  await arch.page.getByRole("button", { name: "Get paid" }).click();
  await expect(arch.page.getByRole("heading", { name: "Test payout setup" })).toBeVisible();
  await arch.page.getByRole("button", { name: "Finish setup (test)" }).click();
  await expect(arch.page.getByText("Payouts are set up with Stripe.")).toBeVisible();

  // the admin reviews and approves the payout
  const admin = await signInByEmail(browser, "rex@example.org", use, "/admin/earnings");
  await expect(admin.page.getByRole("heading", { name: "Subscriptions and referrals" })).toBeVisible();
  await expect(admin.page.getByRole("row", { name: /Paid subscribers\s*\d+/ })).toBeVisible();
  await expect(admin.page.getByRole("row", { name: /Monthly recurring revenue/ })).toContainText("$");
  const due = admin.page.getByRole("row", { name: new RegExp(`ref-arch-${tag}@example.org.*\\$2\\.00`) });
  await due.getByRole("button", { name: "Approve payout" }).click();
  await expect(admin.page.getByText("Payout sent.")).toBeVisible();
  const csv = await (await admin.page.request.get("/api/admin/earnings.csv")).text();
  expect(csv.split("\n")[0]).toContain("referrer_email,kind");
  expect(csv).toContain(`ref-arch-${tag}@example.org,share`);
  await admin.ctx.close();

  // paid
  await arch.page.goto("/earnings");
  await expect(arch.page.getByRole("row", { name: /USD/ }).first()).toContainText("$2.00");
  await expect(arch.page.getByRole("cell", { name: "paid" })).toBeVisible();
  await arch.ctx.close();
});

test("referral terms are a DRAFT and show only configured numbers", async ({ page }) => {
  await page.goto("/terms/referrals");
  await expect(page.getByText("DRAFT — pending legal review")).toBeVisible();
  await expect(page.getByText(/earn 20% of each payment/)).toBeVisible(); // from REV_SHARE_PCT in this test run
  await page.goto("/terms/subscribers");
  await expect(page.getByText("DRAFT — pending legal review")).toBeVisible();
});
