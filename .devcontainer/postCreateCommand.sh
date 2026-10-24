#!/usr/bin/env bash
set -euo pipefail

python -m pip install --user uv==0.13.0
export PATH="$HOME/.local/bin:$PATH"
uv sync --frozen --group docs
uv pip install --python .venv/bin/python ipykernel ipywidgets
npm --prefix frontend ci
