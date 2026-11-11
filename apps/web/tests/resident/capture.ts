import { expect } from "@playwright/test";
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import type { Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

/** Actual loopback synthetic product views; never real pilot records. */
export async function capture(page: Page, name: string) {
  const stage = process.env.SEVA_CAPTURE_STAGE === "before" ? "before" : "after";
  const directory = resolve("../../docs/seva/screenshots/phase7", stage);
  await mkdir(directory, { recursive: true });
  const original = page.viewportSize();
  for (const [size, width] of [["mobile", 390], ["desktop", 1440]] as const) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => window.scrollTo({ top:0, left:0, behavior:"instant" }));
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
    if (stage === "after") await accessible(page, `${name}-${size}`);
    await page.screenshot({ path: resolve(directory, `${name}-${size}.png`), fullPage: true,
      animations: "disabled", style: "nextjs-portal { display:none !important; }" });
  }
  if (original) await page.setViewportSize(original);
}

export async function accessible(page: Page, name: string) {
  const require = createRequire(resolve("package.json"));
  await page.addScriptTag({ path: require.resolve("axe-core/axe.min.js") });
  const result = await page.evaluate(async () => {
    const axe = (window as typeof window & { axe: typeof import("axe-core") }).axe;
    const result = await axe.run(".pilot-ui", { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] } });
    return { violations: result.violations.map((v) => ({ id:v.id, impact:v.impact, nodes:v.nodes.map((n) => n.target) })),
      incomplete: result.incomplete.map((v) => ({ id:v.id, nodes:v.nodes.length })), passed: result.passes.length };
  });
  const dir = resolve("../../docs/seva/evidence/phase7/accessibility"); await mkdir(dir,{ recursive:true });
  await writeFile(resolve(dir,`${name}.json`),JSON.stringify({ engine:"axe-core 4.13.0", condition:"local signed synthetic pilot", ...result },null,2)+"\n");
  expect(result.violations, `${name} rendered accessibility violations`).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),`${name} horizontal overflow`).toBe(true);
}
