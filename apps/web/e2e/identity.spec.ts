import { test, expect } from "@playwright/test";

test("unconfigured protected shells explain unavailable sign-in without exposing records", async ({ page }) => {
  for (const path of ["/resident", "/authority"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: "Sign-in unavailable" })).toBeVisible();
    await expect(page.getByText("Managed sign-in is not configured in this deployment.")).toBeVisible();
    await expect(page.getByRole("textbox")).toHaveCount(0);
  }
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
});

test("anonymous BFF and SDK token/profile paths fail closed and disable shared caching", async ({ request }) => {
  for (const path of ["/api/app/v2/me", "/api/app/v2/resident/reports"]) {
    const response = await request.get(path);
    expect(response.status()).toBe(503); // No managed identity config in regression deployment.
    expect(response.headers()["cache-control"]).toContain("no-store");
    expect(await response.json()).toEqual({ detail: "Sign-in is not configured" });
  }
  for (const path of ["/auth/access-token", "/auth/profile", "/auth/connect", "/auth/logout"]) {
    const response = await request.get(path);
    expect(response.status()).toBe(404);
    expect(response.headers()["cache-control"]).toContain("no-store");
  }
});

test("unsafe login return destination is never reflected into navigation", async ({ page }) => {
  await page.goto("/sign-in?returnTo=https%3A%2F%2Fevil.invalid&status=failed");
  await expect(page.getByRole("heading", { name: "Sign in to AirshedOS" })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Sign-in could not complete." }))
    .toHaveText("Sign-in could not complete. Please try again.");
  await expect(page.locator('a[href*="evil.invalid"]')).toHaveCount(0);
});

test("identity shells remain usable on a narrow screen and by keyboard", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/sign-in");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content", exact: true })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator(".pilot-header").getByRole("link", { name: "AirshedOS home", exact: true })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
