#!/usr/bin/env python3
"""Architecture gate: each rule is proven with a synthetic source tree."""

from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

class ArchitectureRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.book_root = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))
        self.mod = _fixture.load_module(self.book_root, 'check_architecture')

    def write(self, rel: str, body: str) -> str:
        path = os.path.join(self.tmp.name, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(body)
        return path

    def problems(self, rel: str, body: str) -> list[str]:
        path = self.write(rel, body)
        return self.mod.check(path, self.tmp.name)

    def assert_rule(self, rel: str, body: str, needle: str) -> None:
        found = self.problems(rel, body)
        self.assertTrue(any(needle in p for p in found), f'{needle!r} not in {found}')

    # -- dependency matrix ------------------------------------------------
    def test_lib_may_not_import_an_engine(self):
        self.assert_rule('lib/x.py', '"""d"""\nfrom audit import smart\n', 'may not import')

    def test_core_may_import_lib_only(self):
        self.write('lib/_config.py', '"""d"""\n')
        self.assertEqual(self.problems('core/x.py', '"""d"""\nfrom lib import _config\n'), [])
        self.assert_rule('core/y.py', '"""d"""\nfrom render import to_html\n', 'may not import')

    def test_engine_may_not_import_core(self):
        self.assert_rule('audit/x.py', '"""d"""\nfrom core import actions\n', 'may not import')

    def test_channel_may_import_core(self):
        self.write('core/actions.py', '"""d"""\n')
        self.assertEqual(self.problems('app/x.py', '"""d"""\nfrom core import actions\n'), [])

    def test_channel_may_not_import_an_engine(self):
        self.assert_rule('app/x.py', '"""d"""\nfrom render import to_html\n',
                         'channel imports')

    def test_sibling_engines_may_not_import_each_other(self):
        self.assert_rule('audit/x.py', '"""d"""\nfrom manuscript import glossary\n',
                         'may not import')

    # -- channel purity ---------------------------------------------------
    def test_channel_must_not_spawn_processes(self):
        self.assert_rule('app/x.py', '"""d"""\nimport subprocess\n', 'subprocess')

    def test_channel_must_not_write_files(self):
        self.assert_rule('app/x.py', '"""d"""\nopen("x", "w")\n', 'business logic')

    # -- gates stay read-only --------------------------------------------
    def test_audit_may_not_write_outside_baselines(self):
        self.assert_rule('audit/x.py', '"""d"""\nopen("x", "w")\n', 'must not write files')

    def test_audit_writing_a_baseline_is_allowed(self):
        problems = self.problems('audit/x.py', '"""d"""\nbaseline = "b"\nopen("x", "w")\n')
        self.assertEqual([p for p in problems if 'must not write' in p], [])

    # -- naming and documentation ----------------------------------------
    def test_every_module_needs_a_docstring(self):
        self.assert_rule('lib/x.py', 'import os\n', 'missing module docstring')

    def test_stdlib_shadowing_names_are_rejected(self):
        self.assert_rule('audit/json.py', '"""d"""\n', 'shadows a stdlib')

    def test_redundant_audit_prefix_is_rejected(self):
        self.assert_rule('audit/check_links.py', '"""d"""\n', 'redundant audit/check')

    def test_lib_may_use_an_underscore_prefix(self):
        self.assertEqual(self.problems('lib/_util.py', '"""d"""\n'), [])

    def test_entry_scripts_must_not_be_underscored(self):
        self.assert_rule('audit/_hidden.py', '"""d"""\n', 'must not start with an underscore')

    # -- paths ------------------------------------------------------------
    def test_hardcoded_repository_paths_are_rejected(self):
        self.assert_rule('audit/x.py', '"""d"""\nP = "data/manuscript"\n',
                         'hardcodes repository path')

    # -- scripts/ naming --------------------------------------------------
    def test_scripts_directory_accepts_check_and_eval_prefixes(self):
        for name in ('check-fast.sh', 'check.sh', 'eval-score.ps1',
                     'launch.sh', 'bootstrap.ps1', 'bookctl'):
            with self.subTest(name=name):
                self.write('scripts/' + name, '#!/bin/sh\n')
        self.assertEqual(self.mod.check_scripts(os.path.join(self.tmp.name, 'scripts')), [])

    def test_scripts_directory_rejects_other_names(self):
        self.write('scripts/verify.sh', '#!/bin/sh\n')
        self.write('scripts/report.sh', '#!/bin/sh\n')
        problems = self.mod.check_scripts(os.path.join(self.tmp.name, 'scripts'))
        self.assertEqual(len(problems), 2)
        self.assertTrue(all('must start with' in p for p in problems))

    def test_scripts_directory_rejects_unknown_file_types(self):
        self.write('scripts/notes.txt', 'x\n')
        problems = self.mod.check_scripts(os.path.join(self.tmp.name, 'scripts'))
        self.assertTrue(any('unexpected file' in p for p in problems))

    def test_the_real_scripts_directory_follows_the_convention(self):
        self.assertEqual(self.mod.check_scripts(), [])

    # -- the real tree ----------------------------------------------------
    def test_the_real_toolchain_satisfies_every_rule(self):
        code, out = _fixture.run_inproc(
            os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR)),
            'check_architecture.py')
        self.assertEqual(code, 0, out[-600:])

if __name__ == '__main__':
    unittest.main()
