# C2 numerical artifacts, version 1

Python sources: `oxhack2026/models/contracts.py` and
`oxhack2026/evaluation/contracts.py`. These Pydantic types are independent of
training, database, and network implementations. Existing `data` dependencies
provide Pydantic and orjson. Unknown fields and nonfinite numerical values fail
validation. Fields documented as nullable remain null, never implicit zero.

Regenerate committed schemas, then run the saved drift tests:

```bash
uv run --frozen --no-sync python contracts/datasets/models/export.py
uv run --frozen --no-sync pytest tests/unit/models/test_contracts.py
```

The source types enforce cross-field invariants beyond JSON Schema. Consumers
must validate with the Python types at artifact boundaries. Serialize with
`model_dump(mode="json")` and orjson; parse using `model_validate`. Datetimes are
UTC instants, intervals are half-open, and identifiers are opaque strings.
Tuples serialize as arrays. Frozen models prevent field reassignment; callers
must treat nested mappings as immutable and hash serialized published artifacts.

| Artifact | Contract | Separation |
| --- | --- | --- |
| Feature rows | `FeatureRow` | Permitted observations only, explicit feature nulls |
| Label rows | `LabelRow` | Missing actual and availability until complete |
| Feature bundle | `FeatureManifest` | Separate feature/label references |
| Model pair | `ModelReference` | Model and calibrator belong to one scope |
| Forecast bundle | `ForecastManifest` | No outcome artifact reference required |
| Pre-reveal rows | `ForecastResult` | No actual outcome or outcome maturity fields |
| Reveal rows | `MatureOutcome` | Separate mature label and outcome vintage |
| Reveal diagnostics | `OutcomeDiagnostics` | Separate per-tool growth and count/log errors |
| Evaluation | `EvaluationReport` | Counts, periods, metric definitions, limitations |
| Evidence | `EvidenceItem` | Measured observations and cautious interpretations |
| Numerical API | `RankedCandidate`, `ShortlistScore` | Shared ranking/scoring output types |

All artifact paths are relative POSIX paths resolved by Dev 1's storage layer;
digests are lowercase SHA-256. The model/forecast ecosystem and target must
agree. A prospective artifact cannot be first recorded after its decision.
The producer must additionally check observation collection, mappings, model
fit time, and calibration gates; a schema cannot prove those historical facts.

No daily forecast curve is defined. Percentage growth requires reference
downloads of at least 1,000. An unavailable prediction stays null. A validated
forecast band needs a calibration ID and ordered aggregate endpoints. Evidence
validation status is independent of forecast readiness.

`tests/fixtures/models/` contains ready, insufficient-history, low-reference,
missing-source, unvalidated-interval, baseline, immature/mature outcome, feature,
manifest, evidence, and inconclusive-evaluation examples. Every example uses
synthetic provenance. Placeholder paths/hashes are schema examples only and
must not be loaded as real data or used in product demonstrations.

C1 is not yet published at this checkpoint. Data types remain referenced by
dataset/mapping/revision IDs rather than duplicating Dev 1's contracts. Exact
Parquet/Arrow feature layouts will be frozen with the D2-02 builders after C1
review. Any breaking field, target, or meaning change increments the contract
version and regenerates schemas and labelled fixtures together.
