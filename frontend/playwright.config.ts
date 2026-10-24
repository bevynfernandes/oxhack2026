import { defineConfig, devices } from "@playwright/test";

const runId = process.env.SIGNALSHIFT_TEST_RUN ?? `browser-${Date.now()}`;
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
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "../.venv/bin/uvicorn --app-dir ../tests/fixtures/api server:create_app --factory --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/v1/health/ready",
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4173 --strictPort",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: false,
    },
  ],
});
