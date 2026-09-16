import { expect, test } from "./test";
import forecast from "./fixtures/forecast.test.json";
import environment from "./fixtures/environment.test.json";
import satellite from "./fixtures/satellite.test.json";

const endpoint = "**/api/v1/environment/forecast?*";
test.beforeEach(async ({ page }) => {
  await page.route("**/environment/context?*", (route) =>
    route.fulfill({ json: environment }),
  );
  await page.route("**/environment/satellite?*", (route) =>
    route.fulfill({ json: satellite }),
  );
});

test("standalone forecast exposes 6/12/24 hours, source, comparisons and UTC provenance", async ({
  page,
}) => {
  let calls = 0;
  await page.route(endpoint, (route) => {
    const url = new URL(route.request().url());
    expect(url.searchParams.get("lat")).toBe("28.4595");
    expect(url.searchParams.get("lng")).toBe("77.0266");
    calls++;
    return route.fulfill({
      json: {
        ...forecast,
        provider_status: {
          ...forecast.provider_status,
          status: calls > 1 ? "cached" : "live",
        },
      },
    });
  });
  await page.goto("/");
  const panel = page.getByRole("region", {
    name: "Standalone provider forecast",
    exact: true,
  });
  await expect(
    panel.getByRole("heading", { name: "Google Air Quality forecast" }),
  ).toBeVisible();
  await expect(panel.getByText("WORSENING", { exact: true })).toBeVisible();
  await expect(panel.getByText("42 µg/m³", { exact: true })).toBeVisible();
  await expect(panel).toContainText("130 · Moderate");
  await panel.getByRole("button", { name: "Next 12 hours" }).click();
  await expect(panel.getByText("54 µg/m³", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "Next 24 hours" }).click();
  await expect(panel.getByText("78 µg/m³", { exact: true })).toBeVisible();
  await expect(
    panel.getByText("SHARPLY WORSENING", { exact: true }),
  ).toBeVisible();
  await expect(panel).toContainText("220 · Poor");
  await expect(panel).toContainText("does not change corroboration support");
  await expect(panel).toContainText(
    "Source: Includes air quality data from Google",
  );
  await panel.getByText("Forecast source, timing and rules").click();
  await expect(panel).toContainText("Not supplied by provider");
  await expect(panel).toContainText(forecast.retrieved_at);
  await expect(panel).toContainText("IST");
  await panel.screenshot({ path: "test-results/phase2e-forecast-desktop.png" });
  await panel
    .getByRole("button", { name: "Refresh provider forecast" })
    .click();
  await expect(
    panel.getByText("Forecast cached", { exact: true }),
  ).toBeVisible();
  expect(calls).toBe(2);
});

test("missing CPCB uses pollutant values and never substitutes a different AQI", async ({
  page,
}) => {
  const body = structuredClone(forecast);
  body.summaries.forEach((s) =>
    Object.assign(s, {
      max_cpcb_aqi: null,
      worst_category: null,
      cpcb_hours: 0,
    }),
  );
  body.current_air_quality.indexes = body.current_air_quality.indexes.filter(
    (i) => i.code !== "ind_cpcb",
  );
  await page.route(endpoint, (route) => route.fulfill({ json: body }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const panel = page.getByRole("region", {
    name: "Standalone provider forecast",
    exact: true,
  });
  await expect(panel).toContainText(
    "CPCB index unavailable. Other AQI scales are not substituted.",
  );
  await expect(panel.getByText("42 µg/m³", { exact: true })).toBeVisible();
  await panel.screenshot({ path: "test-results/phase2e-forecast-mobile.png" });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("forecast network failure leaves current conditions and incident workflow available", async ({
  page,
}) => {
  await page.route(endpoint, (route) => route.abort());
  await page.goto("/");
  const panel = page.getByRole("region", {
    name: "Standalone provider forecast",
    exact: true,
  });
  await expect(panel.getByRole("alert")).toContainText(
    "Forecast connection unavailable",
  );
  await expect(page.getByText("3 of 3 sources available")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Interpret image", exact: true }),
  ).toBeVisible();
});

test("partial forecast withholds trend and reports missing hours", async ({
  page,
}) => {
  const body = structuredClone(forecast);
  body.summaries.forEach((s) =>
    Object.assign(s, {
      available_hours: 1,
      pm25_hours: 1,
      cpcb_hours: 1,
      coverage: "partial",
      outlook: "UNAVAILABLE",
    }),
  );
  await page.route(endpoint, (route) => route.fulfill({ json: body }));
  await page.goto("/");
  const panel = page.getByRole("region", {
    name: "Standalone provider forecast",
    exact: true,
  });
  await expect(panel).toContainText("Hourly coverage: 1/6");
  await expect(panel).toContainText("Partial or missing forecast");
  await expect(
    panel.getByText("Comparison unavailable", { exact: true }),
  ).toBeVisible();
});
