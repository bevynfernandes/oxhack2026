# API client

`schema.d.ts` is generated from the committed C3 OpenAPI export. `client.ts` uses
openapi-fetch and a bounded TanStack Query retry policy. Browser requests stay on
the application's origin; there are no vendor calls or synthetic fallbacks.
