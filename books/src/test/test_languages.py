#!/usr/bin/env python3
"""Tests for the language analyzers and multi-language digest."""

import importlib
import json
import os
import sys
import tempfile
import unittest

import _fixture

TAGS = ("layer:infra", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, "lib"))

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

languages = importlib.import_module("ingest.languages")


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def test_known_languages(self):
        self.assertEqual(
            sorted(languages.ANALYZERS), ["c", "go", "java", "kotlin", "python", "rust"]
        )

    def test_unknown_language_is_reported(self):
        with self.assertRaises(SystemExit):
            languages.get("cobol")

    def test_detect_per_fixture(self):
        for name, expected in (
            ("mini-java", "java"),
            ("mini-python", "python"),
            ("mini-rust", "rust"),
            ("mini-kotlin", "kotlin"),
            ("mini-go", "go"),
            ("mini-c", "c"),
        ):
            self.assertEqual(languages.detect(os.path.join(FIXTURES, name)), expected)

    def test_a_tree_without_known_suffixes_is_reported(self):
        only = os.path.join(self.tmp.name, "sources")
        os.makedirs(only, exist_ok=True)
        with open(os.path.join(only, "notes.txt"), "w", encoding="utf-8") as fh:
            fh.write("hello")
        with self.assertRaises(SystemExit) as caught:
            languages.detect(only)
        self.assertIn("no known source files", str(caught.exception))


class TestAnalyzers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def analyze(self, language: str, fixture: str) -> dict:
        return languages.get(language).analyze(os.path.join(FIXTURES, fixture))

    def test_python_packages_and_units(self):
        inventory = self.analyze("python", "mini-python")
        self.assertIn("pkg", inventory["packages"])
        self.assertIn("pkg.core", inventory["packages"])
        names = [u["name"] for u in inventory["packages"]["pkg"]["classes"]]
        self.assertIn("Widget", names)

    def test_python_summary_from_docstring(self):
        inventory = self.analyze("python", "mini-python")
        widget = next(u for u in inventory["packages"]["pkg"]["classes"] if u["name"] == "Widget")
        self.assertIn("widget", widget["summary"].lower())

    def test_python_public_api(self):
        inventory = self.analyze("python", "mini-python")
        widget = next(u for u in inventory["packages"]["pkg"]["classes"] if u["name"] == "Widget")
        self.assertIn("describe", widget["api"])

    def test_rust_units_and_docs(self):
        inventory = self.analyze("rust", "mini-rust")
        package = inventory["packages"]["src"]
        names = [u["name"] for u in package["classes"]]
        self.assertIn("Widget", names)
        widget = next(u for u in package["classes"] if u["name"] == "Widget")
        self.assertIn("widget", widget["summary"].lower())

    def test_kotlin_package_unit_and_api(self):
        inventory = self.analyze("kotlin", "mini-kotlin")
        package = inventory["packages"]["com.example"]
        widget = next(u for u in package["classes"] if u["name"] == "Widget")
        self.assertTrue(widget["public"])
        self.assertIn("render", widget["api"])
        self.assertIn("widget", widget["summary"].lower())

    def test_kotlin_imports_become_dependencies(self):
        inventory = self.analyze("kotlin", "mini-kotlin")
        package = inventory["packages"]["com.example"]
        self.assertIn("kotlinx.coroutines", package["depends_on"])

    def test_a_kotlin_file_without_a_package_line_falls_back_to_its_directory(self):
        root = os.path.join(self.tmp.name, "src")
        path = os.path.join(root, "app", "util", "Util.kt")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("class Util\n")
        analyzer = languages.get("kotlin")
        self.assertEqual(analyzer.package_of(root, path), "app.util")

    def test_a_kotlin_type_without_a_doc_comment_has_an_empty_summary(self):
        path = os.path.join(self.tmp.name, "Plain.kt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("package p\n\nclass Plain\n")
        module = languages.get("kotlin").parse(path)
        self.assertEqual(module.package, "p")
        self.assertEqual(module.units[0].summary, "")

    def test_a_go_file_without_a_package_line_falls_back_to_its_directory(self):
        root = os.path.join(self.tmp.name, "src")
        path = os.path.join(root, "app", "util", "util.go")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("func F() {}\n")
        self.assertEqual(languages.get("go").package_of(root, path), "app/util")

    def test_a_go_build_directive_is_not_read_as_a_doc_comment(self):
        path = os.path.join(self.tmp.name, "tagged.go")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("//go:build linux\n\npackage p\n\ntype T struct{}\n")
        module = languages.get("go").parse(path)
        self.assertEqual(module.units[0].summary, "")

    def test_go_package_units_and_visibility(self):
        inventory = self.analyze("go", "mini-go")
        package = next(iter(inventory["packages"].values()))
        names = {u["name"]: u for u in package["classes"]}
        self.assertIn("Widget", names)
        self.assertTrue(names["Widget"]["public"])
        self.assertFalse(names["hidden"]["public"])

    def test_go_imports_become_dependencies(self):
        inventory = self.analyze("go", "mini-go")
        package = next(iter(inventory["packages"].values()))
        self.assertIn("fmt", package["depends_on"])

    def test_c_packages_come_from_directories(self):
        inventory = self.analyze("c", "mini-c")
        self.assertEqual(sorted(inventory["packages"]), ["include", "src", "tools"])
        self.assertEqual(inventory["totals"]["files"], 4)

    def test_c_quoted_includes_become_dependencies_and_system_headers_do_not(self):
        package = self.analyze("c", "mini-c")["packages"]["src"]
        self.assertEqual(package["depends_on"], {"include": 1})

    def test_c_header_declarations_are_public_and_carry_the_api(self):
        package = self.analyze("c", "mini-c")["packages"]["src"]
        units = {u["name"]: u for u in package["classes"]}
        self.assertTrue(units["Widget"]["public"])
        self.assertEqual(units["Widget"]["kind"], "struct")
        self.assertEqual(units["WidgetState"]["kind"], "enum")
        self.assertIn("widget_render", units["Widget"]["api"])

    def test_c_static_helpers_stay_out_of_the_api(self):
        package = self.analyze("c", "mini-c")["packages"]["src"]
        api = {name for unit in package["classes"] for name in unit["api"]}
        self.assertNotIn("widget_note", api)

    def test_c_file_without_a_comment_has_no_summary(self):
        package = self.analyze("c", "mini-c")["packages"]["tools"]
        self.assertEqual(package["summary"], "")
        self.assertEqual(package["depends_on"], {"src": 1})

    def test_java_packages(self):
        inventory = self.analyze("java", "mini-java")
        self.assertIn("org.example", inventory["packages"])
        package = inventory["packages"]["org.example"]
        self.assertGreaterEqual(package["files"], 1)
        self.assertIn("Widget", [u["name"] for u in package["classes"]])

    def test_analyzers_report_totals(self):
        for language, fixture in (
            ("java", "mini-java"),
            ("python", "mini-python"),
            ("rust", "mini-rust"),
        ):
            inventory = self.analyze(language, fixture)
            self.assertGreater(inventory["totals"]["files"], 0, language)
            self.assertGreater(inventory["totals"]["lines"], 0, language)


class AnalyzerBaseTest(unittest.TestCase):
    """The defaults a new language adapter inherits from the base class."""

    def setUp(self):
        self.base = importlib.import_module("ingest.languages._base")

    def test_the_default_package_is_the_directory_below_the_root(self):
        analyzer = self.base.Analyzer()
        self.assertEqual(analyzer.package_of("/src/tree", "/src/tree/a/b/Widget.java"), "a.b")

    def test_a_file_at_the_root_belongs_to_the_root_package(self):
        self.assertEqual(self.base.Analyzer().package_of("/src/tree", "/src/tree/setup.py"), "root")

    def test_the_base_analyzer_leaves_parsing_to_its_subclasses(self):
        with self.assertRaises(NotImplementedError):
            self.base.Analyzer().parse("/src/tree/x.py")


class CSourceTreeTest(unittest.TestCase):
    """Trees the mini-c fixture lacks: header-only APIs, lost includes, repeat tags."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.srctree = os.path.join(self.tmp.name, "csrc")

    def write(self, rel: str, text: str) -> None:
        path = os.path.join(self.srctree, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def package(self, name: str) -> dict:
        return languages.get("c").analyze(self.srctree)["packages"][name]

    def test_a_header_with_only_prototypes_still_exposes_a_unit(self):
        self.write("api/ping.h", "/**/\nextern int ping(void);\n")
        package = self.package("api")
        self.assertEqual([unit["name"] for unit in package["classes"]], ["ping"])
        unit = package["classes"][0]
        self.assertEqual(unit["kind"], "header")
        self.assertTrue(unit["public"])
        self.assertIn("ping", unit["api"])
        self.assertEqual(package["summary"], "")

    def test_an_include_that_is_not_in_the_tree_is_dropped(self):
        self.write("lib/impl.c", '#include "missing.h"\n\nstatic void helper(void) {}\n')
        self.assertEqual(self.package("lib")["depends_on"], {})

    def test_the_same_tag_defined_twice_is_listed_once(self):
        self.write(
            "dup/dup.h",
            "#ifdef HOST\nstruct Thing { int id; };\n#endif\n"
            "#ifdef GUEST\nstruct Thing { int id; };\n#endif\n",
        )
        names = [unit["name"] for unit in self.package("dup")["classes"]]
        self.assertEqual(names, ["Thing"])


class TestDigestLanguages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def configure(self, languages: list[str], fixture: str) -> None:
        base_path = os.path.join(self.root, "data", "config", "base.json")
        with open(base_path, encoding="utf-8") as fh:
            base = json.load(fh)
        base["sources"]["src_main"] = os.path.join(FIXTURES, fixture)
        base["sources"]["languages"] = languages
        with open(base_path, "w", encoding="utf-8") as fh:
            json.dump(base, fh, ensure_ascii=False, indent=2)

    def run_digest(self) -> dict:
        code, out = _fixture.run_inproc(self.root, "digest.py")
        self.assertEqual(code, 0, out[-400:])
        with open(
            os.path.join(self.root, "data", "state", "source-inventory.json"), encoding="utf-8"
        ) as fh:
            return json.load(fh)

    def test_python_digest(self):
        self.configure(["python"], "mini-python")
        inventory = self.run_digest()
        self.assertEqual(inventory["languages"], ["python"])
        self.assertIn("pkg", inventory["packages"])
        self.assertEqual(inventory["packages"]["pkg"]["language"], "python")

    def test_rust_digest(self):
        self.configure(["rust"], "mini-rust")
        inventory = self.run_digest()
        self.assertEqual(inventory["languages"], ["rust"])
        self.assertIn("src", inventory["packages"])

    def test_multi_language_digest_prefixes(self):
        self.configure(["java", "python"], "mini-java")
        inventory = self.run_digest()
        # java-only tree: python contributes nothing but the language is listed
        self.assertEqual(inventory["languages"], ["java", "python"])
        self.assertIn("java:org.example", inventory["packages"])


if __name__ == "__main__":
    unittest.main()


class JavaAnalyzerBranchesTest(unittest.TestCase):
    """A javadoc summary and a package import are the two paths a fixture skips."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.analyzer = languages.get("java")

    def write(self, name: str, body: str) -> str:
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
        return path

    def test_the_javadoc_becomes_the_unit_summary(self):
        path = self.write(
            "Widget.java", "public class Widget { }\n/**\n * A widget that holds state.\n */\n"
        )
        module = self.analyzer.parse(path)
        self.assertEqual(module.units[0].summary, "A widget that holds state.")
        self.assertEqual(module.summary, "A widget that holds state.")

    def test_an_import_becomes_its_package_dependency(self):
        path = self.write(
            "Store.java",
            "package a.b;\nimport org.h2.engine.Database;\npublic class Store { void open() {} }\n",
        )
        module = self.analyzer.parse(path)
        self.assertEqual(module.depends_on.get("org.h2"), 1)  # the file's own package
