#!/usr/bin/env python3
"""Render the PDF one H1 chapter at a time, then merge.

Why this exists: printing the whole document in one `page.pdf()` call is subject
to a whole-page fit-to-scale step that normalises density — page margins, column
width and font size all landed inside 725–754 pages whatever the value, and a
*larger* body font produced *fewer* pages (impossible without a hidden scale).
Rendering each chapter into its own page box keeps every chapter at 1:1, so the
typography decides pagination again, and the outline is computed from chapter
page offsets instead of searching layout-dependent markers (see rf-44).
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

from lib import _browser, _log
from pypdf import PdfReader, PdfWriter

MARKER_RE = re.compile(r"__hdr_(\d+)__")

# One injection for every entry point that renders this book: a content marker at the
# top of #content and a `__hdr_<n>__` before each heading. The marker survives to the
# text layer (3px, white), so the outline maps straight back to the heading list.
INJECT_JS = """() => {
    const content = document.getElementById('content');
    if (!content) return [];
    const mark = (text, before) => {
        const span = document.createElement('span');
        span.textContent = text;
        span.style.cssText = 'display:inline;font-size:3px;color:#ffffff;'
            + 'pointer-events:none;user-select:none;';
        before.parentNode.insertBefore(span, before);
    };
    mark('__CONTENT__', content.firstChild);
    const els = content.querySelectorAll('h1[id], h2[id], h3[id], h4[id]');
    return [...els].map((h, i) => {
        mark('__hdr_' + i + '__', h);
        return {index: i, id: h.id, text: h.textContent.trim(),
                level: parseInt(h.tagName.substring(1))};
    });
}"""

SPLIT_JS = """() => {
    const content = document.getElementById('content');
    if (!content) return [];
    const html = content.innerHTML;
    // split at H1 boundaries; the first chunk may be empty
    const chunks = html.split(/(?=<h1\\b)/i).map(s => s.trim()).filter(Boolean);
    return chunks.map(chunk => {
        const holder = document.createElement('div');
        holder.innerHTML = chunk;
        const heads = [...holder.querySelectorAll('h1, h2, h3, h4')].map(h => ({
            level: parseInt(h.tagName.substring(1)),
            text: h.textContent.trim(),
        }));
        return {html: chunk, headings: heads};
    });
}"""


def _strip_ws(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _page_texts(pdf_path: str) -> list[str]:
    from pypdf import PdfReader

    return [_strip_ws(page.extract_text() or "") for page in PdfReader(pdf_path).pages]


def render_parts(
    page, work_dir: str, pdf_kwargs: dict, headings: list[dict]
) -> tuple[list[str], list[dict]]:
    """Render front matter and every chapter; returns (pdf paths, outline entries).

    Headings are located by the `__hdr_<index>__` markers the caller injects into
    each heading (3px white text, so they survive as real text in the layer). The
    index is global, so the marker maps straight back to `headings` — no title
    search, which used to lose entries to line wrapping and repeated short titles.
    """
    # lay the content out at the paper width (A4 at 96dpi) before printing, or
    # Chromium paginates against the 800x600 default viewport and doubles the count
    page.set_viewport_size({"width": 794, "height": 1123})
    parts = page.evaluate(SPLIT_JS)
    if not parts:
        raise RuntimeError("no chapters found in #content")

    by_index = {h["index"]: h for h in headings if "index" in h}
    seen: set[int] = set()
    paths: list[str] = []
    entries: list[dict] = []
    offset = 0

    front = os.path.join(work_dir, "part-000.pdf")
    page.evaluate(
        "() => { const c = document.getElementById('content'); if (c) c.style.display = 'none'; }"
    )
    page.pdf(path=front, **pdf_kwargs)
    offset += len(_page_texts(front))
    paths.append(front)

    # the cover and the printed TOC belong to the front part only
    page.evaluate("""() => {
        for (const id of ['cover', 'toc-page']) {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        }
    }""")
    for index, part in enumerate(parts, start=1):
        target = os.path.join(work_dir, f"part-{index:03d}.pdf")
        page.evaluate(
            '(payload) => { const c = document.getElementById("content");'
            ' c.style.display = "block"; c.innerHTML = payload.html; }',
            part,
        )
        page.pdf(path=target, **pdf_kwargs)
        texts = _page_texts(target)
        paths.append(target)

        for local, text in enumerate(texts):
            for raw in MARKER_RE.findall(text):
                index = int(raw)  # MARKER_RE only matches digits
                head = by_index.get(index)
                if head is not None and head["index"] not in seen:
                    seen.add(head["index"])
                    entries.append(
                        {"level": head["level"], "text": head["text"], "page": offset + local}
                    )
        offset += len(texts)
    return paths, entries


def merge(paths: list[str], pdf_path: str, entries: list[dict]) -> int:
    """Concatenate the parts and write the outline; returns the page count."""
    writer = PdfWriter()
    for part in paths:
        for page_obj in PdfReader(part).pages:
            writer.add_page(page_obj)

    stack: dict[int, Any] = {}
    for entry in entries:
        parent: Any = None
        for level in sorted(stack):
            if level < entry["level"]:
                parent = stack[level]
        stack[entry["level"]] = writer.add_outline_item(
            title=entry["text"], page_number=entry["page"], parent=parent
        )
        for level in [lvl for lvl in stack if lvl > entry["level"]]:
            del stack[level]
    writer.write(pdf_path)
    return len(writer.pages)


def accept_optimised(
    before_pages: int, before_bytes: int, after_pages: int, after_bytes: int
) -> bool:
    """Whether the gs rewrite may replace the merged file.

    Two conditions, both needed: the page count must survive (a truncated file is
    also a smaller file) and the file must actually be smaller (otherwise the pass
    bought nothing and only risked the merge).
    """
    return after_pages == before_pages and after_bytes < before_bytes


def _optimize(pdf_path: str) -> None:
    """Recompress with ghostscript when it is available and the result is sound.

    pypdf's merge cannot share font programs between the parts, so the merged file
    is larger than the sum of its inputs. gs rewrites the whole file and dedupes
    what it can. The rewrite is accepted only when it is smaller *and* still a
    complete PDF with the same page count: an interrupted gs run leaves a
    truncated file that is smaller than the original, and swapping that in
    corrupts the deliverable.

    Every run is logged (command, both sizes, the decision): whether the pass
    actually fires cannot be told from the output file alone, and a silent skip
    reads exactly like a pass that bought nothing.
    """
    log = _log.get_logger("render.pdf_split")
    before_bytes = os.path.getsize(pdf_path)
    before_pages = len(PdfReader(pdf_path).pages)
    gs = shutil.which("gs")
    if not gs:
        log.info(
            "gs 未安装，跳过分章合并后的压缩：%s %d 页 %.2f MB",
            os.path.basename(pdf_path),
            before_pages,
            before_bytes / 1048576,
        )
        return
    tmp = _scratch_path(pdf_path)
    cmd = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.6",
        "-dPDFSETTINGS=/printer",
        "-dSubsetFonts=true",
        "-dCompressFonts=true",
        "-dDetectDuplicateImages=true",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={tmp}",
        pdf_path,
    ]
    log.debug("gs 压缩：%s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, timeout=600)
        after_bytes = os.path.getsize(tmp)
        after_pages = len(PdfReader(tmp).pages)
        accepted = accept_optimised(before_pages, before_bytes, after_pages, after_bytes)
        log.info(
            "gs 压缩 %s：%d 页 %.2f MB → %d 页 %.2f MB，%s",
            os.path.basename(pdf_path),
            before_pages,
            before_bytes / 1048576,
            after_pages,
            after_bytes / 1048576,
            "已采用" if accepted else "不采用（须同页数且更小）",
        )
        if accepted:
            os.replace(tmp, pdf_path)
    except Exception as exc:
        log.warning("gs 压缩失败，保留合并结果 %s：%s", os.path.basename(pdf_path), exc)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def inject_markers(page) -> list[dict]:
    """Add the content and heading markers; returns the heading records."""
    return page.evaluate(INJECT_JS) or []


def _scratch_path(pdf_path: str) -> str:
    """A hidden sibling for the gs rewrite, on the same filesystem.

    It used to be `<pdf>.gs.pdf`, which reads as a deliverable: a build killed between
    the gs run and the replace left a truncated PDF in `dist/`. The name is now hidden
    and dot-prefixed, so `dist/*` and the archive step cannot pick it up, and it stays
    beside the target because `os.replace` is only atomic within one filesystem.
    """
    return os.path.join(
        os.path.dirname(pdf_path) or ".", "." + os.path.basename(pdf_path) + ".gs.tmp"
    )


def optimize(pdf_path: str) -> None:
    """Compress a finished PDF; the last writer in a pipeline calls this once."""
    _optimize(pdf_path)


def render_html(
    html_path: str,
    pdf_path: str,
    engine: Any = None,
    pdf_kwargs: dict | None = None,
    optimize: bool = True,
) -> int:
    """Split-render an HTML file with the layout's own page box; returns pages.

    Every edition goes through here so a printed page is laid out and paginated by
    the same rules whatever the entry point: the viewport is the sheet at 96dpi and
    the page box comes from the stylesheet (`prefer_css_page_size`), which is what
    makes the column and the margins agree.
    """
    if engine is None:
        from playwright.sync_api import sync_playwright as engine
    kwargs = pdf_kwargs or {
        "format": "A4",
        "print_background": True,
        "display_header_footer": False,
        "prefer_css_page_size": True,
    }
    with engine() as playwright:
        browser = _browser.launch(playwright)
        try:
            page = browser.new_page()
            page.goto(
                "file:///" + str(html_path).replace("\\", "/"),
                wait_until="networkidle",
                timeout=60000,
            )
            page.wait_for_timeout(2000)
            return render(page, pdf_path, kwargs, inject_markers(page), optimize=optimize)
        finally:
            browser.close()


def render(
    page, pdf_path: str, pdf_kwargs: dict, headings: list[dict], optimize: bool = True
) -> int:
    """Split-render into a temporary directory, merge, and report the page count."""
    work = tempfile.mkdtemp(prefix="pdf-split-")
    try:
        paths, entries = render_parts(page, work, pdf_kwargs, headings)
        count = merge(paths, pdf_path, entries)
        if optimize:
            _optimize(pdf_path)
        print(f"  Rendered {len(paths) - 1} chapter part(s) + front matter: {count} pages")
        print(f"  Outline entries: {len(entries)}")
        return count
    finally:
        for name in sorted(os.listdir(work)):
            with contextlib.suppress(OSError):
                os.remove(os.path.join(work, name))
        with contextlib.suppress(OSError):
            os.rmdir(work)
