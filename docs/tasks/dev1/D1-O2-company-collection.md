# D1-O2: durable multi-family company evidence

The collectors combine the verified npm dataset with bounded public GitHub
release captures and explicitly reviewed company financing announcements.
`configs/data/company-vector-20261024-v1.json` pins the real two-company cohort,
measurement cutoff, code revision, page budget, selected announcement dates and
USD claims. It covers Qdrant and Weaviate, both vector infrastructure companies.
The configured selected funding events are not asserted to be their latest rounds.

`capture_get` persists exact request/response checkpoints and actual collection
times. Retries are bounded; 403/429 defer instead of bypassing source limits.
Responses are capped at 4 MiB, redirects are rejected, and an optional GITHUB_TOKEN
header is sent only to api.github.com. CLI tracebacks do not display locals.
A run ID pins configuration; changing settings requires another run/snapshot ID.

GitHub collection verifies the frozen numeric repository ID before reading
paginated releases. Only published stable SDK releases count. Truncated pagination
produces a missing count, never zero or a partial total presented as complete.
Deleted/edited upstream releases remain a reconstruction limitation. npm sums
require every daily row in each 30-day window; SDK activity is not customer growth.
Reviewed announcement anchors must still appear in the captured page; failure
requires source review. No LLM assigns amounts, dates, labels or probabilities.

## Commands

```sh
python -m oxhack2026 data company-build \
  configs/data/company-vector-20261024-v1.json \
  /path/to/published/npm-v2 artifacts/company-vector-20261024-v1
python -m oxhack2026 data company-publish \
  artifacts/company-vector-20261024-v1 company-vector-20261024-v1
python -m oxhack2026 data company-health \
  artifacts/company-vector-20261024-v1 company-vector-20261024-v1
```

To intentionally refresh, use new run/snapshot IDs and an explicit measurement
cutoff. The published store never refreshes on an API request. Successful exact
reruns reuse the validated candidate and source bytes without network requests.

## Real handoff

`company-vector-20261024-v1` contains two companies, fourteen selected metric rows,
ten evidence records and two dated financing announcements. For each company,
traction, execution and financing have observed evidence; all three commercial
metrics are explicitly missing. Effective family membership is unresolved, not
assumed. Weaviate's selected 2023 financing observation is marked stale at the
2026 snapshot cutoff. Current evidence is not a historical success/failure cohort.

The source ZIP includes raw bytes, manifests/index, frozen candidates and capture
checkpoints. It is distributed in the repository's draft release
`data-company-vector-20261024-v1` for authenticated collaborators:

```sh
gh release download data-company-vector-20261024-v1 \
  --repo bevynfernandes/oxhack2026 --dir artifacts/received-company
cd artifacts/received-company
shasum -a 256 -c company-vector-20261024-v1.sha256
unzip company-vector-20261024-v1.zip -d source
```

ZIP SHA-256: `da53705964814e44e1b4beacf01587123f7949ce43cec4abe50a8eb90b6c5abd`.
Manifest SHA-256: `9bafab8d1748ef63ff37ad6c80a07462368387861bd6acedf9ac8f96e7a43fcb`.
Size: 84,071 bytes. Use `LocalCompanyStore(root).snapshot(id)` for exact loading.

Validation: 450 unit tests and nine opt-in filesystem tests pass, with Ruff/mypy.
The real bundle was published/loaded and exactly replayed with HTTP disabled.
This is source evidence only; C2 assessment publication is a separate checkpoint.
