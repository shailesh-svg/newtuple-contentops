"""Canonical tracker schema — loaded from contentops/schema/tracker.schema.json.

This is the single source of truth for the tracker contract. Field names,
agent-facing aliases, the status vocabulary, header detection, and create-time
defaults all come from the JSON contract so the same definition is shared across
every storage backend (Sheets, Apps Script, JSON file, …) instead of being
hand-duplicated in code.

Backends should depend on these helpers, never on hardcoded column maps.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Dict, List

from config import CONTENTOPS_DIR

SCHEMA_PATH = CONTENTOPS_DIR / "schema" / "tracker.schema.json"


@lru_cache(maxsize=1)
def load_schema() -> dict:
    """Load and validate the tracker contract. Cached for the process lifetime."""
    data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    _validate(data)
    return data


def reload_schema() -> None:
    """Clear the cached contract (tests / hot-reload)."""
    load_schema.cache_clear()
    _alias_map.cache_clear()
    _status_alias_map.cache_clear()


def _validate(data: dict) -> None:
    required = {"version", "primary_key", "fields", "statuses"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"tracker.schema.json missing keys: {sorted(missing)}")
    names = [f["name"] for f in data["fields"]]
    if data["primary_key"] not in names:
        raise ValueError(f"primary_key {data['primary_key']!r} is not a declared field")
    keys = [f["key"] for f in data["fields"]]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate field keys in schema")


# ─── Field name normalisation ─────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _alias_map() -> Dict[str, str]:
    """Map every alias AND snake_case key → canonical column name."""
    out: Dict[str, str] = {}
    for f in load_schema()["fields"]:
        canonical = f["name"]
        out[canonical] = canonical
        out[f["key"]] = canonical
        for alias in f.get("aliases", []):
            out[alias] = canonical
    return out


def normalize_field_name(name: str) -> str:
    return _alias_map().get(name, name)


def normalize_fields(fields: dict) -> dict:
    return {normalize_field_name(k): v for k, v in (fields or {}).items()}


def column_names() -> List[str]:
    return [f["name"] for f in load_schema()["fields"]]


def primary_key() -> str:
    return load_schema()["primary_key"]


def status_field() -> str:
    return load_schema().get("status_field", "Status")


# ─── Status normalisation ─────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _status_alias_map() -> Dict[str, str]:
    statuses = load_schema()["statuses"]
    out = {s.lower(): s for s in statuses["canonical"]}
    out.update({k.lower(): v for k, v in statuses.get("aliases", {}).items()})
    return out


def normalize_status(status: str) -> str:
    if not status:
        return status
    raw = str(status).strip().lower().replace("-", "_").replace(" ", "_")
    return _status_alias_map().get(raw, status)


def canonical_statuses() -> List[str]:
    return list(load_schema()["statuses"]["canonical"])


# ─── Header detection ─────────────────────────────────────────────────────────

def is_header_row(row: list) -> bool:
    """True if a spreadsheet row looks like the tracker's header row."""
    cells = [str(c) for c in row]
    markers = load_schema()["header_markers"]
    if any(m in cells for m in markers.get("primary", [])):
        return True
    for combo in markers.get("fallback_any_of", []):
        if all(c in cells for c in combo):
            return True
    combo_markers = markers.get("combo_markers", [])
    if combo_markers:
        matched = sum(1 for m in combo_markers if m in cells)
        if matched >= markers.get("min_combo_match", 3):
            return True
    return False


# ─── Create-row construction ──────────────────────────────────────────────────

def build_create_row(values: dict) -> dict:
    """Build a full tracker row (canonical column names) for a new item.

    `values` may use aliases or canonical names. Missing fields are filled from
    the schema's create defaults; date/datetime computed defaults are resolved.
    """
    schema = load_schema()
    provided = normalize_fields(values)
    template = schema.get("create_template", {})

    row: dict = {}
    for f in schema["fields"]:
        name = f["name"]
        if name in provided and provided[name] not in (None, ""):
            row[name] = provided[name]
            continue
        default = f.get("create_default")
        if default is None:
            row[name] = ""
        elif "value" in default:
            row[name] = default["value"]
        elif default.get("computed") == "today":
            row[name] = datetime.now(timezone.utc).date().isoformat()
        elif default.get("computed") == "now":
            row[name] = datetime.now(timezone.utc).isoformat()
        else:
            row[name] = ""

    # Cross-field fallbacks (e.g. Draft Text defaults to Key Message).
    km_fallback = template.get("key_message_falls_back_to")
    if not row.get("Key Message") and km_fallback:
        row["Key Message"] = provided.get(normalize_field_name(km_fallback), "") or row.get("Working Title / Hook", "")
    dt_fallback = template.get("draft_text_falls_back_to")
    if not row.get("Draft Text") and dt_fallback:
        row["Draft Text"] = row.get(normalize_field_name(dt_fallback), "")

    if row.get("Status"):
        row["Status"] = normalize_status(row["Status"])
    return row


def schema_version() -> str:
    return load_schema().get("version", "unknown")
