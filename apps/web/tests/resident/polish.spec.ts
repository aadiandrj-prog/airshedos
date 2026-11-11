import { test, expect } from "@playwright/test";
import { writeFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";
import { capture, accessible } from "./capture";
import { localNetwork } from "./local-network";

test.beforeEach(async ({context}) => localNetwork(context));
async function login(page: import("@playwright/test").Page) {
  await page.goto("/sign-in?returnTo=%2Fresident%2Freports");
  await page.getByRole("link",{name:"Continue to secure sign-in"}).click();
  await page.getByLabel("Synthetic resident").selectOption("resident-b");
  await page.getByRole("button",{name:"Continue synthetic sign-in"}).click();
  await expect(page.getByRole("heading",{name:"My reports",exact:true})).toBeVisible();
}

test("public navigation, keyboard focus, token contrast, reduced motion and 320px reflow",async ({page}) => {
  test.skip(process.env.SEVA_CAPTURE_STAGE === "before", "New design-specific verification follows the before capture.");
  await page.emulateMedia({reducedMotion:"reduce"});
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link",{name:"Skip to content"})).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await expect(page.locator('a[href="#how-it-works"]')).toHaveCount(1);
  await expect(page.locator('a[href="#"]')).toHaveCount(0);
  expect(await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior)).toBe("auto");
  const pairs = await page.locator(".pilot-ui").evaluate((el) => {
    const css = getComputedStyle(el);
    const lum = (hex: string) => {
      const values=hex.trim().replace("#","").match(/../g)!.map((s) => parseInt(s,16)/255).map((c) => c <= .04045 ? c/12.92 : ((c+.055)/1.055)**2.4);
      return values[0]*.2126+values[1]*.7152+values[2]*.0722;
    };
    const pairs=[["body/white",css.getPropertyValue("--ink"),"#ffffff"],["secondary/canvas",css.getPropertyValue("--muted"),css.getPropertyValue("--paper")],["interactive/white",css.getPropertyValue("--accent"),"#ffffff"],["focus/canvas",css.getPropertyValue("--focus"),css.getPropertyValue("--paper")],["status chip","#0d5c75","#eff6f8"]];
    return pairs.map(([name,fg,bg]) => ({name,ratio:(Math.max(lum(fg),lum(bg))+.05)/(Math.min(lum(fg),lum(bg))+.05)}));
  });
  for (const pair of pairs) expect(pair.ratio,pair.name).toBeGreaterThanOrEqual(4.5);
  const directory=resolve("../../docs/seva/evidence/phase7"); await mkdir(directory,{recursive:true});
  await writeFile(resolve(directory,"contrast.json"),JSON.stringify({condition:"computed pilot tokens; separate rendered axe checks",pairs},null,2)+"\n");
  await page.setViewportSize({width:320,height:900});
  await accessible(page,"landing-320");
  await page.goto("/sign-in");
  const copy=await page.locator(".sign-in-description").boundingBox();
  const signIn=await page.getByRole("link",{name:"Continue to secure sign-in"}).boundingBox();
  expect(signIn!.y-(copy!.y+copy!.height),"sign-in action clears its explanation").toBeGreaterThanOrEqual(24);
  await login(page);
  await page.getByRole("navigation",{name:"Resident navigation"}).getByRole("link",{name:"Report a concern"}).click();
  const description=page.getByLabel("Description",{exact:true}); await expect(description).toBeEnabled();
  await description.focus(); await page.keyboard.press("Tab");
  await expect(page.getByLabel("What did you notice?")).toBeFocused();
  expect(await page.getByLabel("What did you notice?").evaluate((el) => getComputedStyle(el).outlineStyle)).toBe("solid");
  expect(await description.evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(16);
  const submit=page.getByRole("button",{name:"Submit report",exact:true}); expect((await submit.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await page.evaluate(() => { document.documentElement.style.fontSize="200%"; });
  await accessible(page,"resident-form-320-text-200");
  await page.evaluate(() => { document.documentElement.style.fontSize=""; });
});

test("empty history, unavailable report, expired session and loading remain clear and source-free",async ({page}) => {
  test.skip(process.env.SEVA_CAPTURE_STAGE === "before", "New state coverage follows the before capture.");
  let paid=0;
  page.on("request",(r) => { if (/\/context$|\/live-context$|\/enrichments$/.test(new URL(r.url()).pathname)) paid++; });
  await login(page);
  await expect(page.getByText("No reports on this page.",{exact:true})).toBeVisible();
  await capture(page,"resident-empty");
  await page.route("**/api/app/v2/resident/reports/00000000-0000-4000-8000-000000000001",async (route) => {
    await new Promise((done) => setTimeout(done,700)); await route.continue();
  });
  await page.goto("/resident/reports/00000000-0000-4000-8000-000000000001");
  await expect(page.getByRole("status").filter({hasText:"Loading your saved report"})).toBeVisible();
  await expect(page.getByRole("alert").filter({hasText:"outside your account"})).toBeVisible();
  await capture(page,"resident-unavailable");
  await page.route("**/api/app/v2/resident/reports?*",(route) => route.fulfill({status:401,contentType:"application/json",body:'{"detail":"Synthetic expired session"}'}));
  await page.goto("/resident/reports");
  await expect(page.getByRole("alert").filter({hasText:"sign-in"})).toBeVisible();
  await capture(page,"resident-session-expired");
  await page.setViewportSize({width:1200,height:800}); await page.setViewportSize({width:390,height:844});
  expect(paid).toBe(0);
  await page.getByRole("button",{name:"Sign out",exact:true}).click();
  await expect(page.getByRole("heading",{name:"A clearer way to report local pollution."})).toBeVisible();
  await page.goto("/resident/reports");
  await expect(page.getByRole("heading",{name:"Sign in to AirshedOS"})).toBeVisible();
});
