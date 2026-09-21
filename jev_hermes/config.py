"""Plugin settings, readable and writable from inside Hermes.

Storage: ``plugins.entries.jev.settings.<key>`` in Hermes' config.yaml via
``ctx.get_config`` / ``ctx.set_config`` (declared in plugin.yaml's ``config_schema``,
so Hermes' UI can render them). Precedence: env var > Hermes setting > default.
Reads are live — changes via ``/jev set`` apply immediately, no restart.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

# key -> {env, type, default, description}
SETTINGS: Dict[str, Dict[str, Any]] = {
    "base_url": {
        "env": "JEV_BASE_URL", "type": "str", "default": "https://api.typesafe.ai/v1",
        "description": "Decisions API base URL (https; http only for loopback/LAN).",
    },
    "endpoint_path": {
        "env": "JEV_ENDPOINT_PATH", "type": "str", "default": "/systemone",
        "description": "Decisions endpoint path (OpenRouter: /api/alpha/decisions).",
    },
    "api_key_env": {
        "env": "JEV_API_KEY_ENV", "type": "str", "default": "TYPESAFE_API_KEY",
        "description": "Name of the env var holding the API key (OpenRouter: OPENROUTER_API_KEY).",
    },
    "jev_model": {
        "env": "JEV_MODEL", "type": "str", "default": "jev-latest",
        "description": "Model passed in each request (OpenRouter: typesafe/jev-1.13).",
    },
    "request_timeout_s": {
        "env": "JEV_REQUEST_TIMEOUT_S", "type": "float", "default": 30,
        "description": "HTTP timeout per decision call, seconds.",
    },
    "routing_hint": {
        "env": "JEV_ROUTING_HINT", "type": "bool", "default": False,
        "description": "pre_llm_call hook: inject a hint when Jev is confident a request is simple.",
    },
    "filter_output": {
        "env": "JEV_FILTER_OUTPUT", "type": "bool", "default": False,
        "description": "Truncate large *successful* tool/terminal outputs Jev judges disposable.",
    },
    "filter_min_chars": {
        "env": "JEV_FILTER_MIN_CHARS", "type": "int", "default": 6000,
        "description": "Minimum output size before filtering is considered.",
    },
    "keep_threshold": {
        "env": "JEV_KEEP_THRESHOLD", "type": "float", "default": 0.5,
        "description": "Compaction: keep-probability at or above this keeps the unit.",
    },
    "error_keep_threshold": {
        "env": "JEV_ERROR_KEEP_THRESHOLD", "type": "float", "default": 0.25,
        "description": "Compaction: lower keep bar for error results.",
    },
    "min_result_chars": {
        "env": "JEV_MIN_RESULT_CHARS", "type": "int", "default": 2000,
        "description": "Compaction: tool results smaller than this are never candidates.",
    },
    "result_excerpt_chars": {
        "env": "JEV_RESULT_EXCERPT_CHARS", "type": "int", "default": 500,
        "description": "Compaction: result head chars shown to Jev when judging a unit.",
    },
    "truncate_head_chars": {
        "env": "JEV_TRUNCATE_HEAD_CHARS", "type": "int", "default": 300,
        "description": "Compaction: head kept when a result is truncated.",
    },
    "min_reduction_ratio": {
        "env": "JEV_MIN_REDUCTION_RATIO", "type": "float", "default": 0.10,
        "description": "Compaction: Jev pass must shrink the transcript by at least this, else the built-in prune runs.",
    },
}

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}

_ctx: Any = None


def init(ctx: Any) -> None:
    """Capture the plugin context at register() time so settings work in-session."""
    global _ctx
    _ctx = ctx


def _coerce(key: str, raw: Any) -> Any:
    spec = SETTINGS[key]
    stype = spec["type"]
    if stype == "bool":
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise ValueError(f"{key} must be a boolean (true/false), got {raw!r}")
    if stype == "int":
        if isinstance(raw, bool):
            raise ValueError(f"{key} must be an integer, got {raw!r}")
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be an integer, got {raw!r}") from None
    if stype == "float":
        if isinstance(raw, bool):
            raise ValueError(f"{key} must be a number, got {raw!r}")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be a number, got {raw!r}") from None
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{key} must be a finite number, got {raw!r}")
        return value
    return str(raw)


def get(key: str) -> Tuple[Any, str]:
    """Return (value, source) where source is 'env' | 'settings' | 'default'."""
    spec = SETTINGS[key]
    raw = os.environ.get(spec["env"])
    if raw is not None and raw.strip() != "":
        return _coerce(key, raw), "env"
    if _ctx is not None:
        try:
            value = _ctx.get_config(key, None)
            if value is not None:
                return _coerce(key, value), "settings"
        except Exception:
            pass
    return spec["default"], "default"


def get_value(key: str) -> Any:
    return get(key)[0]


def set_value(key: str, raw: Any) -> Tuple[Any, str]:
    """Persist a setting via the Hermes plugin context. Returns (value, message)."""
    if key not in SETTINGS:
        raise KeyError(f"Unknown setting {key!r}; valid: {', '.join(sorted(SETTINGS))}")
    value = _coerce(key, raw)
    if _ctx is None:
        raise RuntimeError("settings can only be changed inside Hermes (no plugin context)")
    _ctx.set_config(key, value)
    return value, f"{key} = {value!r} (saved to Hermes config; applies immediately)"


def describe() -> List[Dict[str, Any]]:
    """Effective value + source + description for every setting."""
    out = []
    for key, spec in SETTINGS.items():
        value, source = get(key)
        out.append({
            "key": key, "value": value, "source": source,
            "default": spec["default"], "env": spec["env"],
            "description": spec["description"],
        })
    return out
