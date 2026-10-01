"""Unit tests for the question-shape normalization in ``client.predict``.

``choice`` and ``score`` are rejected by the live endpoint with HTTP 400 unless
``instructions`` is present, and ``choice.criteria`` must be a record — a bare
list of labels is refused with ``expected record, received array``. Both are
repaired locally so the documented "list or mapping" wording in the bundled
skill does not produce an opaque upstream 400.
"""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jev_hermes import client  # noqa: E402


def _capture_body(questions):
    """Run predict with the transport stubbed; return the JSON body that was sent."""
    sent = {}

    def _fake_transport(url, body, headers, timeout):
        sent["body"] = body
        sent["url"] = url
        return 200, '{"answers": {}}'

    with mock.patch.object(client, "_api_key", return_value="k"), \
            mock.patch.object(client, "_transport", _fake_transport):
        client.predict("state", questions)
    return json.loads(sent["body"])


class NormalizeQuestionsTests(unittest.TestCase):
    def test_choice_list_is_converted_to_a_record(self):
        body = _capture_body({
            "pick": {
                "type": "choice",
                "instructions": "Pick the option to recommend.",
                "criteria": ["Alpha", "Beta"],
            }
        })
        self.assertEqual(
            body["questions"]["pick"]["criteria"],
            {"Alpha": "Alpha", "Beta": "Beta"},
        )

    def test_choice_record_is_passed_through(self):
        body = _capture_body({
            "pick": {
                "type": "choice",
                "instructions": "Pick the option to recommend.",
                "criteria": {"Alpha": "the first one", "Beta": "the second one"},
            }
        })
        self.assertEqual(
            body["questions"]["pick"]["criteria"],
            {"Alpha": "the first one", "Beta": "the second one"},
        )

    def test_score_record_is_converted_to_an_ordered_list(self):
        body = _capture_body({
            "q": {
                "type": "score",
                "instructions": "Rate the risk.",
                "criteria": {"low": "none", "mid": "some", "high": "severe"},
            }
        })
        self.assertEqual(body["questions"]["q"]["criteria"], ["low", "mid", "high"])

    def test_choice_without_instructions_is_refused_locally(self):
        with self.assertRaises(ValueError) as ctx:
            _capture_body({"pick": {"type": "choice", "criteria": ["Alpha", "Beta"]}})
        self.assertIn("instructions is required", str(ctx.exception))

    def test_score_without_instructions_is_refused_locally(self):
        with self.assertRaises(ValueError) as ctx:
            _capture_body({"q": {"type": "score", "criteria": ["low", "high"]}})
        self.assertIn("instructions is required", str(ctx.exception))

    def test_blank_instructions_is_refused(self):
        with self.assertRaises(ValueError):
            _capture_body({
                "pick": {"type": "choice", "instructions": "   ", "criteria": ["A", "B"]}
            })

    def test_noul_needs_neither_instructions_nor_criteria(self):
        body = _capture_body({"q": {"type": "noul", "instructions": "Is this safe?"}})
        self.assertEqual(body["questions"]["q"]["type"], "noul")

    def test_choice_criteria_string_is_refused(self):
        with self.assertRaises(ValueError):
            _capture_body({
                "pick": {
                    "type": "choice",
                    "instructions": "Pick one.",
                    "criteria": "Alpha|Beta",
                }
            })

    def test_choice_criteria_with_non_string_item_is_refused(self):
        with self.assertRaises(ValueError):
            _capture_body({
                "pick": {
                    "type": "choice",
                    "instructions": "Pick one.",
                    "criteria": ["Alpha", 7],
                }
            })

    def test_score_criteria_with_non_string_item_is_refused(self):
        with self.assertRaises(ValueError):
            _capture_body({
                "q": {
                    "type": "score",
                    "instructions": "Rate it.",
                    "criteria": ["low", None],
                }
            })


if __name__ == "__main__":
    unittest.main()
