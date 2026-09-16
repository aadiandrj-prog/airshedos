import { expect, test, type Page } from "./test";
import fixture from "./fixtures/environment.test.json";

// Synthetic normalized fixture, intercepted only in tests. Never used by the app.
const endpoint = "**/api/v1/environment/context?*";

async function mockUnconfigured(page: Page) {
  await page.route(endpoint, (route) => {
    const query = new URL(route.request().url()).searchParams;
    return route.fulfill({
      json: {
        ...fixture,
        latitude: Number(query.get("lat")),
        longitude: Number(query.get("lng")),
        air_quality: null,
        weather: null,
        fires: null,
        source_statuses: Object.fromEntries(
          Object.entries(fixture.source_statuses).map(([key, source]) => [
            key,
            {
              ...source,
              configured: false,
              status: "not_configured",
              retrieved_at: null,
              message:
                "Synthetic test: backend credentials are not configured.",
            },
          ]),
        ),
      },
    });
  });
}

test("unconfigured providers remain separate from the functional demo", async ({
  page,
}) => {
  await mockUnconfigured(page);
  const external: string[] = [];
  page.on("request", (request) => {
    if (/googleapis|modaps\.eosdis/.test(request.url()))
      external.push(request.url());
  });
  await page.goto("/");
  const panel = page.locator("#environment-context");
  await expect(panel.getByText("Not configured", { exact: true })).toHaveCount(
    3,
  );
  await expect(panel.getByText("0 of 3 sources available")).toBeVisible();
  await expect(panel.getByText("These do not", { exact: false })).toContainText(
    "fictional incident",
  );
  await expect(page.getByText("DEMO · PHASE 1A")).toBeVisible();
  await panel.getByLabel("Latitude", { exact: true }).fill("-33.8688");
  await panel.getByLabel("Longitude", { exact: true }).fill("151.2093");
  const response = page.waitForResponse((r) =>
    r.url().includes("lat=-33.8688&lng=151.2093"),
  );
  await panel.getByRole("button", { name: "Check conditions" }).click();
  expect((await response).status()).toBe(200);
  await expect(panel.getByText("Query: -33.8688°, 151.2093°")).toBeVisible();
  expect(external).toEqual([]);
});

test("provider readings, source times, units, and cached states render", async ({
  page,
}) => {
  let calls = 0;
  await page.route(endpoint, async (route) => {
    const body = structuredClone(fixture);
    if (++calls > 1) {
      for (const source of Object.values(body.source_statuses))
        source.status = "cached";
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  const panel = page.locator("#environment-context");
  await expect(panel.getByText("Live data", { exact: true })).toHaveCount(3);
  await expect(panel.getByText("3 of 3 sources available")).toBeVisible();
  await expect(panel.getByText("31.4 °C", { exact: false })).toBeVisible();
  await expect(panel.getByText("225° · southwest")).toBeVisible();
  await expect(panel.getByText("40.2 µg/m³", { exact: true })).toBeVisible();
  await expect(panel.getByText("ppb", { exact: false })).toBeVisible();
  await expect(panel.getByText("Closest detection: 1.11 km")).toBeVisible();
  await expect(panel.getByText("Google Maps", { exact: true })).toHaveCount(2);
  await expect(panel.getByText("VIIRS SNPP NRT", { exact: false })).toBeVisible();
  await panel.locator("summary").first().click();
  await expect(
    panel.getByText("Observed", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    panel.getByText("google_air_quality", { exact: true }),
  ).toBeVisible();
  await panel.getByRole("button", { name: "Check conditions" }).click();
  await expect(panel.getByText("Cached data", { exact: true })).toHaveCount(3);
  await page.screenshot({
    path: "test-results/mocked-readings.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/mocked-mobile.png",
    fullPage: true,
  });
});

test("partial response and legitimate zero detections", async ({ page }) => {
  await page.route(endpoint, (route) =>
    route.fulfill({
      json: {
        ...fixture,
        weather: null,
        fires: [],
        source_statuses: {
          ...fixture.source_statuses,
          weather: {
            ...fixture.source_statuses.weather,
            status: "unavailable",
            message: "Provider timed out.",
          },
        },
      },
    }),
  );
  await page.goto("/");
  const panel = page.locator("#environment-context");
  await expect(panel.getByText("2 of 3 sources available")).toBeVisible();
  await expect(panel.getByText("Unavailable", { exact: true })).toBeVisible();
  await expect(
    panel.getByText("No nearby active-fire detections returned."),
  ).toBeVisible();
  await expect(
    panel.locator(".source-card").last().locator(".metric-value"),
  ).toContainText("0");
  await expect(
    page.getByRole("heading", { name: "Evidence fusion" }),
  ).toBeVisible();
});

test("all provider errors remain distinct from zero detections", async ({
  page,
}) => {
  const body = structuredClone(fixture);
  await page.route(endpoint, (route) =>
    route.fulfill({
      json: {
        ...body,
        air_quality: null,
        weather: null,
        fires: null,
        source_statuses: Object.fromEntries(
          Object.entries(body.source_statuses).map(([key, source]) => [
            key,
            { ...source, status: "error" },
          ]),
        ),
      },
    }),
  );
  await page.goto("/");
  const panel = page.locator("#environment-context");
  await expect(panel.getByText("Provider error", { exact: true })).toHaveCount(
    3,
  );
  await expect(panel.getByText("0 of 3 sources available")).toBeVisible();
  await expect(
    panel.getByText("An unavailable source does not mean zero fires.", {
      exact: false,
    }),
  ).toBeVisible();
});

test("environment connection failure can retry without breaking the incident", async ({
  page,
}) => {
  await page.route(endpoint, (route) => route.abort());
  await page.goto("/");
  const panel = page.locator("#environment-context");
  await expect(panel.getByRole("alert")).toContainText(
    "could not be retrieved",
  );
  await expect(
    page.getByRole("heading", { name: "Evidence fusion" }),
  ).toBeVisible();
  await page.unroute(endpoint);
  await mockUnconfigured(page);
  await panel.getByRole("button", { name: "Check conditions" }).click();
  await expect(panel.getByText("Not configured", { exact: true })).toHaveCount(
    3,
  );
  await page.setViewportSize({ width: 640, height: 450 }); // 1280px desktop at 200% zoom reflow.
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
