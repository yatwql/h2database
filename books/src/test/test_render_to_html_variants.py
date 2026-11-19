#!/usr/bin/env python3
"""to_html: markdown and cover variants the real book relies on."""
from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

_fixture.ensure_tools_path()

MERGED = """<!-- versions: tool=0.1 source=0.0 doc=0.1 -->

# 第1章 测试

正文一段，含 `inline code` 与 **加粗**。

```text
+----+
| 图 |
+----+
```

**图 1-1: 展示组件**

---

```java
void run() {}
```

> 引用一行
"""

COVER = """# 测试之书

## 副标题

版本 v0.1 · 2026-01-01 · 100 行
深入剖析本书的全部实现细节。
共 12 章 + 5 附录 · 100 图

**作者：其·龙**
**联系邮箱：a@b.c**
"""


class ToHtmlVariantTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def build(self, merged: str = MERGED, cover: str = COVER) -> tuple[int, str, str]:
        dist = os.path.join(self.root, 'dist')
        os.makedirs(dist, exist_ok=True)
        with open(os.path.join(dist, 'test-book.md'), 'w', encoding='utf-8') as fh:
            fh.write(merged)
        with open(os.path.join(self.root, 'data', 'manuscript', 'cover.md'),
                  'w', encoding='utf-8') as fh:
            fh.write(cover)
        code, out = _fixture.run_inproc(self.root, 'to_html.py')
        html_path = os.path.join(dist, 'test-book.html')
        html = ''
        if os.path.isfile(html_path):
            with open(html_path, encoding='utf-8') as fh:
                html = fh.read()
        return code, out, html

    def test_full_document_renders_every_block_type(self):
        code, out, html = self.build()
        self.assertEqual(code, 0, out[-500:])
        self.assertIn('<pre><code>', html)
        self.assertIn('fig-caption', html)
        self.assertIn('<hr>', html)
        self.assertIn('引用一行', html)  # blockquotes keep their text
        self.assertIn('<code>inline code</code>', html)

    def test_cover_title_is_rendered(self):
        code, out, html = self.build()
        self.assertEqual(code, 0, out[-400:])
        self.assertIn('测试之书', html)

    def test_cover_without_metadata_still_renders(self):
        code, out, html = self.build(cover='# 只有标题\n')
        self.assertEqual(code, 0, out[-400:])
        self.assertTrue(html)
        self.assertIn('<h1', html)

    def test_unclosed_fence_at_end_is_closed(self):
        merged = MERGED + '\n```text\n未闭合的一段\n'
        code, out, html = self.build(merged=merged)
        self.assertEqual(code, 0, out[-500:])
        self.assertIn('</code></pre>', html)

    def test_bare_fence_after_auto_exit_is_consumed(self):
        merged = MERGED + '\n```text\n自动退出的块\n```\n普通段落\n```\n'
        code, out, html = self.build(merged=merged)
        self.assertEqual(code, 0, out[-500:])
        self.assertIn('普通段落', html)

    def test_headings_get_anchor_ids(self):
        _code, _out, html = self.build()
        self.assertRegex(html, r'<h1[^>]*id="')


if __name__ == '__main__':
    unittest.main()
