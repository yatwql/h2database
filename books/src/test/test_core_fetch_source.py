#!/usr/bin/env python3
"""Cloning the configured source repository: commands, targets, refusal to overwrite."""
from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:core', 'tier:fast')

_fixture.ensure_tools_path()


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module('core.fetch_source')
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.target = os.path.join(self.tmp, 'y')

    def test_a_clone_is_shallow_and_optionally_pinned(self):
        plain = self.mod.clone_commands('https://x/y.git', self.target)
        self.assertEqual(plain, [['git', 'clone', '--depth', '1',
                                  'https://x/y.git', self.target]])
        pinned = self.mod.clone_commands('https://x/y.git', self.target, 'v1.2')
        self.assertIn('--branch', pinned[0])
        self.assertIn('v1.2', pinned[0])

    def test_an_update_fetches_and_lands_on_the_ref(self):
        commands = self.mod.update_commands(self.target, 'main')
        self.assertEqual(commands[0][:4], ['git', '-C', self.target, 'fetch'])
        self.assertIn(['git', '-C', self.target, 'checkout', 'main'], commands)


class RunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = _fixture.build_book(self.tmp)
        self.mod = _fixture.load_module(self.root, 'fetch_source')
        self.config = _fixture.load_module(self.root, '_config')

    def declare(self, repo: str) -> None:
        """Add ``repo`` to the existing [sources] table (a second header is invalid)."""
        path = os.path.join(self.root, 'data', 'book', 'book.toml')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        assert '[sources]' in text
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text.replace('[sources]', f'[sources]\nrepo = "{repo}"', 1))

    def test_without_a_repository_the_tool_says_so(self):
        with self.config.use(self.config.Config(self.root)):
            self.assertEqual(self.mod.main([]), 2)

    def test_dry_run_prints_instead_of_cloning(self):
        self.declare("https://github.com/acme/widget.git")
        with self.config.use(self.config.Config(self.root)), \
                mock.patch('subprocess.run') as runner:
            self.assertEqual(self.mod.main(['--dry-run']), 0)
        runner.assert_not_called()

    def test_an_existing_clone_is_left_alone(self):
        self.declare("https://github.com/acme/widget.git")
        cfg = self.config.Config(self.root)
        target = cfg.clone_target()
        os.makedirs(target, exist_ok=True)
        with self.config.use(cfg), mock.patch('subprocess.run') as runner:
            self.assertEqual(self.mod.main([]), 0)
        runner.assert_not_called()

    def test_a_clone_runs_git_against_the_derived_target(self):
        self.declare("https://github.com/acme/widget.git")
        cfg = self.config.Config(self.root)
        captured = []

        def fake_run(command, check=False):
            captured.append(command)
            return mock.Mock(returncode=0)

        with self.config.use(cfg), mock.patch('subprocess.run', fake_run):
            self.assertEqual(self.mod.main([]), 0)
        self.assertEqual(captured[0][:3], ['git', 'clone', '--depth'])
        self.assertTrue(captured[0][-1].endswith('acme__widget'))


class TargetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = _fixture.build_book(self.tmp)
        self.config = _fixture.load_module(self.root, '_config')

    def declare(self, repo: str) -> None:
        """Add ``repo`` to the existing [sources] table (a second header is invalid)."""
        path = os.path.join(self.root, 'data', 'book', 'book.toml')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        assert '[sources]' in text
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text.replace('[sources]', f'[sources]\nrepo = "{repo}"', 1))

    def test_https_and_ssh_urls_derive_the_same_slug(self):
        cfg = self.config.Config(self.root)
        self.assertTrue(cfg.clone_target('https://github.com/acme/widget.git')
                        .endswith('acme__widget'))
        self.assertTrue(cfg.clone_target('git@github.com:acme/widget.git')
                        .endswith('acme__widget'))

    def test_a_declared_repository_that_is_not_cloned_is_an_error(self):
        self.declare("https://github.com/acme/widget.git")
        cfg = self.config.Config(self.root)
        with self.assertRaises(self.config.ConfigError):
            cfg.source_tree('src_main')


if __name__ == '__main__':
    unittest.main()
