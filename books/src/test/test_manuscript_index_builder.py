#!/usr/bin/env python3
"""Branch coverage for the audit/report paths.

These exercise the error and edge branches (missing files, empty inputs,
threshold violations, alternate CLI modes) that the happy-path tests skip.
"""

import os
import sys
import unittest

from _cases import FixtureCase

TAGS = ("layer:manuscript", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class TestIndexBuilderBranches(FixtureCase):
    def test_hierarchy_check_on_small_index(self):
        code, out = self.run_script("index.py", "--hierarchy-check")
        self.assertEqual(code, 1, out[-300:])
        self.assertIn("below the configured floor", out)

    def test_heading_levels_metadata_markers_and_repeats(self):
        self.declare("ch3-probe.md")
        self.write(
            "data/manuscript/ch3-probe.md",
            "# 第3章 探针\n\n"
            "## 3.1 二级小节\n\n"
            "正文提到 **池化连接** 的实现。\n\n"
            "### 3.1.1 三级小节\n\n"
            "正文提到 **缓冲页** 的实现。\n\n"
            "#### 3.1.1.1 四级小节\n\n"
            "**源码位置**：lib/x.py\n\n"
            "再次提到 **池化连接** 的内容。\n",
        )
        code, out = self.run_script("index.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("- **3.1.1.1 四级小节** — §3.1.1.1", out)
        self.assertIn("- **池化连接** — §3.1", out)
        self.assertIn("- **缓冲页** — §3.1.1", out)
        self.assertEqual(out.count("**池化连接**"), 1)
        self.assertNotIn("**源码位置**", out)

    def test_missing_index_file(self):
        os.unlink(os.path.join(self.root, "data", "manuscript", "back", "index.md"))
        code, out = self.run_script("index.py")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("第1章", out)  # the draft is rebuilt from the chapters


if __name__ == "__main__":
    unittest.main()
