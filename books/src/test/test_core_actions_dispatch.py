#!/usr/bin/env python3
"""Core actions: dispatch, unknown actions, settings and the LLM bridge."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:core", "tier:fast")

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))


class Boom(Exception):
    """An error the LLM layer raises when it cannot answer."""


class ActionDispatchTest(unittest.TestCase):
    def setUp(self):
        self.actions = _fixture.load_module(BOOK_ROOT, "actions")

    def test_every_advertised_action_has_a_handler(self):
        handlers = set(self.actions.DISPATCH)
        handlers.add("llm-ask")
        self.assertEqual(handlers, set(self.actions.ACTIONS))

    def test_unknown_action_returns_two_with_the_known_list(self):
        code, text = self.actions.run("nope")
        self.assertEqual(code, 2)
        self.assertIn("unknown action", text)

    def test_dispatch_invokes_the_handler_and_logs(self):
        handler = mock.Mock(return_value=(0, "ok"))
        with mock.patch.dict(self.actions.DISPATCH, {"status": handler}):
            code, text = self.actions.run("status")
        self.assertEqual((code, text), (0, "ok"))
        handler.assert_called_once()

    def test_llm_ask_routes_through_the_llm_layer(self):
        with mock.patch.object(self.actions._llm, "complete", return_value="回答") as complete:
            code, text = self.actions.run("llm-ask", prompt="问", scenario="summary")
        self.assertEqual(code, 0)
        self.assertIn("回答", text)
        self.assertEqual(complete.call_args.args[0], "问")

    def test_llm_ask_reports_a_provider_error_as_code_two(self):
        with mock.patch.object(
            self.actions._llm, "complete", side_effect=self.actions._llm.LLMError("down")
        ):
            code, text = self.actions.run("llm-ask", prompt="问")
        self.assertEqual(code, 2)
        self.assertIn("down", text)

    def test_the_child_environment_carries_the_selection(self):
        with mock.patch.dict(self.actions._SELECTION, {"book": "/b", "edition": "abridged"}):
            env = self.actions.child_env()
        self.assertEqual(env["BOOK_ROOT"], "/b")
        self.assertEqual(env["BOOK_EDITION"], "abridged")

    def test_an_empty_selection_leaves_the_environment_alone(self):
        with mock.patch.dict(self.actions._SELECTION, {"book": "", "edition": ""}):
            env = self.actions.child_env()
        self.assertNotIn("BOOK_ROOT", env)
        self.assertNotIn("BOOK_EDITION", env)

    def test_a_run_collects_both_streams(self):
        done = mock.Mock(returncode=1, stdout="out\n", stderr="err\n")
        with mock.patch.object(self.actions.subprocess, "run", return_value=done):
            code, text = self.actions._run("merge.py")
        self.assertEqual(code, 1)
        self.assertEqual(text, "out\nerr\n")

    def test_make_is_called_through_the_same_helper(self):
        done = mock.Mock(returncode=0, stdout="ok\n", stderr="")
        with mock.patch.object(self.actions.subprocess, "run", return_value=done) as run:
            code, text = self.actions._make("check", "--only", "lint")
        self.assertEqual((code, text), (0, "ok\n"))
        self.assertIn("make.py", run.call_args[0][0][1])

    def test_the_llm_usage_lines_name_a_failed_ledger(self):
        with mock.patch.object(self.actions._llm, "budget_line", side_effect=Boom("磁盘满")):
            self.actions._llm.LLMError = Boom
            line = self.actions._llm_lines()
        self.assertIn("用量记账不可用", line)

    def test_status_survives_an_llm_layer_that_cannot_answer(self):
        with mock.patch.object(self.actions._llm, "status", side_effect=Boom("无配置")):
            self.actions._llm.LLMError = Boom
            code, text = self.actions.status()
        self.assertEqual(code, 0, text[-200:])
        self.assertIn("llm       :", text)

    def test_the_volume_line_says_when_there_is_nothing_to_compare(self):
        code, line = self.actions._volume_line("not json")
        self.assertEqual(code, 0)
        self.assertIn("无基线可比", line)

    def test_the_volume_line_flags_a_shrunk_manuscript(self):
        code, line = self.actions._volume_line('{"count": 2}')
        self.assertEqual(code, 1)
        self.assertIn("2 项低于基线", line)
        self.assertIn("--update-baseline", line)

    def test_the_estimate_names_the_price_and_the_day_so_far(self):
        guess = {
            "model": "m",
            "prompt_tokens": 10,
            "max_tokens": 20,
            "cost_low": 0.001,
            "cost_high": 0.002,
            "currency": "USD",
        }
        with (
            mock.patch.object(self.actions._llm, "estimate", return_value=guess),
            mock.patch.object(self.actions._llm, "today_cost", return_value=0.5),
        ):
            line = self.actions.estimate_line("写一段小结")
        self.assertIn("≈ 0.0010-0.0020 USD", line)
        self.assertIn("今日已用", line)

    def test_an_unpriced_model_says_so_instead_of_inventing_a_number(self):
        guess = {
            "model": "",
            "prompt_tokens": 1,
            "max_tokens": 2,
            "cost_low": None,
            "cost_high": None,
            "currency": "USD",
        }
        with (
            mock.patch.object(self.actions._llm, "estimate", return_value=guess),
            mock.patch.object(self.actions._llm, "today_cost", return_value=0.0),
        ):
            line = self.actions.estimate_line("写一段小结")
        self.assertIn("未定价", line)
        self.assertNotIn("今日已用", line)

    def test_analyze_runs_three_stage_scripts_then_the_volume_check(self):
        calls = []

        def fake_run(script, *args):
            calls.append(script)
            return 0, ""

        with mock.patch.object(self.actions, "_run", side_effect=fake_run):
            code, text = self.actions.analyze()
        self.assertEqual(code, 0)
        self.assertEqual(
            [os.path.basename(c) for c in calls],
            ["digest.py", "outline.py", "chapters.py", "content_volume.py"],
        )
        self.assertIn("内容体积", text)

    def test_analyze_with_llm_passes_the_flag_only_to_chapters(self):
        calls = []

        def fake_run(script, *args):
            calls.append((os.path.basename(script), args))
            return 0, ""

        with mock.patch.object(self.actions, "_run", side_effect=fake_run):
            self.actions.analyze(use_llm=True)
        self.assertEqual(calls[2], ("chapters.py", ("--llm",)))
        self.assertEqual(calls[0], ("digest.py", ()))

    def test_analyze_passes_force_only_when_asked(self):
        calls = []

        def fake_run(script, *args):
            calls.append((os.path.basename(script), args))
            return 0, ""

        with mock.patch.object(self.actions, "_run", side_effect=fake_run):
            self.actions.analyze(force=True)
        self.assertEqual(calls[2], ("chapters.py", ("--force",)))

    def test_analyze_passes_refresh_only_when_asked(self):
        calls = []

        def fake_run(script, *args):
            calls.append((os.path.basename(script), args))
            return 0, ""

        with mock.patch.object(self.actions, "_run", side_effect=fake_run):
            self.actions.analyze(refresh=True)
        self.assertEqual(calls[2], ("chapters.py", ("--refresh-facts",)))

    def test_dispatched_analyze_forwards_the_switches(self):
        seen = {}

        def fake_run(script, *args):
            if script.endswith("chapters.py"):
                seen["args"] = args
            return 0, ""

        with mock.patch.object(self.actions, "_run", side_effect=fake_run):
            code, _text = self.actions.run("analyze", refresh=True)
        self.assertEqual(code, 0)
        self.assertEqual(seen["args"], ("--refresh-facts",))

    def test_the_refresh_action_is_advertised_and_dispatched(self):
        self.assertIn("analyze-refresh", self.actions.ACTIONS)
        self.assertIn("analyze-refresh", self.actions.DISPATCH)

    def test_a_zero_call_llm_run_explains_why(self):
        def fake_run(script, *args):
            return 0, ""

        with (
            mock.patch.object(self.actions, "_run", side_effect=fake_run),
            mock.patch.object(self.actions._llm, "take_totals", return_value={}),
            mock.patch.object(self.actions._llm, "since", return_value={"calls": 0}),
        ):
            _code, text = self.actions.analyze(use_llm=True)
        self.assertIn("没有触发导读/小结润色", text)

    def test_analyze_reports_a_shrunk_manuscript_as_a_failure(self):
        payload = '{"count": 2, "problems": ["ch1: bytes below floor"]}'

        def fake_run(script, *args):
            if script.endswith("content_volume.py"):
                return 0, payload
            return 0, ""

        with mock.patch.object(self.actions, "_run", side_effect=fake_run):
            code, text = self.actions.analyze()
        self.assertEqual(code, 1)
        self.assertIn("2 项低于基线", text)
        self.assertIn("--update-baseline", text)

    def test_analyze_without_a_baseline_stays_advisory(self):
        def fake_run(script, *args):
            return (0, "no baseline yet" if script.endswith("content_volume.py") else "")

        with mock.patch.object(self.actions, "_run", side_effect=fake_run):
            code, text = self.actions.analyze()
        self.assertEqual(code, 0)
        self.assertIn("无基线", text)

    def test_a_failing_stage_stops_the_pipeline(self):
        def fake_run(script, *args):
            return (1 if script.endswith("outline.py") else 0), ""

        with mock.patch.object(self.actions, "_run", side_effect=fake_run):
            code, _text = self.actions.analyze()
        self.assertEqual(code, 1)

    def test_settings_table_lists_the_writable_keys(self):
        rows = [{"key": "book.title", "value": "X", "description": "书名"}]
        with (
            mock.patch.dict("sys.modules", {}),
            mock.patch("core.settings.list_settings", return_value=rows),
        ):
            code, text = self.actions.settings_table()
        self.assertEqual(code, 0)
        self.assertIn("book.title", text)


class DeliverAllTest(unittest.TestCase):
    """The full-delivery action: every artifact, in dependency order, stop on failure."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.actions = _fixture.load_module(self.root, "actions")

    def test_it_builds_then_delivers_then_prints(self):
        calls = []

        def fake_make(mode, on_line=None):
            calls.append(("make", mode))
            return 0, f"{mode} ok\n"

        def fake_run(script, *args, on_line=None):
            calls.append(("run", script))
            return 0, f"{script} ok\n"

        with (
            mock.patch.object(self.actions, "_make", side_effect=fake_make),
            mock.patch.object(self.actions, "_run", side_effect=fake_run),
        ):
            code, text = self.actions.deliver_all()
        self.assertEqual(code, 0)
        self.assertEqual([call[1] for call in calls], ["build", "deliver", "render/print_pdf.py"])
        self.assertIn("print_pdf.py ok", text)

    def test_a_failed_step_stops_the_run(self):
        calls = []

        def fake_make(mode, on_line=None):
            calls.append(mode)
            return (0, "build ok\n") if mode == "build" else (1, "deliver failed\n")

        with (
            mock.patch.object(self.actions, "_make", side_effect=fake_make),
            mock.patch.object(self.actions, "_run") as run,
        ):
            code, text = self.actions.deliver_all()
        self.assertEqual(code, 1)
        self.assertEqual(calls, ["build", "deliver"])
        run.assert_not_called()
        self.assertIn("deliver failed", text)


class HeartbeatTest(unittest.TestCase):
    """A silent child still reports that it is working."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.actions = _fixture.load_module(self.root, "actions")

    def test_a_quiet_child_gets_a_heartbeat_line(self):
        lines = []
        command = [sys.executable, "-c", "import time; time.sleep(0.4)"]
        with mock.patch.object(self.actions, "HEARTBEAT_S", 0.05):
            code, _text = self.actions._invoke(command, on_line=lines.append)
        self.assertEqual(code, 0)
        self.assertTrue(any("仍在执行" in line for line in lines), lines)


class ReportingHelpersTest(unittest.TestCase):
    """The one-line reports compose the action output; each verdict has a branch."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.actions = _fixture.load_module(self.root, "actions")

    # -- 体积结论 ---------------------------------------------------------

    def test_zero_findings_means_the_baseline_holds(self):
        code, line = self.actions._volume_line('{"count": 0}')
        self.assertEqual(code, 0)
        self.assertIn("与基线一致", line)

    def test_findings_name_the_update_command(self):
        code, line = self.actions._volume_line('{"count": 3}')
        self.assertEqual(code, 1)
        self.assertIn("3 项低于基线", line)
        self.assertIn(self.actions.VOLUME_SCRIPT, line)

    # -- LLM 记账 ---------------------------------------------------------
    def test_a_broken_ledger_does_not_break_the_report(self):
        failure = self.actions._llm.LLMError("no ledger")
        with (
            mock.patch.object(self.actions._llm, "usage_line", side_effect=failure),
            mock.patch.object(self.actions._llm, "summary_line", side_effect=failure),
        ):
            self.assertIn("用量记账不可用", self.actions._llm_lines())
            self.assertIn("用量记账不可用", self.actions._llm_lines({"calls": 1}))

    def test_the_budget_warning_is_appended_when_present(self):
        with (
            mock.patch.object(self.actions._llm, "usage_line", return_value="用量：1 次"),
            mock.patch.object(self.actions._llm, "budget_line", return_value="⚠ 超出日限额"),
        ):
            text = self.actions._llm_lines()
        self.assertIn("用量：1 次", text)
        self.assertIn("⚠ 超出日限额", text)

    # -- 状态 -------------------------------------------------------------
    def test_a_provider_failure_is_reported_as_a_line(self):
        with mock.patch.object(
            self.actions._llm, "status", side_effect=self.actions._llm.LLMError("provider down")
        ):
            code, text = self.actions.status()
        self.assertEqual(code, 0)
        self.assertIn("provider down", text)


class AnalyzeReportTest(unittest.TestCase):
    """The ingest run ends with the volume verdict, and says what the LLM did."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.actions = _fixture.load_module(self.root, "actions")

    def run_analyze(self, *, volume='{"count": 0}', use_llm=True, fail_at=""):
        calls = []

        def fake_run(script, *args):
            calls.append((script, args))
            if script == fail_at:
                return 1, f"{script} failed"
            if script == self.actions.VOLUME_SCRIPT:
                return 0, volume
            return 0, f"{script} ok"

        with (
            mock.patch.object(self.actions, "_run", side_effect=fake_run),
            mock.patch.object(self.actions._llm, "take_totals", return_value={}),
            mock.patch.object(self.actions._llm, "since", return_value={"calls": 0}),
            mock.patch.object(self.actions._llm, "summary_line", return_value=""),
            mock.patch.object(self.actions._llm, "budget_line", return_value=""),
        ):
            code, text = self.actions.analyze(use_llm=use_llm)
        return code, text, calls

    def test_the_volume_verdict_is_part_of_the_report(self):
        code, text, _calls = self.run_analyze(volume='{"count": 2}', use_llm=False)
        self.assertEqual(code, 1)
        self.assertIn("2 项低于基线", text)

    def test_the_llm_run_explains_that_nothing_was_rewritten(self):
        code, text, _calls = self.run_analyze()
        self.assertEqual(code, 0)
        self.assertIn("本轮没有生成或重写的章节", text)

    def test_a_failing_script_stops_before_the_volume_check(self):
        code, text, calls = self.run_analyze(fail_at="ingest/outline.py", use_llm=False)
        self.assertEqual(code, 1)
        self.assertNotIn(self.actions.VOLUME_SCRIPT, [call[0] for call in calls])


class DispatchRoutingTest(unittest.TestCase):
    """Every action name reaches its handler; the report actions share one path."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.actions = _fixture.load_module(self.root, "actions")

    def test_every_report_action_reaches_its_own_handler(self):
        seen = []
        for name in ("build", "check", "test", "print", "deliver"):
            with mock.patch.object(
                self.actions,
                name if name != "print" else "print_edition",
                side_effect=lambda on_line=None, n=name: (seen.append(n), (0, n))[1],
            ):
                code, text = self.actions._dispatch(name, on_progress=None)
            self.assertEqual((code, text), (0, name))
        self.assertEqual(seen, ["build", "check", "test", "print", "deliver"])

    def test_an_unknown_action_is_refused_with_the_known_list(self):
        code, text = self.actions._dispatch("nope")
        self.assertEqual(code, 2)
        self.assertIn("unknown action", text)




class StreamHelpersTest(unittest.TestCase):
    """Streaming, unbuffering and the heartbeat, each callable on its own."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.actions = _fixture.load_module(self.root, "actions")

    def test_a_command_gains_unbuffered_mode_once(self):
        env = {}
        self.assertEqual(
            self.actions._unbuffered(["python", "x.py"], env), ["python", "-u", "x.py"]
        )
        self.assertEqual(env["PYTHONUNBUFFERED"], "1")
        self.assertEqual(
            self.actions._unbuffered(["python", "-u", "x.py"], env), ["python", "-u", "x.py"]
        )

    def test_a_bare_command_is_left_alone(self):
        self.assertEqual(self.actions._unbuffered(["tool"], {}), ["tool"])

    def test_every_line_is_collected_and_forwarded(self):
        seen: list[str] = []
        chunks = self.actions._stream(iter(["one\n", "two\n"]), seen.append)
        self.assertEqual(chunks, ["one\n", "two\n"])
        self.assertEqual(seen, ["one", "two"])

    def test_a_raising_callback_does_not_stop_the_stream(self):
        def explode(_line: str) -> None:
            raise RuntimeError("ui gone")

        chunks = self.actions._stream(iter(["one\n", "two\n"]), explode)
        self.assertEqual(len(chunks), 2)

    def test_without_a_callback_the_lines_are_still_collected(self):
        self.assertEqual(self.actions._stream(iter(["only\n"]), None), ["only\n"])

    def test_the_heartbeat_reports_while_the_child_is_silent(self):
        seen: list[str] = []
        with mock.patch.object(self.actions, "HEARTBEAT_S", 0.02):
            finished, _thread = self.actions._heartbeat(seen.append, 0.0)
            time.sleep(0.08)
            finished.set()
        self.assertTrue(any("仍在执行" in line for line in seen))


class LlmBridgeTest(unittest.TestCase):
    """The status and spend lines the LLM layer feeds, when it can and cannot answer."""

    def setUp(self):
        self.actions = _fixture.load_module(BOOK_ROOT, "actions")

    def test_status_names_the_default_provider_and_its_scenarios(self):
        status = {
            "default_provider": "deepseek",
            "providers": ["deepseek", "qwen"],
            "scenarios": ["summary", "translate"],
        }
        with mock.patch.object(self.actions._llm, "status", return_value=status):
            code, text = self.actions.status()
        self.assertEqual(code, 0)
        self.assertIn("default=deepseek", text)
        self.assertIn("providers=deepseek, qwen", text)
        self.assertIn("scenarios : summary, translate", text)

    def test_a_spend_tally_that_cannot_be_read_is_not_an_error(self):
        with mock.patch.object(self.actions, "_run", return_value=(0, '{"count": 0}')):
            with mock.patch.object(self.actions._llm, "take_totals", return_value={}):
                with mock.patch.object(self.actions, "_llm_lines", return_value=""):
                    with mock.patch.object(
                        self.actions._llm,
                        "since",
                        side_effect=self.actions._llm.LLMError("ledger gone"),
                    ):
                        code, text = self.actions.analyze(use_llm=True)
        self.assertEqual(code, 0, text[-300:])
        self.assertIn("没有触发导读/小结润色", text)

    def test_llm_spend_in_the_round_suppresses_the_idle_note(self):
        with mock.patch.object(self.actions, "_run", return_value=(0, '{"count": 0}')):
            with mock.patch.object(self.actions._llm, "take_totals", return_value={}):
                with mock.patch.object(self.actions, "_llm_lines", return_value=""):
                    with mock.patch.object(
                        self.actions._llm,
                        "since",
                        return_value={"calls": 3},
                    ):
                        code, text = self.actions.analyze(use_llm=True)
        self.assertEqual(code, 0, text[-300:])
        self.assertNotIn("没有触发导读/小结润色", text)

    def test_the_thin_action_wrappers_forward_their_step(self):
        with mock.patch.object(self.actions, "_make", return_value=(0, "ran")) as make:
            self.assertEqual(self.actions.check(), (0, "ran"))
            self.assertEqual(self.actions.test(), (0, "ran"))
            self.assertEqual(self.actions.doctor(), (0, "ran"))
        self.assertEqual(
            [call.args[0] for call in make.call_args_list], ["check", "test", "doctor"]
        )


if __name__ == "__main__":
    unittest.main()
