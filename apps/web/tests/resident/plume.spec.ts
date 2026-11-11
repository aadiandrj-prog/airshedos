import { test, expect } from "@playwright/test";
import axe from "axe-core";
import fixture from "../fixtures/explore-synthetic.json";
import { localNetwork } from "./local-network";
import { installMapsFixture } from "./maps-fixture";
import { mkdir } from "node:fs/promises";
const sample=()=>({...structuredClone(fixture),expires_at:new Date(Date.now()+180000).toISOString()});
test.beforeEach(async({context})=>localNetwork(context));

test("Google map layers and plume controls reuse one map and make no additional source requests",async({page})=>{
  await installMapsFixture(page);let calls=0;
  await page.route('**/api/explore/gurugram',r=>{calls++;return r.fulfill({json:sample()});});
  await page.goto('/explore');
  expect(await page.evaluate(()=>window.__mapsFixture.maps)).toBe(0);
  await page.getByRole('button',{name:'View current conditions'}).click();
  await expect(page.getByTestId('synthetic-google-map')).toBeVisible();
  await expect(page.getByRole('status').filter({hasText:'Google Map ready'})).toBeVisible();
  expect(await page.evaluate(()=>window.__mapsFixture.pointKinds.filter(k=>k==='fire').length)).toBe(2);
  await page.getByRole('button',{name:'Recenter map'}).click();
  expect(await page.evaluate(()=>window.__mapsFixture.pans)).toBe(1);
  await page.getByLabel('NASA detections',{exact:true}).uncheck();
  expect(await page.evaluate(()=>window.__mapsFixture.pointKinds.filter(k=>k==='fire').length)).toBe(0);
  await page.getByLabel('Show illustrative Gaussian plume').check();
  await expect(page.getByText('ILLUSTRATIVE SCENARIO · NOT OBSERVED POLLUTION',{exact:true})).toBeVisible();
  await expect(page.getByRole('img',{name:/Hypothetical Gaussian crosswind profile/})).toBeVisible();
  expect(await page.evaluate(()=>window.__mapsFixture.activeOverlays)).toBe(1);
  await page.getByLabel('Assumed release rate (g/s)',{exact:true}).fill('2');
  await page.getByLabel('Wind comes from (degrees)',{exact:true}).fill('90');
  await expect.poll(()=>page.evaluate(()=>window.__mapsFixture.overlays)).toBeGreaterThan(1);
  expect(await page.evaluate(()=>window.__mapsFixture.maps)).toBe(1);
  expect(await page.evaluate(()=>window.__mapsFixture.activeOverlays)).toBe(1);
  await page.getByRole('button',{name:'Copy retrieved surface wind'}).click();
  await expect(page.getByText(/Google Weather surface wind/)).toBeVisible();
  await page.getByLabel('Constant wind speed (m/s)',{exact:true}).fill('0');
  await expect(page.getByRole('status').filter({hasText:'Calm or low wind'})).toBeVisible();
  expect(await page.evaluate(()=>window.__mapsFixture.activeOverlays)).toBe(0);
  await page.getByRole('button',{name:'Reset scenario'}).click();
  await expect(page.getByRole('img',{name:/Hypothetical Gaussian crosswind profile/})).toBeVisible();
  await page.addScriptTag({content:axe.source});
  expect((await page.evaluate(async()=>await(window as unknown as {axe:{run:()=>Promise<{violations:unknown[]}>}}).axe.run())).violations).toEqual([]);
  expect(calls).toBe(1);
  if(process.env.SEVA_CAPTURE_PLUME==='1'){
    await mkdir('../../docs/seva/screenshots/plume',{recursive:true});
    await page.locator('.plume-workbench').evaluate(el=>el.insertAdjacentHTML('afterbegin','<p>SYNTHETIC TEST DATA · FAKE MAP SDK · ILLUSTRATIVE SCENARIO</p>'));
    await page.locator('.plume-workbench').screenshot({path:'../../docs/seva/screenshots/plume/mobile.png'});
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('.plume-workbench').screenshot({path:'../../docs/seva/screenshots/plume/desktop.png'});
  }
  await page.setViewportSize({width:320,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});

test("map authentication failure is honest and expiry removes map/scenario without a refresh",async({page})=>{
  await installMapsFixture(page);let calls=0;
  await page.route('**/api/explore/gurugram',r=>{calls++;const data=sample();data.expires_at=new Date(Date.now()+5000).toISOString();return r.fulfill({json:data});});
  await page.goto('/explore');await page.getByRole('button',{name:'View current conditions'}).click();
  await expect(page.getByTestId('synthetic-google-map')).toBeVisible();
  await page.getByLabel('Show illustrative Gaussian plume').check();
  await page.evaluate(()=>window.dispatchEvent(new Event('airshedos-map-failure')));
  await expect(page.getByRole('status').filter({hasText:'Google Map is unavailable'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Gurugram',exact:true})).toBeVisible();
  await expect(page.getByRole('alert').filter({hasText:'expired'})).toBeVisible();
  await expect(page.getByRole('region',{name:'Live Google Map and Gaussian plume scenario'})).toHaveCount(0);
  expect(await page.evaluate(()=>window.__mapsFixture.activeOverlays)).toBe(0);
  expect(calls).toBe(1);
});
