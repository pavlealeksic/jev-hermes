# jev-hermes

A [Hermes Agent](https://hermes-agent.nousresearch.com/) plugin that gives the agent access to
**Jev** — TypeSafe's hosted "System One" typed-decision API. Jev answers `choice` / `score` /
boolean (`noul`) questions with calibrated probabilities in a single request (~70–500 ms).
Use it for routing, triage, gating, and moderation decisions instead of spending LLM tokens.

**Jev vs [Laya](https://github.com/pavlealeksic/laya-hermes):** Laya runs the same kind of
decision model locally — free, offline, ~5–15 ms, but limited to a ~1024-token window. Jev is a
hosted, paid API with a huge context window (~25k tokens) at ~70–500 ms per call. The tradeoff:
**transcripts and probed excerpts leave your machine and go to the configured API.** If privacy
or per-call cost matters more than judgment quality, use the Laya plugin instead.

## What the plugin provides

- **`jev_decide` tool** — run typed questions against a state (text, JSON, or conversation list).
  Custom questions or built-in presets (`router`, `guard`, `moderation`, `triage` — bundled as
  inline data; the hosted API has no server-side presets). Multiple questions are batched in
  one request.
- **`jev_status` tool** — configured endpoint, API-key presence, live settings, metrics.
- **`/jev` slash command** — ad-hoc decisions plus `status`, `stats`, `keycheck`, `config`,
  `set` (try `/jev help`).
- **`jev:jev-decisions` skill** — teaches the agent when to prefer Jev over in-LLM reasoning.
- **Opt-in `pre_llm_call` routing hint** — with `routing_hint` on, Jev rates each user
  message's complexity and injects a short hint when it's confident the request is simple.
  Hint only; it never blocks or overrides your model.
- **Opt-in output filtering** — with `filter_output` on, Jev screens *successful* oversized
  tool/terminal outputs and truncates ones it is confident are disposable (install spam, progress
  bars) to head+tail with a marker. Failures and ambiguous output always pass through untouched.
  Jev doesn't generate text, so this truncates — it never summarizes.
- **Context engine (smart compaction)** — opt in with `hermes config set context.engine jev`
  then `/reset`. During context compression, Jev judges each stale tool call/result pair
  (keep / truncate / drop) instead of Hermes pruning by age alone — so a test failure from three
  turns ago survives while install spam is dropped. Design follows
  [hermes-jev-compact](https://pypi.org/project/hermes-jev-compact/) (which pioneered this
  seam). Safety: the proactive hot path stays deterministic, and any error, invalid transcript,
  or under-`min_reduction_ratio` pass falls back to the built-in prune — worst case is stock
  Hermes behavior. Note: compaction sends redacted result excerpts to the hosted API, one paid
  call per candidate unit.
- **Session metrics** — `/jev stats` shows decisions, avg latency, truncations, and estimated
  tokens saved. In-memory; resets when Hermes restarts.
- **Zero dependencies** — the client is pure stdlib `urllib`. Nothing to install beyond this
  package; you only need an API key.

## Backends

One backend: the hosted Decisions API. Two known endpoints speak the same wire shape
(`POST {base_url}{endpoint_path}` with `{model, state, questions}` → `{answers: {...}}`):

| Provider | `base_url` | `endpoint_path` | `api_key_env` | `jev_model` |
|---|---|---|---|---|
| TypeSafe (default) | `https://api.typesafe.ai/v1` | `/systemone` | `TYPESAFE_API_KEY` | `jev-latest` |
| OpenRouter | `https://openrouter.ai` | `/api/alpha/decisions` | `OPENROUTER_API_KEY` | `typesafe/jev-1.13` |

The client is fail-closed: https everywhere, cleartext http only for loopback/private LAN
addresses, no redirects, no credentials in URLs, responses capped at 1 MB, endpoint paths
restricted to `[A-Za-z0-9/._-~]+`.

## Install

From PyPI (once published):

```bash
~/.hermes/hermes-agent/venv/bin/pip install jev-hermes
hermes plugins enable jev
```

Or from GitHub (note the `#jev_hermes` subdir — the plugin lives in the package folder):

```bash
hermes plugins install pavlealeksic/jev-hermes#jev_hermes --enable
```

The plugin declares `requires_env: [TYPESAFE_API_KEY]`, so Hermes prompts for the key on
install. Using OpenRouter instead? Set `OPENROUTER_API_KEY` and run:

```
/jev set base_url https://openrouter.ai
/jev set endpoint_path /api/alpha/decisions
/jev set api_key_env OPENROUTER_API_KEY
/jev set jev_model typesafe/jev-1.13
```

For local development, symlink `jev_hermes/` into `~/.hermes/plugins/jev/` and
`hermes plugins enable jev`.

## Configuration

All settings are adjustable **live from inside Hermes** — no restart needed:

```
/jev config                          # show every setting, its value, and its source
/jev keycheck                        # is the configured API key env var set?
/jev set filter_output true          # enable output filtering immediately
/jev set routing_hint true           # enable pre-LLM-call complexity hints
/jev set jev_model typesafe/jev-1.13 # switch model (applies to next decision)
```

Settings persist in Hermes' `config.yaml` under `plugins.entries.jev.settings` and are
declared in the plugin's `config_schema`, so Hermes' settings UI can render them too.
Environment variables still work and **override** settings: precedence is
env var (`JEV_*`) → Hermes setting → default.

| Key | Env var | Default | Meaning |
|---|---|---|---|
| `base_url` | `JEV_BASE_URL` | `https://api.typesafe.ai/v1` | Decisions API base URL |
| `endpoint_path` | `JEV_ENDPOINT_PATH` | `/systemone` | endpoint path (OpenRouter: `/api/alpha/decisions`) |
| `api_key_env` | `JEV_API_KEY_ENV` | `TYPESAFE_API_KEY` | name of the env var holding the API key |
| `jev_model` | `JEV_MODEL` | `jev-latest` | model sent in each request |
| `request_timeout_s` | `JEV_REQUEST_TIMEOUT_S` | `30` | HTTP timeout per decision call |
| `routing_hint` | `JEV_ROUTING_HINT` | `false` | `pre_llm_call` complexity hint |
| `filter_output` | `JEV_FILTER_OUTPUT` | `false` | truncate large successful tool/terminal outputs Jev judges disposable |
| `filter_min_chars` | `JEV_FILTER_MIN_CHARS` | `6000` | minimum output size before filtering is considered |
| `keep_threshold` | `JEV_KEEP_THRESHOLD` | `0.5` | compaction: keep-probability at/above this keeps the unit |
| `error_keep_threshold` | `JEV_ERROR_KEEP_THRESHOLD` | `0.25` | compaction: lower keep bar for error results |
| `min_result_chars` | `JEV_MIN_RESULT_CHARS` | `2000` | compaction: smaller tool results are never candidates |
| `result_excerpt_chars` | `JEV_RESULT_EXCERPT_CHARS` | `500` | compaction: result head chars shown to Jev per unit |
| `truncate_head_chars` | `JEV_TRUNCATE_HEAD_CHARS` | `300` | compaction: head kept when a result is truncated |
| `min_reduction_ratio` | `JEV_MIN_REDUCTION_RATIO` | `0.10` | compaction: pass must shrink the transcript by this, else built-in prune runs |

## Deliberately not included

- **Per-turn main-model routing** — Hermes v0.21 has no plugin seam for switching the main
  loop's model (`llm.model_override` covers only a plugin's own `ctx.llm` calls). The routing
  hint is the honest approximation until Hermes adds one.
- **Skill routing** — Hermes already progressive-discloses skills (compact index, load on
  demand); there is no skill-context bloat to fix.
- **Output summarization** — Jev is non-generative; filtering truncates, it can't rewrite.
- **Retries** — each decision is a single POST; any failure falls back (hooks fail open,
  compaction falls back to the built-in prune).

## Example

Ask the agent something like *"use jev to triage this ticket: …"*, or call the tool shape directly:

```json
{
  "state": "I was billed twice this month and support never replied.",
  "questions": {
    "department": {"type": "choice", "instructions": "Which team handles this?",
                   "criteria": {"billing": "charges and refunds", "technical": "bugs and outages"}},
    "urgency": {"type": "score", "instructions": "How urgent?",
                "criteria": ["low", "medium", "high", "critical"]},
    "refund_requested": {"type": "noul", "instructions": "Does the customer ask for money back?"}
  }
}
```

→ `answers.department.choice = "billing"`, `answers.refund_requested.noul ≈ 0.9`, plus per-option
probabilities, confidence, and `action.act_probability`.

## Development

```bash
python3 -m unittest discover -s tests -v     # unit tests (stubbed client, no network)
python3 tests/smoke.py                       # end-to-end wiring check, stubbed transport
python -m build                              # build sdist + wheel into dist/
```

## Publishing a release (maintainer)

The repo ships `.github/workflows/publish.yml` using PyPI **Trusted Publishing** (no
stored tokens). One-time setup, then releases are automatic:

1. On [pypi.org](https://pypi.org): create an account → *Account settings → Publishing →
   Add a new pending publisher* → fill in: PyPI project name `jev-hermes`, owner
   `pavlealeksic`, repository `jev-hermes`, workflow `publish.yml`, environment `pypi`.
   (A "pending publisher" creates the project on first publish — no need to pre-create it.)
2. On GitHub: repo *Settings → Environments → New environment* named `pypi`
   (optionally add required reviewers for a manual gate).
3. Cut a release: bump `version` in **both** `pyproject.toml` and
   `jev_hermes/plugin.yaml`, commit, then
   `gh release create v1.0.0 --generate-notes` — the workflow runs tests, builds, publishes.
4. Verify: `pip install jev-hermes==1.0.0` in a scratch venv.

Manual fallback if you prefer: `python -m build && twine upload dist/*` with a PyPI API
token (`pip install twine`).

## Credits & license

Plugin code: Apache-2.0. Jev API by TypeSafe; compaction design adapted from
[hermes-jev-compact](https://pypi.org/project/hermes-jev-compact/) (TheEpTic, MIT).
Preset question text ported from [laya-mlx](https://github.com/mizorewww/laya-mlx)
(Apache-2.0, Convai Innovations). Not affiliated with Nous Research or TypeSafe.
