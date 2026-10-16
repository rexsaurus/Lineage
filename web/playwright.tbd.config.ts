import { defineConfig, devices } from "@playwright/test";

// The default launch mode (PRICE_TBD=true): no price anywhere, no payment, a free reservation (spec §3.3).
// npx playwright test -c playwright.tbd.config.ts
const PORT = 3101;
export default defineConfig({
  testDir: "tests/e2e-tbd",
  timeout: 60_000,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${PORT}` },
  projects: [
    { name: "iphone-13", use: { ...devices["iPhone 13"] } },
    { name: "pixel-7", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: `rm -rf .data/e2e && next start -p ${PORT}`,
    url: `http://localhost:${PORT}/privacy`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      APP_URL: `http://localhost:${PORT}`,
      SESSION_SECRET: "e2e-only-session-secret-e2e-only-session-secret",
      PGLITE_DIR: ".data/e2e/pglite",
      OUTBOX_DIR: ".data/e2e/outbox",
      LOCAL_BLOB_DIR: ".data/e2e/blobs",
      PAYMENTS_DRIVER: "fake",
      MAIL_DRIVER: "console",
    },
  },
});
