import { defineConfig, devices } from "@playwright/test";

// End-to-end on phone viewports (spec §14) against a production build, fully offline: fake payments, email written
// to .data/e2e/outbox, files in .data/e2e/blobs, a fresh PGlite database each run. Build first: npm run build.
const PORT = 3100;
export const E2E_DIR = ".data/e2e";

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 90_000,
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure" },
  projects: [
    { name: "iphone-13", use: { ...devices["iPhone 13"] } },
    { name: "pixel-7", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: `rm -rf ${E2E_DIR} && next start -p ${PORT}`,
    url: `http://localhost:${PORT}/privacy`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      APP_URL: `http://localhost:${PORT}`,
      SESSION_SECRET: "e2e-only-session-secret-e2e-only-session-secret",
      PGLITE_DIR: `${E2E_DIR}/pglite`,
      OUTBOX_DIR: `${E2E_DIR}/outbox`,
      LOCAL_BLOB_DIR: `${E2E_DIR}/blobs`,
      PAYMENTS_DRIVER: "fake",
      PRICE_TBD: "false",
      PRICE_DISPLAY: "TEST-PRICE",
      MAIL_DRIVER: "console",
      STORAGE_DRIVER: "local",
      ADMIN_EMAILS: "rex@example.org",
      KPI_EXPORT_TOKEN: "e2e-kpi-token-e2e-kpi-token-123",
      CRON_SECRET: "e2e-cron-secret-123",
      // family subscriptions and referrals — TEST VALUES ONLY, not decisions: a fake $10 monthly invoice, a 20% share,
      // no hold, so the whole referral → earning → payout path can be exercised in seconds
      SUB_PRICE_TBD: "false",
      SUB_PRICE_DISPLAY: "TEST-SUB-PRICE",
      FAKE_SUB_AMOUNT_CENTS: "1000",
      REV_SHARE_PCT: "20",
      REFUND_HOLD_DAYS: "0",
      CONNECT_DRIVER: "fake",
    },
  },
});
