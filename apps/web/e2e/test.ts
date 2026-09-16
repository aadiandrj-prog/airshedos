import { test as base } from "@playwright/test";
import forecast from "./fixtures/forecast.test.json";
export { expect, type Page } from "@playwright/test";

// Every browser test intercepts forecast networking, including against a configured local app.
// Individual forecast tests override this route with a sanitized synthetic response.
export const test = base.extend<{ forecastIsolation: void }>({
  forecastIsolation: [
    async ({ page }, use) => {
      await page.route("**/api/v1/environment/forecast?*", (route) =>
        route.fulfill({
          json: {
            ...forecast,
            provider_status: {
              ...forecast.provider_status,
              configured: false,
              status: "not_configured",
              message: "Synthetic test: forecast not configured.",
            },
            current_air_quality: null,
            hourly_forecasts: [],
            summaries: [],
            retrieved_at: null,
          },
        }),
      );
      await use();
    },
    { auto: true },
  ],
});
