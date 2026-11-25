#!/usr/bin/env python3
"""Python analyzer: modules from directories, units from the AST."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:ingest', 'tier:fast')

_fixture.ensure_tools_path()

def load_analyzer():
    """The analyzer lives in a nested package, so load it by path."""
    path = os.path.join(_fixture.TOOLS_DIR, 'ingest', 'languages', 'python.py')
    spec = importlib.util.spec_from_file_location('python_analyzer', path)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load the analyzer from {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PythonAnalyzer()

class PythonAnalyzerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.analyzer = load_analyzer()

    def write(self, rel: str, body: str) -> str:
        path = os.path.join(self.tmp.name, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(body)
        return path

    def test_module_summary_comes_from_the_docstring(self):
        path = self.write('pkg/mod.py', '"""模块说明。"""\n\n\ndef public():\n    pass\n')
        module = self.analyzer.parse(path)
        self.assertEqual(module.summary, '模块说明。')

    def test_public_functions_become_units(self):
        path = self.write('pkg/fn.py', '"""d"""\n\n\ndef public():\n    pass\n\n\ndef _hidden():\n    pass\n')
        module = self.analyzer.parse(path)
        names = [unit.name for unit in module.units]
        self.assertIn('public', names)
        self.assertNotIn('_hidden', names)

    def test_classes_expose_their_public_methods(self):
        path = self.write('pkg/cls.py', '"""d"""\n\n\nclass Widget:\n    """组件。"""\n\n'
                                        '    def run(self):\n        pass\n\n'
                                        '    def _helper(self):\n        pass\n')
        unit = next(u for u in self.analyzer.parse(path).units if u.name == 'Widget')
        self.assertEqual(unit.api, ['run'])
        self.assertEqual(unit.kind, 'class')

    def test_unparsable_source_is_returned_as_unparsed(self):
        path = self.write('pkg/broken.py', 'def broken(:\n')
        module = self.analyzer.parse(path)
        self.assertEqual(module.package, 'unparsed')

    def test_package_name_follows_the_directory(self):
        path = self.write('pkg/sub/mod.py', '"""d"""\n')
        module = self.analyzer.parse(path)
        self.assertTrue(module.package.endswith('pkg.sub') or module.package == 'pkg.sub')

    def test_suffix_is_registered_for_digest(self):
        self.assertIn('.py', self.analyzer.suffixes)

if __name__ == '__main__':
    unittest.main()


class PythonImportDepsTest(unittest.TestCase):
    """Imports become dependencies, including dotted ones (first segment only)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.analyzer = load_analyzer()

    def test_dotted_imports_count_their_top_level_package(self):
        path = os.path.join(self.tmp.name, 'mod.py')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('import os\nimport a.b.c\nfrom x.y import z\n')
        module = self.analyzer.parse(path)
        self.assertEqual(module.depends_on.get('a'), 1)
        self.assertEqual(module.depends_on.get('x'), 1)
        self.assertEqual(module.depends_on.get('os'), 1)
