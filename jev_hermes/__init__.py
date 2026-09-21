"""Jev plugin for Hermes Agent.

Exposes the hosted Jev "System One" typed-decision API as agent tools
(``jev_decide``, ``jev_status``), a ``/jev`` slash command (``help``, ``status``,
``stats``, ``keycheck``, ``config``, ``set``, decision forms), a bundled
``jev:jev-decisions`` skill, session metrics, and two hooks: a ``pre_llm_call``
routing hint and conservative output truncation. All hooks are gated by live
plugin settings (``/jev set <key> <value>`` — no restart needed). Zero
dependencies — the client is pure stdlib urllib; there is nothing to install,
only an API key to set (``TYPESAFE_API_KEY`` by default).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from . import config, filters, schemas, tools

logger = logging.getLogger(__name__)

_ROUTING_HINT_QUESTIONS = {
    "complexity": {
        "type": "choice",
        "instructions": "How much reasoning effort does this user request need from an AI assistant?",
        "criteria": {
            "simple": "A short, routine request: lookup, small edit, simple question, formatting, quick command.",
            "complex": "Needs multi-step reasoning, design trade-offs, debugging, or long-form generation.",
        },
    }
}

_ROUTING_HINT_THRESHOLD = 0.8


def _routing_hint_hook(
    session_id: str = "",
    user_message: str = "",
    is_first_turn: bool = False,
    model: str = "",
    **kwargs: Any,
) -> Optional[dict]:
    """pre_llm_call hook, gated live on the ``routing_hint`` setting.

    Runs Jev's complexity check on the user message; when Jev is confident the
    request is simple, injects a short hint into the turn's user message. Never
    raises, never blocks — hint only, no model override. Note: each check is a
    paid hosted API call and the user message is sent to the API.
    """
    try:
        if not config.get_value("routing_hint"):
            return None
        if not isinstance(user_message, str) or not user_message.strip():
            return None
        from . import client

        result, _, _, _ = client.predict(user_message, _ROUTING_HINT_QUESTIONS)
        answer = (result.get("answers") or {}).get("complexity") or {}
        confidence = answer.get("confidence") or 0.0
        if answer.get("choice") == "simple" and confidence >= _ROUTING_HINT_THRESHOLD:
            try:
                from . import metrics

                metrics.record_decision(0.0, feature="routing_hints")
            except Exception:
                pass
            return {"context": (
                f"[jev] Decision API rates this request as simple "
                f"(confidence {confidence:.2f}). Prefer the most direct, minimal path."
            )}
    except Exception as exc:  # a hook must never break the turn
        logger.debug("jev routing hint skipped: %s", exc)
    return None


def register(ctx) -> None:
    config.init(ctx)
    ctx.register_tool(
        name="jev_decide",
        toolset="jev",
        schema=schemas.DECIDE_SCHEMA,
        handler=tools.handle_decide,
        description="Hosted System-One typed decisions (choice/score/boolean) via the Jev API.",
        emoji="⚡",
    )
    ctx.register_tool(
        name="jev_status",
        toolset="jev",
        schema=schemas.STATUS_SCHEMA,
        handler=tools.handle_status,
        description="Jev API status and diagnostics.",
        emoji="⚡",
    )
    ctx.register_command(
        "jev",
        handler=tools.handle_slash,
        description="Quick typed decisions and settings via the Jev API (try /jev help).",
        args_hint="<type>; <question>; <state>",
    )
    skill_path = Path(__file__).parent / "SKILL.md"
    if skill_path.exists():
        ctx.register_skill(
            "jev-decisions",
            skill_path,
            description="When and how to use the Jev API for fast typed decisions.",
        )
    # Hooks register unconditionally and gate on live settings at call time, so
    # `/jev set routing_hint true` / `set filter_output true` take effect without
    # a restart. When disabled the callbacks return None immediately.
    ctx.register_hook("pre_llm_call", _routing_hint_hook)
    ctx.register_hook("transform_terminal_output", filters.transform_terminal_output)
    ctx.register_hook("transform_tool_result", filters.transform_tool_result)
    # Context engine: opt-in via `hermes config set context.engine jev` (+ /reset).
    try:
        from . import engine as jev_engine

        ctx.register_context_engine(jev_engine.JevContextCompressor())
    except Exception as exc:
        logger.warning("jev: context engine registration failed: %s", exc)
