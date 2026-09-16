import { expect, test } from "@playwright/test";
import type { CitizenAnalysis } from "../src/lib/api";
import fixture from "./fixtures/citizen.test.json";
import environment from "./fixtures/environment.test.json";
import satellite from "./fixtures/satellite.test.json";

const endpoint = "**/api/v1/citizen-reports/analyze";
// Developer-created 1x1 PNG for upload interaction; Gemini responses are mocked.
const png = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aL1sAAAAASUVORK5CYII=",
  "base64",
);
const upload = { name: "field.png", mimeType: "image/png", buffer: png };

async function fill(page: import("@playwright/test").Page) {
  await page.getByLabel("Field image").setInputFiles(upload);
  await page.getByLabel("Field latitude").fill("28.4595");
  await page.getByLabel("Field longitude").fill("77.0266");
  await page.getByLabel("Your description").fill("Factory releasing toxic gas");
}

test.beforeEach(async ({ page }) => {
  await page.route("**/environment/context?**", (route) =>
    route.fulfill({ json: environment }),
  );
  await page.route("**/environment/satellite?**", (route) =>
    route.fulfill({ json: satellite }),
  );
});

test("image preview, structured uncertain result, privacy and no fusion", async ({
  page,
}) => {
  const envRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/environment/"))
      envRequests.push(request.url());
  });
  await page.route(endpoint, async (route) => {
    expect(route.request().headers()["content-type"]).toContain(
      "multipart/form-data",
    );
    expect(route.request().postDataBuffer()?.toString()).toContain(
      "Factory releasing toxic gas",
    );
    await new Promise((resolve) => setTimeout(resolve, 250));
    await route.fulfill({ json: fixture });
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "A field observation. A careful interpretation.",
    }),
  ).toBeVisible();
  await fill(page);
  await expect(
    page.getByAltText("Selected citizen submission preview"),
  ).toBeVisible();
  const before = envRequests.length;
  await page
    .getByRole("button", { name: "Interpret image", exact: true })
    .click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Interpreting visual evidence" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "uncertain", exact: true }),
  ).toBeVisible();
  const panel = page.locator("#field-evidence");
  await expect(panel).toContainText("Possible event type");
  await expect(panel).toContainText("Model-estimated ordinal judgment");
  await expect(panel).toContainText(
    "AI interpretation — requires environmental corroboration",
  );
  await expect(panel).toContainText("Citizen description · unverified");
  expect(envRequests.length).toBe(before);
  await panel.screenshot({ path: "test-results/phase2a-citizen-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await panel.screenshot({ path: "test-results/phase2a-citizen-mobile.png" });
  await page.getByRole("button", { name: "Clear submission" }).click();
  await expect(
    page.getByAltText("Selected citizen submission preview"),
  ).toHaveCount(0);
  await expect(panel).not.toContainText("Citizen description · unverified");
  await expect(
    page.getByRole("button", { name: "Interpret image", exact: true }),
  ).toBeDisabled();
});

test("local unsupported/oversized image validation prevents requests", async ({
  page,
}) => {
  let calls = 0;
  await page.route(endpoint, (route) => {
    calls++;
    return route.abort();
  });
  await page.goto("/");
  await page
    .getByLabel("Field image")
    .setInputFiles({
      name: "bad.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("not image"),
    });
  await expect(
    page.getByRole("alert").filter({ hasText: "Choose one JPEG" }),
  ).toBeVisible();
  await page
    .getByLabel("Field image")
    .setInputFiles({
      name: "big.png",
      mimeType: "image/png",
      buffer: Buffer.alloc(5 * 1024 * 1024 + 1),
    });
  await expect(
    page.getByRole("alert").filter({ hasText: "Choose one JPEG" }),
  ).toBeVisible();
  expect(calls).toBe(0);
});

for (const status of ["not_configured", "timeout", "safety_blocked"] as const) {
  test(`honest ${status} failure and retry`, async ({ page }) => {
    await page.route(endpoint, (route) =>
      route.fulfill({
        json: {
          ...fixture,
          status,
          analysis: null,
          evidence: null,
          message: "No interpretation is available.",
        } satisfies Omit<CitizenAnalysis, "report"> & {
          report: typeof fixture.report;
        },
      }),
    );
    await page.goto("/");
    await fill(page);
    await page
      .getByRole("button", { name: "Interpret image", exact: true })
      .click();
    await expect(
      page
        .getByRole("alert")
        .filter({ hasText: "No interpretation is available" }),
    ).toBeVisible();
    await expect(page.locator("#field-evidence")).not.toContainText(
      "Possible event type",
    );
    await expect(
      page.getByRole("button", { name: "Interpret image", exact: true }),
    ).toBeEnabled();
  });
}

test("backend rejects malformed image and the user can resubmit", async ({
  page,
}) => {
  await page.route(endpoint, (route) =>
    route.fulfill({
      status: 422,
      json: { status: "invalid_input", message: "Invalid image" },
    }),
  );
  await page.goto("/");
  await fill(page);
  await page
    .getByRole("button", { name: "Interpret image", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Check the image format" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Interpret image", exact: true }),
  ).toBeEnabled();
});
