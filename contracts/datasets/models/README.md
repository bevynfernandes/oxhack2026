# C2 numerical artifacts

Model/feature manifests use `models-v2`; evaluation reports use `evaluation-v2`.
Version 2 adopts C1's canonical `storage.contracts.ArtifactReference`: required
relative path, SHA-256, byte size, and media type. The model module re-exports
that exact class; there is no second artifact validator. Version-1 manifests
are rejected explicitly and must be regenerated from verified immutable bundles.
No real version-1 model artifacts were published.

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

All artifact paths are canonical relative POSIX paths resolved by Dev 1's storage;
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

C1 is merged. Observation identities remain dataset/mapping/revision references,
while artifact references use C1 directly. Exact Parquet/Arrow feature layouts
will be frozen with the D2-02 builders. Breaking field, target, or meaning changes
increment the version and regenerate schemas and labelled fixtures together.
