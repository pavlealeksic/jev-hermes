---
name: jev-decisions
description: "Fast typed decisions (choice/score/boolean) via the hosted Jev System-One API — use instead of in-LLM reasoning for routing, triage, gating, and moderation."
version: 1.0.0
author: pavlealeksic
license: Apache-2.0
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [jev, decisions, routing, classification, triage, moderation, hosted]
---

# Jev Typed Decisions

Jev is TypeSafe's hosted, non-generative "System One" decision API. Given a
**state** plus **typed questions**, it returns calibrated probabilities in one
request (~70–500 ms). It does **not** generate text.

**Privacy:** the state is sent to the configured hosted API — never include
secrets, credentials, or sensitive user data in the state.

## When to use `jev_decide`

Prefer it over reasoning in-LLM whenever the task is a *decision*, not a *composition*:

- **Routing** — which tool, model, queue, or workflow should handle this?
- **Triage** — department, priority, SLA for a ticket or message.
- **Gating** — yes/no checks before acting ("is this destructive?", "is this about billing?").
- **Scoring** — ordinal levels (urgency low→critical, sentiment, confidence rubrics).
- **Moderation / guardrails** — jailbreak or abuse screening (preset: `guard`, `moderation`).
- **Escalation** — the result's `action.act_probability` signals "act now" vs "escalate".

If a task needs explanation, code, or long text — do that yourself; Jev only decides.

## Question types

- `choice` — pick among labeled options; needs `criteria` (list or `{label: description}`).
- `score` — ordinal rubric; `criteria` is the ordered list of levels (low → high).
- `noul` — boolean; returns `P(true)`. `criteria` not needed.

Multiple questions in one call are batched in a single request — ask everything
at once.

## Example

```json
{
  "state": "I was billed twice this month and nobody replied to my emails!",
  "questions": {
    "department": {"type": "choice", "instructions": "Which team should handle this?",
                   "criteria": {"billing": "invoices, charges, refunds", "technical": "bugs, outages", "sales": "upgrades, quotes"}},
    "urgency": {"type": "score", "instructions": "How urgent is this?",
                "criteria": ["low", "medium", "high", "critical"]},
    "refund_requested": {"type": "noul", "instructions": "Does the customer ask for money back?"}
  }
}
```

Read `answers.<name>.choice` / `.score` / `.noul` plus per-option `probabilities`
and `confidence`. Low confidence → fall back to your own reasoning.

## Built-in presets

Pass `preset` instead of `questions`: `router` (small vs frontier model),
`guard` (jailbreak/prompt-injection), `moderation`, `triage` (support tickets).

## Writing good questions

- 2–8 clear, mutually exclusive options; descriptive instructions beat bare labels.
- Keep the state focused and free of secrets — it goes to the hosted API.
- Known limits: weak above ~20 options; `score` is the weakest primitive (prefer
  `choice` when levels are few); no vision, no arithmetic, no long-document reasoning.

## Operations

- Unsure whether the API key is configured or which endpoint is active? Call
  `jev_status` or `/jev keycheck`.
- Quick ad-hoc checks from chat: `/jev help` shows the slash-command forms;
  `/jev stats` shows usage metrics.
- Settings are user-tunable live: `/jev config` lists them, `/jev set <key> <value>`
  changes them without restart (e.g. `routing_hint`, `filter_output`, `jev_model`).
- The plugin may also run automatically in the background when the user enabled it:
  `routing_hint` injects complexity hints before LLM calls, and `filter_output`
  truncates large *successful* tool outputs Jev judges disposable (a
  `[jev: truncated …]` marker appears in the output — rerun the command if you need
  the full text). Both send excerpts to the hosted API.
- If the user selected `context.engine: jev`, context compression is Jev-targeted:
  stale tool results carry a `[jev-compaction truncated …]` marker, and some old
  call/result pairs may be gone entirely. Treat re-running a dropped command as normal.
  `/jev stats` shows compaction runs and fallbacks.
