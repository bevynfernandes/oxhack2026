import { gzipSync } from "node:zlib";

export const maxDuration = 120;

// Server-only bridge: no provider or gateway credentials enter the browser bundle.
export default {
  async fetch(request) {
    const incoming = new URL(request.url);
    const path = incoming.searchParams.get("__path");
    incoming.searchParams.delete("__path");
    if (
      !path ||
      !/^v[12]\/[a-zA-Z0-9_/-]+$/.test(path) ||
      path.includes("..")
    ) {
      return Response.json({ detail: "Unknown API route." }, { status: 404 });
    }
    const origin = process.env.SIGNALSHIFT_API_ORIGIN;
    const key = process.env.PHRONESIS_GATEWAY_KEY;
    if (!origin || !key) {
      return Response.json(
        { detail: "Research service is not configured." },
        { status: 503 },
      );
    }
    if (!["GET", "POST"].includes(request.method)) {
      return Response.json({ detail: "Method not allowed." }, { status: 405 });
    }
    const body = request.method === "POST" ? await request.text() : undefined;
    if (body && Buffer.byteLength(body) > 65536) {
      return Response.json({ detail: "Request too large." }, { status: 413 });
    }
    try {
      const upstream = await fetch(`${origin}/api/${path}${incoming.search}`, {
        method: request.method,
        headers: {
          "content-type": "application/json",
          "x-phronesis-gateway-key": key,
        },
        body,
        redirect: "error",
        signal: AbortSignal.timeout(90000),
      });
      const headers = {
        "content-type":
          upstream.headers.get("content-type") || "application/json",
        "cache-control": "no-store",
      };
      if (upstream.headers.has("retry-after"))
        headers["retry-after"] = upstream.headers.get("retry-after");
      const bytes = Buffer.from(await upstream.arrayBuffer());
      const compress =
        bytes.length > 1024 &&
        /\bgzip\b/.test(request.headers.get("accept-encoding") || "");
      const payload = compress ? gzipSync(bytes) : bytes;
      headers["content-length"] = String(payload.length);
      headers["vary"] = "Accept-Encoding";
      if (compress) headers["content-encoding"] = "gzip";
      return new Response(payload, { status: upstream.status, headers });
    } catch {
      return Response.json(
        {
          detail:
            "Research service is temporarily offline. Please try again shortly.",
        },
        { status: 503 },
      );
    }
  },
};
