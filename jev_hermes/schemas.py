"""Tool schemas for the Jev Hermes plugin (what the LLM sees)."""

DECIDE_SCHEMA = {
    "name": "jev_decide",
    "description": (
        "Typed decision via the hosted Jev 'System One' API — returns calibrated "
        "probabilities in one request (~70-500 ms), no LLM tokens. Use for "
        "classification, routing, triage, urgency scoring, yes/no gating, moderation "
        "and escalation checks instead of reasoning it out yourself. Three question "
        "types: 'choice' (pick among labeled options), 'score' (ordinal rubric level), "
        "'noul' (boolean, returns P(true)). Provide either 'questions' or a built-in "
        "'preset'. Cannot generate text. Note: the state is sent to the configured "
        "hosted API — do not include secrets."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "state": {
                "description": "The situation to judge: plain text, a JSON object, or a list of conversation messages.",
            },
            "questions": {
                "type": "object",
                "description": (
                    "Map of question name -> {type: choice|score|noul, instructions: string, "
                    "criteria: [option labels] or {label: description}}. 'criteria' is required "
                    "for choice/score (the options or rubric levels), optional for noul. "
                    "Multiple questions are batched in one request."
                ),
            },
            "preset": {
                "type": "string",
                "enum": ["router", "guard", "moderation", "triage"],
                "description": "Use a built-in question set instead of 'questions': router (small vs frontier model), guard (jailbreak/prompt-injection), moderation, triage (support tickets).",
            },
            "model": {
                "type": "string",
                "description": "Model override for this call. Default: env JEV_MODEL or 'jev-latest' (OpenRouter: 'typesafe/jev-1.13').",
            },
        },
        "required": ["state"],
    },
}

STATUS_SCHEMA = {
    "name": "jev_status",
    "description": (
        "Report Jev plugin status: configured endpoint, whether the API key env var "
        "is set, current settings, and session metrics."
    ),
    "parameters": {"type": "object", "properties": {}},
}
