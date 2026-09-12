import { expect, test } from "@playwright/test";
import ground from "./fixtures/environment.test.json";
import satellite from "./fixtures/satellite.test.json";

const endpoint = "**/api/v1/environment/satellite?*";
test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/environment/context?*", (route) =>
    route.fulfill({ json: ground }),
  );
});

test("satellite units, age, QA and scene provenance remain separate from ground AQ", async ({
  page,
}) => {
  let calls = 0;
  await page.route(endpoint, (route) => {
    const body = structuredClone(satellite);
    if (++calls > 1) {
      body.provider_status.status = "cached";
      for (const product of body.products) {
        product.status = "cached";
        product.cache_hit = true;
      }
    }
    return route.fulfill({ json: body });
  });
  await page.goto("/");
  const panel = page.getByRole("region", {
    name: "Latest usable satellite observations",
  });
  await expect(panel.getByText("Available", { exact: true })).toHaveCount(3);
  await expect(
    panel.getByText("Observed 16.0h ago", { exact: true }),
  ).toHaveCount(3);
  await expect(
    panel.getByText("3.200e-5 mol/m²", { exact: true }),
  ).toBeVisible();
  await expect(panel.getByText("0.033 mol/m²", { exact: true })).toBeVisible();
  await expect(
    panel.getByText("-0.7 dimensionless", { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByText("not equivalent to ground-level", { exact: false }),
  ).toBeVisible();
  await expect(panel.getByText("Live satellite", { exact: false })).toHaveCount(
    0,
  );
  await panel.locator("summary").first().click();
  await expect(
    panel.getByText("COPERNICUS/S5P/NRTI/L3_NO2/SYNTHETIC_TEST_SCENE", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    panel.getByText("Catalog L3 ingestion: tropospheric NO2 QA >= 0.75"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Check conditions" }).click();
  await expect(
    panel.getByText("Cached retrieval", { exact: true }),
  ).toBeVisible();
  await panel.screenshot({
    path: "test-results/phase1c-satellite-desktop.png",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(panel.getByText("-0.7 dimensionless")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await panel.screenshot({ path: "test-results/phase1c-satellite-mobile.png" });
});

test("missing scenes, filtered scenes and no usable pixels remain distinct", async ({
  page,
}) => {
  const body = structuredClone(satellite);
  for (const [i, product] of body.products.entries()) {
    Object.assign(product, {
      observation: null,
      status: "unavailable",
      availability: ["no_scene", "quality_filtered", "no_usable_pixels"][i],
      message: "Synthetic absence",
    });
  }
  await page.route(endpoint, (route) => route.fulfill({ json: body }));
  await page.goto("/");
  const panel = page.locator(".satellite-panel");
  for (const label of [
    "No recent scene",
    "Quality filtered",
    "No usable pixels",
  ])
    await expect(panel.getByText(label, { exact: true })).toBeVisible();
  await expect(panel.locator(".satellite-value")).toHaveCount(0);
  await expect(page.getByText("3 of 3 sources available")).toBeVisible();
});

test("partial satellite error preserves other product observations", async ({
  page,
}) => {
  const body = structuredClone(satellite);
  Object.assign(body.products[1], {
    observation: null,
    status: "error",
    availability: "authentication_error",
    message: "Credentials need renewal.",
  });
  await page.route(endpoint, (route) => route.fulfill({ json: body }));
  await page.goto("/");
  const panel = page.locator(".satellite-panel");
  await expect(panel.getByText("Available", { exact: true })).toHaveCount(2);
  await expect(
    panel.getByText("Authentication required", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("3 of 3 sources available")).toBeVisible();
});

test("slow satellite request does not block ground data; new coordinates reach both APIs", async ({
  page,
}) => {
  let release: () => void = () => {};
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(endpoint, async (route) => {
    await pending;
    return route.fulfill({ json: satellite });
  });
  await page.goto("/");
  await expect(page.getByText("3 of 3 sources available")).toBeVisible();
  await expect(
    page.getByText("Searching recent satellite observations…", {
      exact: false,
    }),
  ).toBeVisible();
  release();
  await expect(page.locator(".satellite-value")).toHaveCount(3);
  await page.getByLabel("Latitude", { exact: true }).fill("28.6");
  const requested = page.waitForRequest((request) =>
    request.url().includes("/satellite?lat=28.6&lng=77.0266"),
  );
  await page.getByRole("button", { name: "Check conditions" }).click();
  await requested;
});

test("satellite connection error retries without breaking the demo", async ({
  page,
}) => {
  await page.route(endpoint, (route) => route.abort());
  await page.goto("/");
  await expect(
    page.locator(".satellite-panel").getByRole("alert"),
  ).toContainText("could not be retrieved");
  await expect(
    page.getByRole("heading", { name: "Evidence fusion" }),
  ).toBeVisible();
  await page.unroute(endpoint);
  const body = structuredClone(satellite);
  body.provider_status.status = "not_configured";
  for (const product of body.products)
    Object.assign(product, {
      observation: null,
      status: "not_configured",
      availability: "not_configured",
      message: "Configure backend ADC.",
    });
  await page.route(endpoint, (route) => route.fulfill({ json: body }));
  await page.getByRole("button", { name: "Check conditions" }).click();
  await expect(
    page
      .locator(".satellite-panel")
      .getByText("Setup required", { exact: true }),
  ).toHaveCount(4);
});
