# Deployment

- [Local company runtime](local/README.md): exact publication selection, API-only
  dependency profile, readiness and a separate non-root container recipe.
- [Recovery and refresh](../docs/tasks/dev1/D1-O6-local-recovery.md): verified
  backups, new-root restoration, bounded collection and immutable rollback.
- `local/Dockerfile.api`: non-root API container recipe.
- Docker build/runtime and cloud deployment are distinct acceptance gates.
