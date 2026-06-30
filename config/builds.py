"""Validated build profiles for the first eight Conductor products."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path(__file__).with_name("builds.json")
VALID_MODES = {"solo", "council"}
VALID_PROVIDERS = {"openai", "anthropic", "google", "xai"}


@dataclass(frozen=True)
class BuildConfig:
    build_id: str
    mode: str
    lead: str
    specialists: tuple[str, ...]
    model_env: str | None
    status: str


def _load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported Conductor build manifest schema")
    return manifest


def get_build(build_id: str) -> BuildConfig:
    raw = _load_manifest().get("builds", {}).get(build_id)
    if raw is None:
        raise ValueError(f"Unknown CONDUCTOR_BUILD_ID: {build_id}")

    mode = raw.get("mode")
    lead = raw.get("lead")
    specialists = tuple(raw.get("specialists", ()))

    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode for {build_id}: {mode}")
    if lead not in VALID_PROVIDERS:
        raise ValueError(f"Invalid lead provider for {build_id}: {lead}")
    if any(provider not in VALID_PROVIDERS for provider in specialists):
        raise ValueError(f"Invalid specialist provider for {build_id}")
    if lead in specialists:
        raise ValueError(f"Lead cannot also be a specialist for {build_id}")
    if mode == "solo" and specialists:
        raise ValueError(f"Solo build cannot define specialists: {build_id}")
    if mode == "council" and len(specialists) != 3:
        raise ValueError(f"Council build must define three specialists: {build_id}")

    return BuildConfig(
        build_id=build_id,
        mode=mode,
        lead=lead,
        specialists=specialists,
        model_env=raw.get("model_env"),
        status=raw.get("status", "unknown"),
    )


def get_active_build() -> BuildConfig:
    return get_build(os.getenv("CONDUCTOR_BUILD_ID", "solo-openai"))
