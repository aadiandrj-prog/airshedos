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
  if (process.env.SEVA_CAPTURE_FINAL === "1") {
    await mkdir("../../docs/seva/screenshots/final", { recursive: true });
    await page.locator(".air-intro").evaluate(el => el.insertAdjacentHTML("afterbegin", "<p>SYNTHETIC VERIFICATION DATA · LOCAL TEST</p>"));
    await page.screenshot({ path: "../../docs/seva/screenshots/final/mobile-synthetic.png", fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({ path: "../../docs/seva/screenshots/final/desktop-synthetic.png", fullPage: true });
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

test("optional location is rounded, fetched only on request and can be cleared", async ({ page, context }) => {
  await context.grantPermissions(["geolocation"]);
  await context.setGeolocation({ latitude: 28.459493, longitude: 77.026638, accuracy: 37 });
  let calls = 0;
  await page.route("**/api/explore/nearby", route => {
    calls++;
    expect(route.request().postDataJSON()).toEqual({ latitude: 28.46, longitude: 77.025 });
    expect(route.request().url()).not.toContain("28.46");
    const data = sample();
    data.area = { ...data.area, id: "nearby", name: "Near you", latitude: 28.46, longitude: 77.025 };
    data.context.latitude = 28.46; data.context.longitude = 77.025;
    data.forecast.latitude = 28.46; data.forecast.longitude = 77.025;
    return route.fulfill({ json: data });
  });
  await page.goto("/explore");
  expect(calls).toBe(0);
  await page.getByRole("button", { name: "Use my location" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Approximate location ready" })).toBeVisible();
  expect(calls).toBe(0);
  await expect(page.getByLabel("Choose an area")).toHaveValue("nearby");
  await page.getByRole("button", { name: "View current conditions" }).click();
  await expect(page.getByRole("heading", { name: "Near you", exact: true })).toBeVisible();
  expect(calls).toBe(1);
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
  await page.getByRole("button", { name: "Clear my location" }).click();
  await expect(page.getByRole("heading", { name: "Near you", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Choose an area")).toHaveValue("gurugram");
  expect(calls).toBe(1);
});

test("denied or late location leaves area selection usable and makes no provider request", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "geolocation", { configurable: true, value: {
      getCurrentPosition: (_ok: unknown, fail: (e: {code: number}) => void) => fail({code: 1}),
    } });
  });
  let calls = 0;
  await page.route("**/api/explore/*", route => { calls++; return route.fulfill({ json: sample() }); });
  await page.goto("/explore");
  await page.getByRole("button", { name: "Use my location" }).click();
  await expect(page.getByRole("status").filter({ hasText: "denied or unavailable" })).toBeVisible();
  expect(calls).toBe(0);
  await page.getByLabel("Choose an area").selectOption("delhi");
  await expect(page.getByLabel("Choose an area")).toHaveValue("delhi");
  // A delayed browser callback must not replace a subsequently selected area.
  await page.evaluate(() => Object.defineProperty(navigator, "geolocation", { configurable: true, value: {
    getCurrentPosition: (ok: (p: unknown) => void) => setTimeout(() => ok({coords:{latitude:28.46,longitude:77.025,accuracy:10}}), 700),
  } }));
  await page.getByRole("button", { name: "Use my location" }).click();
  await page.getByLabel("Choose an area").selectOption("noida");
  await page.waitForTimeout(900);
  await expect(page.getByLabel("Choose an area")).toHaveValue("noida");
  expect(calls).toBe(0);
});

test("hourly forecast has keyboard values, missing-data gaps and independent fire details", async ({ page }) => {
  await page.route("**/api/explore/gurugram", route => {
    const data = sample();
    data.forecast.hourly_forecasts.splice(4, 1);
    for (const h of data.forecast.hourly_forecasts) h.pollutants = h.pollutants.filter(p => p.code !== "pm10");
    return route.fulfill({ json: data });
  });
  await page.goto("/explore");
  await page.getByRole("button", { name: "View current conditions" }).click();
  await expect(page.getByRole("region", { name: "Hourly provider forecast" })).toBeVisible();
  await expect(page.getByRole("img", { name: /hourly forecast. Gaps/ })).toBeVisible();
  expect(await page.locator(".air-chart-panel svg path[fill='none']").count()).toBe(2);
  await page.getByLabel("Inspect a forecast hour").selectOption({ index: 1 });
  await expect(page.locator(".air-chart-reading")).not.toBeEmpty();
  await page.getByText("View hourly values as a table", { exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await page.getByLabel("Chart metric").selectOption("pm10");
  await expect(page.getByRole("region", { name: "Hourly provider forecast" })).toContainText("No usable hourly values");
  await page.getByLabel("Chart metric").selectOption("ind_cpcb");
  await expect(page.getByRole("img", { name: /ind_cpcb hourly forecast/ })).toBeVisible();
  await page.getByLabel("Inspect a detection").selectOption({ index: 1 });
  await expect(page.locator(".air-detection-distance")).toContainText("11.1");
  await page.getByText("View detection list and acquisition times", { exact: true }).click();
  await expect(page.locator(".air-fire-list li")).toHaveCount(2);
});

test("home explorer is functional without automatic requests; methodology stays honest", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/explore/gurugram", route => { calls++; return route.fulfill({ json: sample() }); });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Understand local air. Report what you notice." })).toBeVisible();
  expect(calls).toBe(0);
  if (process.env.SEVA_CAPTURE_FINAL === "1") {
    await mkdir("../../docs/seva/screenshots/final", { recursive: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.screenshot({ path: "../../docs/seva/screenshots/final/home-desktop.png", fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: "../../docs/seva/screenshots/final/home-mobile.png", fullPage: true });
  }
  await page.getByRole("button", { name: "View current conditions" }).click();
  await expect(page.getByRole("heading", { name: "Gurugram", exact: true })).toBeVisible();
  expect(calls).toBe(1);
  await page.goto("/methodology");
  await expect(page.getByRole("heading", { name: "Useful context. Visible uncertainty." })).toBeVisible();
  await expect(page.getByText(/There is no established government partnership/)).toBeVisible();
  expect(calls).toBe(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.addScriptTag({ content: axe.source });
  expect((await page.evaluate(async () => await (window as unknown as {axe:{run:()=>Promise<{violations:unknown[]}>}}).axe.run())).violations).toEqual([]);
});
