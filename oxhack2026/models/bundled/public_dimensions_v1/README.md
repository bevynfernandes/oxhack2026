# Public dimension baseline bundle v1

Actual fitted portable JSON weights from 24 October 2026. The API verifies every
model against `run.json` and never loads pickle or trains at request time.
The bundle is packaged with the Python application, so local model availability
does not depend on ignored `artifacts/` directories.

These are experimental dimension proxies, not the Growth/Survival/Financial
Health company-outcome models. Only adoption's complete adjacent npm windows
currently support experimental company inference. Execution is withheld because
its held-out benchmark fails; sentiment needs validated entity text, competition
needs a complete matched peer cohort, and the financial model is not validated
for private startups. No complete AScore is inferred from missing dimensions.

Attribution and data lineage:

- FinEntity, Yixuan Tang, Yi Yang, Allen Huang, Andy Tam and Justin Tang (2023),
  https://aclanthology.org/2023.emnlp-main.956/ and
  https://github.com/yixuantt/FinEntity, dataset commit
  3b6cedc5485b669c2ed168f1d949f517636eb7b8. Dataset licensed ODC-BY 1.0:
  https://opendatacommons.org/licenses/by/1-0/ . No original news articles are
  redistributed in this bundle.
- SequelSEC, US public company fundamentals, retrieved 24 October 2026:
  https://sequelsec.com/datasets/us-public-company-fundamentals . Normalization
  and derived dataset licensed CC BY 4.0:
  https://creativecommons.org/licenses/by/4.0/ . Financial weights/reference
  distributions are transformations of reported annual software-issuer values,
  not original filing-availability histories. No raw financial CSV is bundled.
- Official npm download counts and GitHub stable releases, acquired for the
  declared commercial SDK cohort in configs/experiments/public-sdk-cohort-v1.json.
  https://github.com/npm/registry/blob/main/docs/download-counts.md and
  https://docs.github.com/en/rest/releases/releases . No source code is bundled.

Evaluation files include the actual held-out results and population limitations.
run.json preserves source/code hashes, original training-run digest and model
hashes. Artifact paths are made relative for this packaged copy. See
`docs/tasks/dev2/public-dimension-training-20261024.md` for targets, splits,
research, reproduction and the broader exploratory architecture comparison.
