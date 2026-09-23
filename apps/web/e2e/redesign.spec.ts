import { expect, test } from "./test";
import source from "./fixtures/handoff-case.test.json";
import handoff from "./fixtures/handoff.test.json";
import environment from "./fixtures/environment.test.json";
import satellite from "./fixtures/satellite.test.json";
import forecast from "./fixtures/forecast.test.json";

const incoming = { ...handoff, state: "SENT_SIMULATED", revision: 2, sent_at: handoff.created_at, allowed_transitions: ["RECEIVED"] };

for (const [name, width, height] of [["desktop", 1440, 1000], ["tablet", 1024, 900], ["mobile", 390, 844]] as const) {
  test(`${name} intelligence hierarchy, keyboard selector and horizon peaks`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/environment/context?**", r => r.fulfill({ json: environment }));
    await page.route("**/environment/satellite?**", r => r.fulfill({ json: satellite }));
    await page.route("**/environment/forecast?**", r => r.fulfill({ json: forecast }));
    await page.route("**/api/v1/review/cases", r => r.fulfill({ json: [{ id: source.id, event_type: source.snapshot.assessment.event_type, is_synthetic: true, jurisdiction: source.snapshot.jurisdiction, review: source.review, support_level: source.snapshot.assessment.support_level, submitted_at: source.snapshot.record.report.created_at }] }));
    await page.route(`**/api/v1/review/cases/${source.id}`, r => r.fulfill({ json: source }));
    await page.route("**/api/v1/handoffs?*", r => r.fulfill({ json: [incoming] }));
    await page.route(`**/api/v1/handoffs/${handoff.id}`, r => r.fulfill({ json: incoming }));
    await page.goto("/");
    await expect(page.getByText("API operational")).toBeVisible();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to command center" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("#officer-command")).toBeFocused();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: `test-results/redesign-${name}-command.png` });
    if (width < 1200) await page.getByRole("button", { name: "Show case selector" }).click();
    const queue = page.getByRole("complementary", { name: "Case queue" });
    const choice = queue.getByRole("button").filter({ hasText: "SYNTHETIC INPUT" });
    await choice.focus(); await page.keyboard.press("Enter");
    const detail = page.getByRole("region", { name: "Selected case details" });
    await expect(detail.getByRole("region", { name: "Corroboration overview" })).toContainText(source.snapshot.assessment.support_level);
    await expect(detail.getByText("Rule-based support, not a probability or confirmation.")).toBeVisible();
    await expect(detail.getByRole("region", { name: "Forecast outlook" })).toBeVisible();
    await expect(detail.locator('.forecast-extra')).not.toHaveAttribute('open');
    await expect(detail.locator('.forecast-horizons')).toContainText('µg/m³');
    await expect(detail).toContainText('Peaks within each window, not readings at the end of it');
    if (width < 1200) {
      const toggle = page.getByRole('button', { name: 'Hide case selector' });
      await toggle.focus(); await page.keyboard.press('Enter');
      await expect(queue).toBeHidden();
      await page.getByRole('button', { name: 'Show case selector' }).click();
      await expect(choice).toBeVisible();
    }
    await detail.getByRole('link', { name: 'Review & handoff ↓' }).click();
    await expect(detail.getByRole('region', { name: 'Officer review controls' })).toBeInViewport();
    await detail.getByRole('link', { name: 'Assessment', exact: true }).click();
    await detail.evaluate(e => e.scrollTop = 0);
    await page.locator('.officer-workspace').screenshot({ path: `test-results/redesign-${name}-case.png` });
    await detail.locator('summary').filter({ hasText: 'Corroboration ·' }).click();
    await detail.locator('.fusion-card').evaluate(e => e.scrollIntoView({ block: 'start', behavior: 'instant' }));
    await detail.screenshot({ path: `test-results/redesign-${name}-fusion.png` });
    await page.getByRole('button', { name: 'Incoming handoffs', exact: true }).click();
    await page.getByRole('region', { name: 'Incoming handoffs', exact: true }).getByRole('button').filter({ hasText: 'SIMULATED · SYNTHETIC' }).click();
    await expect(detail.getByRole('region', { name: 'Handoff review panel' })).toContainText('INTEGRITY VERIFIED');
    await expect.poll(() => detail.evaluate(e => e.scrollTop)).toBe(0);
    await expect(detail.getByRole('heading', { name: 'Jurisdiction handoff' })).toBeInViewport();
    await expect(detail.getByText('View packet details', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const badges = await detail.locator('.badge').evaluateAll(elements => elements.every(e => e.scrollWidth <= e.clientWidth));
    expect(badges).toBe(true);
    await page.locator('.officer-workspace').screenshot({ path: `test-results/redesign-${name}-inbox.png` });
  });
}
