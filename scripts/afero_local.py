"""Shared helpers for local afero login / bridge scripts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aioafero.v1 import TokenData

DEFAULT_CONFIG = Path("afero.yaml")
DEFAULT_SESSION = Path(".aioafero-session.json")


def load_config(path: Path) -> dict[str, Any]:
    """Load a flat YAML config mapping."""
    try:
        import yaml
    except ImportError as err:  # pragma: no cover - exercised when extra missing
        raise SystemExit(
            "PyYAML is required for afero.yaml. "
            "Install with: uv sync --extra cli"
        ) from err
    if not path.is_file():
        raise SystemExit(
            f"Config not found: {path}\n"
            f"Copy scripts/afero.yaml.example to {DEFAULT_CONFIG} and edit."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a YAML mapping: {path}")
    return data


def config_username(config: dict[str, Any]) -> str:
    username = config.get("username") or os.environ.get("AFERO_USERNAME")
    if not isinstance(username, str) or not username:
        raise SystemExit("Set username in afero.yaml or AFERO_USERNAME.")
    return username


def session_path(config: dict[str, Any]) -> Path:
    raw = config.get("session_file", DEFAULT_SESSION)
    return Path(raw)


def save_session(path: Path, username: str, tokens: TokenData) -> None:
    """Write TokenData to JSON (mode ``0600``)."""
    path.write_text(
        json.dumps(tokens.to_session_dict(username), indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def load_session(path: Path) -> tuple[str, TokenData]:
    """Load username + TokenData from a session JSON file."""
    if not path.is_file():
        raise SystemExit(
            f"Session file not found: {path}\n"
            "Run: uv run --extra cli python scripts/afero_login.py"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise SystemExit(f"Unable to read session file {path}: {err}") from err
    try:
        return TokenData.from_session_dict(payload)
    except (TypeError, ValueError) as err:
        raise SystemExit(f"Invalid session file {path}: {err}") from err
