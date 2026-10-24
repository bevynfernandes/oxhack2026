import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

const root = process.env.SIGNALSHIFT_COMPANY_ROOT;
const publications = process.env.SIGNALSHIFT_COMPANY_PUBLICATIONS;
if (!root || !publications) {
  throw new Error(
    "Real company tests require an explicit restored root and publication selection",
  );
}
const servers = Array.isArray(base.webServer) ? base.webServer : [];
const apiPort = Number(process.env.SIGNALSHIFT_TEST_API_PORT ?? 8000);

export default defineConfig({
  ...base,
  testDir: "./tests/real-company",
  webServer: [
    {
      ...servers[0],
      command: `../.venv/bin/uvicorn --app-dir .. oxhack2026.api.company_runtime:create_company_app --factory --host 127.0.0.1 --port ${apiPort}`,
      env: {
        SIGNALSHIFT_COMPANY_ROOT: root,
        SIGNALSHIFT_COMPANY_PUBLICATIONS: publications,
      },
    },
    servers[1],
  ],
});
