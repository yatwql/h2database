#!/usr/bin/env python3
"""lib._llm: the configurations and provider answers that must not be trusted.

A missing provider, an unknown one, a plain-http endpoint, a connection that
drops, a body that is not JSON, a response shaped differently than announced —
each is one guard in the layer, and each gets a case here. No socket is opened:
the transport is replaced before it is reached.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:lib", "tier:fast")

_fixture.ensure_tools_path()


class LlmCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.llm = _fixture.load_module(self.root, "_llm")

    def write_config(self, name: str, payload) -> str:
        path = os.path.join(self.root, "data", "config", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            if isinstance(payload, str):
                handle.write(payload)
            else:
                json.dump(payload, handle, ensure_ascii=False)
        return path

    def configure(self, providers: dict, *, default: str = "", routing: dict | None = None):
        config: dict = {"providers": providers, "routing": routing or {}}
        if default:
            config["default_provider"] = default
        patcher = mock.patch.object(self.llm, "providers", return_value=config)
        patcher.start()
        self.addCleanup(patcher.stop)
        return config


class ConfigFileTest(LlmCase):
    def test_a_config_file_that_is_not_json_names_itself(self):
        self.write_config("llm_provider.json", "{broken")
        with self.assertRaises(self.llm.LLMError) as caught:
            self.llm.providers()
        self.assertIn("invalid JSON", str(caught.exception))


class ResolveTest(LlmCase):
    def test_a_book_without_a_default_provider_is_refused(self):
        self.configure({}, routing={"scenario": {}})
        with self.assertRaises(self.llm.LLMError) as caught:
            self.llm.resolve("summary")
        self.assertIn("no provider resolved", str(caught.exception))

    def test_a_default_provider_that_is_not_declared_is_refused(self):
        self.configure({"mock": {"kind": "mock"}}, default="ghost")
        with self.assertRaises(self.llm.LLMError) as caught:
            self.llm.resolve("summary")
        self.assertIn("unknown provider 'ghost'", str(caught.exception))


class TransportTest(LlmCase):
    def test_a_plain_http_endpoint_is_refused_before_connecting(self):
        with self.assertRaises(self.llm.LLMError) as caught:
            self.llm._post_json("http://example.invalid/v1", {}, "k", 5)
        self.assertIn("must be https", str(caught.exception))

    def connection(self, *, raw: bytes = b"{}", raise_on_request=None):
        connection = mock.MagicMock()
        if raise_on_request is not None:
            connection.request.side_effect = raise_on_request
        else:
            connection.getresponse.return_value.read.return_value = raw
        return connection

    def test_a_dropped_connection_becomes_one_message(self):
        with mock.patch.object(
            self.llm.http.client,
            "HTTPSConnection",
            return_value=self.connection(raise_on_request=OSError("reset")),
        ):
            with self.assertRaises(self.llm.LLMError) as caught:
                self.llm._post_json("https://example.invalid/v1", {}, "k", 5)
        self.assertIn("request failed: reset", str(caught.exception))

    def test_a_body_that_is_not_json_becomes_one_message(self):
        with mock.patch.object(
            self.llm.http.client,
            "HTTPSConnection",
            return_value=self.connection(raw=b"<html>oops</html>"),
        ):
            with self.assertRaises(self.llm.LLMError) as caught:
                self.llm._post_json("https://example.invalid/v1", {}, "k", 5)
        self.assertIn("invalid JSON", str(caught.exception))


class ProviderResponseTest(LlmCase):
    def test_an_anthropic_answer_without_content_is_refused(self):
        spec = {
            "kind": "anthropic",
            "base_url": "https://a.invalid",
            "api_key_env": "ANTHROPIC_KEY",
        }
        os.environ["ANTHROPIC_KEY"] = "k"
        self.addCleanup(os.environ.pop, "ANTHROPIC_KEY", None)
        with mock.patch.object(self.llm, "_post_json", return_value={"stop_reason": "x"}):
            with self.assertRaises(self.llm.LLMError) as caught:
                self.llm._complete_anthropic("提示", "primary", spec, {}, None)
        self.assertIn("unexpected provider response", str(caught.exception))

    def test_an_openai_answer_without_choices_is_refused(self):
        spec = {
            "kind": "openai-compatible",
            "base_url": "https://b.invalid",
            "api_key_env": "OPENAI_KEY",
        }
        os.environ["OPENAI_KEY"] = "k"
        self.addCleanup(os.environ.pop, "OPENAI_KEY", None)
        with mock.patch.object(self.llm, "_post_json", return_value={"error": "quota"}):
            with self.assertRaises(self.llm.LLMError) as caught:
                self.llm._attempt("提示", "primary", spec, {}, None)
        self.assertIn("unexpected provider response", str(caught.exception))

    def test_a_model_named_by_the_caller_wins_over_the_configuration(self):
        self.assertEqual(self.llm._model_for("primary", {"models": ["m1"]}, "m9"), "m9")

    def test_an_environment_variable_without_a_value_falls_through_to_the_key_file(self):
        self.write_config("llm_key.json", {"keys": {"primary": "from-file"}})
        os.environ["EMPTY_KEY"] = ""
        self.addCleanup(os.environ.pop, "EMPTY_KEY", None)
        spec = {"api_key_env": "EMPTY_KEY"}
        self.assertEqual(self.llm._api_key("primary", spec), "from-file")


class PricingTest(LlmCase):
    def test_a_book_without_a_price_table_has_none(self):
        self.assertEqual(self.llm.pricing(), {})

    def test_a_price_table_that_cannot_be_parsed_reads_as_no_table(self):
        self.write_config("llm_pricing.json", "[")
        self.assertEqual(self.llm.pricing(), {})


class MoneyTest(LlmCase):
    def test_an_unpriced_model_says_so(self):
        self.assertEqual(self.llm._money(None), "未定价")


class UsageLedgerTest(LlmCase):
    def ledger(self, *lines: str) -> str:
        path = self.llm.usage_log()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        return path

    def test_a_corrupt_ledger_line_is_skipped_and_yesterday_is_not_counted(self):
        self.ledger(
            "not json",
            json.dumps({"at": "2000-01-01T00:00:00", "cost": 9}),
            json.dumps({"at": self.llm._utcnow(), "cost": 0.5}),
        )
        self.assertAlmostEqual(self.llm.today_cost(), 0.5)

    def test_an_unreadable_ledger_counts_as_nothing_spent(self):
        self.ledger("{}")
        with mock.patch.object(self.llm._fsutil, "read_lines", side_effect=OSError("gone")):
            self.assertEqual(self.llm.today_cost(), 0.0)

    def test_a_spend_below_the_ceiling_prints_no_warning(self):
        log = self.ledger(json.dumps({"at": self.llm._utcnow(), "cost_display": 0.25}))
        self.assertTrue(os.path.isfile(log))
        with mock.patch.object(self.llm, "settings", return_value={"daily_cost_limit": 10}):
            self.assertEqual(self.llm.budget_line(), "")


if __name__ == "__main__":
    unittest.main()
