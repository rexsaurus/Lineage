import { test, expect } from "@playwright/test";
import { checkSeniorFriendly, lastMail, photoBuffer } from "../e2e/helpers";

test("price not set: reserve free, no price shown, straight to the family page", async ({ page, context }, info) => {
  const email = `reserve-${info.project.name}@example.org`;
  await page.goto("/?src=tbd-test");
  await expect(page.getByRole("heading", { name: /^Founding Archivist$/ })).toBeVisible();
  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(/\$\s?\d/); // no price anywhere
  expect(text).toContain("Price announced soon");
  await checkSeniorFriendly(page);
  await page.getByRole("link", { name: "Reserve my spot" }).click();
  await page.getByLabel("Your email").fill(email);
  await page.getByRole("button", { name: "Reserve my spot" }).click();
  await expect(page.getByText("Step 2 of 4")).toBeVisible(); // signed in on this device, no checkout
  expect((await context.cookies()).find(c => c.name === "lineage_session")).toBeTruthy();
  await lastMail(email, "magic-link"); // a link for next time
  await page.getByLabel("Family name").fill("The Reserved Family");
  await page.getByRole("button", { name: "Create my family page" }).click();
  await page.getByTestId("camera-input").setInputFiles({ name: "photo.jpg", mimeType: "image/jpeg", buffer: await photoBuffer(page) });
  await page.getByRole("button", { name: "Add to my family page" }).click();
  await expect(page.getByRole("heading", { name: "The Reserved Family" })).toBeVisible();
  await expect(page.getByText(/You're family #\d+ in Lineage/)).toBeVisible();
});
