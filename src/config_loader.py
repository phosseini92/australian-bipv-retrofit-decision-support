"""Load JSON-compatible YAML configuration without hidden defaults."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_config(filename: str) -> dict[str, Any]:
    """Load a locked configuration file from ``config``.

    Configuration files use JSON syntax, which is valid YAML 1.2, so milestone
    0.1 needs no parser dependency and introduces no parser-specific coercion.
    """

    path = PROJECT_ROOT / "config" / filename
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def load_variants() -> dict[str, Any]:
    return load_config("variants.yaml")


def load_model() -> dict[str, Any]:
    return load_config("model.yaml")


def load_sensitivity() -> dict[str, Any]:
    return load_config("sensitivity.yaml")


def load_qa_assertions() -> dict[str, Any]:
    return load_config("qa_assertions.yaml")
