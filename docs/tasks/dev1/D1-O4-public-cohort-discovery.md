# Public historical-cohort discovery

User confirmed public sources only. The pinned Winter 2020 batch from the
[yc-oss mirror](https://github.com/yc-oss/api) is now captured and normalized.
It includes every returned company, without a status or success filter:
229 records, comprising 134 currently Active, 61 Inactive and 34 Acquired.
Each retains its upstream numeric ID, primary YC profile URL and actual collection
time. Three unresolved source-review work items per company produce 687 pending
follow-ups. There are zero inferred labels and zero verified historical families.

This is a discovery ledger for a historical batch, **not a validated historical
training set**. The mirror only includes publicly launched companies whose YC
profiles remain returned. Current names, status and descriptions were not known
at batch entry. Batch membership is not a verified founding date. Missing public
pages and YC selection may bias the population. No current directory field is
silently backdated. Inactive does not establish a shutdown date; Acquired does
not establish transaction completion/date; Active does not establish growth or
cash-flow self-sufficiency. All three outcome labels therefore remain null.

## Exact retrieval and verification

- Source commit: `d7ecae893271b38e6f4d74ff550cd2488d9b7305`.
- Source URL: `https://raw.githubusercontent.com/yc-oss/api/d7ecae893271b38e6f4d74ff550cd2488d9b7305/batches/winter-2020.json`.
- First collected: `2026-10-24T15:43:52.448124Z`.
- Raw SHA-256: `513ee3fc200dad3f1c8077ba5bc2fd51002b09715266fadff33b4eff1e957825`.
- ZIP SHA-256: `2070c979737a8ea2bb9ca5ca5e11cab6dc2a43fce757d7b3bbf0ae97db257d05`.
- Collector revision: `9621f3d1b0713f6c7a9b2b561637055fa900449a`.
- Configuration: `configs/data/yc-winter2020-discovery-20261024-v1.json`.

Run `python -m oxhack2026 data cohort-discover SETTINGS.json ROOT` to capture the
pinned batch with actual availability. Existing-run replay is network-free and
byte-identical; changed configuration requires a new run ID. Read an exact ledger
with `ingest.company_cohort.load_cohort(root, cohort_version)`. Reads verify the raw
hash and complete normalized company set. The transfer ZIP also retains capture
checkpoints. It is not a company-source recovery archive or an API publication.
Raw redistributability/licensing is not inferred from public reachability; the
team handoff stays in a draft release.

## Follow-up handoff

Start with each retained primary profile, including the inactive and acquired
rows. Resolve legal/company/product identity and family using dated primary
sources. Capture dated shutdown notices, company/acquirer announcements, registry
filings or public financial reports where available, retaining actual source
availability. Obtain feature vintages that precede the intended prediction cutoff.
Record contrary evidence and unresolved sources; absence is not a negative label.
Dev 2 then applies the existing label maturity, source-policy and fit-time rules.

Kaggle's commonly used Startup Success Prediction listing was also inspected;
this run did not acquire a verified dated raw dataset or establish feature-vintage
provenance from it. It is not used as ground truth. Public pages cannot reliably
supply private cash flow across this cohort. Calibration remains blocked until
sufficient dated, mature labels and historical features actually exist.

## First primary-source follow-up: Datree

- Retained inactive company `yc-13053`, linked to its exact discovery row.
- Captured its primary YC profile and company-owned repository README.
- The README reports closure of the supporting commercial company in July 2023,
  while explaining that the standalone open-source tool remains usable.
- Preserve month precision; do not invent an exact shutdown day or infer closure
  solely from a repository being archived.
- Reviewed manifest: `data/catalog/datree-discovery-followup-20261024-v1.json`.
- Pinned README commit: `0c3b63e6ce9688cdb5ad3bf06768875664cf15be`.
- Transfer ZIP SHA-256:
  `830697e826743212d1621d0f7bba81797307757166990b7ba24f4021a89d7d43`.
- Both raw captures and metadata are in the separate draft-release ZIP
  `datree-discovery-followup-20261024-v1.zip`.
- Labels remain unresolved pending dated identity, feature-vintage and Dev 2
  policy review. The original discovery ledger remains immutable.
