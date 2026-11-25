#!/usr/bin/env python3
"""Tests for the language analyzers and multi-language digest."""

import importlib
import json
import os
import sys
import tempfile
import unittest

import _fixture

TAGS = ('layer:infra', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, 'lib'))

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')

languages = importlib.import_module('ingest.languages')

class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def test_known_languages(self):
        self.assertEqual(sorted(languages.ANALYZERS),
                         ['go', 'java', 'kotlin', 'python', 'rust'])

    def test_unknown_language_is_reported(self):
        with self.assertRaises(SystemExit):
            languages.get('cobol')

    def test_detect_per_fixture(self):
        for name, expected in (('mini-java', 'java'), ('mini-python', 'python'),
                               ('mini-rust', 'rust'), ('mini-kotlin', 'kotlin'),
                               ('mini-go', 'go')):
            self.assertEqual(languages.detect(os.path.join(FIXTURES, name)), expected)

class TestAnalyzers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def analyze(self, language: str, fixture: str) -> dict:
        return languages.get(language).analyze(os.path.join(FIXTURES, fixture))

    def test_python_packages_and_units(self):
        inventory = self.analyze('python', 'mini-python')
        self.assertIn('pkg', inventory['packages'])
        self.assertIn('pkg.core', inventory['packages'])
        names = [u['name'] for u in inventory['packages']['pkg']['classes']]
        self.assertIn('Widget', names)

    def test_python_summary_from_docstring(self):
        inventory = self.analyze('python', 'mini-python')
        widget = next(u for u in inventory['packages']['pkg']['classes']
                      if u['name'] == 'Widget')
        self.assertIn('widget', widget['summary'].lower())

    def test_python_public_api(self):
        inventory = self.analyze('python', 'mini-python')
        widget = next(u for u in inventory['packages']['pkg']['classes']
                      if u['name'] == 'Widget')
        self.assertIn('describe', widget['api'])

    def test_rust_units_and_docs(self):
        inventory = self.analyze('rust', 'mini-rust')
        package = inventory['packages']['src']
        names = [u['name'] for u in package['classes']]
        self.assertIn('Widget', names)
        widget = next(u for u in package['classes'] if u['name'] == 'Widget')
        self.assertIn('widget', widget['summary'].lower())

    def test_kotlin_package_unit_and_api(self):
        inventory = self.analyze('kotlin', 'mini-kotlin')
        package = inventory['packages']['com.example']
        widget = next(u for u in package['classes'] if u['name'] == 'Widget')
        self.assertTrue(widget['public'])
        self.assertIn('render', widget['api'])
        self.assertIn('widget', widget['summary'].lower())

    def test_kotlin_imports_become_dependencies(self):
        inventory = self.analyze('kotlin', 'mini-kotlin')
        package = inventory['packages']['com.example']
        self.assertIn('kotlinx.coroutines', package['depends_on'])

    def test_go_package_units_and_visibility(self):
        inventory = self.analyze('go', 'mini-go')
        package = next(iter(inventory['packages'].values()))
        names = {u['name']: u for u in package['classes']}
        self.assertIn('Widget', names)
        self.assertTrue(names['Widget']['public'])
        self.assertFalse(names['hidden']['public'])

    def test_go_imports_become_dependencies(self):
        inventory = self.analyze('go', 'mini-go')
        package = next(iter(inventory['packages'].values()))
        self.assertIn('fmt', package['depends_on'])

    def test_java_packages(self):
        inventory = self.analyze('java', 'mini-java')
        self.assertIn('org.example', inventory['packages'])
        package = inventory['packages']['org.example']
        self.assertGreaterEqual(package['files'], 1)
        self.assertIn('Widget', [u['name'] for u in package['classes']])

    def test_analyzers_report_totals(self):
        for language, fixture in (('java', 'mini-java'), ('python', 'mini-python'),
                                  ('rust', 'mini-rust')):
            inventory = self.analyze(language, fixture)
            self.assertGreater(inventory['totals']['files'], 0, language)
            self.assertGreater(inventory['totals']['lines'], 0, language)

class TestDigestLanguages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def configure(self, languages: list[str], fixture: str) -> None:
        base_path = os.path.join(self.root, 'data', 'config', 'base.json')
        with open(base_path, encoding='utf-8') as fh:
            base = json.load(fh)
        base['sources']['src_main'] = os.path.join(FIXTURES, fixture)
        base['sources']['languages'] = languages
        with open(base_path, 'w', encoding='utf-8') as fh:
            json.dump(base, fh, ensure_ascii=False, indent=2)

    def run_digest(self) -> dict:
        code, out = _fixture.run_inproc(self.root, 'digest.py')
        self.assertEqual(code, 0, out[-400:])
        with open(os.path.join(self.root, 'data', 'state', 'source-inventory.json'),
                  encoding='utf-8') as fh:
            return json.load(fh)

    def test_python_digest(self):
        self.configure(['python'], 'mini-python')
        inventory = self.run_digest()
        self.assertEqual(inventory['languages'], ['python'])
        self.assertIn('pkg', inventory['packages'])
        self.assertEqual(inventory['packages']['pkg']['language'], 'python')

    def test_rust_digest(self):
        self.configure(['rust'], 'mini-rust')
        inventory = self.run_digest()
        self.assertEqual(inventory['languages'], ['rust'])
        self.assertIn('src', inventory['packages'])

    def test_multi_language_digest_prefixes(self):
        self.configure(['java', 'python'], 'mini-java')
        inventory = self.run_digest()
        # java-only tree: python contributes nothing but the language is listed
        self.assertEqual(inventory['languages'], ['java', 'python'])
        self.assertIn('java:org.example', inventory['packages'])

if __name__ == '__main__':
    unittest.main()


class JavaAnalyzerBranchesTest(unittest.TestCase):
    """A javadoc summary and a package import are the two paths a fixture skips."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.analyzer = languages.get('java')

    def write(self, name: str, body: str) -> str:
        path = os.path.join(self.tmp.name, name)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(body)
        return path

    def test_the_javadoc_becomes_the_unit_summary(self):
        path = self.write('Widget.java', 'public class Widget { }\n'
                                          '/**\n * A widget that holds state.\n */\n')
        module = self.analyzer.parse(path)
        self.assertEqual(module.units[0].summary, 'A widget that holds state.')
        self.assertEqual(module.summary, 'A widget that holds state.')

    def test_an_import_becomes_its_package_dependency(self):
        path = self.write('Store.java', 'package a.b;\nimport org.h2.engine.Database;\n'
                                         'public class Store { void open() {} }\n')
        module = self.analyzer.parse(path)
        self.assertEqual(module.depends_on.get('org.h2'), 1)   # the file's own package
