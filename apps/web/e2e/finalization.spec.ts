import { test, expect } from "./test";

test("one keyboard-accessible journey distinguishes provider, AI, rules and simulation", async ({ page }) => {
  await page.goto("/");
  const guide = page.getByRole("region", { name: "Demo journey" });
  await expect(guide).toContainText("deterministic corroboration rules");
  await expect(guide).toContainText("All handoffs are simulated");
  const evidence = guide.getByRole("link", { name: /Synthetic image/ });
  await evidence.focus(); await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#field-evidence$/);
  await page.getByRole("button", { name: "Use synthetic cross-jurisdiction demo" }).click();
  await expect(page.locator('.citizen-panel')).toContainText('SYNTHETIC CROSS-JURISDICTION DEMO');
  await expect(page.getByText('ILLUSTRATIVE DEMO FORECAST', { exact: true })).toBeVisible();
});
