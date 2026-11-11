/** Every synthetic browser context refuses nonlocal requests, including map SDKs. */
import type { BrowserContext } from "@playwright/test";
export async function localNetwork(context: BrowserContext) {
  await context.route("**/*", (route) => {
    const hostname=new URL(route.request().url()).hostname;
    return ["127.0.0.1","localhost","resident-fixture.invalid"].includes(hostname)
      ? route.continue() : route.abort("blockedbyclient");
  });
}
