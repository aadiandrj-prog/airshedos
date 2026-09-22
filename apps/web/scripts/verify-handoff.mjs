/* Developer-only real synthetic-input gate. Run from repository root; never run in CI.
   No raw console messages, network URLs, HARs or traces are retained. */
import { chromium, expect } from '@playwright/test';
import fs from 'node:fs';
import { createHash } from 'node:crypto';

(async () => {
  const directory = 'data/verification';
  fs.mkdirSync(directory, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const result = { captured_at: new Date().toISOString(), simulated: true, external_authority_dispatch: false };
  const calls = { analysis: 0, corroboration: 0, environment: 0 };
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (path.endsWith('/citizen-reports/analyze')) calls.analysis++;
    if (path.endsWith('/corroborate')) calls.corroboration++;
    if (path.startsWith('/api/v1/environment/')) calls.environment++;
  });
  let stage = 'open';
  try {
    await page.goto('http://localhost:3000');
    stage = 'synthetic_input';
    await page.getByRole('button', { name: 'Use synthetic cross-jurisdiction demo' }).click();
    await expect(page.getByLabel('Field latitude')).toHaveValue('28.52');
    await expect(page.getByLabel('Field longitude')).toHaveValue('77.08');
    const analysisResponse = page.waitForResponse(r => new URL(r.url()).pathname.endsWith('/citizen-reports/analyze'), { timeout: 45000 });
    await page.getByRole('button', { name: 'Interpret image', exact: true }).click();
    const analysis = await (await analysisResponse).json();
    result.analysis_status = analysis.status;
    if (analysis.status !== 'interpreted' || !analysis.report.is_synthetic) throw new Error('Analysis unavailable');
    stage = 'corroboration';
    const assessmentResponse = page.waitForResponse(r => new URL(r.url()).pathname.endsWith('/corroborate'), { timeout: 90000 });
    await page.getByRole('button', { name: 'Corroborate with environmental data' }).click();
    const assessment = await (await assessmentResponse).json();
    await expect(page.locator('.officer-detail')).toContainText('SYNTHETIC INPUT', { timeout: 10000 });
    stage = 'review';
    await page.getByRole('region', { name: 'Officer review controls' }).getByRole('button', { name: 'Begin review' }).click();
    await expect(page.getByRole('region', { name: 'Officer review controls' })).toContainText('UNDER REVIEW');
    const base = 'http://127.0.0.1:8000/api/v1';
    const before = await (await context.request.get(`${base}/review/cases/${assessment.id}`)).json();
    const callsBefore = { ...calls };
    stage = 'create';
    await page.getByRole('combobox', { name: 'Source control room', exact: true }).selectOption('HARYANA');
    await page.getByRole('combobox', { name: 'Destination jurisdiction', exact: true }).selectOption('DELHI');
    await page.getByRole('combobox', { name: 'Handoff reason', exact: true }).selectOption('CROSS_BORDER_EVENT');
    const createdResponse = page.waitForResponse(r => new URL(r.url()).pathname.endsWith(`/cases/${assessment.id}/handoffs`));
    await page.getByRole('button', { name: 'Generate frozen packet' }).click();
    const created = await (await createdResponse).json();
    const panel = page.getByRole('region', { name: 'Handoff review panel' });
    await expect(panel).toContainText('INTEGRITY VERIFIED');
    stage = 'send';
    await panel.getByRole('button', { name: 'Mark packet ready' }).click();
    await panel.getByRole('button', { name: 'Send simulated handoff' }).click();
    await expect(panel).toContainText('SENT SIMULATED');
    const sent = await (await context.request.get(`${base}/handoffs/${created.id}`)).json();
    stage = 'receive';
    await page.getByRole('button', { name: 'Incoming handoffs', exact: true }).click();
    await page.getByRole('region', { name: 'Incoming handoffs', exact: true }).getByRole('button').filter({ hasText: 'SIMULATED · SYNTHETIC' }).first().click();
    await panel.getByRole('button', { name: 'Receive in demo inbox' }).click();
    await expect(panel).toContainText('INTEGRITY VERIFIED');
    await panel.getByRole('button', { name: 'Accept handoff' }).click();
    await expect(panel).toContainText('ACCEPTED');
    stage = 'export';
    const downloadPromise = page.waitForEvent('download');
    await panel.getByRole('button', { name: 'Export PollutionEvent JSON' }).click();
    const download = await downloadPromise;
    const exportedPath = `${directory}/phase3b-pollution-event.json`;
    await download.saveAs(exportedPath);
    const data = fs.readFileSync(exportedPath);
    const received = await (await context.request.get(`${base}/handoffs/${created.id}`)).json();
    const after = await (await context.request.get(`${base}/review/cases/${assessment.id}`)).json();
    if (JSON.stringify(after) !== JSON.stringify(before)) throw new Error('Source changed');
    if (JSON.stringify(created.payload) !== JSON.stringify(received.payload)) throw new Error('Packet changed');
    if (createHash('sha256').update(data).digest('hex') !== received.payload_hash) throw new Error('Hash mismatch');
    if (JSON.stringify(sent.audit) !== JSON.stringify(received.audit.slice(0, sent.audit.length))) throw new Error('Audit changed');
    if (JSON.stringify(callsBefore) !== JSON.stringify(calls)) throw new Error('Provider rerun');
    const sourceList = await (await context.request.get(`${base}/handoffs?case_id=${assessment.id}`)).json();
    const destinationList = await (await context.request.get(`${base}/handoffs?destination=DELHI`)).json();
    if (sourceList.find(r => r.id === created.id)?.state !== 'ACCEPTED' || destinationList.find(r => r.id === created.id)?.state !== 'ACCEPTED') throw new Error('Inbox inconsistency');
    result.handoff = { id: created.id, from: received.origin_jurisdiction, to: received.destination_jurisdiction,
      state: received.state, integrity: received.integrity, hash: received.payload_hash,
      event_version: received.event_version, revision: received.revision, audit_entries: received.audit.length };
    result.case_unchanged = true; result.packet_unchanged = true; result.audit_append_only = true;
    result.provider_reruns = 0; result.source_destination_consistent = true;
    result.support = assessment.support_level; result.forecast_status = assessment.forecast_outlook?.provider_status.status ?? 'unavailable';
    result.location = received.payload.location;
    await expect(page.getByText('Loading Google map…', { exact: false })).toHaveCount(0, { timeout: 20000 });
    result.map_loaded = await page.getByText('Google map loaded.', { exact: false }).isVisible();
    if (result.map_loaded) {
      const marker = page.locator('gmp-advanced-marker').filter({ has: page.locator('.spatial-marker.report') });
      await expect(marker).toHaveCount(1);
      result.map_marker = await marker.evaluate(element => ({ title: element.title, latitude: element.position.lat, longitude: element.position.lng }));
      if (result.map_marker.latitude !== 28.52 || result.map_marker.longitude !== 77.08 || !result.map_marker.title.includes('SIMULATED HANDOFF REPORT')) throw new Error('Map location mismatch');
    }
    // Allow newly centered map tiles to paint before capturing the visual artifact.
    await page.waitForTimeout(1500);
    await page.locator('.officer-workspace').screenshot({ path: `${directory}/phase3b-desktop.png` });
    await page.setViewportSize({ width: 390, height: 844 });
    result.mobile_no_overflow = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
    await page.locator('.officer-workspace').screenshot({ path: `${directory}/phase3b-mobile.png` });
    if (!result.mobile_no_overflow) throw new Error('Mobile overflow');
    result.pass = true;
  } catch (error) { result.pass = false; result.failed_stage = stage; result.error_type = error.name; }
  fs.writeFileSync(`${directory}/phase3b-manual.json`, JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
  process.exitCode = result.pass ? 0 : 1;
})();
