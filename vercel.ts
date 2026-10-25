const configuredOrigin = process.env.SIGNALSHIFT_API_ORIGIN;
if (!configuredOrigin) {
  throw new Error(
    "Set SIGNALSHIFT_API_ORIGIN to the deployed HTTPS research API before deploying.",
  );
}
const origin = new URL(configuredOrigin);
if (
  origin.protocol !== "https:" ||
  origin.username ||
  origin.password ||
  origin.search ||
  origin.hash ||
  origin.pathname !== "/" ||
  ["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname)
) {
  throw new Error(
    "SIGNALSHIFT_API_ORIGIN must be a public HTTPS origin without credentials or a path.",
  );
}

export const config = {
  framework: "vite",
  installCommand: "npm ci --prefix frontend",
  buildCommand: "npm run build --prefix frontend",
  outputDirectory: "frontend/dist",
  rewrites: [
    { source: "/api/:path*", destination: `${origin.origin}/api/:path*` },
    { source: "/(.*)", destination: "/index.html" },
  ],
  headers: [
    {
      source: "/api/:path*",
      headers: [{ key: "Cache-Control", value: "no-store" }],
    },
  ],
};
