import { defineConfig } from "@playwright/test";
import resident from "./playwright.resident.config";
export default defineConfig({ ...resident, testDir:"./tests/authority", timeout:120000, use:{ ...resident.use, actionTimeout:15000 } });
