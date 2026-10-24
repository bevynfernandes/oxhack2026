FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --group docs --no-install-project

COPY . .
RUN uv sync --frozen --group docs --no-editable \
    && useradd --create-home --uid 10001 scaffold \
    && chown -R scaffold:scaffold /app

USER scaffold
CMD ["/bin/bash"]
