#!/usr/bin/env python3
"""Two editions of one book: separate state, mappings and archives.

Nothing here is about a second book — it is the same book with two manuscripts.
What must hold: the derived state and the baselines never land in the same
place, the renumbering mapping lives beside the state of its own edition, an
archive directory says which edition it holds, and an undeclared edition is
refused by name rather than silently falling back.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

EDITIONS = ('\n[editions]\nmain = "主版本"\n'
            '\n[editions.abridged]\ndisplay = "删节版"\n'
            '\n[editions.abridged.chapters.numbering]\n"ch2-test.md" = [7]\n')
DEFAULT_EDITION = 'default_edition = "main"\n'


class EditionCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        book_toml = os.path.join(self.root, 'data', 'book', 'book.toml')
        with open(book_toml, encoding='utf-8') as fh:
            original = fh.read()
        with open(book_toml, 'w', encoding='utf-8') as fh:
            fh.write(DEFAULT_EDITION + original + EDITIONS)
        for edition in ('main', 'abridged'):
            folder = os.path.join(self.root, 'data', 'manuscript', edition)
            os.makedirs(folder, exist_ok=True)
            for name in ('ch1-test.md', 'ch2-test.md'):
                source = os.path.join(self.root, 'data', 'manuscript', name)
                with open(source, encoding='utf-8') as fh:
                    text = fh.read()
                with open(os.path.join(folder, name), 'w', encoding='utf-8') as fh:
                    fh.write(text)

    def config(self, edition: str):
        module = _fixture.load_module(self.root, 'merge')
        return module._config.Config(self.root, edition)


class EditionIsolationTest(EditionCase):
    def test_the_derived_state_and_the_baselines_do_not_share_a_directory(self):
        main = self.config('main')
        abridged = self.config('abridged')
        self.assertNotEqual(main.state_dir(), abridged.state_dir())
        self.assertNotEqual(main.baseline_dir(), abridged.baseline_dir())
        for cfg, edition in ((main, 'main'), (abridged, 'abridged')):
            self.assertTrue(cfg.state_dir().endswith(os.path.join('state', edition)))
            self.assertTrue(cfg.baseline_dir().endswith(os.path.join('baselines', edition)))

    def test_each_edition_manscript_is_its_own_directory(self):
        main = self.config('main')
        abridged = self.config('abridged')
        self.assertTrue(main.manuscript_dir.endswith(os.path.join('manuscript', 'main')))
        self.assertTrue(abridged.manuscript_dir.endswith(
            os.path.join('manuscript', 'abridged')))

    def test_the_artifacts_carry_the_edition(self):
        self.assertNotEqual(self.config('main').merged_md(),
                            self.config('abridged').merged_md())


class EditionBaselineTest(EditionCase):
    """Each edition is judged against its own floor, not the other edition's."""

    def volume_baseline(self, edition: str) -> str:
        """The path content_volume resolves for one edition."""
        os.environ['BOOK_EDITION'] = edition
        self.addCleanup(os.environ.pop, 'BOOK_EDITION', None)
        module = _fixture.load_module(self.root, 'content_volume')
        return module.baseline_path()

    def test_the_volume_baseline_follows_the_edition(self):
        main = self.volume_baseline('main')
        abridged = self.volume_baseline('abridged')
        self.assertIn(os.path.join('baselines', 'main'), main)
        self.assertIn(os.path.join('baselines', 'abridged'), abridged)
        self.assertNotEqual(main, abridged)

    def test_without_editions_the_baseline_stays_where_it_was(self):
        plain = _fixture.build_book(os.path.join(self.tmp.name, 'single'))
        module = _fixture.load_module(plain, 'content_volume')
        self.assertTrue(module.baseline_path().endswith(
            os.path.join('baselines', 'content-volume.json')))


class RenumberMappingTest(EditionCase):
    def test_the_mapping_is_written_inside_the_edition_state(self):
        renumber = _fixture.load_module(self.root, 'renumber')
        os.environ['BOOK_EDITION'] = 'abridged'
        self.addCleanup(os.environ.pop, 'BOOK_EDITION', None)
        assert renumber is not None
        code, out = _fixture.run_inproc(self.root, 'renumber.py', '--write')
        self.assertEqual(code, 0, out[-400:])
        mapping = os.path.join(self.root, 'data', 'state', 'abridged', 'renumber.json')
        self.assertTrue(os.path.isfile(mapping), out[-400:])
        with open(mapping, encoding='utf-8') as fh:
            stored = json.load(fh)
        self.assertTrue(stored, 'the mapping must map at least one chapter')
        self.assertIn('abridged', out)


class ArchiveNamingTest(EditionCase):
    def test_an_archive_directory_names_its_edition(self):
        archive = _fixture.load_module(self.root, 'archive')
        for edition, expected in (('main', 'main'), ('abridged', 'abridged')):
            archive._config.reset(archive._config.Config(self.root, edition))
            self.assertIn(expected, archive.book_slug())


class EditionSelectionChannelsTest(EditionCase):
    """Every front end takes the edition the same way."""

    def restore(self) -> None:
        for key in ('BOOK_ROOT', 'BOOK_EDITION'):
            value = os.environ.get(key)
            self.addCleanup(lambda k=key, v=value: (os.environ.pop(k, None)
                                                    if v is None else os.environ.__setitem__(k, v)))

    def test_the_cli_and_the_tui_accept_the_edition_flag(self):
        self.restore()
        cli = _fixture.load_module(self.root, 'cli')
        tui = _fixture.load_module(self.root, 'tui')
        for name, run in (('cli', lambda: cli.main(['status', '--edition', 'abridged'])),
                          ('tui', lambda: tui.main(['--once', 'status',
                                                    '--edition', 'abridged']))):
            with self.subTest(channel=name):
                buffer = io.StringIO()
                with redirect_stdout(buffer), redirect_stderr(buffer):
                    code = run()
                self.assertEqual(code, 0, buffer.getvalue()[-300:])

    def test_the_web_console_takes_the_edition_with_the_request(self):
        self.restore()
        actions = _fixture.load_module(self.root, 'actions')
        code, text = actions.run('status', book=self.root, edition='abridged')
        self.assertEqual(code, 0, text[-300:])


class UndeclaredEditionTest(EditionCase):
    def run_make(self, *args: str) -> tuple[int, str]:
        """Run make.main, putting the process selection back afterwards.

        The entry writes BOOK_ROOT/BOOK_EDITION for its child steps; leaving them
        set would point every later suite at this temporary book.
        """
        make = _fixture.load_module(self.root, 'make')
        previous = {key: os.environ.get(key) for key in ('BOOK_ROOT', 'BOOK_EDITION')}
        active = make._config.current()
        self.addCleanup(make._config.reset, active)
        for key, value in previous.items():
            self.addCleanup(self.restore_env, key, value)
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = make.main(list(args))
        return code, err.getvalue()

    def restore_env(self, key: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    def test_an_undeclared_edition_is_refused_before_any_step(self):
        code, err = self.run_make('check', '--book', self.root, '--edition', 'nope')
        self.assertEqual(code, 2)
        self.assertIn('未声明版本', err)
        self.assertIn('abridged', err)

    def test_a_declared_edition_passes_the_guard(self):
        code, err = self.run_make('check', '--book', self.root, '--edition', 'abridged')
        self.assertNotEqual(code, 2, err)
        self.assertNotIn('未声明版本', err)


if __name__ == '__main__':
    unittest.main()
