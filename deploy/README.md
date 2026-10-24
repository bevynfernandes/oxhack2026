# Deployment templates

No cloud resources, scheduled jobs, database connections, or API services are
configured or provisioned.

- local/: future local-service composition.
- tiger/: future managed database configuration and restore procedure.
- vultr/: future hosting, object storage, timer, and rollback configuration.

The root Dockerfile supplies a development shell only. Follow PLAN.md section
10 before implementing cloud deployment, including verified credits and a
resource lifetime. These notes do not enforce budgets or establish readiness.
