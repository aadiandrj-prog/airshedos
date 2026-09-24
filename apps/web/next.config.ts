import type { NextConfig } from "next";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// Explicit public allowlist: backend credentials never enter Next's environment.
const rootEnv = resolve(process.cwd(), "../../.env");
const lines = existsSync(rootEnv) ? readFileSync(rootEnv, "utf8").split(/\r?\n/) : [];
const publicEnv: Record<string, string> = {};
for (const name of ["NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY", "NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID"]) {
  const line = lines.find((entry) => entry.startsWith(`${name}=`));
  publicEnv[name] = process.env[name] ?? line?.slice(name.length + 1).trim().replace(/^['"]|['"]$/g, "") ?? "";
}
const config: NextConfig = {
  // Vercel supplies its own adapter; Docker still needs a standalone server.
  output: process.env.VERCEL === "1" ? undefined : "standalone",
  agentRules: false,
  env: publicEnv,
};
export default config;
