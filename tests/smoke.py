"""End-to-end wiring smoke test with a stubbed transport — NO real API calls.

Exercises the tool handlers, slash command, and client request shaping through
a fake transport. Usage: python3 tests/smoke.py"""

import json
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jev_hermes import client, tools  # noqa: E402


def fake_transport(url, body, headers, timeout_s):
    """Deterministic stand-in for the Jev API."""
    request = json.loads(body.decode("utf-8"))
    questions = request["questions"]
    answers = {}
    for name, spec in questions.items():
        qtype = spec.get("type")
        if qtype == "noul":
            answers[name] = {"noul": 0.87}
        elif qtype == "choice":
            options = list(spec.get("criteria") or ["a", "b"])
            answers[name] = {
                "choice": options[0],
                "confidence": 0.91,
                "probabilities": {o: round(1.0 / len(options), 4) for o in options},
            }
        elif qtype == "score":
            levels = list(spec.get("criteria") or ["low", "high"])
            answers[name] = {"score": levels[0], "confidence": 0.8}
    return 200, json.dumps({"answers": answers, "action": {"act_probability": 0.87}})


env = {**os.environ, "TYPESAFE_API_KEY": "sk-smoke-stub"}
with mock.patch.dict(os.environ, env), \
     mock.patch.object(client, "_transport", side_effect=fake_transport):

    print("== jev_status ==")
    print(tools.handle_status({}))
    print()

    print("== jev_decide: choice + score + noul in one call ==")
    out = tools.handle_decide({
        "state": "I was billed twice this month and support never replied. I want my money back.",
        "questions": {
            "department": {
                "type": "choice",
                "instructions": "Which team should handle this support request?",
                "criteria": {
                    "billing": "invoices, charges, refunds, payments",
                    "technical": "bugs, crashes, outages",
                    "sales": "upgrades, quotes, new plans",
                },
            },
            "urgency": {
                "type": "score",
                "instructions": "How urgent is this request?",
                "criteria": ["low", "medium", "high", "critical"],
            },
            "refund_requested": {
                "type": "noul",
                "instructions": "Does the customer explicitly ask for money back?",
            },
        },
    })
    parsed = json.loads(out)
    print(json.dumps(parsed, indent=2)[:2000])
    assert parsed["success"], "decide call failed"

    print()
    print("== jev_decide: triage preset (bundled inline data) ==")
    out2 = tools.handle_decide({"state": "App crashes on launch after update.", "preset": "triage"})
    parsed2 = json.loads(out2)
    print(json.dumps(parsed2, indent=2)[:1500])
    assert parsed2["success"], "preset call failed"

    print()
    print("== /jev slash command ==")
    print(tools.handle_slash("noul; Is the user angry?; This is ridiculous, fix it NOW"))
    print()
    print("SMOKE OK" if parsed["success"] and parsed2["success"] else "SMOKE FAILED")
