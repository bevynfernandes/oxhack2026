import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

const servers = Array.isArray(base.webServer) ? base.webServer : [];
const apiPort = Number(process.env.SIGNALSHIFT_TEST_API_PORT ?? 8000);

/** Exercise packaged real examples without research workers or external sources. */
export default defineConfig({
  ...base,
  testDir: "./tests/preloaded",
  webServer: [
    {
      ...servers[0],
      command: `../.venv/bin/uvicorn --app-dir .. oxhack2026.api.company_runtime:create_company_app --factory --host 127.0.0.1 --port ${apiPort}`,
      env: {
        GEMINI_API_KEY: "",
        SIGNALSHIFT_COMPANY_ROOT: "",
        SIGNALSHIFT_COMPANY_PUBLICATIONS: "",
        SIGNALSHIFT_PRELOADED_COMPANIES: "1",
        SIGNALSHIFT_RESEARCH_ROOT: "",
        SIGNALSHIFT_RESEARCH_ENABLED: "0",
        SIGNALSHIFT_RESEARCH_MAPPING_ENABLED: "0",
      },
    },
    servers[1],
  ],
});
