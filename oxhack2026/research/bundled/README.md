# Company-name discovery snapshot

`company-domains.parquet` derives from the **Majestic Million**, published by
[Majestic](https://majestic.com/reports/majestic-million) under
[Creative Commons Attribution 3.0 Unported](https://creativecommons.org/licenses/by/3.0/).
The original download is
`https://downloads.majestic.com/majestic_million.csv`.

Changes: retain domain and source rank, lowercase domain names, remove duplicates
and names shorter than two characters, derive a punctuation-insensitive first-label
lookup key, and sort for Parquet predicate pruning. The adjacent JSON manifest
records original and derived SHA-256 digests, build time and row count. The retained
unmodified download is in the local acceptance output directory.

This is a website directory, not a company register or a list of verified official
websites. Candidate ranking is used only for discovery. No popularity fields enter
business features, dimension scores or startup predictions. Exact normalized label
matches may refer to different businesses. The user must choose a candidate and
confirm its independently fetched website identity. Missing companies, aliases,
non-Latin names and names unlike their domains require an exact website URL.

Rebuild after downloading the official CSV:

```sh
uv run --frozen --no-sync python -m oxhack2026.research.build_name_index \
  /path/to/majestic_million.csv \
  oxhack2026/research/bundled/company-domains.parquet
```

Refresh the dated attribution in `company_search.py` when updating this snapshot.
The snapshot is bundled so a search never downloads a million-row file or depends
on a search-engine quota, CAPTCHA, credential or live directory availability.
# Reviewed registry mapping

`reviewed-registry-mappings.json` supplies one independently reviewed Cloudflare
domain-to-CIK link, not a general name resolver. On 25 October 2026 the original
SEC annual report, accession `0001477333-26-000016`, identified
`https://www.cloudflare.com/impact/` as its own website. The complete document's
SHA-256 was `94e61fa7cc9b825817ab51dd1f6005b29fd9681019389566cc36a90517a14780`.
The collector retrieves this supporting filing and checks the exact quoted URL
before using CIK `0001477333`; submissions and financial facts must repeat that CIK.

The packaged mapping is used when no operator catalog override is configured.
SEC collection still requires an identifying `SEC_USER_AGENT`. Unknown domains
remain unmapped. To extend or replace the catalog, set
`SIGNALSHIFT_RESEARCH_REGISTRY_MAPPINGS` to a reviewed JSON file with the same
schema. Current legal-entity mappings do not establish old corporate-family or
reporting-scope continuity for model evaluation.

