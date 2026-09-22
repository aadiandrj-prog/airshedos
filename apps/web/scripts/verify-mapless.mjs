/* Local-only drill against a separately built frontend with an empty Maps key. */
import { chromium, expect } from '@playwright/test';
import fs from 'node:fs';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
let sdkRequests = 0;
page.on('request', request => {
  const url = new URL(request.url());
  if (url.hostname === 'maps.googleapis.com' && url.pathname === '/maps/api/js') sdkRequests++;
});
let stage = 'open';
const result = { captured_at: new Date().toISOString(), drill: 'compiled_without_maps_key' };
try {
  await page.goto('http://localhost:3000');
  stage = 'map_unavailable';
  await expect(page.getByText('Map unavailable.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Use synthetic cross-jurisdiction demo' }).click();
  await expect(page.getByLabel('Field latitude')).toHaveValue('28.52');
  stage = 'case_queue';
  const queue = page.getByRole('complementary', { name: 'Case queue' });
  await queue.getByRole('button').filter({ hasText: 'SYNTHETIC INPUT' }).first().click();
  stage = 'review';
  const review = page.getByRole('region', { name: 'Officer review controls' });
  await expect(review).toBeVisible();
  const begin = review.getByRole('button', { name: 'Begin review', exact: true });
  if (await begin.count()) await begin.click();
  await expect(review).toContainText('UNDER REVIEW');
  await expect(page.getByRole('region', { name: 'Hand off case' })).toBeVisible();
  result.sdk_requests = sdkRequests;
  result.textual_review_usable = true;
  result.mobile_no_overflow = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
  result.pass = sdkRequests === 0 && result.mobile_no_overflow;
} catch (error) { result.pass = false; result.error_type = error.name; result.failed_stage = stage; }
fs.mkdirSync('data/verification', { recursive: true });
fs.writeFileSync('data/verification/phase3c-mapless.json', JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
await browser.close();
process.exitCode = result.pass ? 0 : 1;
