#!/usr/bin/env python3
"""Architecture gate: each rule is proven with a synthetic source tree."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()


class ArchitectureRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.book_root = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))
        self.mod = _fixture.load_module(self.book_root, "check_architecture")

    def write(self, rel: str, body: str) -> str:
        path = os.path.join(self.tmp.name, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        return path

    def problems(self, rel: str, body: str) -> list[str]:
        path = self.write(rel, body)
        return self.mod.check(path, self.tmp.name)

    def assert_rule(self, rel: str, body: str, needle: str) -> None:
        found = self.problems(rel, body)
        self.assertTrue(any(needle in p for p in found), f"{needle!r} not in {found}")

    # -- book identity ----------------------------------------------------
    def test_book_identity_literal_is_reported(self):
        path = self.write("render/x.py", '"""d"""\nMERGED = "h2-source-code-analysis.md"\n')
        with mock.patch.object(self.mod, "scripts", return_value=[path]):
            problems = self.mod.check_book_identity()
        self.assertEqual(len(problems), 1)
        self.assertIn("book identity", problems[0])

    def test_a_generic_name_passes(self):
        path = self.write("render/y.py", '"""d"""\nMERGED = _config.MERGED_NAME\n')
        with mock.patch.object(self.mod, "scripts", return_value=[path]):
            self.assertEqual(self.mod.check_book_identity(), [])

    # -- dependency matrix ------------------------------------------------
    def test_lib_may_not_import_an_engine(self):
        self.assert_rule("lib/x.py", '"""d"""\nfrom audit import smart\n', "may not import")

    def test_core_may_import_lib_only(self):
        self.write("lib/_config.py", '"""d"""\n')
        self.assertEqual(self.problems("core/x.py", '"""d"""\nfrom lib import _config\n'), [])
        self.assert_rule("core/y.py", '"""d"""\nfrom render import to_html\n', "may not import")

    def test_engine_may_not_import_core(self):
        self.assert_rule("audit/x.py", '"""d"""\nfrom core import actions\n', "may not import")

    def test_channel_may_import_core(self):
        self.write("core/actions.py", '"""d"""\n')
        self.assertEqual(self.problems("app/x.py", '"""d"""\nfrom core import actions\n'), [])

    def test_channel_may_not_import_an_engine(self):
        self.assert_rule("app/x.py", '"""d"""\nfrom render import to_html\n', "channel imports")

    def test_sibling_engines_may_not_import_each_other(self):
        self.assert_rule(
            "audit/x.py", '"""d"""\nfrom manuscript import glossary\n', "may not import"
        )

    # -- channel purity ---------------------------------------------------
    def test_channel_must_not_spawn_processes(self):
        self.assert_rule("app/x.py", '"""d"""\nimport subprocess\n', "subprocess")

    def test_channel_must_not_write_files(self):
        self.assert_rule("app/x.py", '"""d"""\nopen("x", "w")\n', "business logic")

    # -- gates stay read-only --------------------------------------------
    def test_audit_may_not_write_outside_baselines(self):
        self.assert_rule("audit/x.py", '"""d"""\nopen("x", "w")\n', "must not write files")

    def test_audit_writing_a_baseline_is_allowed(self):
        problems = self.problems("audit/x.py", '"""d"""\nbaseline = "b"\nopen("x", "w")\n')
        self.assertEqual([p for p in problems if "must not write" in p], [])

    # -- naming and documentation ----------------------------------------
    def test_every_module_needs_a_docstring(self):
        self.assert_rule("lib/x.py", "import os\n", "missing module docstring")

    def test_stdlib_shadowing_names_are_rejected(self):
        self.assert_rule("audit/json.py", '"""d"""\n', "shadows a stdlib")

    def test_redundant_audit_prefix_is_rejected(self):
        self.assert_rule("audit/check_links.py", '"""d"""\n', "redundant audit/check")

    def test_lib_may_use_an_underscore_prefix(self):
        self.assertEqual(self.problems("lib/_util.py", '"""d"""\n'), [])

    def test_entry_scripts_must_not_be_underscored(self):
        self.assert_rule("audit/_hidden.py", '"""d"""\n', "must not start with an underscore")

    # -- paths ------------------------------------------------------------
    def test_hardcoded_repository_paths_are_rejected(self):
        self.assert_rule(
            "audit/x.py", '"""d"""\nP = "data/manuscript"\n', "hardcodes repository path"
        )

    def test_deriving_the_book_directory_by_name_is_rejected(self):
        self.assert_rule(
            "render/x.py",
            '"""d"""\nimport os\nP = os.path.join(R, "books")\n',
            "derives the book directory by name",
        )

    def test_reading_the_book_root_from_config_passes(self):
        self.assertEqual(
            self.problems(
                "render/y.py", '"""d"""\nfrom lib import _config\nP = _config.BOOK_ROOT\n'
            ),
            [],
        )

    # -- scripts/ naming --------------------------------------------------
    def test_scripts_directory_accepts_check_and_eval_prefixes(self):
        for name in (
            "check-fast.sh",
            "check.sh",
            "eval-score.ps1",
            "launch.sh",
            "bootstrap.ps1",
            "bookctl",
        ):
            with self.subTest(name=name):
                self.write("scripts/" + name, "#!/bin/sh\n")
        self.assertEqual(self.mod.check_scripts(os.path.join(self.tmp.name, "scripts")), [])

    def test_scripts_directory_rejects_other_names(self):
        self.write("scripts/verify.sh", "#!/bin/sh\n")
        self.write("scripts/report.sh", "#!/bin/sh\n")
        problems = self.mod.check_scripts(os.path.join(self.tmp.name, "scripts"))
        self.assertEqual(len(problems), 2)
        self.assertTrue(all("must start with" in p for p in problems))

    def test_scripts_directory_rejects_unknown_file_types(self):
        self.write("scripts/notes.txt", "x\n")
        problems = self.mod.check_scripts(os.path.join(self.tmp.name, "scripts"))
        self.assertTrue(any("unexpected file" in p for p in problems))

    def test_the_real_scripts_directory_follows_the_convention(self):
        self.assertEqual(self.mod.check_scripts(), [])

    # -- the real tree ----------------------------------------------------
    def test_the_real_toolchain_satisfies_every_rule(self):
        code, out = _fixture.run_inproc(
            os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR)), "check_architecture.py"
        )
        self.assertEqual(code, 0, out[-600:])


if __name__ == "__main__":
    unittest.main()


class ArchitectureRuleCoverageTest(unittest.TestCase):
    """The remaining rule branches and the scripts/ directory failure modes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.book_root = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))
        self.mod = _fixture.load_module(self.book_root, "check_architecture")

    def write(self, rel: str, body: str) -> str:
        path = os.path.join(self.tmp.name, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
        return path

    def problems(self, rel: str, body: str) -> list[str]:
        return self.mod.check(self.write(rel, body), self.tmp.name)

    def test_write_calls_reports_write_text_and_write_modes(self):
        import ast

        tree = ast.parse('_fsutil.write_text(p, "x")\nopen(p, "w")\nopen(p, "r")\n')
        self.mod.write_calls(tree)
        self.assertEqual(self.mod.write_calls(tree), [1, 2])

    def test_an_engine_may_not_depend_on_render(self):
        problems = self.problems("audit/x.py", '"""d"""\nfrom render import to_html\n')
        self.assertTrue(any("must not depend on render" in p for p in problems), problems)

    def test_a_channel_may_not_drive_make_py(self):
        problems = self.problems("app/web.py", '"""d"""\nimport make\n')
        self.assertTrue(any("must not drive make.py" in p for p in problems), problems)

    def test_a_scripts_directory_that_cannot_be_listed_is_reported(self):
        directory = os.path.join(self.tmp.name, "scripts")
        os.makedirs(directory, exist_ok=True)
        with mock.patch.object(self.mod.os, "listdir", side_effect=OSError("denied")):
            problems = self.mod.check_scripts(directory)
        self.assertEqual(len(problems), 1)
        self.assertIn("cannot list the directory", problems[0])

    def test_a_python_file_in_scripts_is_reported_but_a_dotfile_is_ignored(self):
        directory = os.path.join(self.tmp.name, "scripts")
        os.makedirs(directory, exist_ok=True)
        for name in ("helper.py", ".DS_Store"):
            with open(os.path.join(directory, name), "w", encoding="utf-8") as handle:
                handle.write("pass\n")
        problems = self.mod.check_scripts(directory)
        self.assertEqual(len(problems), 1)
        self.assertIn("helper.py", problems[0])


class WiringAuditTest(unittest.TestCase):
    """The rules that judge wiring, proven on injected sources and step tables."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.book_root = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))
        self.mod = _fixture.load_module(self.book_root, "check_architecture")

    def write(self, rel: str, body: str) -> str:
        path = os.path.join(self.tmp.name, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
        return path

    def test_a_report_script_without_json_output_is_reported(self):
        problems = self.mod._exit_problems(
            "audit/report.py", "audit", 'parser.add_argument("--verbose")'
        )
        self.assertEqual(problems, ["audit/report.py: report script should support --json"])

    def test_an_unparsable_module_is_skipped_and_a_spawned_script_is_a_wiring(self):
        broken = self.write("src/python/broken.py", "def (:\n")
        spawner = self.write(
            "src/python/runner.py",
            '"""d"""\nimport subprocess\nsubprocess.run(["book", "spawned_tool.py"])\n',
        )
        with mock.patch.object(self.mod.glob, "glob", return_value=[broken, spawner]):
            mentioned = self.mod.referenced_modules()
        self.assertIn("subprocess", mentioned)
        self.assertIn("spawned_tool", mentioned)

    def test_an_unparsable_step_table_yields_no_wiring(self):
        path = self.write("make_broken.py", "STEPS = [\n")
        with mock.patch.object(self.mod, "MAKE_PY", path):
            self.assertEqual(self.mod.declared_steps(), ({}, {}))

    def test_step_entries_that_are_not_name_script_pairs_are_ignored(self):
        path = self.write(
            "make_odd.py",
            'STEPS = [("one",), (name, "x.py"), ("two", "audit/two.py")]\n'
            'GROUPS = {"test": (member, "two")}\n',
        )
        with mock.patch.object(self.mod, "MAKE_PY", path):
            steps, groups = self.mod.declared_steps()
        self.assertEqual(steps, {"two": "audit/two.py"})
        self.assertEqual(groups, {"test": ("two",)})

    def test_an_empty_step_table_skips_the_reachability_check(self):
        self.assertEqual(self.mod.check_wiring({}, {}), [])

    def test_a_command_group_is_not_checked_for_membership(self):
        problems = self.mod.check_wiring({"build": "audit/x.py"}, {"test": ("nowhere",)})
        self.assertFalse(any("unknown step" in problem for problem in problems), problems)

class ImportTimeConfigReadTest(unittest.TestCase):
    """Modules the console entry imports must read configuration when they run.

    `[project.scripts] bookwright = app.cli:main` imports a fixed set of modules
    in-process; a module-level `_config.` read binds the first book's values there
    and breaks `with _config.use(cfg)`. Script modules outside that closure run in
    a child process, where an import-time read is harmless — so the invariant is
    about the entry chain, not about every file.
    """

    SEEDS = ('cli', 'tui', 'web', 'actions', 'make', 'check_runner', 'settings', 'scaffold')
    # scaffold keeps its layout constants at module level on purpose: creating a
    # book must report a broken source policy as its own error, and a call-time
    # read would let _config raise ConfigError first (see rf-75).
    ALLOWED = frozenset({'scaffold'})

    def modules(self) -> dict[str, str]:
        root = os.path.join(_fixture.TOOLS_DIR)
        found = {}
        for base, _dirs, files in os.walk(root):
            for name in files:
                if name.endswith('.py'):
                    found[name[:-3]] = os.path.join(base, name)
        return found

    def imports_of(self, path: str) -> set[str]:
        import ast

        with open(path, encoding='utf-8') as handle:
            tree = ast.parse(handle.read())
        out = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                out.update(alias.name for alias in node.names)
                out.add(node.module.split('.')[-1])
            elif isinstance(node, ast.Import):
                out.update(alias.name.split('.')[-1] for alias in node.names)
        return out

    def module_level_reads(self, path: str) -> bool:
        import ast

        with open(path, encoding='utf-8') as handle:
            tree = ast.parse(handle.read())
        for node in tree.body:
            value = getattr(node, 'value', None)
            if not isinstance(node, (ast.Assign, ast.AnnAssign)) or value is None:
                continue
            for sub in ast.walk(value):
                if (isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name)
                        and sub.value.id == '_config'):
                    return True
        return False

    def test_the_entry_chain_never_reads_config_while_importing(self):
        modules = self.modules()
        seen, todo = set(), [name for name in self.SEEDS if name in modules]
        while todo:
            name = todo.pop()
            if name in seen:
                continue
            seen.add(name)
            todo.extend(m for m in self.imports_of(modules[name]) if m in modules and m not in seen)
        offenders = sorted(name for name in seen
                           if name not in self.ALLOWED and self.module_level_reads(modules[name]))
        self.assertEqual(offenders, [],
                         f"module-level _config read on the console entry chain: {offenders}")
