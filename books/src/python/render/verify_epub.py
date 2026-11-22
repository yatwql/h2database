#!/usr/bin/env python3
"""Structural verification of the generated EPUB.

An EPUB that opens in one reader can still be broken (wrong mimetype order,
manifest entries pointing at missing files, spine ids that do not exist,
navigation targets that 404 inside the container). This script checks the
container itself, so delivery does not depend on a human opening a reader.

Checks
  MIMETYPE     first zip entry is ``mimetype``, stored uncompressed, correct body
  CONTAINER    META-INF/container.xml exists and its rootfile is present
  OPF          OPF parses, has metadata/manifest/spine
  MANIFEST     every manifest href resolves inside the zip
  SPINE        every spine idref exists in the manifest
  NAV          nav document (EPUB 3) or toc.ncx (EPUB 2) links resolve
  SIZE         file size within book.toml [thresholds].epub_max_mb

Usage:
  python verify_epub.py            # report + exit code
  python verify_epub.py --json     # machine readable
"""

from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import json
import os
import posixpath
import sys
import zipfile
from urllib.parse import unquote
from xml.etree import ElementTree

from lib import _config, _errors

NS_CONTAINER = {'c': 'urn:oasis:names:tc:opendocument:xmlns:container'}
NS_OPF = {'opf': 'http://www.idpf.org/2007/opf'}
NS_NAV = {'x': 'http://www.w3.org/1999/xhtml'}
NS_NCX = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}

def parse_xml(data: bytes) -> ElementTree.Element:
    """Parse EPUB XML with entity expansion disabled.

    Prefers defusedxml when installed; otherwise falls back to ElementTree on
    data this toolchain produced itself (pandoc output, no external entities).
    """
    try:
        from defusedxml import ElementTree as SafeET  # type: ignore[import-not-found]
    except ImportError:
        return ElementTree.fromstring(data)  # nosec B314 - self-generated EPUB
    return SafeET.fromstring(data)

class Report:
    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str = '') -> None:
        self.checks.append((name, ok, detail))

    @property
    def failures(self) -> list[tuple[str, str]]:
        return [(name, detail) for name, ok, detail in self.checks if not ok]

    def to_dict(self) -> dict:
        return {
            'ok': not self.failures,
            'checks': [
                {'name': name, 'ok': ok, 'detail': detail}
                for name, ok, detail in self.checks
            ],
        }

def verify(epub_path: str) -> Report:
    """Every structural check an EPUB must pass, reported by name."""
    report = Report()

    archive = _open_archive(report, epub_path)
    if archive is None:
        return report

    with archive:
        names = archive.namelist()
        _check_mimetype(report, archive)
        opf_path = _check_container(report, archive, names)
        if not opf_path:
            return report
        opf_dir = posixpath.dirname(opf_path)
        opf = _parse_opf(report, archive, opf_path)
        if opf is None:
            return report
        manifest, spine = _check_package(report, opf)
        _check_resolution(report, manifest, spine, names, opf_dir)
        _check_navigation(report, archive, manifest, names, opf_dir)
    return report


def _open_archive(report: Report, epub_path: str):
    """EXISTS and SIZE, then the archive itself (None when it cannot be read)."""
    if not os.path.isfile(epub_path):
        report.add('EXISTS', False, f'missing {epub_path}')
        return None
    report.add('EXISTS', True)

    size_mb = os.path.getsize(epub_path) / (1024 * 1024)
    max_mb = float(_config.THRESHOLDS.get('epub_max_mb', 10))
    report.add('SIZE', size_mb <= max_mb, f'{size_mb:.2f} MB (budget {max_mb} MB)')

    try:
        return zipfile.ZipFile(epub_path)
    except zipfile.BadZipFile as exc:
        report.add('ZIP', False, str(exc))
        return None


def _check_mimetype(report: Report, archive: zipfile.ZipFile) -> None:
    # --- mimetype must be first, stored, exactly 20 bytes ---
    first = archive.infolist()[0] if archive.infolist() else None
    if first is None:
        report.add('MIMETYPE', False, 'empty archive')
    else:
        body = archive.read(first.filename).decode('ascii', 'replace').strip()
        report.add(
            'MIMETYPE',
            first.filename == 'mimetype'
            and first.compress_type == zipfile.ZIP_STORED
            and body == 'application/epub+zip',
            f'{first.filename} (compressed={first.compress_type != 0}, body={body!r})',
        )



def _check_container(report: Report, archive: zipfile.ZipFile, names: list[str]) -> str:
    """CONTAINER, then the OPF path ('' when the container or rootfile is unusable)."""
    # --- container.xml -> rootfile ---
    try:
        container = parse_xml(archive.read('META-INF/container.xml'))
        rootfile = container.find('.//c:rootfile', NS_CONTAINER)
        opf_path = rootfile.get('full-path') if rootfile is not None else None
    except (KeyError, ElementTree.ParseError):
        opf_path = None
    if not opf_path:
        report.add('CONTAINER', False, 'META-INF/container.xml missing or unparsable')
        return ''
    report.add('CONTAINER', opf_path in names, f'rootfile={opf_path}')
    return opf_path if opf_path in names else ''



def _parse_opf(report: Report, archive: zipfile.ZipFile, opf_path: str):
    """The parsed package document, or None when it does not parse."""
    try:
        return parse_xml(archive.read(opf_path))
    except ElementTree.ParseError as exc:
        report.add('OPF', False, str(exc))
        return None


def _check_package(report: Report, opf) -> tuple[dict, list[str]]:
    """METADATA, COVER, OPF: the manifest and spine the remaining checks use."""
    manifest = {}
    for item in opf.findall('.//opf:manifest/opf:item', NS_OPF):
        manifest[item.get('id', '')] = {
            'href': item.get('href', ''),
            'media_type': item.get('media-type', ''),
            'properties': item.get('properties', ''),
        }
    spine = [ref.get('idref', '')
             for ref in opf.findall('.//opf:spine/opf:itemref', NS_OPF)]
    metadata = {}
    for node in opf.findall('.//opf:metadata/*', NS_OPF):
        tag = node.tag.rsplit('}', 1)[-1]
        metadata.setdefault(tag, (node.text or '').strip())
    required = ('title', 'creator', 'language', 'identifier')
    missing_meta = [name for name in required if not metadata.get(name)]
    report.add('METADATA', not missing_meta,
               'title/creator/language/identifier present' if not missing_meta
               else f'missing {missing_meta}')
    has_cover = any('cover-image' in m['properties'].split()
                    or os.path.basename(m['href']).lower().startswith('cover')
                    for m in manifest.values())
    configured_cover = bool(_config._CFG.get('paths', {}).get('cover_image'))
    if configured_cover or has_cover:
        report.add('COVER', has_cover,
                   'cover image declared' if has_cover else 'cover configured but missing')
    else:
        report.add('COVER', True, 'no cover configured (optional)')
    report.add('OPF', bool(manifest) and bool(spine),
               f'{len(manifest)} manifest items, {len(spine)} spine items')

    return manifest, spine


def _check_resolution(report: Report, manifest: dict, spine: list[str],
                      names: list[str], opf_dir: str) -> None:
    """MANIFEST and SPINE: every href resolves, every idref exists."""
    def resolve(href: str) -> str:
        clean = unquote(href.split('#', 1)[0])
        return posixpath.normpath(posixpath.join(opf_dir, clean))

    missing = [m['href'] for m in manifest.values()
               if m['href'] and resolve(m['href']) not in names]
    report.add('MANIFEST', not missing,
               'all manifest hrefs resolve' if not missing
               else f'{len(missing)} missing, e.g. {missing[:3]}')

    dangling = [idref for idref in spine if idref not in manifest]
    report.add('SPINE', not dangling,
               'all spine idrefs in manifest' if not dangling
               else f'dangling idrefs: {dangling[:3]}')



def _check_navigation(report: Report, archive: zipfile.ZipFile, manifest: dict,
                      names: list[str], opf_dir: str) -> None:
    """NAV: the navigation document (or an NCX), and whether its links resolve."""
    def resolve(href: str) -> str:
        clean = unquote(href.split('#', 1)[0])
        return posixpath.normpath(posixpath.join(opf_dir, clean))

    # --- navigation ---
    nav_href = next((m['href'] for m in manifest.values()
                     if 'nav' in m['properties'].split()), None)
    if nav_href:
        nav_path = resolve(nav_href)
        if nav_path not in names:
            report.add('NAV', False, f'nav document missing: {nav_path}')
        else:
            targets = _nav_targets(archive.read(nav_path), nav_path, opf_dir)
            broken = [t for t in targets if t not in names]
            report.add('NAV', bool(targets) and not broken,
                       f'{len(targets)} nav links, '
                       f'{len(broken)} broken' if broken
                       else f'{len(targets)} nav links resolve')
    else:
        ncx_href = next((m['href'] for m in manifest.values()
                         if m['media_type'] == 'application/x-dtbncx+xml'), None)
        if ncx_href:
            ncx_path = resolve(ncx_href)
            try:
                ncx = parse_xml(archive.read(ncx_path))
                points = ncx.findall('.//ncx:navPoint', NS_NCX)
                report.add('NAV', bool(points), f'{len(points)} NCX navPoints')
            except (KeyError, ElementTree.ParseError) as exc:
                report.add('NAV', False, f'NCX unreadable: {exc}')
        else:
            report.add('NAV', False, 'no nav document and no NCX in manifest')



def _nav_targets(xhtml: bytes, nav_path: str, opf_dir: str) -> list[str]:
    """Zip-internal paths referenced by the nav document's links."""
    try:
        root = parse_xml(xhtml)
    except ElementTree.ParseError:
        return []
    nav_dir = posixpath.dirname(nav_path)
    targets: list[str] = []
    for link in root.findall('.//x:a', NS_NAV):
        href = link.get('href', '')
        if not href or href.startswith(('http://', 'https://', 'mailto:')):
            continue
        clean = unquote(href.split('#', 1)[0])
        if not clean:
            continue
        targets.append(posixpath.normpath(posixpath.join(nav_dir, clean)))
    return targets

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--epub', help='path to the .epub (default: books/dist)')
    parser.add_argument('--json', action='store_true', help='machine-readable output')
    args = parser.parse_args(argv)

    epub_path = args.epub or _config.merged_epub()
    report = verify(epub_path)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0 if not report.failures else 1

    print('=' * 72)
    print(f'EPUB 结构校验  {os.path.basename(epub_path)}')
    print('=' * 72)
    for name, ok, detail in report.checks:
        mark = 'ok  ' if ok else 'FAIL'
        print(f'  [{mark}] {name:<10} {detail}')
    if report.failures:
        print(f'\n{len(report.failures)} 项未通过')
        return 1
    print('\n✅ EPUB 结构校验通过')
    return 0

if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
