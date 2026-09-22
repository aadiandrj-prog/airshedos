import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { test, expect, type Page } from "./test";
import source from "./fixtures/handoff-case.test.json";
import fixture from "./fixtures/handoff.test.json";
import environment from "./fixtures/environment.test.json";
import satellite from "./fixtures/satellite.test.json";

const transitions: Record<string, string[]> = { DRAFT: ["READY"], READY: ["SENT_SIMULATED"], SENT_SIMULATED: ["RECEIVED"], RECEIVED: ["ACCEPTED", "REJECTED", "RETURNED_FOR_REVIEW"], RETURNED_FOR_REVIEW: ["READY"], ACCEPTED: [], REJECTED: [] };
const canonical = readFileSync("e2e/fixtures/handoff-canonical.test.json");
const panel = (page: Page) => page.getByRole("region", { name: "Handoff review panel" });

async function setup(page: Page) {
  let record = structuredClone(fixture);
  let created = false;
  const calls = { environmental: 0, create: 0, transition: 0 };
  await page.route("**/environment/context?**", r => { calls.environmental++; return r.fulfill({ json: environment }); });
  await page.route("**/environment/satellite?**", r => r.fulfill({ json: satellite }));
  await page.route("**/api/v1/review/cases", r => r.fulfill({ json: [{ id: source.id, event_type: source.snapshot.assessment.event_type, is_synthetic: true, jurisdiction: source.snapshot.jurisdiction, review: source.review, support_level: source.snapshot.assessment.support_level, submitted_at: source.snapshot.record.report.created_at }] }));
  await page.route(`**/api/v1/review/cases/${source.id}`, r => r.fulfill({ json: source }));
  await page.route(`**/api/v1/review/cases/${source.id}/handoffs`, r => {
    calls.create++;
    expect(r.request().postDataJSON()).toEqual({ origin_jurisdiction: "HARYANA", destination_jurisdiction: "DELHI", reason: "CROSS_BORDER_EVENT", expected_case_revision: 1 });
    created = true; return r.fulfill({ status: 201, json: record });
  });
  await page.route("**/api/v1/handoffs?*", r => {
    const destination = new URL(r.request().url()).searchParams.get("destination");
    const visible = created && (!destination || (record.sent_at && record.destination_jurisdiction === destination));
    const { payload: _payload, audit: _audit, audit_notice: _notice, ...summary } = record;
    void _payload; void _audit; void _notice;
    return r.fulfill({ json: visible ? [summary] : [] });
  });
  await page.route(`**/api/v1/handoffs/${fixture.id}`, r => r.fulfill({ json: record }));
  await page.route(`**/api/v1/handoffs/${fixture.id}/transition`, r => {
    calls.transition++;
    const data = r.request().postDataJSON();
    if (data.expected_revision !== record.revision || !transitions[record.state].includes(data.state)) return r.fulfill({ status: 409, json: { detail: "Invalid transition" } });
    record = { ...record, state: data.state, revision: record.revision + 1, allowed_transitions: transitions[data.state], sent_at: data.state === "SENT_SIMULATED" ? "2026-09-22T12:00:00Z" : record.sent_at } as typeof fixture;
    record.audit.push({ ...record.audit[0], action: data.state, state: data.state, sequence: record.audit.length, handoff_revision: record.revision, actor: ["READY", "SENT_SIMULATED"].includes(data.state) ? "source_control_room" : "destination_control_room" });
    return r.fulfill({ json: record });
  });
  await page.route(`**/api/v1/handoffs/${fixture.id}/export`, r => r.fulfill({ contentType: "application/json", body: canonical }));
  await page.goto("/");
  await page.getByRole("complementary", { name: "Case queue" }).getByRole("button").filter({ hasText: "SYNTHETIC INPUT" }).click();
  return calls;
}
async function generate(page: Page) {
  await page.getByRole("combobox", { name: "Source control room", exact: true }).selectOption("HARYANA");
  await page.getByRole("combobox", { name: "Destination jurisdiction", exact: true }).selectOption("DELHI");
  await page.getByRole("combobox", { name: "Handoff reason", exact: true }).selectOption("CROSS_BORDER_EVENT");
  await page.getByRole("button", { name: "Generate frozen packet" }).click();
  await expect(panel(page)).toContainText("DRAFT");
}
async function send(page: Page) {
  await generate(page);
  await panel(page).getByRole("button", { name: "Mark packet ready" }).click();
  await panel(page).getByRole("button", { name: "Send simulated handoff" }).click();
  await expect(panel(page)).toContainText("SENT SIMULATED");
}
async function incoming(page: Page) {
  await page.getByRole("button", { name: "Incoming handoffs", exact: true }).click();
  await page.getByRole("region", { name: "Incoming handoffs", exact: true }).getByRole("button").filter({ hasText: "SIMULATED · SYNTHETIC" }).click();
  await expect(panel(page)).toContainText("INTEGRITY VERIFIED");
}

test("explicit origin/destination/reason, frozen preview, simulated send and destination accept", async ({ page }) => {
  const calls = await setup(page); await send(page);
  const before = calls.environmental;
  await incoming(page);
  await expect(panel(page)).toContainText("HARYANA → DELHI");
  await expect(page.locator('[data-mock-marker]')).toHaveAttribute("aria-label", /SIMULATED HANDOFF REPORT/);
  await panel(page).getByRole("button", { name: "Receive in demo inbox" }).click();
  await panel(page).getByRole("button", { name: "Accept handoff" }).click();
  await expect(panel(page)).toContainText("ACCEPTED");
  await expect(panel(page)).toContainText("UNDER REVIEW");
  expect(calls.environmental).toBe(before);
  expect(calls.create).toBe(1); expect(calls.transition).toBe(4);
  await panel(page).getByText("Ephemeral prototype audit trail (5)", { exact: true }).click();
  await expect(panel(page)).toContainText("source_control_room");
  await expect(panel(page)).toContainText("destination_control_room");
  await page.locator('.officer-workspace').screenshot({ path: "test-results/phase3b-desktop.png" });
});

for (const [action, state] of [["Reject handoff", "REJECTED"], ["Return for review", "RETURNED FOR REVIEW"]]) {
  test(`destination ${state.toLowerCase()} preserves frozen assessment`, async ({ page }) => {
    await setup(page); await send(page); await incoming(page);
    await panel(page).getByRole("button", { name: "Receive in demo inbox" }).click();
    await panel(page).getByRole("button", { name: action }).click();
    await expect(panel(page)).toContainText(state);
    await expect(panel(page)).toContainText(`${source.snapshot.assessment.support_level} support`);
    await expect(panel(page)).toContainText("UNDER REVIEW");
    await expect(panel(page)).toContainText("Google AQ forecast");
  });
}

test("export downloads exactly the hash-verified canonical packet", async ({ page }) => {
  await setup(page); await generate(page);
  await panel(page).getByText("Frozen evidence & provenance", { exact: true }).click();
  await panel(page).getByText("PollutionEvent JSON preview", { exact: true }).click();
  await expect(panel(page).locator('pre')).toContainText('"schema_version": "pollution_event_v1"');
  const downloaded = page.waitForEvent("download");
  await panel(page).getByRole("button", { name: "Export PollutionEvent JSON" }).click();
  const download = await downloaded;
  expect(download.suggestedFilename()).toBe(`pollution-event-${fixture.event_id}-v1.json`);
  const data = readFileSync((await download.path())!);
  expect(data.equals(canonical)).toBe(true);
  expect(createHash("sha256").update(data).digest("hex")).toBe(fixture.payload_hash);
  expect(JSON.parse(data.toString()).evidence.gemini).toEqual(source.snapshot.record.analysis);
  expect(data.toString()).not.toContain("PRIVATE_CITIZEN_TEXT");
});

test("conflicting transition leaves packet/state unchanged and shows recovery", async ({ page }) => {
  await setup(page); await generate(page);
  await expect(panel(page).getByRole('button', { name: 'Accept handoff' })).toHaveCount(0);
  await page.route(`**/api/v1/handoffs/${fixture.id}/transition`, r => r.fulfill({ status: 409, json: { detail: "Invalid transition" } }));
  await panel(page).getByRole('button', { name: 'Mark packet ready' }).click();
  await expect(panel(page).getByRole('alert')).toContainText('conflict');
  await expect(panel(page)).toContainText('DRAFT');
});

test("integrity mismatch blocks acceptance and download", async ({ page }) => {
  await setup(page); await send(page); await incoming(page);
  await page.route(`**/api/v1/handoffs/${fixture.id}`, r => r.fulfill({ json: { ...fixture, state: 'RECEIVED', revision: 3, integrity: 'MISMATCH', allowed_transitions: ['ACCEPTED','REJECTED','RETURNED_FOR_REVIEW'] } }));
  await panel(page).getByRole('button', { name: 'Refresh handoff' }).click();
  await expect(panel(page)).toContainText('INTEGRITY MISMATCH');
  await expect(panel(page).getByRole('button', { name: 'Accept handoff' })).toBeDisabled();
  await expect(panel(page).getByRole('button', { name: 'Export PollutionEvent JSON' })).toBeDisabled();
});

test("tampered export bytes do not download", async ({ page }) => {
  await setup(page); await generate(page);
  await page.route(`**/api/v1/handoffs/${fixture.id}/export`, r => r.fulfill({ body: canonical.toString() + ' ' }));
  await panel(page).getByRole('button', { name: 'Export PollutionEvent JSON' }).click();
  await expect(panel(page).getByRole('alert')).toContainText('Integrity mismatch');
});

test("mobile keyboard handoff works when map is unavailable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => Object.assign(window, { mockMapsFailure: true }));
  await setup(page); await send(page);
  await expect(page.getByText('Map unavailable.', { exact: false })).toBeVisible();
  await incoming(page);
  const receive = panel(page).getByRole('button', { name: 'Receive in demo inbox' });
  await receive.focus(); await page.keyboard.press('Enter');
  const accept = panel(page).getByRole('button', { name: 'Accept handoff' });
  await accept.focus(); await page.keyboard.press('Enter');
  await expect(panel(page)).toContainText('ACCEPTED');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator('.officer-workspace').screenshot({ path: "test-results/phase3b-mobile.png" });
});

test("synthetic border-area intake is labeled and has explicit demo coordinates", async ({ page }) => {
  await setup(page);
  await page.getByRole('button', { name: 'Use synthetic cross-jurisdiction demo' }).click();
  await expect(page.locator('.citizen-panel')).toContainText('SYNTHETIC CROSS-JURISDICTION DEMO');
  await expect(page.getByLabel('Field latitude')).toHaveValue('28.52');
  await expect(page.getByLabel('Field longitude')).toHaveValue('77.08');
  await expect(page.locator('.citizen-panel')).toContainText('Exact boundary and location ownership are unverified');
});


test("late incoming response cannot override a newly selected source workflow", async ({ page }) => {
  await setup(page); await send(page);
  let release!: () => void;
  const waiting = new Promise<void>(resolve => { release = resolve; });
  let started!: () => void;
  const requestStarted = new Promise<void>(resolve => { started = resolve; });
  await page.route(`**/api/v1/handoffs/${fixture.id}`, async route => {
    started(); await waiting; await route.fulfill({ json: fixture });
  });
  await page.getByRole("button", { name: "Incoming handoffs", exact: true }).click();
  await page.getByRole("region", { name: "Incoming handoffs", exact: true }).getByRole("button").filter({ hasText: "SIMULATED · SYNTHETIC" }).click();
  await requestStarted;
  await page.getByRole("button", { name: "Source cases", exact: true }).click();
  await page.getByRole("button", { name: /Gurugram coordinate probe/ }).click();
  const response = page.waitForResponse(r => r.url().endsWith(`/handoffs/${fixture.id}`));
  release(); await response;
  await expect(page.locator('.officer-detail')).toContainText('COORDINATE PROBE');
  await expect(panel(page)).toHaveCount(0);
});
