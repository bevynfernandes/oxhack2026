# C1/C2: Canonical immutable artifact references

- Owner: Dev 2; branch `dev/models-artifact-alignment`.
- Paths: model/evaluation contracts, generated model schemas, synthetic model
  fixtures/tests, Dev 2 documentation.
- Depends on: merged C1 PR #9; no new dependencies or root changes.

C2 re-exports and consumes C1's exact ArtifactReference class. This removes
the parallel path/hash validator and adds required byte size and media type.
The source type rejects noncanonical paths, URLs, traversal, invalid digests,
and invalid sizes before storage access.

Because the reference shape changes, feature/forecast manifests are versioned
`models-v2`, and evaluation reports are `evaluation-v2`. Old manifests fail
explicitly; regenerate them from verified artifacts rather than infer missing
sizes or media types. No real version-1 artifact was published. Synthetic
fixtures have placeholder metadata and still cannot be loaded as data.

Saved tests verify fixture/schema compatibility and safe artifact paths.
Dev 3 consumes the same C2 types without changes to public C3 numerical fields;
Dev 1 can use one canonical type for every immutable bundle reference.
