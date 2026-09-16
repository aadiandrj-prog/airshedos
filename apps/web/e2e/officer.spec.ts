import { test, expect, type Page } from "./test";
import citizen from "./fixtures/citizen.test.json";
import assessment from "./fixtures/corroboration.test.json";
import environment from "./fixtures/environment.test.json";
import satellite from "./fixtures/satellite.test.json";
import forecast from "./fixtures/forecast.test.json";

const transitions: Record<string, string[]> = { NEW: ["UNDER_REVIEW"], UNDER_REVIEW: ["ACKNOWLEDGED", "MONITORING", "CLOSED_NO_ACTION"], ACKNOWLEDGED: ["MONITORING", "CLOSED_NO_ACTION"], MONITORING: ["UNDER_REVIEW", "ACKNOWLEDGED", "CLOSED_NO_ACTION"], CLOSED_NO_ACTION: [] };
function sample(id = "CA-officer", fires = true) {
  const context = structuredClone(assessment.environmental_context);
  if (!fires) context.fires = [];
  return {
    id, created_at: citizen.report.created_at, expires_at: "2099-09-17T00:00:00Z", storage: "ephemeral_process_local",
    snapshot: { record: { report: { ...citizen.report, is_synthetic: true }, analysis: citizen.analysis, evidence: citizen.evidence },
      assessment: { ...assessment, id, environmental_context: context, forecast_outlook: forecast },
      jurisdiction: { state: "Haryana", method: "prototype_lookup_area_v1", authoritative: false, note: "Prototype area, not an official boundary. No authority routing." }, evidence_sha256: "fixture-only" },
    review: { state: "NEW", revision: 0, action_at: null as string | null, allowed_transitions: transitions.NEW },
  };
}
async function setup(page: Page, fires = true, initiallyQueued = true) {
  let current = sample("CA-officer", fires);
  let queued = initiallyQueued;
  const calls = { environment: 0, analysis: 0, corroboration: 0 };
  await page.route("**/environment/context?**", r => { calls.environment++; return r.fulfill({ json: environment }); });
  await page.route("**/environment/satellite?**", r => r.fulfill({ json: satellite }));
  await page.route("**/api/v1/review/cases", r => r.fulfill({ json: queued ? [{ id: current.id, event_type: "open_burning", is_synthetic: true, jurisdiction: current.snapshot.jurisdiction, support_level: assessment.support_level, review: current.review, submitted_at: citizen.report.created_at }] : [] }));
  await page.route("**/api/v1/review/cases/CA-officer", r => r.fulfill({ json: current }));
  await page.route("**/api/v1/review/cases/CA-officer/review", r => {
    const data = r.request().postDataJSON();
    expect(data.expected_revision).toBe(current.review.revision);
    const before = JSON.stringify(current.snapshot);
    current = { ...current, review: { state: data.state, revision: current.review.revision + 1, action_at: "2026-09-17T12:00:00Z", allowed_transitions: transitions[data.state] } };
    expect(JSON.stringify(current.snapshot)).toBe(before);
    return r.fulfill({ json: current });
  });
  await page.route("**/citizen-reports/analyze", r => { calls.analysis++; expect(r.request().postDataBuffer()?.toString()).toContain('name="is_synthetic"'); return r.fulfill({ json: { ...citizen, report: { ...citizen.report, is_synthetic: true } } }); });
  await page.route("**/citizen-reports/*/corroborate", r => { calls.corroboration++; queued = true; return r.fulfill({ json: current.snapshot.assessment }); });
  await page.goto("/");
  return calls;
}
async function choose(page: Page) {
  await page.getByRole("complementary", { name: "Case queue" }).getByRole("button").filter({ hasText: "SYNTHETIC INPUT" }).click();
  await expect(page.getByRole("region", { name: "Selected case details" })).toContainText("Haryana · prototype");
}
const review = (page: Page) => page.getByRole("region", { name: "Officer review controls" });

test("mocked map, fictional demo selection and coordinate probe", async ({ page }) => {
  await setup(page);
  await expect(page.getByText("Google map loaded.", { exact: false })).toBeVisible();
  await expect(page.locator('[data-mock-marker]')).toHaveAttribute("aria-label", /DEMO INCIDENT/);
  await page.getByRole("button", { name: /Gurugram coordinate probe/ }).click();
  await expect(page.getByRole("region", { name: "Selected case details" })).toContainText("No incident is inferred");
  await expect(page.locator('[data-mock-marker]')).toHaveAttribute("aria-label", /PROBE/);
});

test("select case, report marker and fire panel; no provider refetch on marker click", async ({ page }) => {
  const calls = await setup(page);
  await choose(page);
  const marker = page.locator('[data-mock-marker]').filter({ hasText: "R" });
  await expect(marker).toHaveAttribute("aria-pressed", "true");
  const before = calls.environment;
  await page.locator('[data-mock-marker]').filter({ hasText: "F" }).first().click();
  await expect(page.getByRole("region", { name: "Selected active fire detection" })).toContainText("does not establish pollution causality");
  expect(calls.environment).toBe(before);
  await expect(page.locator('[data-mock-map]')).toHaveAttribute("data-bounds-count", "2");
});

test("no FIRMS centers on report and preserves forecast", async ({ page }) => {
  await setup(page, false); await choose(page);
  await expect(page.locator('[data-mock-marker]')).toHaveCount(1);
  await expect(page.locator('[data-mock-map]')).toHaveAttribute("data-center", '{"lat":28.4595,"lng":77.0266}');
  await expect(page.getByRole("region", { name: "Selected case details" })).toContainText("No nearby active-fire detections returned");
  await expect(page.getByRole("region", { name: "Selected case details" })).toContainText("Google Air Quality");
});

test("NEW → UNDER_REVIEW → ACKNOWLEDGED; evidence and forecast unchanged", async ({ page }) => {
  const calls = await setup(page); await choose(page);
  await page.locator(".officer-detail summary").filter({ hasText: "Corroboration ·" }).click();
  const card = page.locator(".officer-detail .fusion-card");
  const before = await card.innerText();
  await review(page).getByRole("button", { name: "Begin review" }).click();
  await expect(review(page)).toContainText("UNDER REVIEW");
  await review(page).getByRole("button", { name: "Acknowledge case" }).click();
  await expect(review(page)).toContainText("ACKNOWLEDGED");
  expect(await card.innerText()).toBe(before);
  expect(calls.analysis).toBe(0); expect(calls.corroboration).toBe(0);
});

test("monitoring and close with no action", async ({ page }) => {
  await setup(page); await choose(page);
  await review(page).getByRole("button", { name: "Begin review" }).click();
  await review(page).getByRole("button", { name: "Mark for monitoring" }).click();
  await expect(review(page)).toContainText("MONITORING");
  await review(page).getByRole("button", { name: "Close with no action" }).click();
  await expect(review(page)).toContainText("CLOSED NO ACTION");
  await expect(review(page).getByRole("button", { name: "Begin review" })).toHaveCount(0);
});

test("map authentication failure leaves review usable and does not reveal credentials", async ({ page }) => {
  await setup(page); await choose(page);
  await page.evaluate(() => window.dispatchEvent(new Event("airshedos-map-failure")));
  await expect(page.getByText("Map unavailable.", { exact: false })).toBeVisible();
  await review(page).getByRole("button", { name: "Begin review" }).click();
  await expect(review(page)).toContainText("UNDER REVIEW");
  expect(await page.locator("body").innerText()).not.toMatch(/AIza[\w-]{35}/);
});

test("mobile stacks queue, map and case details without overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page); await choose(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const boxes = await Promise.all([".case-queue", ".spatial-map", ".officer-detail"].map(s => page.locator(s).boundingBox()));
  expect(boxes[0]!.y).toBeLessThan(boxes[1]!.y); expect(boxes[1]!.y).toBeLessThan(boxes[2]!.y);
  await page.locator(".officer-workspace").screenshot({ path: "test-results/phase3a-mobile.png" });
});

test("synthetic citizen → interpretation → corroboration → queue → map → forecast → monitoring", async ({ page }) => {
  const calls = await setup(page, true, false);
  await page.getByRole("button", { name: "Use synthetic sample image" }).click();
  await expect(page.locator(".citizen-panel")).toContainText("SYNTHETIC IMAGE");
  await page.getByRole("button", { name: "Interpret image", exact: true }).click();
  await page.getByRole("button", { name: "Corroborate with environmental data" }).click();
  await expect(page.locator(".officer-detail")).toContainText("SYNTHETIC INPUT");
  await expect(page.locator(".officer-detail")).toContainText("Google Air Quality");
  await expect(page.locator('[data-mock-marker]').filter({ hasText: "R" })).toHaveAttribute("aria-pressed", "true");
  await review(page).getByRole("button", { name: "Begin review" }).click();
  await review(page).getByRole("button", { name: "Mark for monitoring" }).click();
  await expect(review(page)).toContainText("MONITORING");
  expect(calls.analysis).toBe(1); expect(calls.corroboration).toBe(1);
});

test("keyboard queue selection and text marker alternative", async ({ page }) => {
  await setup(page);
  const item = page.locator('.case-queue .case-choice').filter({ hasText: "SYNTHETIC INPUT" });
  await item.focus(); await page.keyboard.press("Enter");
  await expect(item).toHaveAttribute("aria-pressed", "true");
  const fire = page.locator('.map-text-points button').filter({ hasText: "ACTIVE FIRE DETECTION" });
  await fire.focus(); await page.keyboard.press("Enter");
  await expect(page.getByRole("region", { name: "Selected active fire detection" })).toBeVisible();
});

test("expired case action reports failure without replacing evidence", async ({ page }) => {
  await setup(page); await choose(page);
  await page.route("**/api/v1/review/cases/CA-officer/review", r => r.fulfill({ status: 404, json: { detail: "Case expired" } }));
  await review(page).getByRole("button", { name: "Begin review" }).click();
  await expect(page.locator('.officer-detail [role=alert]')).toContainText(/expired/i);
  await expect(review(page)).toContainText("NEW");
  await expect(page.locator('.officer-detail')).toContainText("Google Air Quality");
});

test("SDK import failure produces bounded map-unavailable state", async ({ page }) => {
  await page.addInitScript(() => { Object.assign(window, { mockMapsFailure: true }); });
  await setup(page); await choose(page);
  await expect(page.getByText("Map unavailable.", { exact: false })).toBeVisible();
  await review(page).getByRole("button", { name: "Begin review" }).click();
  await expect(review(page)).toContainText("UNDER REVIEW");
});
