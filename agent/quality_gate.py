"""Deterministic content quality gate — the CI step for content.

The agent is *asked* (in its system prompt) to follow brand rules, but a model
under load occasionally slips. This module enforces the rules in code so a draft
that violates them is blocked before it ever reaches a human reviewer in Slack —
exactly like a failing test blocks a deploy.

Two severities:
  - ``block``  : hard failure. The draft is not posted; violations are returned
                 to the agent so it can revise and retry.
  - ``warn``   : surfaced for visibility (and on the dashboard) but non-blocking,
                 because the check is heuristic and could false-positive.

Rules are sourced from the brand markdown in ``contentops/brand/`` so there is a
single source of truth shared with the prompt.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, List, Optional

from config import (
    CONTENTOPS_DIR,
    QUALITY_MAX_CHARS,
    QUALITY_MIN_CHARS,
    QUALITY_MIN_VOICE_SCORE,
)

# Fallbacks used only if the brand markdown can't be parsed, so the gate is never
# silently disabled.
_FALLBACK_BANNED = [
    "ai will change everything",
    "game changer",
    "revolutionary",
    "future of work",
    "just add ai",
    "set and forget",
    "fully autonomous",
]
_FALLBACK_BUCKETS = [
    "Shipping Production-Ready Intelligence",
    "Workflow Wins",
    "What Changed In AI",
    "Founder Notes",
    "Building Your Agentic Enterprise",
]

# Heuristic cue words for the soft structural checks.
_IMPLICATION_CUES = [
    "enterprise", "production", "team", "organization", "org ", "ops",
    "reliability", "governance", "compliance", "cost", "risk", "scale",
    "stakeholder", "leadership", "rollout", "adoption",
]
_TAKEAWAY_CUES = [
    "start", "try", "ask", "review", "audit", "build", "map", "define",
    "measure", "check", "next step", "this week", "begin", "identify",
    "what's one", "what is one",
]


@lru_cache(maxsize=1)
def load_banned_phrases() -> tuple:
    """Parse the hard-ban list from contentops/brand/banned-phrases.md."""
    path = CONTENTOPS_DIR / "brand" / "banned-phrases.md"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return tuple(_FALLBACK_BANNED)

    phrases: List[str] = []
    in_hard = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## "):
            in_hard = "hard ban" in stripped.lower()
            continue
        if not in_hard or not stripped.startswith("-"):
            continue
        # Prefer the quoted phrase; the parenthetical qualifier (e.g.
        # "without specifics") can't be judged deterministically, so the quoted
        # phrase is treated as a hard ban outright.
        m = re.search(r'"([^"]+)"', stripped)
        candidate = m.group(1) if m else stripped.lstrip("- ").strip()
        candidate = candidate.strip().lower()
        if candidate:
            phrases.append(candidate)
    return tuple(phrases or _FALLBACK_BANNED)


@lru_cache(maxsize=1)
def load_valid_buckets() -> tuple:
    """Parse bucket names from contentops/brand/content-buckets.md."""
    path = CONTENTOPS_DIR / "brand" / "content-buckets.md"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return tuple(_FALLBACK_BUCKETS)

    buckets: List[str] = []
    for line in text.splitlines():
        # Matches headings like "## 1) Shipping Production-Ready Intelligence"
        m = re.match(r"^#{1,3}\s*\d+\)\s*(.+?)\s*$", line.strip())
        if m:
            buckets.append(m.group(1).strip())
    return tuple(buckets or _FALLBACK_BUCKETS)


def reload_rules() -> None:
    """Clear cached brand rules (used by tests and hot-reload)."""
    load_banned_phrases.cache_clear()
    load_valid_buckets.cache_clear()


def evaluate_draft(
    text: str,
    bucket: Optional[str] = None,
    voice_score: Optional[float] = None,
) -> Dict:
    """Run all gate checks against a draft.

    Returns a dict:
      {
        "passed": bool,                # True when no blocking violations
        "violations": [{rule, severity, message}, ...],  # blocking
        "warnings":   [{rule, severity, message}, ...],  # non-blocking
        "checks": int,                 # number of rules evaluated
      }
    """
    text = text or ""
    lowered = text.lower()
    violations: List[Dict] = []
    warnings: List[Dict] = []
    checks = 0

    # 1) Banned phrases (HARD)
    checks += 1
    hits = [p for p in load_banned_phrases() if p in lowered]
    for phrase in hits:
        violations.append(
            {
                "rule": "banned_phrase",
                "severity": "block",
                "message": f'Banned phrase used: "{phrase}"',
            }
        )

    # 2) Length bounds (HARD)
    checks += 1
    length = len(text.strip())
    if length < QUALITY_MIN_CHARS:
        violations.append(
            {
                "rule": "length_min",
                "severity": "block",
                "message": f"Draft too short: {length} chars (min {QUALITY_MIN_CHARS}).",
            }
        )
    elif length > QUALITY_MAX_CHARS:
        violations.append(
            {
                "rule": "length_max",
                "severity": "block",
                "message": f"Draft too long: {length} chars (max {QUALITY_MAX_CHARS}).",
            }
        )

    # 3) Bucket assigned and valid (HARD)
    checks += 1
    valid_buckets = load_valid_buckets()
    if not bucket or not str(bucket).strip():
        violations.append(
            {
                "rule": "bucket_missing",
                "severity": "block",
                "message": "No content bucket assigned.",
            }
        )
    elif not _bucket_matches(bucket, valid_buckets):
        violations.append(
            {
                "rule": "bucket_invalid",
                "severity": "block",
                "message": (
                    f'Bucket "{bucket}" is not one of the approved buckets: '
                    + ", ".join(valid_buckets)
                ),
            }
        )

    # 4) Voice / self-score threshold (HARD when provided, WARN when missing)
    checks += 1
    if voice_score is None:
        warnings.append(
            {
                "rule": "voice_score_missing",
                "severity": "warn",
                "message": "No self-assessed voice score was provided.",
            }
        )
    elif voice_score < QUALITY_MIN_VOICE_SCORE:
        violations.append(
            {
                "rule": "voice_score_low",
                "severity": "block",
                "message": f"Voice score {voice_score} is below the minimum {QUALITY_MIN_VOICE_SCORE}.",
            }
        )

    # 5) Concrete enterprise implication (WARN — heuristic)
    checks += 1
    if not any(cue in lowered for cue in _IMPLICATION_CUES):
        warnings.append(
            {
                "rule": "enterprise_implication",
                "severity": "warn",
                "message": "Could not detect a concrete enterprise implication.",
            }
        )

    # 6) Actionable takeaway (WARN — heuristic)
    checks += 1
    if not any(cue in lowered for cue in _TAKEAWAY_CUES):
        warnings.append(
            {
                "rule": "actionable_takeaway",
                "severity": "warn",
                "message": "Could not detect an actionable next step / takeaway.",
            }
        )

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
        "checks": checks,
    }


def _bucket_matches(bucket: str, valid: tuple) -> bool:
    norm = re.sub(r"[^a-z0-9]+", "", str(bucket).lower())
    return any(re.sub(r"[^a-z0-9]+", "", b.lower()) == norm for b in valid)


def format_violations(result: Dict) -> str:
    """Human-readable summary for returning to the agent / Slack."""
    lines = []
    for v in result.get("violations", []):
        lines.append(f"• ❌ [{v['rule']}] {v['message']}")
    for w in result.get("warnings", []):
        lines.append(f"• ⚠️ [{w['rule']}] {w['message']}")
    return "\n".join(lines) if lines else "All quality checks passed."
