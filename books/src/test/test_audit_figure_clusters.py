#!/usr/bin/env python3
"""Unit tests for the helper functions behind the audits.

These target the pure logic (counting, parsing, clustering, PDF checks) that the
end-to-end tests exercise only indirectly.
"""

import io
import json
import os
import sys
import unittest
from unittest import mock

from _cases import FixtureCase

TAGS = ("layer:audit", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class TestFigureClusterHelpers(FixtureCase):
    FIGURES = (
        "展示三个组件之间的调用关系与数据流向。\n\n"
        "**图 1-1: 展示组件 A 的调用**\n\n"
        "**图 1-2: 展示组件 B 的调用**\n\n"
        "**图 1-3: 展示组件 C 的调用**\n"
    )

    def test_find_clusters_with_bridge(self):
        clusters = self.module("figure_clusters")
        path = self.write("data/manuscript/cluster.md", self.FIGURES)
        found = clusters.find_clusters(path, min_figs=3, window=40)
        self.assertEqual(len(found), 1)

    def test_find_clusters_without_bridge(self):
        clusters = self.module("figure_clusters")
        path = self.write(
            "data/manuscript/cluster2.md",
            "**图 2-1: 展示 A**\n\n**图 2-2: 展示 B**\n\n**图 2-3: 展示 C**\n",
        )
        found = clusters.find_clusters(path, min_figs=3, window=40)
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0]["bridged"])

    def test_window_default_comes_from_the_config(self):
        clusters = self.module("figure_clusters")
        patched = dict(clusters._config.STYLE_POLICY)
        patched["clusters"] = {"min_figures": 2, "window_lines": 12}
        # the module reads the manuscript directory through the active book, which
        # this fixture already is, so only the policy needs patching
        with (
            mock.patch.object(clusters._config, "STYLE_POLICY", patched),
            mock.patch("sys.stdout", new=io.StringIO()) as out,
        ):
            clusters.main(["--json"])
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["window_lines"], 12)
        self.assertEqual(payload["min_figs"], 2)

    def test_no_cluster_below_threshold(self):
        clusters = self.module("figure_clusters")
        path = self.write("data/manuscript/single.md", "**图 3-1: 展示 A**\n")
        self.assertEqual(clusters.find_clusters(path, min_figs=3, window=40), [])

    def test_bridge_hint_in_the_leading_paragraph_marks_the_cluster(self):
        clusters = self.module("figure_clusters")
        path = self.write(
            "data/manuscript/bridged.md",
            "以下三张图共同展示调用的三个阶段。\n\n"
            "**图 4-1: 展示调用入口**\n\n"
            "**图 4-2: 展示调用路由**\n\n"
            "**图 4-3: 展示调用返回**\n",
        )
        found = clusters.find_clusters(path, min_figs=3, window=40)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["bridged"])
        self.assertEqual(found[0]["bridge_hint"], "以下三张图")

    def test_a_file_without_figure_captions_has_no_clusters(self):
        clusters = self.module("figure_clusters")
        path = self.write("data/manuscript/plain.md", "# 第5章 测试章节\n\n只有正文，没有图。\n")
        self.assertEqual(clusters.find_clusters(path, min_figs=2, window=2), [])

    def test_a_gap_closes_a_cluster_only_when_it_reaches_the_threshold(self):
        clusters = self.module("figure_clusters")
        lines = [""] * 40
        for line, fig in ((1, 1), (3, 2), (7, 3), (9, 4), (25, 5), (40, 6)):
            lines[line - 1] = f"**图 9-{fig}: 展示第 {fig} 幅**"
        path = self.write("data/manuscript/gaps.md", "\n".join(lines) + "\n")
        found = clusters.find_clusters(path, min_figs=2, window=2)
        self.assertEqual([c["first_line"] for c in found], [1, 7])


if __name__ == "__main__":
    unittest.main()
