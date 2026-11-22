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

TAGS = ('layer:infra', 'tier:fast')

BOOK_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

AUDITS = [
    'links.py',
    'diagrams.py',
    'captions.py',
    'figures.py',
    'crossrefs.py',
    'exercises.py',
    'figure_clusters.py',
    'index_xrefs.py',
    'smart.py',
    'balance.py',
    'readability.py',
    'source_refs.py',
    'glossary.py',
    'index.py',
    'style.py',
    'structure.py',
]

# Modes that produce extra report branches on the real manuscript.
MODES = [
    ('captions.py', ('--json',)),
    ('exercises.py', ('--json',)),
    ('figure_clusters.py', ('--json',)),
    ('glossary.py', ('--coverage',)),
    ('glossary.py', ('--validate',)),
    ('index.py', ('--hierarchy-check',)),
    ('balance.py', ('--json',)),
    ('source_refs.py', ('--suggest',)),
    ('diagrams.py', ('--json',)),
    ('links.py', ('--json',)),
]

REAL_EXIT_CODES = {
    'links.py': 0,
    'diagrams.py': 0,
    'captions.py': 1,
    'figures.py': 0,
    'crossrefs.py': 0,
    'exercises.py': 0,
    'figure_clusters.py': 0,
    'index_xrefs.py': 0,
    'smart.py': 0,
    'balance.py': 0,
    'readability.py': 0,
    'source_refs.py': 0,
    'glossary.py': 0,
    'index.py': 0,
    'style.py': 0,
    'structure.py': 0,
}

REAL_MODE_CODES = {
    ('captions.py', ('--json',)): 1,
    ('exercises.py', ('--json',)): 0,
    ('figure_clusters.py', ('--json',)): 0,
    ('glossary.py', ('--coverage',)): 0,
    ('glossary.py', ('--validate',)): 0,
    ('index.py', ('--hierarchy-check',)): 0,
    ('balance.py', ('--json',)): 0,
    ('source_refs.py', ('--suggest',)): 0,
    ('diagrams.py', ('--json',)): 0,
    ('links.py', ('--json',)): 0,
}

@unittest.skipUnless(os.path.isdir(os.path.join(BOOK_ROOT, 'manuscript')),
                     'real manuscript not available')
class TestRealBook(unittest.TestCase):
    def test_audits_run_on_real_book(self):
        for script in AUDITS:
            with self.subTest(script=script):
                code, out = _fixture.run_inproc(BOOK_ROOT, script)
                self.assertIn(script, REAL_EXIT_CODES, 'every audit needs a recorded verdict')
                self.assertEqual(code, REAL_EXIT_CODES[script],
                                 f'{script} -> {code}\n{out[-800:]}')
                self.assertNotIn('Traceback', out, f'{script}:\n{out[-800:]}')

    def test_alternate_modes_on_real_book(self):
        for script, args in MODES:
            with self.subTest(script=script, args=args):
                code, out = _fixture.run_inproc(BOOK_ROOT, script, *args)
                self.assertIn((script, args), REAL_MODE_CODES, 'every mode needs a recorded verdict')
                self.assertEqual(code, REAL_MODE_CODES[(script, args)],
                                 f'{script} {args} -> {code}\n{out[-800:]}')
                self.assertNotIn('Traceback', out, f'{script} {args}:\n{out[-800:]}')

if __name__ == '__main__':
    unittest.main()
