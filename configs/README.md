# Versioned configuration

Nonsecret, versioned inputs for data collection and model experiments:

- `data/`: pinned npm, company-source and public-cohort collection recipes.
- `experiments/`: company and public-SDK experiment settings.

The administrative data/model commands validate these inputs through their Python
contracts. Keep source identities, policy versions and experimental cutoffs
explicit so collection and evaluation can be reproduced.

Runtime environment configuration is documented in
[the local runbook](../deploy/local/README.md). Files in this directory contain no
provider credentials; `.env.example` lists supported runtime configuration names.
