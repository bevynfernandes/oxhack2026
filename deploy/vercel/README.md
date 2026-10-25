# Vercel frontend deployment

- Deploy from the repository root; Node.js 24.x. The Vercel configuration installs the locked frontend dependencies, runs contract/type checks and builds `frontend/dist`.
- Set `SIGNALSHIFT_API_ORIGIN` to the HTTPS origin of the hosted research API, without `/api` or credentials. The configuration fails if this is missing; it does not publish a disconnected UI as a working product.
- `/api/*` is proxied to that API before the SPA fallback. Deep links such as `/compare` and `/research/v2/reports/...` serve the application normally.
- Keep the Python API on a persistent single-process service with its company/research volumes. Existing collection jobs are not migrated into ephemeral Vercel functions.
- Configure backend access controls and bounded admission before enabling public research writes. Provider credentials remain on the backend, never in `VITE_*` variables or frontend assets.
- Use `vercel login`, then `vercel --prod` from this directory's repository root. Configure the API origin for the selected Vercel environment and redeploy after changing it.
- Validate `/api/v1/health/ready`, saved dossiers, comparison, identity confirmation, job polling and deep-link reloads against the production URL before sharing it as fully operational.

References: [Vercel TypeScript configuration](https://vercel.com/docs/project-configuration/vercel-ts), [external API rewrites](https://vercel.com/docs/routing/rewrites).

## Temporary laptop demo

- The server-only `api/proxy.mjs` forwards API requests using `PHRONESIS_GATEWAY_KEY`; set it as a sensitive production variable alongside `SIGNALSHIFT_API_ORIGIN`. Neither is a `VITE_*` variable.
- Start `node --env-file=PATH_TO_PRIVATE_ENV deploy/vercel/gateway.mjs` with a random key of at least 32 characters. Keep the private environment file outside version control and mode 0600. The gateway listens only on localhost:8010 and forwards to the existing API on localhost:8000.
- Tunnel port 8010, never the raw API. For example, `ssh -T -R 80:127.0.0.1:8010 nokey@localhost.run`. Set the resulting HTTPS origin in Vercel and redeploy if it changes.
- The gateway accepts only GET/POST operations present in the OpenAPI contract, caps request bodies at 64 KiB and allows at most 30 POSTs and 2,400 total requests per hour across this shared demo. The API's existing worker admission limits still apply. A rejected request returns 429 with Retry-After.
- Large reports use gzip and an explicit content length across the tunnel, avoiding stalled chunked transfers while preserving every evidence field.
- Public visitors can view retained research and initiate bounded research; this is a shared demonstration, not a private multi-user workspace. Provider keys remain solely in the existing API process.
- The laptop must remain awake, connected, with the API, gateway and SSH tunnel running. `caffeinate -i -w GATEWAY_PID` prevents idle sleep while the gateway runs; it does not keep a closed laptop online. Free tunnels may expire independently. In this environment, anonymous localhost.run addresses rotated roughly every 10 minutes and large responses were speed-limited; that setup is not suitable for an unattended demo. Use an allowed network with a more stable tunnel or a persistent API host.
- Stop the tunnel and gateway to end the live demo. The Vercel frontend stays online but research requests then return an unavailable state. For permanent hosting, replace the tunnel with a persistent authenticated backend; do not move the file-backed worker into a serverless function.
- Local process IDs and logs for this launch are under ignored `tests/outputs/vercel-runtime/`. The gateway key is stored only in its private `.env` and Vercel's sensitive environment variables. No logs contain the key.

Validation: `node --test deploy/vercel/*.test.mjs`; frontend unit tests, build and browser regression suite; public desktop/mobile journeys and unauthorized tunnel access.
