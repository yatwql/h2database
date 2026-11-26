#!/usr/bin/env python3
"""Contract tests for the delivery pipeline and the dependency single source.

Three properties this suite pins, none of them visible to a per-script test:

  WIRING     a script that nothing calls (it imports fine, its own unit test
             passes, running it by hand passes — it just never runs)
  ORDER      a gate that verifies what a later step produces, or an earlier
             step that overwrites the artifact a later gate validated
  PINNING    a system interpreter whose browser/pypdf versions differ from the
             pins, so the same command behaves differently on two machines
"""

import os
import sys
import unittest

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))
STEPS_REL = 'render/pdf_toc_links.py'


_CACHE: dict = {}


def tool(name: str):
    """Load a toolchain module against the fixture root (cached per process).

    Loaded lazily: importing make.py reads book.toml, which cannot happen at
    collection time (pytest imports the module before the fixture root exists).
    """
    if name not in _CACHE:
        _CACHE[name] = _fixture.load_module(BOOK_ROOT, name)
    return _CACHE[name]


def requirements_lines(name='requirements.txt'):
    path = os.path.join(BOOK_ROOT, name)
    with open(path, encoding='utf-8') as handle:
        text = handle.read()
    return [line.split('#', 1)[0].strip() for line in text.splitlines()
            if line.split('#', 1)[0].strip()]


class DependencyPinningCase(unittest.TestCase):
    def test_every_runtime_requirement_is_an_exact_pin(self):
        """A range lets two machines resolve different versions (drift by design)."""
        loose = [line for line in requirements_lines() if '==' not in line]
        self.assertEqual(loose, [], f'unpinned requirements: {loose}')

    def test_optional_tools_are_named_as_pinned_requirements(self):
        """make.py OPTIONAL_TOOLS is the reader's map; the pins are the truth."""
        pinned = tool('make').pinned_versions()
        for module in tool('make').OPTIONAL_TOOLS:
            if module == 'pandoc':
                continue
            self.assertIn(module, pinned,
                          f'{module} is used by a step but not pinned in requirements.txt')

    def test_installed_versions_match_the_pins(self):
        """Skipped outside .venv: drift there is reported by `make.py doctor`."""
        venv = tool('make').venv_python()
        if venv is None:
            self.skipTest('no books/.venv')
        if os.path.realpath(sys.executable) != os.path.realpath(venv):
            self.skipTest('not running on books/.venv')
        self.assertEqual(tool('make').pin_drift(), [])


class InterpreterGuardCase(unittest.TestCase):
    """The rule is pure: both paths are arguments, so no global state is patched.

    A module-level patch here would leak into other suites that import make.py
    through runpy, which is exactly the order dependence the audit hunts.
    """

    def setUp(self):
        self.make = tool('make')
        self._saved = os.environ.pop('BOOK_ALLOW_SYSTEM_PYTHON', None)

    def tearDown(self):
        # restore the *absence* too: a case below sets the override directly, and
        # leaving it set leaks the permission into every later suite (that is what
        # made test_make depend on the order the modules run in)
        if self._saved is None:
            os.environ.pop('BOOK_ALLOW_SYSTEM_PYTHON', None)
        else:
            os.environ['BOOK_ALLOW_SYSTEM_PYTHON'] = self._saved

    def test_refuses_a_foreign_interpreter(self):
        with self.assertRaises(SystemExit) as caught:
            self.make.enforce_venv('/opt/other/python', sys.executable)
        self.assertEqual(caught.exception.code, 3)

    def test_accepts_the_project_interpreter(self):
        self.assertIsNone(self.make.enforce_venv(__file__, __file__))

    def test_absent_venv_does_not_block(self):
        self.assertIsNone(self.make.enforce_venv(None, sys.executable))
        self.assertIsNone(self.make.interpreter_problem(None, '/usr/bin/python3'))

    def test_override_is_explicit(self):
        os.environ['BOOK_ALLOW_SYSTEM_PYTHON'] = '1'
        self.assertIsNone(self.make.interpreter_problem('/opt/other/python', sys.executable))


class DeliveryOrderCase(unittest.TestCase):
    def setUp(self):
        self.make = tool('make')

    def group_names(self, group):
        return [step[0] for step in self.make.STEPS if step[0] in self.make.GROUPS[group]]

    def test_group_members_all_exist(self):
        names = {step[0] for step in self.make.STEPS}
        for group, members in self.make.GROUPS.items():
            if group in ('test', 'cover', 'report'):
                continue  # dispatch to a dedicated function, not a step list
            unknown = [member for member in members if member not in names]
            self.assertEqual(unknown, [], f'group {group} names unknown steps')

    def test_toc_links_run_between_the_pdf_render_and_its_gate(self):
        """verify_pdf --require-toc-links needs the link step to have run."""
        order = self.group_names('deliver')
        self.assertIn('pdf_toc_links', order)
        self.assertLess(order.index('to_pdf'), order.index('pdf_toc_links'))
        self.assertLess(order.index('pdf_toc_links'), order.index('verify_pdf'))

    def test_each_gate_runs_after_its_producer(self):
        for group in self.make.GROUPS:
            order = self.group_names(group)
            for gate, producer in (('verify_pdf', 'to_pdf'), ('verify_epub', 'to_epub')):
                if gate in order:
                    self.assertLess(order.index(producer), order.index(gate))


class WiringCase(unittest.TestCase):
    def test_the_toolchain_has_no_orphan_entry_points(self):
        self.assertEqual(tool('check_architecture').check_wiring(), [])

    def test_a_dropped_step_is_reported_as_an_orphan(self):
        """Mutation: remove the step from the wiring, the gate names the script."""
        steps, groups = tool('check_architecture').declared_steps()
        self.assertIn(STEPS_REL, set(steps.values()))
        dropped = {name: script for name, script in steps.items() if script != STEPS_REL}
        problems = tool('check_architecture').check_wiring(dropped, groups)
        # the report names the step; the script path is what the wiring table holds
        step = 'pdf_toc_links'
        self.assertTrue(any(step in problem for problem in problems),
                        f'orphan not reported: {problems}')

    def test_unknown_group_member_is_reported(self):
        steps, groups = tool('check_architecture').declared_steps()
        broken = dict(groups, deliver=(*groups['deliver'], 'no_such_step'))
        problems = tool('check_architecture').check_wiring(steps, broken)
        self.assertTrue(any('no_such_step' in problem for problem in problems), problems)


if __name__ == '__main__':
    unittest.main()
