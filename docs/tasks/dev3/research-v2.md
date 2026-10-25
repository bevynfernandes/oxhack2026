# Standalone public startup research v2

V2 adds explicitly confirmed domain identities and independent public collectors.
V1 routes, saved publications and immutable reports retain their existing meaning.
No frontend flows or model training are included in this backend change.

## Run locally

```sh
uv sync --locked --all-extras --group docs
uv run --no-sync playwright install --with-deps chromium
export SIGNALSHIFT_RESEARCH_ROOT="$PWD/tests/outputs/local-research"
export SIGNALSHIFT_RESEARCH_ENABLED=1
# Optional: render up to three sparse JavaScript pages per job.
export SIGNALSHIFT_RESEARCH_BROWSER=1
uv run --no-sync uvicorn oxhack2026.api.company_runtime:create_company_app --factory
```

Use exactly one ASGI worker process. Two research threads share one network gate
and the root's exclusive POSIX worker lease. Persist the entire writable research
root, including content-addressed objects and metadata. Stored reads require no
worker, browser, saved company publication, provider credential or external fetch.
Set `SIGNALSHIFT_RESEARCH_ENABLED=0` to disable new discovery and research writes.
`SIGNALSHIFT_RESEARCH_ROOT` defaults to `SIGNALSHIFT_COMPANY_ROOT` if configured.
Saved context additionally requires the existing explicit company root/publication
configuration; standalone domains do not need it.

## API sequence

1. `GET /api/v2/research-capabilities` reads local configuration without vendor probes.
2. `POST /api/v2/research-identities` with `{"domain":"qdrant.tech"}` returns 202.
   A bare domain or HTTPS URL is accepted. Credentials, query strings, IP identities
   and nonstandard ports are rejected. Optional exact `company_id` and
   `assessment_publication_id` must both be supplied and match the requested domain.
3. Poll `GET /api/v2/research-identities/{identity_id}` until ready or failed.
   Show the name, canonical domain, evidence, conflicts and limitations. A different
   redirect destination must be displayed for explicit user confirmation. An
   unavailable website may leave a ready domain-only preview with an unverified name.
   Neither a domain nor an official link proves legal entity or parent ownership.
4. `POST /api/v2/research-jobs` with `identity_id` and boolean `identity_confirmed:true`
   returns 202. Confirmation applies to the immutable identity preview, including
   its displayed destination and conflicts. Equivalent active canonical identities
   with the same saved context coalesce. A terminal identity can be refreshed by
   submitting again, creating a new job and report.
5. Poll `GET /api/v2/research-jobs/{job_id}` only while queued or running. Each source
   includes its display name, state, reasons, captures and extracted results.
6. Read `GET /api/v2/research-reports/{report_id}`. Reads verify report and raw capture
   integrity. Old report bytes and captures remain unchanged after refresh.

Queue saturation returns 429 and `Retry-After: 30`. Disabled writes return 503;
unready identities return 409; missing IDs return 404. Never automatically retry
POST requests after an ambiguous response. Explicit user refresh is a new write.

## Collection and interpretation

Company pages yield first-party statements and dated events. The crawler visits at
most twenty relevant pages, depth two, with sitemap and linked feed discovery.
Financial prose stays an attributed claim with its excerpt and extraction location;
it is not converted into fabricated numbers. All claims, including disagreements,
remain visible. Missing revenue, retention, cash/burn and competitor coverage are
explicit. Funding does not establish runway, logos do not establish customers and
an inaccessible website does not establish business failure.

GitHub repositories, npm packages and hiring boards require exact links from the
confirmed official website. Name similarity never attaches an account. GitHub
metadata and stable releases are execution/developer-interest signals. Public
Greenhouse, Lever and Ashby postings are advertised openings, not realized hiring
or headcount. Plain careers pages remain evidence without invented job totals.

npm observations use two adjacent thirty-day windows of the latest available daily
data, with the collection time separate from the measurement period. HN retains
matching dated records even when totals are non-exhaustive, with separate retrieved
and nullable complete-window counts. GDELT articles remain coverage candidates;
domain matching is explicit and bounded accessible article collection stops at six.

Registry collection requires a local reviewed mapping file selected through
`SIGNALSHIFT_RESEARCH_REGISTRY_MAPPINGS`. Each row contains `domain`, `jurisdiction`,
`evidence_url`, `reviewed:true`, and an exact `cik` or `company_number`. No fuzzy
registry search is performed. SEC additionally requires `SEC_USER_AGENT` containing
operator contact information. Companies House requires `COMPANIES_HOUSE_API_KEY`.
Store credential values only in `.env`; never commit them. Registry disclosures
retain original periods and units in captures; they do not establish private
startup financial coverage. Optional `GITHUB_TOKEN` changes the shared GitHub quota.
No paid services are enabled automatically.

## Limits and recovery

There are two active and eight queued discovery/research tasks, eight global network
operations and at least one second between host requests. GitHub uses a shared
rolling hourly budget of 60 unauthenticated or 5,000 authenticated requests and
honors HTTP backoff. Discovery has a 45-second budget. Each research job has a
five-minute deadline, 120 HTTP requests, 32 MiB of captured bodies and 4 MiB per
response. Provider page/account limits produce explicit partial reasons.

HTTP connects directly to a validated public IP with TLS hostname verification;
redirects revalidate destinations and cross-host redirects discard credentials.
Cookies and proxy environment settings are never used by collection. The local
browser has an empty context, blocked service workers and WebSockets, disabled
unproxied WebRTC, and a dead proxy for traffic outside interception. Every allowed
HTTP request is fulfilled through the same controlled fetcher. Authentication,
CAPTCHA, paywalls and access denials produce blocked-source reasons.

Collectors checkpoint independently. Recovery retains terminal collector states
and marks pending/running work interrupted. Useful results produce partial reports;
saved context alone never qualifies. No useful fresh results means failed. Reports
embed the shared five specialist groups and approved Growth, Survival and Financial
Health horizons, with numerical forecasts always null.

## Verification

```sh
uv run --no-sync pytest
uv run --no-sync pytest tests/integration/api/test_research_v2_persistence.py -m integration
SIGNALSHIFT_LIVE_RESEARCH_ACCEPTANCE=1 uv run --no-sync pytest \
  tests/integration/api/test_research_v2_persistence.py::test_real_startup_acceptance -m integration
make check docs-test
uv run --no-sync python -m oxhack2026.api.export_contract --check
npm --prefix frontend run build
```

The opt-in live check researches Qdrant, PostHog and Linear without saved context,
then refreshes Linear and checks that the first report is unchanged. Exact captures,
job metadata and `acceptance.json` remain under ignored `tests/outputs/research-live-*`.
External services are mocked in normal tests; browser acceptance uses a saved local
JavaScript fixture.

Provider semantics: [npm daily download counts](https://github.com/npm/registry/blob/main/docs/download-counts.md),
[GitHub limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api),
and [SEC APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

## Evidence mapping and retained-capture re-mapping

New reports include optional `mapping` metadata under the existing v2 contract.
Old reports omit it and remain readable without changing their stored bytes.
The mapper extracts capture-only normalized documents, preserving exact Unicode
quotes, character offsets, document hashes, DOM locations and raw capture IDs.
It retains tables and headings and excludes navigation and hidden content. Website
statements remain attributed claims; subject ambiguity, customer stories and
quotations cannot establish company financial measurements. Exact ISO currencies,
locale-aware decimals, explicit dates and qualifiers are retained as attributed
numeric context. Ambiguous amounts and missing measurement periods remain gaps.

The five dimensions contain separate claim, event and observation references.
Measured status requires fresh supported provider observations; reported status
means attributed claims/events only. Mapping coverage is separate from trained
experimental dimension models and does not create outcome probabilities. Existing
company model payloads remain attached. Unknown definitions, rejected model
proposals and bounded interpretation coverage have explicit reasons.

Install the `research` and `explanations` extras for interpretation. The default
`SIGNALSHIFT_RESEARCH_MAPPING_MODE=rules_gemini` enables the interpreter,
using `gemini-3.8-live-extended-thinking` through Google's Live API. Set
`SIGNALSHIFT_RESEARCH_MAPPING_MODE=rules` explicitly to make no model requests.
The adapter enables audio output and transcription, discards audio immediately,
and receives data through an asynchronous, local-only evidence submission function.
It waits for explicit `IDLE` rather than stopping on `turnComplete`.
Structured output is not supported by this Live model; every submitted proposal
is instead strictly validated locally against the same evidence schema.
An explicit `GEMINI_MODEL=gemma-4-31b-it` selects native structured text calls.
`GEMINI_MODEL` overrides the model explicitly; errors never select another model.
The private repository contains a shared backend default in
`oxhack2026/explanations/internal-gemini.env`, as requested by the repository owner.
A process `GEMINI_API_KEY` overrides it; an explicitly empty value disables it.
The key is excluded from public API DTOs, captured prompts, logs and frontend
configuration. Other provider credentials remain local environment configuration.

Each mapping run has a two-minute deadline, at most six bounded requests, a
conservative sixty-thousand input-token reservation and two simultaneous model
operations. Live interpretation consolidates up to 24 candidate sentences into
one size-bounded session so asynchronous background reasoning shares that budget.
Candidates are selected round-robin across captured pages, retaining each page's
priority order, so a long pricing page cannot consume the whole request.
Short request-local handles select exact retained document blocks; model output
never supplies quote text or capture locations. Additional candidates remain an
explicit coverage limitation. A connection loss after a received submission
preserves it with an interrupted-background reason, rather than discarding it.
Product prices classified as financial performance are rejected independently of
the model; they do not establish company revenue, ARR, funding or profitability.
`SIGNALSHIFT_GEMINI_RPM` and `SIGNALSHIFT_GEMINI_TPM` configure the
shared process quota (defaults ten requests and sixty thousand reserved tokens per
minute). These are application limits, not claims about Google's project quota.
The mapper caches exact prompt/model responses as hashed artifacts, independently
validates concepts, subjects and contiguous quotes and checkpoints each batch.
Unavailability or malformed responses preserve deterministic results as partial.
No browsing, external tool execution or external source instructions reach the
interpreter as trusted instructions.

`POST /api/v2/research-mapping-jobs` with `{"source_report_id":"..."}` explicitly
queues interpretation of retained captures. Poll
`GET /api/v2/research-mapping-jobs/{job_id}` while pending/running. Equivalent
active requests coalesce and share the research queue limits. Completion links a
new immutable report with `derived_from_report_id`; original collection times,
source cutoff and capture artifacts are preserved. It does not refresh sources.
`SIGNALSHIFT_RESEARCH_MAPPING_ENABLED=1` enables this worker independently of source
collection. Capabilities expose mapping mode, local credential/SDK configuration
and worker availability without contacting Google. Stored reads need neither
worker nor credentials. Restart recovery preserves completed cached batches.

Google documents the [Live model protocol](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live-extended-thinking),
[Gemma text API](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api)
and [project-specific quotas](https://ai.google.dev/gemini-api/docs/rate-limits).
A configured key/model is not proof of a successful provider generation; live
acceptance must record actual results separately from mocked regression tests.
