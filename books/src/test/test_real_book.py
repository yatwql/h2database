#!/usr/bin/env python3
"""In-process runs against the real book.

Unit and fixture tests use tiny synthetic inputs; the report code paths only
light up on a full-size manuscript (many chapters, hundreds of figures, real
glossary and index). These tests exercise the toolchain against the project's
own manuscript so those branches are covered too.

They deliberately avoid scripts that rewrite tracked files: only audits and
the (gitignored) HTML build run here.
"""
import os
import unittest

import _fixture

BOOK_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

AUDITS = [
    '_audit_links.py',
    '_audit_ascii.py',
    '_audit_captions.py',
    '_audit_figures.py',
    '_audit_crossrefs.py',
    '_audit_exercises.py',
    '_audit_figure_clusters.py',
    '_audit_index_xrefs.py',
    '_audit_smart.py',
    'balance_check.py',
    'readability_check.py',
    'source_freshness_check.py',
    'build_glossary.py',
    'build_index.py',
    'check_style.py',
    'final_check.py',
]

# Modes that produce extra report branches on the real manuscript.
MODES = [
    ('_audit_captions.py', ('--json',)),
    ('_audit_exercises.py', ('--json',)),
    ('_audit_figure_clusters.py', ('--json',)),
    ('build_glossary.py', ('--coverage',)),
    ('build_glossary.py', ('--validate',)),
    ('build_index.py', ('--hierarchy-check',)),
    ('balance_check.py', ('--json',)),
    ('source_freshness_check.py', ('--suggest',)),
    ('_audit_ascii.py', ('--json',)),
    ('_audit_links.py', ('--json',)),
]


@unittest.skipUnless(os.path.isdir(os.path.join(BOOK_ROOT, 'manuscript')),
                     'real manuscript not available')
class TestRealBook(unittest.TestCase):
    def test_audits_run_on_real_book(self):
        for script in AUDITS:
            with self.subTest(script=script):
                code, out = _fixture.run_inproc(BOOK_ROOT, script)
                self.assertIn(code, (0, 1), f'{script} -> {code}\n{out[-800:]}')
                self.assertNotIn('Traceback', out, f'{script}:\n{out[-800:]}')

    def test_alternate_modes_on_real_book(self):
        for script, args in MODES:
            with self.subTest(script=script, args=args):
                code, out = _fixture.run_inproc(BOOK_ROOT, script, *args)
                self.assertIn(code, (0, 1), f'{script} {args} -> {code}\n{out[-800:]}')
                self.assertNotIn('Traceback', out, f'{script} {args}:\n{out[-800:]}')


if __name__ == '__main__':
    unittest.main()
