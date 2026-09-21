"""Unit tests for the Jev plugin handlers and the stdlib client — no network."""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jev_hermes import client, tools  # noqa: E402


def _fake_result():
    return {
        "answers": {
            "answer": {
                "choice": "billing",
                "confidence": 0.91,
                "probabilities": {"billing": 0.91, "technical": 0.06, "other": 0.03},
            }
        },
        "action": {"act_probability": 0.87},
    }


class DecideTests(unittest.TestCase):
    def test_requires_state(self):
        out = json.loads(tools.handle_decide({"questions": {"q": {"type": "noul"}}}))
        self.assertFalse(out["success"])
        self.assertIn("state", out["error"])

    def test_requires_questions_or_preset(self):
        out = json.loads(tools.handle_decide({"state": "hello"}))
        self.assertFalse(out["success"])
        self.assertIn("questions", out["error"])

    def test_rejects_both_questions_and_preset(self):
        out = json.loads(tools.handle_decide({
            "state": "x", "preset": "triage",
            "questions": {"q": {"type": "noul"}},
        }))
        self.assertFalse(out["success"])

    def test_rejects_bad_question_type(self):
        out = json.loads(tools.handle_decide({
            "state": "x", "questions": {"q": {"type": "essay"}},
        }))
        self.assertFalse(out["success"])
        self.assertIn("essay", out["error"])

    def test_choice_requires_criteria(self):
        out = json.loads(tools.handle_decide({
            "state": "x", "questions": {"q": {"type": "choice", "instructions": "pick"}},
        }))
        self.assertFalse(out["success"])
        self.assertIn("criteria", out["error"])

    def test_success_path(self):
        with mock.patch.object(client, "predict",
                               return_value=(_fake_result(), 12.3, "jev", "jev-latest")):
            out = json.loads(tools.handle_decide({
                "state": "I was billed twice",
                "questions": {"answer": {"type": "choice", "instructions": "dept?",
                                         "criteria": ["billing", "technical", "other"]}},
            }))
        self.assertTrue(out["success"])
        self.assertEqual(out["answers"]["answer"]["choice"], "billing")
        self.assertEqual(out["meta"]["backend"], "jev")
        self.assertEqual(out["meta"]["latency_ms"], 12.3)
        self.assertEqual(out["action"]["act_probability"], 0.87)

    def test_preset_path(self):
        with mock.patch.object(client, "get_preset",
                               return_value={"q": {"type": "noul", "instructions": "x"}}), \
             mock.patch.object(client, "predict",
                               return_value=(_fake_result(), 1.0, "jev", "jev-latest")):
            out = json.loads(tools.handle_decide({"state": "ticket text", "preset": "triage"}))
        self.assertTrue(out["success"])

    def test_bundled_presets_match_names(self):
        for name in ("router", "guard", "moderation", "triage"):
            questions = client.get_preset(name)
            self.assertIsInstance(questions, dict)
            self.assertTrue(questions)
        with self.assertRaises(ValueError):
            client.get_preset("nope")

    def test_backend_unavailable_is_json_error(self):
        with mock.patch.object(client, "predict",
                               side_effect=client.BackendUnavailableError("TYPESAFE_API_KEY is not set")):
            out = json.loads(tools.handle_decide({
                "state": "x", "questions": {"q": {"type": "noul"}},
            }))
        self.assertFalse(out["success"])
        self.assertIn("TYPESAFE_API_KEY", out["error"])

    def test_never_raises(self):
        with mock.patch.object(client, "predict", side_effect=RuntimeError("boom")):
            out = json.loads(tools.handle_decide({
                "state": "x", "questions": {"q": {"type": "noul"}},
            }))
        self.assertFalse(out["success"])
        self.assertIn("boom", out["error"])


class SlashTests(unittest.TestCase):
    def test_help(self):
        out = json.loads(tools.handle_slash("help"))
        self.assertTrue(out["success"])
        self.assertTrue(any("preset triage" in u for u in out["usage"]))

    def test_noul_form(self):
        captured = {}

        def fake_decide(args, **kw):
            captured.update(args)
            return json.dumps({"success": True})

        with mock.patch.object(tools, "handle_decide", side_effect=fake_decide):
            tools.handle_slash("noul; Refund requested?; I want my money back")
        self.assertEqual(captured["state"], "I want my money back")
        self.assertEqual(captured["questions"]["answer"]["type"], "noul")

    def test_choice_form(self):
        captured = {}

        def fake_decide(args, **kw):
            captured.update(args)
            return json.dumps({"success": True})

        with mock.patch.object(tools, "handle_decide", side_effect=fake_decide):
            tools.handle_slash("choice; Which dept?; billing, technical, other; billed twice")
        q = captured["questions"]["answer"]
        self.assertEqual(q["type"], "choice")
        self.assertEqual(q["criteria"], ["billing", "technical", "other"])
        self.assertEqual(captured["state"], "billed twice")

    def test_bad_form(self):
        out = json.loads(tools.handle_slash("essay; whatever"))
        self.assertFalse(out["success"])

    def test_choice_needs_two_options(self):
        out = json.loads(tools.handle_slash("choice; pick; onlyone; state text"))
        self.assertFalse(out["success"])


class ClientTests(unittest.TestCase):
    """URL policy + predict() with a stubbed transport — no real API calls."""

    def test_check_url_allows_https(self):
        self.assertEqual(client._check_url("https://api.typesafe.ai/v1/systemone"),
                         ("https", "api.typesafe.ai"))

    def test_check_url_rejects_non_http(self):
        with self.assertRaises(client.BackendUnavailableError):
            client._check_url("file:///etc/passwd")

    def test_check_url_rejects_userinfo(self):
        with self.assertRaises(client.BackendUnavailableError):
            client._check_url("https://key@api.typesafe.ai/v1")

    def test_check_url_rejects_cleartext_off_lan(self):
        with self.assertRaises(client.BackendUnavailableError):
            client._check_url("http://api.typesafe.ai/v1")
        # cloud metadata endpoint is link-local, NOT in the allowed networks
        with self.assertRaises(client.BackendUnavailableError):
            client._check_url("http://169.254.169.254/")

    def test_check_url_allows_cleartext_loopback_and_lan(self):
        for url in ("http://localhost:8080/systemone", "http://127.0.0.1/systemone",
                    "http://192.168.1.10/systemone", "http://100.64.1.1/systemone"):
            client._check_url(url)

    def test_normalize_endpoint_path(self):
        self.assertEqual(client._normalize_endpoint_path("/api/alpha/decisions"),
                         "/api/alpha/decisions")
        for bad in ("", "systemone", "/api%2fdecisions", "/a b", "https://x/y",
                    "/path?q=1", "/path#frag", "/x\ny"):
            self.assertEqual(client._normalize_endpoint_path(bad), "/systemone")

    def test_join_url(self):
        self.assertEqual(
            client._join_url("https://api.typesafe.ai/v1/", "/systemone"),
            "https://api.typesafe.ai/v1/systemone")
        with self.assertRaises(client.BackendUnavailableError):
            client._join_url("https://api.typesafe.ai/v1#frag")

    def _run_predict(self, status, text, env=None):
        captured = {}

        def fake_transport(url, body, headers, timeout_s):
            captured["url"] = url
            captured["body"] = json.loads(body.decode("utf-8"))
            captured["headers"] = headers
            captured["timeout_s"] = timeout_s
            return status, text

        env = env or {}
        with mock.patch.object(client, "_transport", side_effect=fake_transport), \
             mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "sk-test", **env}):
            return client.predict("state text", {"q": {"type": "noul"}}), captured

    def test_predict_success_shape(self):
        (result, latency_ms, backend, model), captured = self._run_predict(
            200, json.dumps(_fake_result()))
        self.assertEqual(backend, "jev")
        self.assertEqual(model, "jev-latest")
        self.assertEqual(result["answers"]["answer"]["choice"], "billing")
        self.assertEqual(captured["url"], "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(captured["body"]["model"], "jev-latest")
        self.assertEqual(captured["body"]["state"], "state text")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test")
        self.assertGreaterEqual(latency_ms, 0.0)

    def test_predict_openrouter_config(self):
        env = {"JEV_BASE_URL": "https://openrouter.ai",
               "JEV_ENDPOINT_PATH": "/api/alpha/decisions",
               "JEV_API_KEY_ENV": "OPENROUTER_API_KEY",
               "JEV_MODEL": "typesafe/jev-1.13",
               "OPENROUTER_API_KEY": "or-key"}
        (result, _, _, model), captured = self._run_predict(200, json.dumps(_fake_result()), env)
        self.assertEqual(model, "typesafe/jev-1.13")
        self.assertEqual(captured["url"], "https://openrouter.ai/api/alpha/decisions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer or-key")

    def test_missing_key_raises_with_setup_instructions(self):
        env = {k: v for k, v in os.environ.items() if k != "TYPESAFE_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(client.BackendUnavailableError) as ctx:
                client.predict("x", {"q": {"type": "noul"}})
        self.assertIn("TYPESAFE_API_KEY", str(ctx.exception))

    def test_http_error_raises(self):
        with self.assertRaises(client.BackendUnavailableError) as ctx:
            self._run_predict(401, '{"error": "bad key"}')
        self.assertIn("http 401", str(ctx.exception))
        self.assertNotIn("bad key", str(ctx.exception))  # upstream body not echoed

    def test_malformed_json_raises(self):
        with self.assertRaises(client.BackendUnavailableError):
            self._run_predict(200, "not json")

    def test_missing_answers_raises(self):
        with self.assertRaises(client.BackendUnavailableError):
            self._run_predict(200, '{"ok": true}')

    def test_noul_out_of_range_raises(self):
        bad = {"answers": {"q": {"noul": 1.7}}}
        with self.assertRaises(client.BackendUnavailableError):
            self._run_predict(200, json.dumps(bad))

    def test_noul_non_finite_raises(self):
        with self.assertRaises(client.BackendUnavailableError):
            self._run_predict(200, '{"answers": {"q": {"noul": NaN}}}')

    def test_unknown_backend_rejected(self):
        with self.assertRaises(ValueError):
            client.predict("x", {"q": {"type": "noul"}}, backend="mlx")

    def test_bad_timeout_raises(self):
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "sk", "JEV_REQUEST_TIMEOUT_S": "0"}):
            with self.assertRaises(client.BackendUnavailableError):
                client.predict("x", {"q": {"type": "noul"}})


if __name__ == "__main__":
    unittest.main()
