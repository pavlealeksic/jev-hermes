"""Request-body shaping: TypeSafe requires choice.criteria as a dict and score.criteria as a list."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jev_hermes import client  # noqa: E402


class CriteriaShapeTests(unittest.TestCase):
    def _body(self, questions):
        return json.loads(client._build_body("jev-latest", "state", questions))["questions"]

    def test_choice_list_becomes_label_dict(self):
        q = self._body({"q": {"type": "choice", "instructions": "x", "criteria": ["a", "b"]}})
        self.assertEqual(q["q"]["criteria"], {"a": "a", "b": "b"})

    def test_choice_dict_untouched(self):
        crit = {"a": "desc a", "b": "desc b"}
        q = self._body({"q": {"type": "choice", "instructions": "x", "criteria": crit}})
        self.assertEqual(q["q"]["criteria"], crit)

    def test_score_list_untouched(self):
        q = self._body({"q": {"type": "score", "instructions": "x", "criteria": ["low", "high"]}})
        self.assertEqual(q["q"]["criteria"], ["low", "high"])

    def test_noul_untouched(self):
        q = self._body({"q": {"type": "noul", "instructions": "x"}})
        self.assertNotIn("criteria", q["q"])

    def test_input_not_mutated(self):
        spec = {"type": "choice", "instructions": "x", "criteria": ["a"]}
        self._body({"q": spec})
        self.assertEqual(spec["criteria"], ["a"])


if __name__ == "__main__":
    unittest.main()