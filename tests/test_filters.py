"""Unit tests for filters, metrics, and the status/keycheck slash surface."""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jev_hermes import client, filters, metrics, tools  # noqa: E402

BIG_OUTPUT = "A" * 5000 + "B" * 3000  # 8000 chars > 6000 default threshold


def _predict_returning(p_needed):
    return ({"answers": {"needed": {"type": "noul", "noul": p_needed}}}, 5.0, "jev", "jev-latest")


class FilterTests(unittest.TestCase):
    def setUp(self):
        self._env = mock.patch.dict(os.environ, {"JEV_FILTER_OUTPUT": "1"})
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_disabled_by_default(self):
        with mock.patch.dict(os.environ, {"JEV_FILTER_OUTPUT": "0"}):
            self.assertIsNone(filters.transform_terminal_output(
                command="npm install", output=BIG_OUTPUT, returncode=0))

    def test_nonzero_returncode_untouched(self):
        with mock.patch.object(client, "predict") as p:
            self.assertIsNone(filters.transform_terminal_output(
                command="npm test", output=BIG_OUTPUT, returncode=1))
            p.assert_not_called()

    def test_short_output_untouched(self):
        with mock.patch.object(client, "predict") as p:
            self.assertIsNone(filters.transform_terminal_output(
                command="ls", output="small", returncode=0))
            p.assert_not_called()

    def test_needed_output_passes_through(self):
        with mock.patch.object(client, "predict", return_value=_predict_returning(0.9)):
            self.assertIsNone(filters.transform_terminal_output(
                command="npm install", output=BIG_OUTPUT, returncode=0))

    def test_disposable_output_truncated(self):
        with mock.patch.object(client, "predict", return_value=_predict_returning(0.05)):
            out = filters.transform_terminal_output(
                command="npm install", output=BIG_OUTPUT, returncode=0)
        self.assertIsNotNone(out)
        self.assertIn("[jev: truncated", out)
        self.assertTrue(out.startswith("A" * 100))
        self.assertTrue(out.endswith("B" * 500))
        self.assertLess(len(out), len(BIG_OUTPUT))

    def test_tool_result_skips_terminal_tool(self):
        with mock.patch.object(client, "predict") as p:
            self.assertIsNone(filters.transform_tool_result(
                tool_name="terminal", result=BIG_OUTPUT, status="success"))
            p.assert_not_called()

    def test_tool_result_skips_errors(self):
        with mock.patch.object(client, "predict") as p:
            self.assertIsNone(filters.transform_tool_result(
                tool_name="browser", result=BIG_OUTPUT, status="error"))
            p.assert_not_called()

    def test_fail_open_on_exception(self):
        with mock.patch.object(client, "predict", side_effect=RuntimeError("boom")):
            self.assertIsNone(filters.transform_terminal_output(
                command="x", output=BIG_OUTPUT, returncode=0))
            self.assertIsNone(filters.transform_tool_result(
                tool_name="browser", result=BIG_OUTPUT, status="success"))


class MetricsTests(unittest.TestCase):
    def test_record_and_snapshot(self):
        before = metrics.snapshot()
        metrics.record_decision(10.0, feature="tool_calls")
        metrics.record_truncation(400)
        metrics.record_error()
        after = metrics.snapshot()
        self.assertEqual(after["decisions"], before["decisions"] + 1)
        self.assertEqual(after["tool_calls"], before["tool_calls"] + 1)
        self.assertEqual(after["chars_saved"], before["chars_saved"] + 400)
        self.assertEqual(after["est_tokens_saved"], before["est_tokens_saved"] + 100)
        self.assertEqual(after["errors"], before["errors"] + 1)

    def test_render(self):
        self.assertIn("decisions:", metrics.render())


class SlashStatusTests(unittest.TestCase):
    def test_keycheck_without_key(self):
        env = {k: v for k, v in os.environ.items() if k != "TYPESAFE_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            out = json.loads(tools.handle_slash("keycheck"))
        self.assertFalse(out["success"])
        self.assertIn("TYPESAFE_API_KEY", out["error"])
        self.assertIn("setup", out)

    def test_keycheck_with_key(self):
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "sk-secret"}):
            out = json.loads(tools.handle_slash("keycheck"))
        self.assertTrue(out["success"])
        self.assertNotIn("sk-secret", json.dumps(out))  # never leak the key

    def test_stats(self):
        out = tools.handle_slash("stats")
        self.assertIn("decisions:", out)

    def test_help_lists_forms(self):
        out = json.loads(tools.handle_slash("help"))
        self.assertTrue(any("stats" in u for u in out["usage"]))
        self.assertTrue(any("keycheck" in u for u in out["usage"]))

    def test_status_embeds_metrics(self):
        out = json.loads(tools.handle_status({}))
        self.assertTrue(out["success"])
        self.assertIn("metrics", out)
        self.assertIn("decisions", out["metrics"])
        self.assertEqual(out["api"]["backend"], "jev")
        self.assertEqual(out["context_engine"]["registered_as"], "jev")


if __name__ == "__main__":
    unittest.main()
