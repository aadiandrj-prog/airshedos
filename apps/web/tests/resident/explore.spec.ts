import { test, expect } from "@playwright/test";
import fixture from "../fixtures/explore-synthetic.json";
import axe from "axe-core";
import { mkdir } from "node:fs/promises";

function sample() {
  const data = structuredClone(fixture);
  data.expires_at = new Date(Date.now() + 60000).toISOString();
  return data;
}

test("public overview loads only on request; narrow view, source times, forecast and attribution", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/explore/gurugram", async route => {
    calls++;
    expect(route.request().method()).toBe("POST");
    expect(route.request().postDataJSON()).toEqual({});
    await route.fulfill({ json: sample() });
  });
  await page.goto("/explore");
  await expect(page.getByRole("heading", { name: "The air around you, with context." })).toBeVisible();
  expect(calls).toBe(0);
  await page.getByRole("button", { name: "View current conditions" }).click();
  await expect(page.getByRole("heading", { name: "Gurugram", exact: true })).toBeVisible();
  await expect(page.getByText("Window peaks, not readings at the end", { exact: false })).toBeVisible();
  await expect(page.getByText("NASA FIRMS", { exact: false }).first()).toBeVisible();
  expect(await page.getByAltText("Google Maps", { exact: true }).count()).toBe(4);
  expect(calls).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.addScriptTag({ content: axe.source });
  const audit = await page.evaluate(async () => await (window as unknown as { axe: { run: () => Promise<{ violations: { id: string }[] }> } }).axe.run());
  expect(audit.violations).toEqual([]);
  if (process.env.SEVA_CAPTURE_OVERVIEW === "1") {
    await mkdir("../../docs/seva/screenshots/explore", { recursive: true });
    await page.locator(".air-intro").evaluate(el => el.insertAdjacentHTML("afterbegin", "<p>SYNTHETIC VERIFICATION DATA · LOCAL TEST</p>"));
    await page.screenshot({ path: "../../docs/seva/screenshots/explore/mobile-synthetic.png", fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({ path: "../../docs/seva/screenshots/explore/desktop-synthetic.png", fullPage: true });
  }
});

test("area change rejects stale arrival and failures remain understandable", async ({ page }) => {
  await page.route("**/api/explore/gurugram", async route => {
    await new Promise(done => setTimeout(done, 800));
    await route.fulfill({ json: sample() });
  });
  await page.route("**/api/explore/delhi", route => route.fulfill({ status: 429, json: { detail: "Synthetic quota denial" } }));
  await page.goto("/explore");
  await page.getByRole("button", { name: "View current conditions" }).click();
  await page.getByLabel("Choose an area").selectOption("delhi");
  await page.waitForTimeout(1000);
  await expect(page.getByRole("heading", { name: "Gurugram", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "View current conditions" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "request limit" })).toContainText("request limit");
  await expect(page.getByRole("link", { name: "Report a concern", exact: true }).first()).toBeVisible();
});

test("expired public provider content clears without automatic paid refresh", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/explore/gurugram", route => {
    calls++;
    const data = sample(); data.expires_at = new Date(Date.now() + 3000).toISOString();
    return route.fulfill({ json: data });
  });
  await page.goto("/explore");
  await page.getByRole("button", { name: "View current conditions" }).click();
  await expect(page.getByRole("heading", { name: "Gurugram", exact: true })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "expired" })).toContainText("expired");
  await expect(page.getByRole("heading", { name: "Gurugram", exact: true })).toHaveCount(0);
  expect(calls).toBe(1);
});
