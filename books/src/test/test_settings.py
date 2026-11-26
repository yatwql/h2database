#!/usr/bin/env python3
"""Tests for the writable settings layer and the TUI/CLI surfaces on top of it."""

import importlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:infra", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, "lib"))


class SettingsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def settings(self):
        return _fixture.load_module(self.root, "settings")

    def read(self, rel: str) -> str:
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()


class HeaderGlanceTest(SettingsCase):
    """The header answers "how much left" without running an action."""

    def test_summary_carries_spend_and_volume_margin(self):
        summary = self.settings().summary()
        self.assertIn("llm_spend", summary)
        self.assertIn("volume_margin", summary)

    def test_the_spend_line_uses_the_display_currency(self):
        summary = self.settings().summary()
        self.assertTrue(
            summary["llm_spend"].startswith("¥") or summary["llm_spend"] == "—",
            summary["llm_spend"],
        )

    def test_a_book_without_a_baseline_says_dash(self):
        summary = self.settings().summary()
        self.assertEqual(summary["volume_margin"], "—")

    def test_the_margin_names_lines_and_both_counts(self):
        room = {
            "lines": 40097,
            "baseline": 36893,
            "floor": 35048,
            "above": 5049,
            "margin_pct": 14.4,
        }
        settings = self.settings()
        with mock.patch.object(settings._volume, "headroom", lambda: room):
            text = settings.volume_summary()
        self.assertIn("40,097 行", text)
        self.assertIn("再少 5,049 行", text)
        self.assertIn("内容变薄", text)
        self.assertNotIn("%", text)  # a percentage here reads as growth
        self.assertNotIn("下限", text)  # the gate's vocabulary, not the reader's

    def test_the_volume_margin_is_measured_against_the_floor(self):
        volume = _fixture.load_module(self.root, "_volume")
        baseline = {"manuscript": {"total": {"lines": 100}}, "thresholds": {"floor_ratio": 0.95}}
        path = os.path.join(self.root, "data", "baselines")
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "content-volume.json"), "w", encoding="utf-8") as fh:
            json.dump(baseline, fh)
        current = volume.current_lines()
        room = volume.headroom()
        self.assertEqual(room["baseline"], 100)
        self.assertEqual(room["lines"], current)
        self.assertEqual(room["floor"], 95)


class TestSettings(SettingsCase):
    def test_list_covers_known_keys(self):
        rows = {row["key"] for row in self.settings().list_settings()}
        self.assertEqual(
            rows,
            {
                "title",
                "version",
                "manuscript",
                "dist",
                "languages",
                "log.level",
                "llm.provider",
                "llm.daily_cost_limit",
                "llm.ingest_prose",
            },
        )

    def test_set_title_persists_to_toml(self):
        settings = self.settings()
        settings.set_value("title", "新的书名")
        self.assertIn('title = "新的书名"', self.read("data/book/book.toml"))

    def test_set_dist_persists(self):
        settings = self.settings()
        settings.set_value("dist", "out")
        self.assertIn('dist = "out"', self.read("data/book/book.toml"))

    def test_set_languages_list(self):
        settings = self.settings()
        self.assertEqual(settings.set_value("languages", "java, python"), "java,python")
        payload = json.loads(self.read("data/config/base.json"))
        self.assertEqual(payload["sources"]["languages"], ["java", "python"])

    def test_set_ingest_prose_writes_a_toml_boolean(self):
        settings = self.settings()
        self.assertEqual(settings.set_value("llm.ingest_prose", "true"), "true")
        with open(os.path.join(self.root, "data", "book", "book.toml"), encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("ingest_prose = true", body)
        self.assertEqual(settings.get("llm.ingest_prose"), "true")

    def test_a_bad_boolean_is_refused(self):
        with self.assertRaises(ValueError):
            self.settings().set_value("llm.ingest_prose", "maybe")

    def test_the_daily_cost_limit_is_writable_and_non_negative(self):
        settings = self.settings()
        self.assertEqual(settings.set_value("llm.daily_cost_limit", "3"), "3.0")
        self.assertEqual(settings.get("llm.daily_cost_limit"), "3.0")
        with self.assertRaises(ValueError):
            settings.set_value("llm.daily_cost_limit", "-1")

    def test_set_log_level_validates(self):
        settings = self.settings()
        with self.assertRaises(ValueError):
            settings.set_value("log.level", "LOUD")
        self.assertEqual(settings.set_value("log.level", "debug"), "DEBUG")

    def test_set_llm_provider_persists(self):
        settings = self.settings()
        settings.set_value("llm.provider", "mock")
        payload = json.loads(self.read("data/config/llm_provider.json"))
        self.assertEqual(payload["default_provider"], "mock")

    def test_empty_value_rejected(self):
        with self.assertRaises(ValueError):
            self.settings().set_value("title", "   ")

    def test_unknown_key_rejected(self):
        with self.assertRaises(KeyError):
            self.settings().set_value("nope", "x")

    def test_summary_shape(self):
        summary = self.settings().summary()
        for key in (
            "title",
            "version",
            "manuscript",
            "dist",
            "languages",
            "log_level",
            "llm_provider",
        ):
            self.assertIn(key, summary)


class TestTuiSurface(SettingsCase):
    def test_header_shows_identity(self):
        tui = _fixture.load_module(self.root, "tui")
        text = tui.header()
        self.assertIn("v", text)
        self.assertIn("手稿", text)
        self.assertIn("LLM", text)

    def test_the_frequent_actions_sit_on_the_first_level(self):
        tui = _fixture.load_module(self.root, "tui")
        text = tui.menu_text("main")
        for label in ("源码 → 手稿", "手稿 → Markdown + HTML", "质量", "配置"):
            self.assertIn(label, text)

    def test_every_second_level_screen_offers_back(self):
        tui = _fixture.load_module(self.root, "tui")
        for screen in ("quality", "config"):
            with self.subTest(screen=screen):
                self.assertIn("返回主菜单", tui.menu_text(screen))

    def test_once_status_shows_the_book_identity(self):
        code, out = _fixture.run_inproc(self.root, "tui.py", "--once", "status")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("测试之书", out)
        self.assertIn("chapters", out)

    def test_quit_with_zero(self):
        tui = _fixture.load_module(self.root, "tui")
        import io
        from contextlib import redirect_stdout

        old = sys.stdin
        sys.stdin = io.StringIO("0\n")
        try:
            with redirect_stdout(io.StringIO()):
                code = tui.main([])
        finally:
            sys.stdin = old
        self.assertEqual(code, 0)

    def test_quit_with_q(self):
        tui = _fixture.load_module(self.root, "tui")
        import io
        from contextlib import redirect_stdout

        old = sys.stdin
        sys.stdin = io.StringIO("q\n")
        try:
            with redirect_stdout(io.StringIO()):
                code = tui.main([])
        finally:
            sys.stdin = old
        self.assertEqual(code, 0)

    def test_ctrl_c_exits_cleanly(self):
        tui = _fixture.load_module(self.root, "tui")
        import io
        from contextlib import redirect_stdout

        class Interrupting(io.StringIO):
            def readline(self, *args, **kwargs):
                raise KeyboardInterrupt

        old = sys.stdin
        sys.stdin = Interrupting()
        try:
            with redirect_stdout(io.StringIO()):
                code = tui.main([])
        finally:
            sys.stdin = old
        self.assertEqual(code, 0)

    def test_configure_rejects_unknown_choice(self):
        tui = _fixture.load_module(self.root, "tui")
        answers = iter(["99"])
        with redirect_stdout(io.StringIO()):
            result = tui.configure(reader=lambda _prompt: next(answers))
        self.assertIn("未修改", result)


class TestCliSurface(SettingsCase):
    def test_cli_settings_lists_keys(self):
        code, out = _fixture.run_inproc(self.root, "cli.py", "settings")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("llm.provider", out)

    def test_cli_settings_set(self):
        code, out = _fixture.run_inproc(self.root, "cli.py", "settings", "set", "title", "CLI 书名")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("CLI 书名", self.read("data/book/book.toml"))

    def test_cli_settings_set_rejects_unknown_key(self):
        code, out = _fixture.run_inproc(self.root, "cli.py", "settings", "set", "nope", "x")
        self.assertEqual(code, 2)
        self.assertIn("error", out)




class SettingsEdgeTest(unittest.TestCase):
    """Validation messages, TOML rewriting, provider moves and the spend line."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "settings")

    def write_toml(self, path: str, text: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_the_provider_file_sits_beside_the_config(self):
        self.assertTrue(self.mod.provider_json().endswith("llm_provider.json"))

    def test_an_unknown_key_raises(self):
        with self.assertRaises(KeyError):
            self.mod.get("no.such.key")

    def test_a_list_setting_reads_back_comma_separated(self):
        from types import SimpleNamespace

        path = os.path.join(self.tmp.name, "book.toml")
        self.write_toml(path, '[sections]\nlanguages = "zh,en"\n')
        row = (path, "sections", "languages", "list", "语言")
        with (
            mock.patch.object(self.mod, "spec_table", return_value={"sections.languages": row}),
            mock.patch.object(
                self.mod._fsutil,
                "read_text",
                return_value='[sections]\nlanguages = "zh,en"\n',
                create=True,
            ),
        ):
            self.assertEqual(self.mod.get("sections.languages"), "zh,en")
        self.assertIsInstance(row, tuple)
        self.assertTrue(SimpleNamespace)

    def test_validation_messages_name_the_reason(self):
        spec = self.mod.spec_table()
        number = next((key for key, row in spec.items() if row[3] == "number"), None)
        level = next((key for key, row in spec.items() if row[3] == "level"), None)
        list_key = next((key for key, row in spec.items() if row[3] == "list"), None)
        if number:
            with self.assertRaises(ValueError) as bad:
                self.mod._validate(number, "many")
            self.assertIn("number", str(bad.exception))
        if level:
            with self.assertRaises(ValueError) as bad:
                self.mod._validate(level, "LOUD")
            self.assertIn("log.level", str(bad.exception))
        if list_key:
            with self.assertRaises(ValueError) as bad:
                self.mod._validate(list_key, " , ")
            self.assertIn("at least one value", str(bad.exception))

    def test_a_literal_is_written_into_an_existing_section(self):
        path = os.path.join(self.tmp.name, "book.toml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('[book]\ntitle = "x"\n\n[toolchain]\n')
        self.mod._write_toml_literal(path, "toolchain", "print_scale", "0.71")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("print_scale = 0.71", text)
        self.assertEqual(text.count("[toolchain]"), 1)

    def test_a_missing_section_is_appended(self):
        path = os.path.join(self.tmp.name, "book2.toml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('[book]\ntitle = "x"\n')
        self.mod._write_toml_literal(path, "archive", "retention_days", "30")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("[archive]", text)
        self.assertIn("retention_days = 30", text)

    def test_a_missing_source_tree_reads_as_empty(self):
        with mock.patch.object(
            self.mod._config, "source_tree", side_effect=RuntimeError("unconfigured")
        ):
            self.assertEqual(self.mod._source_dir(), "")

    def test_the_spend_line_shows_the_currency_symbol_and_the_ceiling(self):
        fake = types.SimpleNamespace(
            today_cost=lambda: 1.5,
            daily_limit=lambda: 5.0,
            display_currency=lambda: "USD",
            SYMBOLS={"USD": "$"},
            LLMError=RuntimeError,
        )
        lib = importlib.import_module("lib")
        with mock.patch.object(lib, "_llm", fake):
            self.assertEqual(self.mod.spend_summary(), "$1.50/$5.00")

    def test_an_unconfigured_llm_still_gets_a_header_cell(self):
        def fail():
            raise RuntimeError("no config")

        fake = types.SimpleNamespace(
            today_cost=fail,
            daily_limit=lambda: 0.0,
            display_currency=lambda: "USD",
            SYMBOLS={},
            LLMError=RuntimeError,
        )
        lib = importlib.import_module("lib")
        with mock.patch.object(lib, "_llm", fake):
            self.assertEqual(self.mod.spend_summary(), "—")

    def test_a_literal_already_in_its_section_is_replaced_in_place(self):
        path = os.path.join(self.tmp.name, "book3.toml")
        self.write_toml(path, "[toolchain]\nprint_scale = 0.65\nother = 1\n")
        self.mod._write_toml_literal(path, "toolchain", "print_scale", "0.71")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("print_scale = 0.71", text)
        self.assertNotIn("0.65", text)
        self.assertEqual(text.count("[toolchain]"), 1)

    def test_a_json_list_setting_reads_back_comma_separated(self):
        path = os.path.join(self.tmp.name, "base.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"sources": {"roots": ["h2/src/main", "h2/h2"]}}, handle)
        row = (path, "sources", "roots", "list", "源码树")
        with mock.patch.object(self.mod, "spec_table", return_value={"sources.roots": row}):
            self.assertEqual(self.mod.get("sources.roots"), "h2/src/main,h2/h2")

    def test_the_first_provider_cannot_move_above_the_top(self):
        providers = os.path.join(self.root, "data", "config", "llm_provider.json")
        with open(providers, "w", encoding="utf-8") as handle:
            json.dump({"providers": {"mock": {"priority": 10}, "qwen": {"priority": 20}}}, handle)
        order = [row["name"] for row in self.mod.provider_order()]
        self.assertEqual(order, ["mock", "qwen"])
        self.assertEqual(self.mod.move_provider(order[0], -1)[: len(order[0])], order[0])
        self.assertEqual([row["name"] for row in self.mod.provider_order()], order)


if __name__ == "__main__":
    unittest.main()
