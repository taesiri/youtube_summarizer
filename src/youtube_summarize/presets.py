"""Preset storage helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
PRESETS_DIR = ROOT_DIR / "src" / "data" / "presets"
DEFAULT_PRESET_ID = "summary_keywords"
DEFAULT_PROMPT = "Summarize the YouTube video. Return a short summary and a list of keywords."


def list_presets() -> list[dict[str, Any]]:
    presets = []
    if not PRESETS_DIR.exists():
        return presets
    for path in sorted(PRESETS_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            presets.append({"id": path.stem, "name": payload.get("name", path.stem)})
        except Exception:
            continue
    return presets


def load_preset(preset_id: str) -> dict[str, Any]:
    path = PRESETS_DIR / f"{preset_id}.json"
    if not path.exists():
        raise FileNotFoundError(preset_id)
    return json.loads(path.read_text(encoding="utf-8"))


def load_preset_safe(preset_id: str) -> Optional[dict[str, Any]]:
    try:
        return load_preset(preset_id)
    except Exception:
        return None


def save_preset(preset_id: str, payload: dict[str, Any]) -> None:
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    path = PRESETS_DIR / f"{preset_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def sanitize_preset_id(value: str) -> str:
    safe = "".join(ch for ch in value.strip().lower().replace(" ", "_") if ch.isalnum() or ch in "_-")
    return safe
