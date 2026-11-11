import { capture } from "./capture";
import { localNetwork } from "../resident/local-network";
import { test, expect, type Page } from "@playwright/test";
import { Pool } from "pg";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

const database = process.env.TEST_DATABASE_URL!.replace("postgresql+psycopg:", "postgresql:");
const parsed = new URL(database);
if (parsed.hostname !== "127.0.0.1" || parsed.username !== "seva_test" || parsed.pathname !== "/seva_phase1_test") throw new Error("Local synthetic database required");
const pool = new Pool({ connectionString: database, max: 2 });
test.beforeEach(async ({context}) => localNetwork(context));
test.afterAll(async () => pool.end());

async function login(page: Page, resident = "resident-a") {
  await page.goto("/sign-in?returnTo=%2Fresident%2Freports%2Fnew");
  await page.getByRole("link", { name: "Continue to secure sign-in" }).click();
  await expect(page.getByRole("heading", { name: "Local synthetic sign-in" })).toBeVisible();
  await page.getByLabel("Synthetic resident").selectOption(resident);
  await page.getByRole("button", { name: "Continue synthetic sign-in" }).click();
  await expect(page.getByRole("heading", { name: "Report a concern", exact: true })).toBeVisible();
  if (process.env.SEVA_TEST_RELEASE === "1") {
    const cookie=(await page.context().cookies()).find((entry) => entry.name === "__Host-airshedos");
    expect(cookie?.secure).toBe(true); expect(cookie?.httpOnly).toBe(true); expect(cookie?.path).toBe("/");
    expect(await page.evaluate(() => document.cookie.includes("__Host-airshedos"))).toBe(false);
  }
}
async function fill(page: Page, description: string) {
  await page.getByLabel("Description", { exact: true }).fill(description);
  await page.getByLabel("Reported place", { exact: true }).fill("Synthetic landmark near the north entrance");
  await page.getByLabel("Latitude", { exact: true }).fill("28.5");
  await page.getByLabel("Longitude", { exact: true }).fill("77.1");
}
async function receipt(page: Page) {
  await expect(page.getByRole("heading", { name: "Report received", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Analysis pending", exact: true })).toBeVisible();
  await expect(page.getByText("Unknown (not supplied)", { exact: true })).toBeVisible();
  return page.url().split("/").pop()!;
}
async function count(description: string) {
  return Number((await pool.query("SELECT count(*) FROM reports WHERE description=$1", [description])).rows[0].count);
}

test("mobile login, lost receipt, safe retry, reload and own list persist without AI", async ({ page }) => {
  await page.goto("/"); await capture(page,"landing");
  await page.goto("/sign-in"); await capture(page,"sign-in");
  await login(page); await capture(page,"resident-form");
  const text = "SYNTHETIC RESIDENT REPORT — lost receipt and safe retry " + Date.now();
  await fill(page, text);
  await page.route("**/api/app/v2/resident/reports", async (route) => {
    if (route.request().method() === "POST") { await route.fetch(); await route.abort("failed"); }
    else await route.continue();
  });
  await page.getByRole("button", { name: "Submit report", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "could not confirm" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Report received", exact: true })).toHaveCount(0);
  expect(await count(text)).toBe(1);
  await page.unroute("**/api/app/v2/resident/reports");
  await page.getByRole("button", { name: "Retry same report", exact: true }).click();
  const id = await receipt(page);
  expect(await count(text)).toBe(1);
  await expect(page.getByText("Original visual analysis: not applicable (no photo).", { exact: true })).toBeVisible();
  await capture(page,"resident-receipt");
  await page.route(`**/api/app/v2/resident/reports/${id}`,async (route) => {
    const response=await route.fetch(); const data=await response.json(); data.processing.state="PARTIAL";
    await route.fulfill({response,json:data});
  });
  await page.reload(); await expect(page.getByRole("heading",{name:"Analysis incomplete",exact:true})).toBeVisible();
  await capture(page,"resident-partial-synthetic-state");
  await page.unroute(`**/api/app/v2/resident/reports/${id}`);
  await page.reload(); await receipt(page);
  await page.getByText("Optional local AQ and weather context", {exact:true}).click();
  await page.getByRole("button",{name:"Load optional context",exact:true}).click();
  await expect(page.getByText("No local context is available. Your saved report remains available.")).toBeVisible();
  await page.getByRole("link", { name: "Back to my reports", exact: true }).click();
  await expect(page.locator(`a[href="/resident/reports/${id}"]`)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const records = (await pool.query("SELECT declared_capture_at FROM reports WHERE id=$1", [id])).rows;
  expect(records[0].declared_capture_at).toBeNull();
});

test("failed save shows no receipt, and absent photo, denied GPS/map/context leave reporting usable", async ({ page }) => {
  await login(page);
  await page.addInitScript(() => Object.defineProperty(navigator, "geolocation", { value: {
    getCurrentPosition: (_success: unknown, error: (value: unknown) => void) => error({ code: 1 }) } }));
  await page.reload();
  await page.getByRole("button", { name: "Use my device location (optional)", exact: true }).click();
  await expect(page.getByText("Location access unavailable. Enter coordinates manually; reporting still works.")).toBeVisible();
  await page.route("**/maps.googleapis.com/**", (route) => route.abort());
  await page.route("**/maps.gstatic.com/**", (route) => route.abort());
  await page.getByRole("button", { name: "Choose on an optional map", exact: true }).click();
  await expect(page.getByText("Map unavailable. Enter coordinates manually; reporting still works.")).toBeVisible();
  const text = "SYNTHETIC RESIDENT REPORT — failure before save " + Date.now();
  await fill(page, text);
  let sourceRequests=0;
  page.on("request",(request) => { if (request.url().includes("/resident/context")) sourceRequests++; });
  await page.getByText("Optional local AQ and weather context", { exact: true }).click();
  await page.getByRole("button", { name: "Load optional context", exact: true }).click();
  expect(sourceRequests).toBe(0);
  await expect(page.getByText("No local context is available. You can still submit your report.")).toBeVisible();
  await expect(page.getByLabel("Photo (optional)", { exact: true })).toBeDisabled();
  await page.route("**/api/app/v2/resident/reports", (route) => route.request().method() === "POST"
    ? route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"Synthetic unavailable save"}' }) : route.continue());
  await page.getByRole("button", { name: "Submit report", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "could not be confirmed" })).toBeVisible();
  expect(await count(text)).toBe(0);
  await capture(page,"resident-failure");
  await expect(page.getByRole("heading", { name: "Report received", exact: true })).toHaveCount(0);
  await page.unroute("**/api/app/v2/resident/reports");
  await page.getByRole("button", { name: "Retry same report", exact: true }).focus();
  await page.keyboard.press("Enter"); await receipt(page);
  expect(await count(text)).toBe(1);
});

test("private consented derivative and append-only reply remain owned and hide internal notes", async ({ page, browser }) => {
  await login(page);
  const text = "SYNTHETIC RESIDENT REPORT — private image and reply " + Date.now();
  await fill(page, text);
  await page.getByLabel("I agree to private retention of a cleaned photo for report review.").check();
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAFElEQVR4nGNsaGhgwAaYsIoOWgkAMBcBkGHHl6YAAAAASUVORK5CYII=", "base64");
  await page.getByLabel("Photo (optional)", { exact: true }).setInputFiles({ name: "synthetic-private.png", mimeType: "image/png", buffer: png });
  await page.getByRole("button", { name: "Submit report", exact: true }).click();
  const id = await receipt(page);
  await expect(page.getByRole("img", { name: "Private photo attached to your report" })).toBeVisible();
  execFileSync(process.env.SEVA_TEST_PYTHON!, ["tests/resident_fixture.py", "request-information", "--report-id", id], {
    cwd: resolve(process.cwd(), "../api"), env: { ...process.env }, stdio: "ignore" });
  await page.reload();
  await expect(page.getByRole("heading", { name: "More information requested", exact: true })).toBeVisible();
  await expect(page.getByText("INTERNAL FIXTURE NOTE - DO NOT SHOW", { exact: true })).toHaveCount(0);
  await page.getByLabel("Additional information", { exact: true }).fill("SYNTHETIC REPLY — the activity has stopped.");
  await page.getByRole("button", { name: "Send reply", exact: true }).click();
  await expect(page.getByRole("heading", { name: "More information requested", exact: true })).toHaveCount(0);
  await expect(page.getByText("SYNTHETIC REPLY — the activity has stopped.", { exact: true })).toBeVisible();
  await page.reload(); await receipt(page);
  await expect(page.getByText(text, { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "More information requested", exact: true })).toHaveCount(0);
  const media = (await pool.query("SELECT id FROM media WHERE report_id=$1", [id])).rows[0].id;
  const otherContext = await browser.newContext({ baseURL: process.env.RESIDENT_TEST_WEB_URL,
    ignoreHTTPSErrors: true, viewport: { width: 390, height: 844 } });
  await localNetwork(otherContext);
  const other = await otherContext.newPage(); await login(other, "resident-b");
  await other.goto(`/resident/reports/${id}`);
  await expect(other.getByRole("alert").filter({ hasText: "outside your account" })).toBeVisible();
  expect((await other.request.get(`/api/app/v2/resident/media/${media}`)).status()).toBe(404);
  await other.goto("/resident/reports"); await expect(other.getByText(text, { exact: true })).toHaveCount(0);
  await otherContext.close();
  expect(await count(text)).toBe(1);
});

test("an unavailable optional image upload permits a text-only retry", async ({ page }) => {
  await login(page);
  const text = "SYNTHETIC RESIDENT REPORT — optional photo unavailable " + Date.now();
  await fill(page, text);
  await page.getByLabel("I agree to private retention of a cleaned photo for report review.").check();
  await page.getByLabel("Photo (optional)", { exact: true }).setInputFiles({ name: "unavailable.jpg", mimeType: "image/jpeg", buffer: Buffer.from("synthetic") });
  await page.route("**/api/app/v2/resident/media", (route) => route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"Synthetic private storage outage"}' }));
  await page.getByRole("button", { name: "Submit report", exact: true }).click();
  await expect(page.getByRole("button", { name: "Send without photo", exact: true })).toBeVisible();
  expect(await count(text)).toBe(0);
  await page.getByRole("button", { name: "Send without photo", exact: true }).click();
  await receipt(page); expect(await count(text)).toBe(1);
});


test("retention expiry removes an already displayed private report",async ({page}) => {
  await login(page);
  const description="SYNTHETIC EXPIRING RESIDENT REPORT "+Date.now();
  await fill(page,description);
  await page.getByRole("button",{name:"Submit report",exact:true}).click();
  const reportId=await receipt(page);
  await pool.query("UPDATE reports SET content_expires_at=now()+interval '3 seconds' WHERE id=$1",[reportId]);
  await page.reload();
  await expect(page.getByText(description,{exact:true})).toBeVisible();
  await expect(page.getByRole("alert").filter({hasText:"retention period ended"})).toBeVisible();
  await expect(page.getByText(description,{exact:true})).toHaveCount(0);
  expect((await page.request.get(`/api/app/v2/resident/reports/${reportId}`)).status()).toBe(404);
});
