import { defineConfig, devices } from "@playwright/test";

const runId = process.env.SIGNALSHIFT_TEST_RUN ?? `browser-${Date.now()}`;
const apiPort = Number(process.env.SIGNALSHIFT_TEST_API_PORT ?? 8000);
const webPort = Number(process.env.SIGNALSHIFT_TEST_WEB_PORT ?? 4173);
if (
  ![apiPort, webPort].every(
    (port) => Number.isInteger(port) && port > 0 && port <= 65535,
  ) ||
  apiPort === webPort
) {
  throw new Error("Browser tests require two distinct valid TCP ports");
}
const apiOrigin = `http://127.0.0.1:${apiPort}`;
const webOrigin = `http://127.0.0.1:${webPort}`;
export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: `../tests/outputs/${runId}/results`,
  reporter: [
    ["list"],
    [
      "html",
      { outputFolder: `../tests/outputs/${runId}/report`, open: "never" },
    ],
  ],
  use: {
    baseURL: webOrigin,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `../.venv/bin/uvicorn --app-dir ../tests/fixtures/api server:create_app --factory --host 127.0.0.1 --port ${apiPort}`,
      url: `${apiOrigin}/api/v1/health/ready`,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${webPort} --strictPort`,
      env: { SIGNALSHIFT_API_ORIGIN: apiOrigin },
      url: webOrigin,
      reuseExistingServer: false,
    },
  ],
});
