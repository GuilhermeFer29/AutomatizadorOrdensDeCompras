"""
Prompt loader — loads agent prompts from YAML files at ``app/agents/prompts/``.

Usage::

    from app.agents.prompts import load_prompts

    prompts = load_prompts("supply_chain")
    prompt_text = prompts["analista_demanda"]
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=16)
def load_prompts(name: str) -> dict[str, Any]:
    """Load and cache a YAML prompt file by name (without extension).

    Args:
        name: Stem of the YAML file inside ``app/agents/prompts/``.

    Returns:
        Dict mapping prompt keys to their string values.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
    """
    path = _PROMPTS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    logger.debug("Loaded prompts from %s (%d keys)", path.name, len(data))
    return data
