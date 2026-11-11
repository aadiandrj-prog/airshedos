import { defineConfig, devices } from "@playwright/test";
export default defineConfig({ testDir: "./tests/resident", testMatch: "*.spec.ts", workers: 1,
  timeout: 60000, expect: { timeout: 15000 }, fullyParallel: false,
  use: { ...devices["Desktop Chrome"], baseURL: process.env.RESIDENT_TEST_WEB_URL,
    launchOptions: { args: ["--no-proxy-server", `--host-resolver-rules=MAP resident-fixture.invalid:443 127.0.0.1:${new URL(process.env.TEST_OIDC_TRANSPORT!).port}`] },
    viewport: { width: 390, height: 844 }, timezoneId: "Asia/Kolkata", ignoreHTTPSErrors: true,
    trace: "retain-on-failure" } });
