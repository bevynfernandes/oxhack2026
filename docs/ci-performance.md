# CI performance

The workflow runs on every pull request, on pushes to `main`, and on manual
dispatch. Feature branches receive their checks through pull requests, avoiding a
second full run for each push. A newer update cancels an older run for the same
pull request or branch. There are no path filters that could leave a required
check pending or overlook cross-language contract changes.

## Jobs and dependency caches

Independent jobs run concurrently on separate runners. Steps within a job run
sequentially. Frontend formatting, contract/type checks, production build, and
unit tests run in `frontend-checks`, alongside end-to-end tests in `browser`.
The existing `frontend` check remains an aggregate gate: it succeeds only when
both jobs succeed. Python checks and the isolated lightweight API smoke test
retain their existing coverage.

- `setup-node` caches npm's download cache using `frontend/package-lock.json`.
  Every job still uses `npm ci` to verify and install the locked dependency tree.
  `--prefer-offline` favors cached packages while fetching missing packages.
  There is no `node_modules` cache that bypasses installation or integrity checks.
- `setup-uv` keys the package cache on `pyproject.toml` and `uv.lock`, with separate
  suffixes for the full Python suite, lightweight API, and browser API fixture.
  This avoids simultaneous cache writers with different installed extras.
  Default CI pruning is retained: a small cache is expected when packages have
  prebuilt wheels. Copying a large wheel cache can cost more than downloading it.
- The browser job installs only the API/data Python extras, without development
  tools. The Python job retains all extras needed by its tests and type checks.
- Chromium binaries are downloaded rather than cached. Python's research browser
  uses the default headless shell, so its installer uses `--only-shell`.
  Frontend tests select `channel: "chromium"`, so their installer uses `--no-shell`
  to download full Chromium without the unused headless shell. Both still install
  Linux system dependencies.

At this project's current size, TypeScript compilation and frontend unit tests
take seconds. Separate TypeScript build caches, test shards, custom browser
images, and a package-manager migration add overhead without measured benefit.
Reconsider them if the corresponding steps become a bottleneck. Do not cache
successful test results or skip checks based on a dependency cache hit.

## Measurements

The baseline is the successful acceptance PR run
[40132761865](https://github.com/bevynfernandes/oxhack2026/actions/runs/40132761865)
on 2026-10-24, before these workflow changes:

| Work | Duration |
| --- | ---: |
| Entire workflow, including queue/startup | 145 s |
| Frontend job | 141 s |
| Frontend formatting, build, and unit tests | 18 s |
| Frontend browser installation | 28 s |
| Frontend end-to-end tests | 65 s |
| Python job | 73 s |
| Python browser installation | 29 s |
| Lightweight API job | 13 s |

Compare completed GitHub runs after the change, using job and step timestamps
from `gh api repos/bevynfernandes/oxhack2026/actions/runs/<run-id>/jobs`.
Separate queue time, execution time, and total runner time; adding parallel jobs
can reduce latency while increasing total runner time. Compare multiple runs
because browser downloads, Linux package mirrors, and runner scheduling vary.
Check both fresh lockfile caches and unchanged-lockfile runs. Do not report an
estimated saving as a measured improvement.

## Maintainer references

- [GitHub workflow concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
- [Node setup and npm cache behavior](https://github.com/actions/setup-node#caching-global-packages-data)
- [npm clean installation](https://docs.npmjs.com/cli/v11/commands/npm-ci/)
- [uv GitHub Actions integration](https://docs.astral.sh/uv/guides/integration/github/)
- [setup-uv v6 caching and pruning](https://github.com/astral-sh/setup-uv/tree/v6#enable-caching)
- [Playwright CI and browser caching](https://playwright.dev/docs/ci#caching-browsers)
- [Playwright Chromium installation modes](https://playwright.dev/docs/browsers#chromium-headless-shell)
