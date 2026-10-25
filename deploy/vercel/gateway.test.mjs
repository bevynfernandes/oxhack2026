import assert from "node:assert/strict";
import { test } from "node:test";
import { createServer } from "node:http";
import { once } from "node:events";
import { createGateway } from "./gateway.mjs";
import proxy from "../../api/proxy.mjs";

const key = "test-only-key-that-is-at-least-32-characters";
test("gateway authenticates, preserves API requests, denies arbitrary routes and bounds writes", async (t) => {
  const received = [];
  const upstream = createServer(async (req, res) => {
    let body = "";
    for await (const chunk of req) body += chunk;
    received.push({ url: req.url, body, headers: req.headers });
    res.writeHead(202, { "content-type": "application/json" });
    res.end(
      req.url.includes("research-reports")
        ? JSON.stringify({ evidence: "source excerpt ".repeat(1000) })
        : '{"ok":true}',
    );
  }).listen(0, "127.0.0.1");
  await once(upstream, "listening");
  const gateway = createGateway({
    key,
    upstream: `http://127.0.0.1:${upstream.address().port}`,
    writeLimit: 1,
  }).listen(0, "127.0.0.1");
  await once(gateway, "listening");
  t.after(() => {
    gateway.closeAllConnections();
    gateway.close();
    upstream.closeAllConnections();
    upstream.close();
  });
  const base = `http://127.0.0.1:${gateway.address().port}`;
  assert.equal((await fetch(`${base}/api/v1/health/ready`)).status, 401);
  const headers = { "x-phronesis-gateway-key": key };
  assert.equal((await fetch(`${base}/api/secrets`, { headers })).status, 404);
  const response = await fetch(`${base}/api/v2/research-identities?test=1`, {
    method: "POST",
    headers,
    body: '{"query":"qdrant.tech"}',
  });
  assert.equal(response.status, 202);
  assert.equal(received[0].url, "/api/v2/research-identities?test=1");
  assert.equal(received[0].body, '{"query":"qdrant.tech"}');
  assert.equal(received[0].headers["x-phronesis-gateway-key"], undefined);
  const large = await fetch(`${base}/api/v2/research-reports/example`, {
    headers,
  });
  assert.equal(large.headers.get("content-encoding"), "gzip");
  assert.equal((await large.json()).evidence, "source excerpt ".repeat(1000));
  const limited = await fetch(`${base}/api/v2/research-identities`, {
    method: "POST",
    headers,
    body: "{}",
  });
  assert.equal(limited.status, 429);
  assert.ok(limited.headers.get("retry-after"));
  assert.equal(
    (await fetch(`${base}/api/v1/health/ready`, { headers })).status,
    202,
  );
});
test("Vercel proxy preserves parameters and status without exposing credentials", async (t) => {
  process.env.SIGNALSHIFT_API_ORIGIN = "https://api.example.com";
  process.env.PHRONESIS_GATEWAY_KEY = key;
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "https://api.example.com/api/v2/company-search?q=qdrant");
    assert.equal(options.headers["x-phronesis-gateway-key"], key);
    assert.equal(options.headers["accept-encoding"], "gzip");
    assert.equal(options.headers.cookie, undefined);
    return Response.json({ companies: [] }, { status: 200 });
  });
  const result = await proxy.fetch(
    new Request(
      "https://demo.example/api/proxy?__path=v2/company-search&q=qdrant",
    ),
  );
  assert.equal(result.status, 200);
  assert.equal(result.headers.get("cache-control"), "no-store");
  assert.ok(!(await result.text()).includes(key));
  assert.equal(
    (
      await proxy.fetch(
        new Request("https://demo.example/api/proxy?__path=../secret"),
      )
    ).status,
    404,
  );
});
test("Vercel proxy returns a clear unavailable state when the laptop disconnects", async (t) => {
  t.mock.method(globalThis, "fetch", async () => {
    throw new Error("offline");
  });
  const result = await proxy.fetch(
    new Request("https://demo.example/api/proxy?__path=v1/health/ready"),
  );
  assert.equal(result.status, 503);
  assert.match(await result.text(), /temporarily offline/);
});

test("Vercel buffers and compresses large reports without losing evidence", async (t) => {
  const { gunzipSync } = await import("node:zlib");
  const evidence = "retained evidence ".repeat(1000);
  t.mock.method(globalThis, "fetch", async () => Response.json({ evidence }));
  const response = await proxy.fetch(
    new Request(
      "https://demo.example/api/proxy?__path=v2/research-reports/example",
      { headers: { "accept-encoding": "gzip" } },
    ),
  );
  assert.equal(response.headers.get("content-encoding"), "gzip");
  const bytes = Buffer.from(await response.arrayBuffer());
  assert.equal(Number(response.headers.get("content-length")), bytes.length);
  assert.equal(JSON.parse(gunzipSync(bytes).toString()).evidence, evidence);
});
