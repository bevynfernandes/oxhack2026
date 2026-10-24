"""Backend-only defaults for the private team's Gemini configuration."""

import os
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values

DEFAULT_MODEL = "gemini-3.8-live-extended-thinking"


def gemini_api_key() -> str:
    """Return an environment override or the private repository's shared default.

    An explicitly empty environment value disables the shared credential. The
    file is resolved beside this module so installed packages behave like clones.
    No credentials are written into the process environment or returned by APIs.
    """
    if "GEMINI_API_KEY" in os.environ:
        return os.environ["GEMINI_API_KEY"]
    values = dotenv_values(Path(__file__).with_name("internal-gemini.env"))
    return values.get("GEMINI_API_KEY") or ""


def mapping_mode() -> Literal["rules", "rules_gemini"]:
    """Return the explicit mapping mode; raise ValueError for unsupported settings."""
    mode = os.environ.get("SIGNALSHIFT_RESEARCH_MAPPING_MODE", "rules")
    if mode not in {"rules", "rules_gemini"}:
        message = "Unsupported research mapping mode"
        raise ValueError(message)
    return "rules_gemini" if mode == "rules_gemini" else "rules"
