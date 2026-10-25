# Vercel frontend deployment

- Deploy from the repository root; Node.js 24.x. The Vercel configuration installs the locked frontend dependencies, runs contract/type checks and builds `frontend/dist`.
- Set `SIGNALSHIFT_API_ORIGIN` to the HTTPS origin of the hosted research API, without `/api` or credentials. The configuration fails if this is missing; it does not publish a disconnected UI as a working product.
- `/api/*` is proxied to that API before the SPA fallback. Deep links such as `/compare` and `/research/v2/reports/...` serve the application normally.
- Keep the Python API on a persistent single-process service with its company/research volumes. Existing collection jobs are not migrated into ephemeral Vercel functions.
- Configure backend access controls and bounded admission before enabling public research writes. Provider credentials remain on the backend, never in `VITE_*` variables or frontend assets.
- Use `vercel login`, then `vercel --prod` from this directory's repository root. Configure the API origin for the selected Vercel environment and redeploy after changing it.
- Validate `/api/v1/health/ready`, saved dossiers, comparison, identity confirmation, job polling and deep-link reloads against the production URL before sharing it as fully operational.

References: [Vercel TypeScript configuration](https://vercel.com/docs/project-configuration/vercel-ts), [external API rewrites](https://vercel.com/docs/routing/rewrites).
