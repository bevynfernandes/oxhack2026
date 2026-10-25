# Standalone public startup research v2

V2 adds explicitly confirmed domain identities and independent public collectors.
V1 routes, saved publications and immutable reports retain their existing meaning.
The frontend supports domain confirmation, bounded collection, cited findings and
explicit continuation. This workflow does not train prediction models.

## Run locally

```sh
uv sync --locked --all-extras --group docs
uv run --no-sync playwright install --with-deps chromium
export SIGNALSHIFT_RESEARCH_ROOT="$PWD/tests/outputs/local-research"
export SIGNALSHIFT_RESEARCH_ENABLED=1
# Optional: render sparse JavaScript pages within the selected profile.
export SIGNALSHIFT_RESEARCH_BROWSER=1
export SIGNALSHIFT_RUNTIME_REVISION="$(git rev-parse --short HEAD)"
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
most the selected profile's company-page allowance, at depth three, with sitemap
and linked feed discovery. Official ordinary HTML paths are eligible regardless of
language; family ranking balances commercial, company, updates, docs and careers.
Linked docs, developers, careers, jobs, blog, newsroom and changelog subdomains
are included within the same confirmed domain and collection limits.
Login, account, search and asset paths are excluded.
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
domain matching is explicit and accessible article collection uses the profile limit.

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
profile-specific deadline, request budget and captured-byte budget shown below,
with 4 MiB per ordinary response (verified SEC company facts allow 16 MiB). Provider page/account limits produce explicit partial reasons.

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

Install the `research` and `explanations` extras for interpretation. New jobs
use `gemma-4-31b-it` through the native text API and
`SIGNALSHIFT_RESEARCH_MAPPING_MODE=rules_gemini`. Set `GEMINI_API_KEY` in the
worker environment; an explicitly empty value disables the existing credential
fallback. `GEMINI_MODEL` selects an explicit alternative. Credentials never enter
public DTOs, prompts, logs or frontend configuration. Use
`SIGNALSHIFT_RESEARCH_MAPPING_MODE=rules` to disable all model requests, including
Search discovery. No Gemini CLI installation or audio configuration is required.

Gemma uses MINIMAL thinking for bounded extraction and HIGH for cited synthesis.
Extraction batches contain at most six sentences. Compact classifications select
retained source sentences; the backend reconstructs exact
quotes and quantities. The API schema uses compatible objects, arrays, enums and
required fields; strict local validation enforces lengths, counts, subjects,
financial qualifiers, dates and citation support. A generated classification
never establishes independent truth. Pricing cannot establish company revenue,
ARR, funding, cash or profitability.

Extraction streams have an absolute 45-second request deadline; synthesis and
Search allow 90 seconds. These limits are bounded by the job's
remaining deadline, and a 128 KiB public-response limit. Partial JSON, truncated
streams and access refusals are rejected. Private thinking content is discarded.
Extraction and Search allow 2,048 output tokens; synthesis allows 8,192,
included in conservative quota
reservations. Synthesis receives up to 90 seconds and two available request slots
before additional extraction spends its budget. Transient failures receive one
bounded retry; configuration and authentication errors fail without retries.
Failed extraction batches do not prevent subsequent batches from running within
the remaining budget. Unprocessed candidates remain explicit gaps. Status codes
distinguish provider errors, overload, connection failures and request timeouts;
provider error messages are not exposed. Fast/Thorough/Deep limits include
both collection and interpretation; the mapper uses at most the profile's
interpretation allocation and remaining overall time.

Re-interpreting retained evidence uses the full selected job deadline because no
website collection is required. The synthesis time reserve is capped at 40% of
remaining mapping time so a Fast run still has time to extract evidence.
Structured counts and supported financial measurements retain their exact values
and units in synthesis context. Gap validation rejects missingness claims about
collected values or events, and rejects unrelated concepts added to a cited gap.

`SIGNALSHIFT_GEMINI_RPM` and `SIGNALSHIFT_GEMINI_TPM` set process-wide model quotas
(defaults ten requests and sixty thousand reserved tokens per minute). Native
model requests also share the eight network-operation slots, at most two model
operations and one request per second to the model host. Actual requests and
reported usage are recorded; missing usage is not presented as zero. Cache keys
include prompt, model, thinking level, response schema and parser/prompt policy.
Malformed and interrupted responses cannot become reusable successful results.

### Google Search discovery

New collection jobs include a separately checkpointed Google Search source.
`SIGNALSHIFT_RESEARCH_GOOGLE_SEARCH=0` disables it. Discovery makes one native
request with minimal thinking and the Search tool, separately from structured
extraction. Discovery shares model/profile budgets with interpretation. Provider
Search queries may exceed one query per generation; retained metadata records
what the provider actually reports.

Grounding metadata supplies candidate URLs, queries and provider attribution.
At most six candidates are fetched per run through the protected HTTPS fetcher,
within shared request, capture and deadline limits. Exact official hosts or
independent pages referencing the confirmed domain can match; unrelated pages
remain retained candidates and cannot support findings. Search prose and snippets
are never metric evidence. Original captured pages supply quotes and publication
dates. Provider metadata is retained as a hashed discovery artifact, separately
from source captures. Provider suggestions render in an isolated sandboxed frame.

Pending candidates survive continuation without repeating completed discovery or
page requests. Legacy eight-source jobs remain readable alongside new nine-source
jobs, and existing report bytes are never rewritten. Search failures preserve
successful sources and expose their actual reason. Search availability in
capabilities describes configuration, not a live provider health check.

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

Google documents the [Gemma text API](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api)
and [project-specific quotas](https://ai.google.dev/gemini-api/docs/rate-limits).
A configured key/model is not proof of a successful provider generation; live
acceptance must record actual results separately from mocked regression tests.

## Research profiles and explicit continuation

V2 job creation accepts `profile: fast | thorough | deep` (default `thorough`).
The worker snapshots the effective configuration on each job. Capabilities expose
all three profiles, process start time and an optional `SIGNALSHIFT_RUNTIME_REVISION`.
The limits are ceilings, not assertions that all public information was searched.

| Profile | Total seconds | Company pages | Article pages | Browser pages | Requests | Capture MiB | Model requests |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Fast | 300 | 20 | 6 | 3 | 120 | 32 | 6 |
| Thorough | 600 | 60 | 12 | 6 | 240 | 64 | 12 |
| Deep | 1200 | 120 | 24 | 12 | 480 | 128 | 24 |

`POST /api/v2/research-jobs/{job_id}/continue` accepts a profile and explicitly
queues remaining durable work from a terminal useful job. It never rewrites that
job or report. A job without a usable checkpoint requires Refresh instead.
`POST /api/v2/research-mapping-jobs` accepts `cache_policy: reuse | bypass`;
reuse is the default. Continuation can additionally name `source_report_id` to
resume a later re-mapped report belonging to that exact job. Reports from other
jobs or identities are rejected. Older stored values omit optional checkpoint and
configuration fields and retain their original bytes.

### Source collection coverage

The website frontier records visited and outstanding URLs, samples page families,
and follows linked public company subdomains. Linked GitHub organisations can
supply public repositories; package manifests require reciprocal npm repository
metadata. Explicit npm/pnpm/yarn/bun installation commands retain the quoted command
as discovery evidence; ownership requires the separate verification above.
Scoped Organization JSON-LD `sameAs` links retain
their extraction location; an unrelated Organization's accounts are excluded. Hiring follows embedded public boards and deduplicates posting IDs.
HN subdivides non-exhaustive time windows within its profile and stores unfinished
pagination for continuation. News distinguishes matched articles and unverified
candidates instead of marking every response partial. Public text PDFs are bounded
to forty pages; scanned/encrypted documents remain explicit unsupported sources.

Independent provider workers share atomic request/byte budgets and process-wide
quotas. Collector execution and coverage are separate in `SourceState.details`;
validation metadata is informational, while incomplete coverage remains visible.

### Gemini interpretation and cited analysis

Profiled jobs use stable per-document chunks, replaying successful cached chunks
before spending their remaining model budget on new work. This permits an explicit
continuation to advance beyond an earlier interpretation limit. Gemini reviews
important rule-mapped evidence as well as unclassified text, then submits cited
findings. Local validation rejects unsupported quotes, subjects, citations,
quantities and forecasts. Extraction reserves one provider request, input capacity
and 30% of remaining interpretation time (up to 120 seconds) for synthesis.
Each Live turn has at most 90 seconds. A submitted but unfinished turn is retained
with an explicit interruption reason.

`mapping.statistics` separates processed/deferred evidence, accepted/rejected
proposals, cached batches and actual provider requests. Unreported provider usage
is null. `mapping.analysis` distinguishes unavailable synthesis from completed
findings. Rule-only mode never presents deterministic output as Gemini analysis.
Live connections reuse bounded turns, rotate on schema/context changes, discard
audio and thoughts, and wait for explicit IDLE. Validated nonempty submissions
from interrupted turns can be replayed with their original interruption reasons.
Invalid or empty failed chunks do not become successful cache entries. Model
calls honour shared quotas and job deadlines.


### Frontend actions and retained evidence

The confirmation screen offers Fast, Thorough and Deep, defaulting to Thorough.
Source progress shows execution separately from scope/coverage and supplies a
human-readable issue and next action. Claims and unavailable observations do not
inflate the count of measurements. Gemini accounting reports actual provider
requests, cache hits, accepted/rejected proposals, deferred evidence and nullable
provider-reported token usage. Rule-only and historical reports cannot imply that
Gemini ran.

Installation commands and npm links are discovery candidates, including possible
third-party dependencies. Download observations require an exact registry package
name and either a reciprocal company homepage or the matching package manifest
in an officially linked repository. Name similarity does not establish ownership.
Continuation revalidates older npm observations lacking this association check;
their original report bytes and captures remain unchanged.

Completed reports expose findings with original quotations, subjects, attribution,
public source links and collection dates. Continue spends another explicit budget
on retained frontier/cursors and deferred interpretation; completed captures stay
available with their original dates. Refresh requires identity confirmation and
collects new sources. Re-map reads retained captures only, with an explicit cache
reuse/bypass choice. Every action creates a new immutable report, and failed reads
or writes never silently resubmit research.
Jobs that failed without producing a report offer identity confirmation for a new
attempt; only useful completed/partial jobs expose continuation.

The browser shares a twenty-second page deadline and twenty-request cap with its
controlled network requests, so callbacks cannot outlive the page budget. Failed rendering
retains successful static HTML and an explicit limitation. Source-level GitHub,
npm and hiring checkpoints preserve completed resource evidence for continuation.
The website phase uses at most 42% of total job time and GitHub discovery at most
10%; collection as a whole uses at most 70%, leaving interpretation time.
Website collection uses at most 60% of the shared HTTP and capture budgets,
preserving capacity for external providers.

After pulling implementation changes, restart the API worker. Check
`process_started_at`, `runtime_revision` and `mapping.mode` in capabilities before
expecting new behavior; fetching Git changes does not reload an existing process.
Only enable one worker process per research root. Credentials remain backend-only;
provider availability does not promise a successful live request.

### Real-source acceptance, 25 October 2026

The local acceptance runs used public network responses and actual Gemini calls,
without substituting fixtures. All four domains were researched as standalone
identities without saved publications. Raw captures, hashed model submissions,
source checkpoints and immutable reports remain under ignored `tests/outputs/`.

| Domain/action | Immutable report | Captures | Actual model requests |
| --- | --- | ---: | ---: |
| Qdrant | `7d8f4a0df76949bda53b997f3a9e86cb` | 131 | 6 |
| PostHog | `9c120885e09944dfa151f0a78f612683` | 75 | 4 |
| Linear | `3bac22e2a1c340578a3743639519d03d` | 87 | 4 |
| ElevenLabs initial | `dfa888321200475191bb5bf3ed3f21e0` | 243 | 5 |
| ElevenLabs Continue | `6be01d45eab9439c8918a8e6341e329a` | 300 | 2 |
| ElevenLabs Refresh | `47df5e44d62f40f58298402c73c927fd` | 65 | 3 |
| ElevenLabs uncached Re-map | `55353d7fc87c4f0fb72d4e56944d8078` | 243 | 3 |

The initial broad runs exposed interpretation deadline starvation. Subsequent
integration changes reserve synthesis capacity and external collection budgets.
The final ElevenLabs re-map produced seven cited statements, including explicit
gaps, and zero cached batches. Refresh and Continue retained useful fresh results
but their synthesis requests were unavailable. These are recorded limitations,
not successful generations. Continue replayed three cached batches while making
two actual provider requests. The original report SHA-256 remained
`da09c57d755decb328e6f0de3e57db2ead9dad848f838882b3b05bd79f3abb5f`.

`research-final-artifact-audit.json` verifies report/capture integrity, newer
refresh timestamps, unchanged retained captures, no collection during re-map,
standalone identity coverage and current validation of all published statements.
The underlying summaries are `research-complete-live-20261025/acceptance-summary.json`
and `research-complete-elevenlabs-20261025/workflow-acceptance-summary.json`.

Real restrictions remain visible: GitHub returned HTTP 403 on some requests,
GDELT returned HTTP 429, and bounded website/HN/hiring collection retained pending
work. An attempted reviewed Cloudflare SEC mapping received HTTP 403 before
verification; `research-sec-live-20261025/source-result.json` retains that denied
capture and publishes no registry claims. Companies House had no configured key;
profile, filing and identity-mismatch behavior is covered by mocked tests rather
than represented as live acceptance. These runs establish useful collection and
honest failure reporting, not unrestricted provider access or complete financial
coverage for private startups.
