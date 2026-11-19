#!/usr/bin/env python3
"""Meta: every suite declares a valid layer/tier and follows the naming rule."""
from __future__ import annotations

import ast
import importlib
import os
import unittest

import _fixture

_fixture.ensure_tools_path()

# imported through importlib: no import statement may follow the path setup
_tags = importlib.import_module('_tags')

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
TAGS = ('layer:infra', 'tier:fast')


def suites() -> list[str]:
    return sorted(name for name in os.listdir(TEST_DIR)
                  if name.startswith('test_') and name.endswith('.py'))


def parse_suite(name: str) -> ast.Module:
    with open(os.path.join(TEST_DIR, name), encoding='utf-8') as fh:
        return ast.parse(fh.read())


def module_tags(name: str) -> tuple[str, ...]:
    tree = parse_suite(name)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                getattr(target, 'id', '') == 'TAGS' for target in node.targets):
            try:
                return tuple(ast.literal_eval(node.value))
            except ValueError:
                return ()
    return ()


class TaxonomyTest(unittest.TestCase):
    def test_every_suite_declares_a_valid_tag_set(self):
        for name in suites():
            if name == 'test_meta_taxonomy.py':
                continue
            with self.subTest(suite=name):
                labels = module_tags(name)
                self.assertTrue(labels, f'{name} has no TAGS')
                self.assertEqual(_tags.validate(labels), [], f'{name}: {labels}')

    def test_declared_layer_matches_the_filename(self):
        for name in suites():
            if name == 'test_meta_taxonomy.py':
                continue
            with self.subTest(suite=name):
                declared = [label.split(':', 1)[1] for label in module_tags(name)
                            if label.startswith('layer:')]
                self.assertEqual(declared[0], _tags.layer_of(name),
                                 f'{name} declares layer:{declared[0]}')

    def test_suite_names_are_lower_snake_case(self):
        # preferred form is test_<layer>_<object>.py; legacy names are accepted
        # while they declare their layer in TAGS (checked above)
        for name in suites():
            with self.subTest(suite=name):
                stem = name.removesuffix('.py')
                self.assertRegex(stem, r'^test_[a-z0-9_]+$')

    def test_case_classes_are_named_as_subjects(self):
        for name in suites():
            tree = parse_suite(name)
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                if not any(isinstance(base, ast.Name) and base.id in
                           ('TestCase', 'DepthCase') for base in node.bases):
                    continue
                with self.subTest(suite=name, klass=node.name):
                    self.assertTrue(node.name.startswith('Test')
                                    or node.name.endswith(('Test', 'Case')),
                                    f'{name}: {node.name} does not name its subject')

    def test_layer_directories_have_suites(self):
        layers = {_tags.layer_of(name) for name in suites()}
        for layer in ('audit', 'render', 'ingest', 'manuscript', 'app', 'lib'):
            with self.subTest(layer=layer):
                self.assertIn(layer, layers, f'no suite covers {layer}')


if __name__ == '__main__':
    unittest.main()
