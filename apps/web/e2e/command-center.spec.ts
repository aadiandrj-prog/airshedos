import { expect, test } from "./test";

test("a sleeping hosted backend can wake without a premature connection error", async ({ page }) => {
  await page.route("**/ready", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 11000));
    await route.fulfill({ json: { status: "ready" } });
  });
  await page.goto("/");
  await expect(page.getByText("The demo server may take up to a minute to wake.", { exact: false })).toBeVisible();
  await expect(page.getByText("API operational")).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole("heading", { name: "Connection unavailable" })).toHaveCount(0);
});

test("backend incident, evidence, acknowledgment and simulated sharing", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByText("API operational")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Evidence fusion" }),
  ).toBeVisible();
  await expect(page.getByText("86%", { exact: false }).first()).toBeVisible();
  await page.getByText("Citizen report", { exact: true }).click();
  await expect(
    page.getByText("Source: fixture:citizen_report", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("88% · supported")).toBeVisible();
  await expect(page.getByText("unavailable", { exact: true })).toBeVisible();
  await expect(page.getByText("DEMO · PHASE 1A")).toBeVisible();
  const acknowledge = page.getByRole("button", {
    name: "Acknowledge",
    exact: true,
  });
  if (await acknowledge.count()) {
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/acknowledge") && r.request().method() === "POST",
    );
    await acknowledge.click();
    expect((await response).status()).toBe(200);
  }
  await expect(
    page.getByRole("button", { name: "✓ Acknowledged" }),
  ).toBeDisabled();
  const share = page.getByRole("button", { name: "Share", exact: true });
  if (await share.count()) {
    const response = page.waitForResponse(
      (r) => r.url().endsWith("/share") && r.request().method() === "POST",
    );
    await share.click();
    expect((await response).status()).toBe(200);
  }
  await expect(
    page.getByRole("heading", { name: "Action record" }),
  ).toBeVisible();
  await expect(
    page
      .getByText(
        "Simulated sharing with South West Delhi. No notification was sent.",
      )
      .last(),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Shared (demo)" }),
  ).toBeDisabled();
  await page.screenshot({
    path: "test-results/command-center-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "Evidence fusion" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/command-center-mobile.png",
    fullPage: true,
  });
});

test("connection failure, retry, loading and empty state", async ({ page }) => {
  await page.route("**/api/v1/incidents", (route) => route.abort());
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Connection unavailable" }),
  ).toBeVisible();
  await page.unroute("**/api/v1/incidents");
  await page.route("**/api/v1/incidents", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 400));
    await route.fulfill({ json: [] });
  });
  await page.getByRole("button", { name: "Retry connection" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Loading incident evidence" }),
  ).toContainText("Loading incident evidence");
  await expect(
    page.getByRole("heading", { name: "No active incidents" }),
  ).toBeVisible();
});

test("action failure leaves state unchanged and permits retry", async ({
  page,
}) => {
  await page.route("**/api/v1/incidents*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const reset = (incident: Record<string, unknown>) => ({
      ...incident,
      status: "open",
      actions: [],
    });
    await route.fulfill({ json: Array.isArray(body) ? body.map(reset) : body });
  });
  await page.route("**/api/v1/incidents/AS-DEL-001", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      json: { ...(await response.json()), status: "open", actions: [] },
    });
  });
  await page.route("**/acknowledge", (route) =>
    route.fulfill({ status: 503, json: { detail: "Unavailable" } }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Acknowledge", exact: true }).click();
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "The action could not be saved" }),
  ).toContainText("The action could not be saved");
  await expect(
    page.getByRole("button", { name: "Acknowledge", exact: true }),
  ).toBeEnabled();
});
