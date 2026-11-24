"""The run summary is one text, used by the log and the TUI alike."""
from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()

_status = __import__('lib.status', fromlist=['artifact_facts', 'render'])
render = _status.render
artifact_facts = _status.artifact_facts


class RenderTest(unittest.TestCase):
    def test_the_verdict_and_the_time_are_readable(self):
        text = render(True, 'build', 12.3, 0, source={'root': '/src', 'version': '1.0',
                                                      'changed': ''}, artifacts=[])
        self.assertIn('✓ 完成', text)
        self.assertIn('12.3s', text)
        self.assertIn('/src', text)

    def test_a_failure_says_so_and_carries_the_exit_code(self):
        text = render(False, 'deliver', 3.0, 2, source={}, artifacts=[])
        self.assertIn('✗ 失败', text)
        self.assertIn('退出码 2', text)

    def test_artifacts_are_listed_with_their_numbers(self):
        text = render(True, 'build', 1.0, artifacts=[
            {'name': 'a.pdf', 'size': '8.00 MB', 'pages': '877 页', 'changed': '2026-11-24'}])
        self.assertIn('a.pdf', text)
        self.assertIn('877 页', text)


class ArtifactFactsTest(unittest.TestCase):
    def test_only_delivery_suffixes_are_listed(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ('a.html', 'b.pdf', 'notes.txt'):
                with open(os.path.join(directory, name), 'w', encoding='utf-8') as handle:
                    handle.write('x')
            names = [item['name'] for item in artifact_facts(directory)]
        self.assertEqual(sorted(names), ['a.html', 'b.pdf'])

    def test_a_missing_directory_is_empty_not_an_error(self):
        self.assertEqual(artifact_facts(os.path.join(tempfile.gettempdir(), 'nope-dir')), [])

    def test_a_non_pdf_gets_no_page_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'a.epub')
            with open(path, 'wb') as handle:
                handle.write(b'PK\x03\x04 not a pdf')
            facts = artifact_facts(directory)
        self.assertEqual(facts[0]['pages'], '')


if __name__ == '__main__':
    unittest.main()
