import { createServer } from "node:http";
import { timingSafeEqual } from "node:crypto";
import { gzipSync } from "node:zlib";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const contract = JSON.parse(
  readFileSync(
    new URL("../../contracts/api/openapi.json", import.meta.url),
    "utf8",
  ),
);
const routes = Object.entries(contract.paths).map(([path, methods]) => ({
  pattern: new RegExp(`^${path.replace(/\{[^}]+\}/g, "[a-zA-Z0-9_-]+")}$`),
  methods: Object.keys(methods).map((method) => method.toUpperCase()),
}));

export function createGateway({
  key,
  upstream = "http://127.0.0.1:8000",
  writeLimit = 30,
  requestLimit = 2400,
}) {
  if (!key || key.length < 32)
    throw new Error("A strong gateway key is required.");
  let writes = 0;
  let requests = 0;
  let resetAt = Date.now() + 3600000;
  return createServer(async (req, res) => {
    res.setHeader("cache-control", "no-store");
    const fail = (status, detail) => {
      res.writeHead(status, { "content-type": "application/json" });
      res.end(JSON.stringify({ detail }));
    };
    const supplied = Buffer.from(req.headers["x-phronesis-gateway-key"] || "");
    const expected = Buffer.from(key);
    if (
      supplied.length !== expected.length ||
      !timingSafeEqual(supplied, expected)
    )
      return fail(401, "Unauthorized.");
    const url = new URL(req.url, "http://gateway.local");
    if (
      !["GET", "POST"].includes(req.method) ||
      !routes.some(
        (route) =>
          route.pattern.test(url.pathname) &&
          route.methods.includes(req.method),
      )
    )
      return fail(404, "Unknown API route.");
    if (Date.now() >= resetAt) {
      writes = 0;
      requests = 0;
      resetAt = Date.now() + 3600000;
    }
    if (
      ++requests > requestLimit ||
      (req.method === "POST" && ++writes > writeLimit)
    ) {
      res.setHeader(
        "retry-after",
        String(Math.ceil((resetAt - Date.now()) / 1000)),
      );
      return fail(
        429,
        "This shared demo has reached its hourly research limit. Saved reports remain available when read capacity permits.",
      );
    }
    try {
      let size = 0;
      const chunks = [];
      for await (const chunk of req) {
        size += chunk.length;
        if (size > 65536) return fail(413, "Request too large.");
        chunks.push(chunk);
      }
      const response = await fetch(`${upstream}${url.pathname}${url.search}`, {
        method: req.method,
        headers: { "content-type": "application/json" },
        body: req.method === "POST" ? Buffer.concat(chunks) : undefined,
        redirect: "error",
        signal: AbortSignal.timeout(85000),
      });
      const bytes = Buffer.from(await response.arrayBuffer());
      const compress =
        bytes.length > 1024 &&
        /\bgzip\b/.test(req.headers["accept-encoding"] || "");
      const payload = compress ? gzipSync(bytes) : bytes;
      res.writeHead(response.status, {
        "content-type":
          response.headers.get("content-type") || "application/json",
        "content-length": payload.length,
        ...(compress ? { "content-encoding": "gzip" } : {}),
      });
      res.end(payload);
    } catch {
      if (!res.headersSent)
        fail(503, "The laptop research service is temporarily unavailable.");
      else res.destroy();
    }
  });
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  createGateway({ key: process.env.PHRONESIS_GATEWAY_KEY }).listen(
    8010,
    "127.0.0.1",
    () => console.log("Demo gateway listening on localhost:8010"),
  );
}
