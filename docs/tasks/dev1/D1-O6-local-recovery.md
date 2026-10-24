# Company publication recovery and refresh

The filesystem store is the supported local runtime. This is not a PostgreSQL
migration or a cloud deployment claim. Install the locked data/API/CLI extras;
imports do not open connections or provision services.

## Backup and restore

`python -m oxhack2026 data company-backup ROOT NEW_ARCHIVE.zip` emits the ZIP's
SHA-256. Record it separately. The backup locks source/assessment publication
while capturing their indexes, verifies every retained version and copies only
reachable source manifests, normalized records, raw evidence and assessments.
It excludes `.env`, capture caches, failed candidates and unrelated files.
Archives and their raw source evidence are private operational artifacts, not
public API responses. Bounds: 256 MiB expanded/compressed, 100,000 files.

`python -m oxhack2026 data company-restore ARCHIVE.zip NEW_ROOT SHA256` verifies
the independently recorded checksum, rejects unsafe/duplicate/nonregular paths,
checks every source and assessment hash/foreign key and only then renames the
staging directory to NEW_ROOT. Existing destinations are refused. Failed staging
files remain for diagnosis. Point the application at the new root only after
health checks; retain the original root for rollback. File locks/atomic rename
require a local POSIX filesystem, not an object-storage mount.

On 2026-10-24 the real `company-vector-20261024-v1` draft release was downloaded
independently, SHA-256 checked, loaded, backed up and restored successfully.
All 14 observations and ten evidence records survived exactly. Test-only C2
assessment publication history also survives restore; real C2 is a separate
integration acceptance. Scripts/logs are retained under ignored `tests/outputs/`.

## Bounded refresh

1. Create a new reviewed CompanyBuildSettings JSON with unique run/snapshot IDs,
   current code revision and a closed UTC measurement day. First refresh the npm
   dataset with its existing pinned run recipe; bind the new company run to that
   explicit dataset version. Do not reuse an old source vintage as current data.
2. Run `data company-build SETTINGS.json NPM_ROOT COMPANY_ROOT`. Captures and
   canonical configuration are checkpointed per run. A retry reuses exact bytes;
   changed configuration under a used ID fails. A new ID is required for fresh
   HTTP observations. GitHub pages, response bytes, timeouts and retries are
   bounded. Rate limiting fails the run without publishing partial candidates.
3. Inspect coverage with the validated candidate. Commercial unknowns remain
   missing; truncated release history is never zero. Publish with
   `data company-publish COMPANY_ROOT SNAPSHOT --expected-current OLD_SNAPSHOT`.
   A lost compare-and-swap or validation failure leaves the old pointer intact.
4. Dev 2 builds assessments against that exact snapshot. Publish their JSON array
   with `data assessment-publish ROOT PUBLICATION ASSESSMENTS.json
   --expected-current OLD_PUBLICATION`, then run `data assessment-health` and
   `data company-health` with exact IDs. Do not generate model interpretations in
   the data worker. Source refresh alone never changes the API assessment choice.
5. Configure `SourceScopedAssessmentReader` with explicit approved publication
   IDs. Run list/profile/compare acceptance before changing production selection.
   Roll back by selecting the previous immutable batch; never edit its bytes.

No recurring collection job is enabled by default. An external scheduler may
invoke the bounded CLI recipe; API workers do not collect or schedule. Verified
credits, a real deployed runtime, TLS, monitoring and database restoration remain
separate cloud gates. Do not describe these local checks as CLOUD_DEPLOYED.
