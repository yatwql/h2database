#!/usr/bin/env python3
"""verify_epub: synthetic EPUB packages for every check it performs."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout

import _fixture

TAGS = ("layer:render", "tier:fast")

_fixture.ensure_tools_path()

CONTAINER = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""

NAV = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <body><nav epub:type="toc"><ol>
    <li><a href="text/ch1.xhtml">第一章</a></li>
  </ol></nav></body>
</html>
"""


def opf(metadata: str = "", extra_manifest: str = "", spine: str = "", nav: bool = True) -> str:
    meta = metadata or (
        "<dc:title>T</dc:title><dc:creator>A</dc:creator>"
        + "<dc:language>zh</dc:language>"
        + '<dc:identifier id="id">urn:uuid:1</dc:identifier>'
    )
    nav_item = (
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        if nav
        else ""
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">{meta}</metadata>
  <manifest>
    <item id="ch1" href="text/ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    {nav_item}{extra_manifest}
  </manifest>
  <spine>{spine or '<itemref idref="ch1"/>'}</spine>
</package>
"""


def ncx(points: int = 1) -> str:
    body = "".join(
        f'<navPoint id="p{i}" playOrder="{i}"><navLabel><text>c</text>'
        f'</navLabel><content src="text/ch1.xhtml"/></navPoint>'
        for i in range(points)
    )
    return (
        '<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" '
        f'version="2005-1"><navMap>{body}</navMap></ncx>'
    )


class EpubVerifySyntheticTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(
            os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR)), "verify_epub"
        )

    def build(
        self,
        *,
        mimetype: str | None = "application/epub+zip",
        container: str | None = CONTAINER,
        opf_text: str | None = None,
        nav: str | None = NAV,
        ncx_text: str | None = None,
        with_ch1: bool = True,
        first_entry: str = "mimetype",
        files: dict[str, str] | None = None,
    ) -> str:
        path = os.path.join(self.tmp.name, "book.epub")
        with zipfile.ZipFile(path, "w") as zf:

            def add(name: str, data: str, stored: bool = False) -> None:
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
                zf.writestr(info, data)

            if mimetype is not None and first_entry == "mimetype":
                add("mimetype", mimetype, stored=True)
            if container is not None:
                add("META-INF/container.xml", container)
            add("OEBPS/content.opf", opf_text if opf_text is not None else opf())
            if with_ch1:
                add("OEBPS/text/ch1.xhtml", "<html><body><h1>c</h1></body></html>")
            if nav is not None:
                add("OEBPS/nav.xhtml", nav)
            for name, data in (files or {}).items():
                add(name, data)
            if ncx_text is not None:
                add("OEBPS/toc.ncx", ncx_text)
            if mimetype is not None and first_entry != "mimetype":
                add("mimetype", mimetype, stored=True)
        return path

    def check(self, report, name: str) -> tuple[bool, str]:
        for check_name, ok, detail in report.checks:
            if check_name == name:
                return ok, detail
        self.fail(f"{name} missing from {[c[0] for c in report.checks]}")

    def test_a_well_formed_epub_passes_every_check(self):
        report = self.mod.verify(self.build(ncx_text=ncx()))
        self.assertTrue(report.to_dict()["ok"], report.to_dict())

    def test_not_a_zip_is_reported(self):
        path = os.path.join(self.tmp.name, "broken.epub")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not a zip")
        self.assertFalse(self.check(self.mod.verify(path), "ZIP")[0])

    def test_missing_mimetype_is_reported(self):
        report = self.mod.verify(self.build(mimetype=None))
        self.assertFalse(self.check(report, "MIMETYPE")[0])

    def test_wrong_mimetype_body_is_reported(self):
        report = self.mod.verify(self.build(mimetype="text/plain"))
        self.assertFalse(self.check(report, "MIMETYPE")[0])

    def test_mimetype_not_first_is_reported(self):
        report = self.mod.verify(self.build(first_entry="container"))
        self.assertFalse(self.check(report, "MIMETYPE")[0])

    def test_missing_container_is_reported(self):
        report = self.mod.verify(self.build(container=None))
        self.assertFalse(self.check(report, "CONTAINER")[0])

    def test_unparsable_opf_is_reported(self):
        report = self.mod.verify(self.build(opf_text="<package"))
        self.assertFalse(self.check(report, "OPF")[0])

    def test_missing_metadata_is_reported(self):
        report = self.mod.verify(self.build(opf_text=opf(metadata="<dc:title>T</dc:title>")))
        ok, detail = self.check(report, "METADATA")
        self.assertFalse(ok)
        self.assertIn("creator", detail)

    def test_missing_manifest_target_is_reported(self):
        report = self.mod.verify(self.build(with_ch1=False, nav=NAV, ncx_text=ncx()))
        self.assertFalse(self.check(report, "MANIFEST")[0])

    def test_dangling_spine_entry_is_reported(self):
        report = self.mod.verify(self.build(opf_text=opf(spine='<itemref idref="ghost"/>')))
        self.assertFalse(self.check(report, "SPINE")[0])

    def test_ncx_is_used_when_there_is_no_nav_document(self):
        report = self.mod.verify(self.build(opf_text=opf(nav=False), nav=None, ncx_text=ncx(2)))
        ok, detail = self.check(report, "NAV")
        self.assertTrue(ok, detail)
        self.assertIn("navPoints", detail)

    def test_epub_without_any_navigation_is_reported(self):
        report = self.mod.verify(self.build(opf_text=opf(nav=False), nav=None))
        self.assertFalse(self.check(report, "NAV")[0])

    def test_broken_nav_links_are_reported(self):
        broken = NAV.replace("text/ch1.xhtml", "text/missing.xhtml")
        report = self.mod.verify(self.build(nav=broken))
        ok, detail = self.check(report, "NAV")
        self.assertFalse(ok)
        self.assertIn("broken", detail)

    def test_an_empty_archive_is_reported_as_having_no_mimetype(self):
        path = os.path.join(self.tmp.name, "empty.epub")
        zipfile.ZipFile(path, "w").close()
        ok, detail = self.check(self.mod.verify(path), "MIMETYPE")
        self.assertFalse(ok)
        self.assertEqual(detail, "empty archive")

    def test_a_cover_image_in_the_manifest_satisfies_the_cover_check(self):
        cover_item = (
            '<item id="cover" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>'
        )
        report = self.mod.verify(
            self.build(
                opf_text=opf(extra_manifest=cover_item),
                files={"OEBPS/cover.jpg": "jpeg"},
                ncx_text=ncx(),
            )
        )
        ok, detail = self.check(report, "COVER")
        self.assertTrue(ok, detail)
        self.assertIn("declared", detail)

    def test_a_package_with_neither_nav_nor_ncx_is_reported(self):
        without_ncx = opf(nav=False).replace(
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>', ""
        )
        report = self.mod.verify(self.build(opf_text=without_ncx, nav=None))
        ok, detail = self.check(report, "NAV")
        self.assertFalse(ok)
        self.assertIn("no nav document", detail)

    def test_an_unparsable_nav_document_yields_no_targets(self):
        report = self.mod.verify(self.build(nav="<html><body><nav>"))
        ok, detail = self.check(report, "NAV")
        self.assertFalse(ok)
        self.assertIn("0 nav links", detail)

    def test_nav_links_outside_the_archive_are_ignored(self):
        nav = NAV.replace(
            '<li><a href="text/ch1.xhtml">第一章</a></li>',
            '<li><a href="text/ch1.xhtml">第一章</a></li>'
            '<li><a href="https://example.com/x">外链</a></li>'
            '<li><a href="">空</a></li>'
            '<li><a href="#anchor">锚点</a></li>',
        )
        report = self.mod.verify(self.build(nav=nav))
        ok, detail = self.check(report, "NAV")
        self.assertTrue(ok, detail)
        self.assertIn("1 nav links", detail)

    def test_main_reports_a_clean_package(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(["--epub", self.build(ncx_text=ncx())])
        self.assertEqual(code, 0, buffer.getvalue()[-300:])
        self.assertIn("EPUB 结构校验通过", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
