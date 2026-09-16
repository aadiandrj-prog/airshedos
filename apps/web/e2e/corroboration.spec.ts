import { expect, test, type Page } from "@playwright/test";
import citizen from "./fixtures/citizen.test.json";
import fixture from "./fixtures/corroboration.test.json";
import environment from "./fixtures/environment.test.json";
import satellite from "./fixtures/satellite.test.json";

const endpoint = "**/api/v1/citizen-reports/*/corroborate";
const button = "Corroborate with environmental data";
let analysisCalls = 0;
async function analyze(page: Page) {
  await page.goto("/");
  await page
    .getByLabel("Field image")
    .setInputFiles({
      name: "field.png",
      mimeType: "image/png",
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1sAAAAASUVORK5CYII=",
        "base64",
      ),
    });
  await page.getByLabel("Field latitude").fill("28.4595");
  await page.getByLabel("Field longitude").fill("77.0266");
  await page
    .getByRole("button", { name: "Interpret image", exact: true })
    .click();
  await expect(page.getByRole("button", { name: button })).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  analysisCalls = 0;
  await page.route("**/environment/context?**", (route) =>
    route.fulfill({ json: environment }),
  );
  await page.route("**/environment/satellite?**", (route) =>
    route.fulfill({ json: satellite }),
  );
  await page.route("**/citizen-reports/analyze", (route) => {
    analysisCalls++;
    return route.fulfill({
      json: {
        ...citizen,
        analysis: {
          ...citizen.analysis,
          event_type: "open_burning",
          event_type_confidence: "high",
          insufficient_evidence: false,
        },
      },
    });
  });
});

test("explicit analyze → corroborate, staged state and strong card", async ({
  page,
}) => {
  let calls = 0;
  await page.route(endpoint, async (route) => {
    calls++;
    expect(route.request().method()).toBe("POST");
    expect(route.request().postData()).toBeNull();
    expect(route.request().url()).toContain(citizen.report.id);
    await new Promise((resolve) => setTimeout(resolve, 250));
    await route.fulfill({ json: fixture });
  });
  await analyze(page);
  expect(calls).toBe(0);
  await page.getByRole("button", { name: button }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Looking up environmental sources" }),
  ).toBeVisible();
  const card = page
    .getByRole("article")
    .filter({ hasText: "EVIDENCE FUSION CARD" });
  await expect(card).toContainText("STRONG SUPPORT");
  await expect(card).toContainText("FIELD VERIFICATION");
  await expect(card).toContainText("Image capture time is unknown");
  await expect(card).toContainText(
    "not equivalent to ground-level pollutant concentrations",
  );
  expect(analysisCalls).toBe(1);
  expect(calls).toBe(1);
  await card.screenshot({ path: "test-results/phase2b-fusion-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await card.screenshot({ path: "test-results/phase2b-fusion-mobile.png" });
});

test("moderate categorical support", async ({ page }) => {
  await page.route(endpoint, (route) =>
    route.fulfill({ json: { ...fixture, support_level: "MODERATE" } }),
  );
  await analyze(page);
  await page.getByRole("button", { name: button }).click();
  await expect(page.locator(".fusion-card")).toContainText("MODERATE SUPPORT");
  await expect(page.locator(".fusion-card")).toContainText(
    "Checklist category, not a probability",
  );
});

test("partial provider failure remains visible", async ({ page }) => {
  const partial = structuredClone(fixture);
  partial.rules[1].verdict = "UNAVAILABLE";
  partial.rules[1].summary = "Current AQ context is unavailable.";
  partial.source_summary[1].status = "error";
  partial.source_summary[1].verdict = "UNAVAILABLE";
  await page.route(endpoint, (route) => route.fulfill({ json: partial }));
  await analyze(page);
  await page.getByRole("button", { name: button }).click();
  const aq = page
    .locator(".fusion-row")
    .filter({
      has: page.getByRole("heading", {
        name: "Current air quality",
        exact: true,
      }),
    });
  await expect(aq).toContainText("UNAVAILABLE");
  await expect(aq).toContainText("Source: error");
  await expect(page.locator(".fusion-card")).toContainText("STRONG SUPPORT");
});

test("insufficient evidence gives review, no automatic action", async ({
  page,
}) => {
  await page.route(endpoint, (route) =>
    route.fulfill({
      json: {
        ...fixture,
        support_level: "INSUFFICIENT",
        recommended_next_step: "REVIEW",
        aggregation_explanation:
          "No fresh applicable environmental evidence is available for corroboration.",
      },
    }),
  );
  await analyze(page);
  await page.getByRole("button", { name: button }).click();
  await expect(page.locator(".fusion-card")).toContainText(
    "INSUFFICIENT EVIDENCE",
  );
  await expect(page.locator(".fusion-next")).toContainText("REVIEW");
  await expect(page.locator(".fusion-next")).toContainText(
    "No incident or authority task has been created",
  );
});

test("expired report asks for new analysis without rerunning Gemini", async ({
  page,
}) => {
  await page.route(endpoint, (route) =>
    route.fulfill({ status: 404, json: { detail: "Report expired" } }),
  );
  await analyze(page);
  await page.getByRole("button", { name: button }).click();
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Report expired or unavailable" }),
  ).toBeVisible();
  await expect(page.locator(".fusion-card")).toHaveCount(0);
  expect(analysisCalls).toBe(1);
});

test("rule provenance expands with timestamps, inputs and source references", async ({
  page,
}) => {
  await page.route(endpoint, (route) => route.fulfill({ json: fixture }));
  await analyze(page);
  await page.getByRole("button", { name: button }).click();
  await page
    .getByText("Nearby fire provenance and rule", { exact: true })
    .click();
  const details = page.locator("details[open]");
  await expect(details).toContainText("FIRMS.PROXIMITY.v1");
  await expect(details).toContainText("test-fire");
  await expect(details).toContainText("Observed:");
  await expect(details).toContainText("very near km");
  await page.getByText("Assessment provenance", { exact: true }).click();
  await expect(
    page.locator("details[open]").filter({ hasText: "Assessment provenance" }),
  ).toContainText("submission time proxy");
});

test("clearing submission discards an in-flight corroboration result", async ({
  page,
}) => {
  await page.route(endpoint, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 300));
    await route.fulfill({ json: fixture });
  });
  await analyze(page);
  await page.getByRole("button", { name: button }).click();
  await page.getByRole("button", { name: "Clear submission" }).click();
  await expect(
    page.getByRole("region", { name: "Evidence corroboration" }),
  ).toHaveCount(0);
  await expect(page.locator(".fusion-card")).toHaveCount(0);
});
