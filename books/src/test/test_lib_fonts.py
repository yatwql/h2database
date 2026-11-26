"""Font resolution judges files by their content and stacks by script."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import types
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:lib", "tier:fast")

# fontTools is an optional dependency: without it `coverage()` answers with
# a message instead of face data, so the face-merging cases cannot run
HAS_FONTTOOLS = importlib.util.find_spec("fontTools") is not None

_fixture.ensure_tools_path()

_fonts = __import__("lib.fonts", fromlist=["is_collection_file", "portable_stack"])
is_collection_file = _fonts.is_collection_file
portable_stack = _fonts.portable_stack


class CollectionDetectionTest(unittest.TestCase):
    def test_a_collection_header_is_recognised(self):
        with tempfile.NamedTemporaryFile(suffix=".otf", delete=False) as handle:
            handle.write(b"ttcf" + b"\x00" * 8)
            path = handle.name
        self.addCleanup(os.remove, path)
        # an .otf name would suggest a single face; the header says otherwise
        self.assertTrue(is_collection_file(path))

    def test_a_single_face_header_is_not_a_collection(self):
        with tempfile.NamedTemporaryFile(suffix=".ttc", delete=False) as handle:
            handle.write(b"OTTO" + b"\x00" * 8)
            path = handle.name
        self.addCleanup(os.remove, path)
        self.assertFalse(is_collection_file(path))

    def test_a_missing_file_is_not_a_collection(self):
        self.assertFalse(
            is_collection_file(os.path.join(tempfile.gettempdir(), "no-such-font.ttf"))
        )


class PortableStackTest(unittest.TestCase):
    """A viewer-side stack must describe the reader's device, not this machine."""

    def test_the_latin_face_comes_before_the_cjk_one(self):
        stack = portable_stack("mono")
        self.assertLess(stack.index("Consolas"), stack.index("Source Han Mono"))

    def test_the_roles_end_in_their_generic_family(self):
        self.assertTrue(portable_stack("serif").endswith("serif"))
        self.assertTrue(portable_stack("mono").endswith("monospace"))
        self.assertTrue(portable_stack("sans").endswith("sans-serif"))

    def test_an_unknown_role_falls_back_to_sans(self):
        self.assertEqual(portable_stack("nonsense"), portable_stack("sans"))

    def test_families_with_spaces_are_quoted(self):
        self.assertIn('"Source Han Serif"', portable_stack("serif"))


def _reset_caches() -> None:
    for name in ("index", "resolve"):
        getattr(_fonts, name).cache_clear()


class FontDirsTest(unittest.TestCase):
    """The candidate list follows the platform, and only existing dirs survive."""

    def test_linux_candidates_include_the_user_directories(self):
        with (
            mock.patch.object(_fonts.os, "name", "posix"),
            mock.patch.object(_fonts.os.path, "isdir", return_value=True),
        ):
            dirs = _fonts.font_dirs()
        self.assertIn("/usr/share/fonts", dirs)
        self.assertTrue(any(".local/share/fonts" in path for path in dirs))

    def test_windows_candidates_come_from_the_windows_directory(self):
        windir = os.path.join("C:" + os.sep, "Windows")
        with (
            mock.patch.object(_fonts.os, "name", "nt"),
            mock.patch.dict(os.environ, {"WINDIR": windir}),
            mock.patch.object(_fonts.os.path, "isdir", return_value=True),
        ):
            self.assertIn(os.path.join(windir, "Fonts"), _fonts.font_dirs())

    def test_missing_directories_are_dropped(self):
        with mock.patch.object(_fonts.os.path, "isdir", return_value=False):
            self.assertEqual(_fonts.font_dirs(), [])


class FontFilesTest(unittest.TestCase):
    def test_only_font_suffixes_are_collected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("a.ttf", "b.otf", "notes.txt"):
                with open(os.path.join(directory, name), "w", encoding="utf-8") as handle:
                    handle.write("x")
            with mock.patch.object(_fonts, "font_dirs", return_value=[directory]):
                files = _fonts._font_files()
        self.assertTrue(any(path.endswith("a.ttf") for path in files))
        self.assertTrue(any(path.endswith("b.otf") for path in files))
        self.assertFalse(any(path.endswith("notes.txt") for path in files))


class StampTest(unittest.TestCase):
    def test_a_missing_file_does_not_break_the_stamp(self):
        with tempfile.TemporaryDirectory() as directory:
            real = os.path.join(directory, "a.ttf")
            with open(real, "w", encoding="utf-8") as handle:
                handle.write("x")
            missing = os.path.join(directory, "gone.ttf")
            self.assertTrue(_fonts._stamp([real, missing]))
            self.assertEqual(_fonts._stamp([missing]), _fonts._stamp([missing]))


class IndexTest(unittest.TestCase):
    """The family index is cached on disk, keyed by path/size/mtime."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = os.path.join(self.tmp.name, "font-index.json")
        _reset_caches()
        patcher = mock.patch.object(_fonts, "_cache_path", return_value=self.cache)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(_reset_caches)

    def build(self, rows):
        patcher = mock.patch.object(_fonts, "_font_files", return_value=["/fonts/a.ttf"])
        patcher.start()
        self.addCleanup(patcher.stop)
        reader = mock.patch.object(_fonts, "_read_families", return_value=rows)
        reader.start()
        self.addCleanup(reader.stop)

    def test_a_fresh_scan_writes_the_cache(self):
        self.build([("Book Sans", 0, False)])
        self.assertEqual(
            _fonts.index(),
            {"Book Sans": [{"path": "/fonts/a.ttf", "face": 0, "collection": False}]},
        )
        with open(self.cache, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["families"], _fonts.index())

    def test_a_matching_stamp_reuses_the_cache(self):
        self.build([("Book Sans", 0, False)])
        _fonts.index()
        _reset_caches()
        with mock.patch.object(_fonts, "_read_families") as reader:
            self.assertEqual(list(_fonts.index()), ["Book Sans"])
        reader.assert_not_called()

    def test_a_newer_file_invalidates_the_cache(self):
        self.build([("Old", 0, False)])
        _fonts.index()
        _reset_caches()
        self.build([("New", 0, False)])
        with mock.patch.object(_fonts, "_stamp", side_effect=["older", "newer"]):
            self.assertEqual(list(_fonts.index()), ["New"])

    def test_an_unwritable_cache_still_returns_the_index(self):
        self.build([("Book Sans", 0, False)])
        with mock.patch.object(_fonts.os, "makedirs", side_effect=OSError("read-only")):
            self.assertEqual(list(_fonts.index()), ["Book Sans"])


class FamilyLookupTest(unittest.TestCase):
    def setUp(self):
        _reset_caches()
        self.addCleanup(_reset_caches)

    def test_a_single_face_file_is_preferred(self):
        index = {
            "F": [
                {"path": "/c.ttc", "face": 0, "collection": True},
                {"path": "/f.ttf", "face": 0, "collection": False},
            ]
        }
        with mock.patch.object(_fonts, "index", return_value=index):
            self.assertEqual(_fonts._font_file("F"), "/f.ttf")
            self.assertTrue(_fonts.is_embeddable("F"))

    def test_only_a_collection_leaves_nothing_embeddable(self):
        index = {"F": [{"path": "/c.ttc", "face": 1, "collection": True}]}
        with mock.patch.object(_fonts, "index", return_value=index):
            self.assertEqual(_fonts._font_file("F"), "/c.ttc")
            self.assertFalse(_fonts.is_embeddable("F"))

    def test_an_unknown_family_has_no_file(self):
        with mock.patch.object(_fonts, "index", return_value={}):
            self.assertEqual(_fonts._font_file("Nope"), "")
            self.assertFalse(_fonts.is_embeddable("Nope"))


class CoverageTest(unittest.TestCase):
    def setUp(self):
        if not HAS_FONTTOOLS:
            self.skipTest('fontTools is not installed')
        _reset_caches()
        self.addCleanup(_reset_caches)

    def test_an_unknown_family_reports_every_character_missing(self):
        with mock.patch.object(_fonts, "index", return_value={}):
            drawn, missing = _fonts.coverage("Nope", "abc ")
        self.assertEqual(drawn, 0)
        self.assertEqual(missing, ["a", "b", "c"])

    def test_faces_are_merged_to_cover_the_requested_characters(self):
        faces = [
            mock.Mock(getBestCmap=lambda: {ord("a"): 1}),
            mock.Mock(getBestCmap=lambda: {ord("b"): 2}),
        ]
        with (
            mock.patch.object(
                _fonts, "index", return_value={"F": [{"path": "/a"}, {"path": "/b"}]}
            ),
            mock.patch.object(_fonts, "_open_face", side_effect=faces),
        ):
            drawn, missing = _fonts.coverage("F", "abz")
        self.assertEqual((drawn, missing), (2, ["z"]))

    def test_an_unreadable_face_is_skipped(self):
        with (
            mock.patch.object(_fonts, "index", return_value={"F": [{"path": "/a"}]}),
            mock.patch.object(_fonts, "_open_face", return_value=None),
        ):
            self.assertEqual(_fonts.coverage("F", "a"), (0, ["a"]))


class FontconfigTest(unittest.TestCase):
    def test_a_missing_fc_list_yields_no_names(self):
        with mock.patch.object(_fonts.shutil, "which", return_value=None):
            self.assertEqual(_fonts._fontconfig_names(), set())

    def test_names_are_split_on_commas(self):
        done = subprocess.CompletedProcess(
            ["fc-list"], 0, stdout="Book Sans,Book Sans Bold\nOther\n"
        )
        with (
            mock.patch.object(_fonts.shutil, "which", return_value="/usr/bin/fc-list"),
            mock.patch.object(_fonts.subprocess, "run", return_value=done),
        ):
            self.assertEqual(_fonts._fontconfig_names(), {"Book Sans", "Book Sans Bold", "Other"})

    def test_a_failing_command_yields_no_names(self):
        with (
            mock.patch.object(_fonts.shutil, "which", return_value="/usr/bin/fc-list"),
            mock.patch.object(_fonts.subprocess, "run", side_effect=OSError("boom")),
        ):
            self.assertEqual(_fonts._fontconfig_names(), set())


class ResolveTest(unittest.TestCase):
    def setUp(self):
        _reset_caches()
        self.addCleanup(_reset_caches)

    def test_installed_families_come_first_and_unknown_ones_are_kept(self):
        index = {"Known": [{"path": "/k.ttf", "face": 0, "collection": False}]}
        with mock.patch.object(_fonts, "index", return_value=index):
            stack = _fonts.resolve(("Unknown", "Known"), "sans-serif")
        self.assertTrue(stack.startswith("Known"))
        self.assertIn("Unknown", stack)
        self.assertTrue(stack.endswith("sans-serif"))

    def test_a_collection_only_family_comes_after_an_embeddable_one(self):
        index = {
            "Loose": [{"path": "/l.ttf", "face": 0, "collection": False}],
            "Tight": [{"path": "/t.ttc", "face": 0, "collection": True}],
        }
        with mock.patch.object(_fonts, "index", return_value=index):
            stack = _fonts.resolve(("Tight", "Loose"), "sans-serif")
        self.assertLess(stack.index("Loose"), stack.index("Tight"))

    def test_without_an_index_the_fontconfig_list_decides(self):
        with (
            mock.patch.object(_fonts, "index", return_value={}),
            mock.patch.object(_fonts, "_fontconfig_names", return_value={"Present"}),
        ):
            stack = _fonts.resolve(("Present", "Absent"), "sans-serif")
        self.assertIn("Present", stack)
        self.assertIn("Absent", stack)

    def test_without_any_probe_every_candidate_is_kept(self):
        with (
            mock.patch.object(_fonts, "index", return_value={}),
            mock.patch.object(_fonts, "_fontconfig_names", return_value=set()),
        ):
            stack = _fonts.resolve(("A", "B"), "serif")
        self.assertTrue(stack.startswith("A, B"))

    def test_spaces_are_quoted(self):
        index = {"Book Sans": [{"path": "/b.ttf", "face": 0, "collection": False}]}
        with mock.patch.object(_fonts, "index", return_value=index):
            self.assertIn('"Book Sans"', _fonts.resolve(("Book Sans",), "sans-serif"))

    def test_the_default_candidates_reach_the_stack(self):
        with (
            mock.patch.object(_fonts, "index", return_value={}),
            mock.patch.object(_fonts, "_fontconfig_names", return_value=set()),
        ):
            sans = _fonts.sans_stack()
            mono = _fonts.mono_stack()
        self.assertIn(_fonts.DEFAULT_SANS[0].strip('"'), sans)
        self.assertIn(_fonts.DEFAULT_MONO[0].strip('"'), mono)

    def test_the_default_sans_list_is_a_copy(self):
        first = _fonts.default_sans()
        first.append("Mutated")
        self.assertNotIn("Mutated", _fonts.default_sans())




class FontFallbackTest(unittest.TestCase):
    """Missing fontTools, unreadable faces and the platform directory list."""

    def setUp(self):
        self.mod = _fixture.load_module(
            os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR)), "fonts"
        )

    def test_macos_directories_are_used_when_the_platform_says_so(self):
        fake = mock.Mock(sysname="Darwin")
        with mock.patch.object(self.mod.os, "uname", lambda: fake, create=True):
            dirs = self.mod.font_dirs()
        self.assertTrue(any("/Library/Fonts" in path for path in dirs) or dirs == [])

    def test_a_face_without_a_name_table_reads_as_none(self):
        self.assertIsNone(self.mod._name_table({}))

    def test_an_unreadable_face_reads_as_none(self):
        entry = {
            "path": os.path.join(tempfile.mkdtemp(), "missing.ttf"),
            "collection": False,
            "face": 0,
        }
        self.assertIsNone(self.mod._open_face(entry))

    def test_a_collection_index_beyond_the_faces_falls_back_to_the_first(self):
        collection = mock.Mock()
        collection.fonts = ["first"]
        table = mock.Mock(TTCollection=lambda *_a, **_k: collection)
        for name in ("TTCollection", "TTFont"):
            setattr(table, name, getattr(table, name))
        with mock.patch.dict("sys.modules", {"fontTools": mock.Mock(), "fontTools.ttLib": table}):
            entry = {"path": "x.ttc", "collection": True, "face": 5}
            self.assertEqual(self.mod._open_face(entry), "first")

    def test_no_families_are_read_without_fonttools(self):
        real_import = __import__

        def guarded(name, *args, **kwargs):
            if name.startswith("fontTools"):
                raise ImportError("absent")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=guarded):
            self.assertEqual(self.mod._read_families("x.ttf"), [])
            with mock.patch.object(self.mod, "index", lambda: {"fam": [{}]}):
                drawn, missing = self.mod.coverage("fam", "字")
        self.assertEqual(drawn, 0)
        self.assertIn("fonttools", missing[0])

    def test_an_unreadable_file_yields_no_families(self):
        self.assertEqual(self.mod._read_families(os.path.join(tempfile.mkdtemp(), "x.ttf")), [])

    def test_a_face_without_a_name_table_is_skipped(self):
        ttlib = types.SimpleNamespace(
            TTCollection=lambda path, lazy=True: types.SimpleNamespace(
                fonts=[_NamelessFace(), _NamedFace("DejaVu Sans")]),
            TTFont=lambda path, lazy=True: _NamedFace("DejaVu Sans"),
        )
        with mock.patch.dict("sys.modules", {"fontTools.ttLib": ttlib}), \
                mock.patch.object(self.mod, "is_collection_file", return_value=True):
            rows = self.mod._read_families("/fonts/x.ttc")
        self.assertEqual(rows, [("DejaVu Sans", 1, True)])


class _NamelessFace:
    """A face whose `name` table is absent: the lookup raises KeyError."""

    def __getitem__(self, key):
        raise KeyError(key)


class _NamedFace:
    def __init__(self, family):
        self.family = family

    def __getitem__(self, key):
        if key == "name":
            return types.SimpleNamespace(
                getDebugName=lambda name_id: self.family if name_id == 1 else None
            )
        raise KeyError(key)


if __name__ == "__main__":
    unittest.main()
