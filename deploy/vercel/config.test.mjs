import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

const root = new URL("../../", import.meta.url);
const inspect =
  'import {config} from "./vercel.ts"; console.log(JSON.stringify(config))';

test("deploys the existing frontend build with API routing ahead of deep-link fallback", () => {
  const result = spawnSync(
    process.execPath,
    ["--input-type=module", "-e", inspect],
    {
      cwd: root,
      env: {
        ...process.env,
        SIGNALSHIFT_API_ORIGIN: "https://api.example.com",
      },
      encoding: "utf8",
    },
  );
  assert.equal(result.status, 0, result.stderr);
  const config = JSON.parse(result.stdout);
  assert.equal(config.outputDirectory, "frontend/dist");
  assert.deepEqual(config.rewrites, [
    { source: "/api/:path*", destination: "/api/proxy?__path=:path*" },
    { source: "/(.*)", destination: "/index.html" },
  ]);
});

test("refuses disconnected, local or credential-bearing API destinations", () => {
  for (const origin of [
    "",
    "http://localhost:8000",
    "https://localhost",
    "https://user:secret@example.com",
    "https://example.com/api",
  ]) {
    const result = spawnSync(
      process.execPath,
      ["--input-type=module", "-e", inspect],
      {
        cwd: root,
        env: { ...process.env, SIGNALSHIFT_API_ORIGIN: origin },
        encoding: "utf8",
      },
    );
    assert.notEqual(result.status, 0);
    assert.equal(result.stdout, "");
    assert.ok(!result.stderr.includes("user:secret"));
  }
});
