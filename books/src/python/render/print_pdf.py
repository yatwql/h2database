#!/usr/bin/env python3
"""The print edition: the delivery renderer plus `print_profile`'s typography.

Why this is thin: the print edition and the delivery PDF must agree on the page
box, the column, the code size and the pagination, so both go through
`render.pdf_split`. What a printed page may add — chapter banners, TOC dot leaders —
lives in `render.print_profile`, in `em` and behind `@media print`. Nothing here
sets a scale or a margin: those belong to `lib.layout`, and a second copy of them is
what let the print edition run its text 642pt wide on a 595pt sheet.

Steps (each callable, engine injectable, so tests need no browser):

  build(html_path, pdf_path, engine)   inject the profile, split-render, report
  main(argv, engine)                   CLI: regenerate the HTML, then build
"""

from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import contextlib
import importlib.util
import os
import subprocess
from typing import Any

from lib import _config, _errors, _fsutil
from render import pdf_split, print_profile

_fsutil.pin_stdout_utf8()

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, "..", "..", "..", ".."))
generate_script = os.path.join(script_dir, "to_html.py")


_DEFAULT_LINKER = object()


def reference_metrics(pdf_path: str | None = None) -> dict:
    """Measure the delivery edition: same font, column and text as the print one.

    The print edition is the same markup set the same way, so the delivery PDF is
    the cheapest sample of "how many characters does a line hold with this face" —
    no extra render, and the answer moves when the book's font changes.
    """
    from render import pdf_metrics  # noqa: PLC0415 - only needed for adaptation

    source = pdf_path or _config.merged_pdf()
    if not os.path.exists(source):
        return {}
    return pdf_metrics.measure(source)


def adaptive_numbers(pdf_path: str | None = None) -> dict | None:
    """Print type solved from the measurement, or None when there is nothing to read."""
    from lib import layout as _layout  # noqa: PLC0415 - call-time resolution

    metrics = reference_metrics(pdf_path)
    # solve against running text, not the whole page: a listing's size is set by the
    # column width, so letting it into the average would move the prose type for a
    # reason that has nothing to do with the prose
    chars = metrics.get("prose_chars_per_line") or metrics.get("chars_per_line")
    if not chars:
        return None
    metrics = dict(metrics, chars_per_line=chars)
    layout, _problems = _layout.Layout.from_mapping(_config.THRESHOLDS or {})
    target = float(_config.THRESHOLDS.get("layout_print_lead_target", 0.4) or 0.4)
    lead_target = 1.0 + target
    # listings keep their own leading: the page is mostly listings, so the value is
    # a print decision of its own rather than a copy of the prose one
    code_target = _config.THRESHOLDS.get("layout_print_code_lead_target")
    code_lead_target = None if code_target is None else 1.0 + float(code_target)
    # the code size is width-driven (it must fit the widest listing), so it is passed
    # in rather than derived from the body: shrinking or enlarging it would change the
    # page count without improving legibility
    metrics = dict(metrics)
    metrics["code_px"] = layout.print_code_px(
        int(float(str(_config.THRESHOLDS.get("ascii_max_cols", 100))))
    )
    return print_profile.solve_print_type(
        metrics,
        body_px=layout.body_size_px(),
        chars_per_line=layout.print_chars_per_line,
        lead_target=lead_target,
        code_lead_target=code_lead_target,
    )


def build(
    html_path: str | None = None,
    pdf_path: str | None = None,
    engine: Any = None,
    linker: Any = _DEFAULT_LINKER,
    probe: Any = None,
) -> int:
    """Render the print edition; returns the page count.

    The printed TOC needs its link targets stamped after rendering, exactly as the
    delivery edition does (`pdf_toc_links`), otherwise Chromium's split render
    leaves every TOC entry as a link annotation with no destination.
    """
    source = html_path or _config.merged_html()
    target = pdf_path or _config.merged_print_pdf()
    html = _fsutil.read_text(source)
    print(
        f"  读取 {os.path.basename(source)}（{os.path.getsize(source) / 1048576:.2f} MB）",
        flush=True,
    )
    print(f"  {print_profile.describe()}")

    numbers = probe() if probe is not None else None
    if numbers:
        print(
            f"  自适应印刷参数：body={numbers['body_px']}px "
            f"lead={numbers['line_height']}/{numbers.get('code_line_height', numbers['line_height'])} "
            f"code={numbers['code_px']}px "
            f"(scale {numbers['scale']})",
            flush=True,
        )
    staging = _config.dist(f"_{_config.MERGED_NAME}-print.html")
    _fsutil.write_text(staging, print_profile.inject(html, numbers))
    try:
        print("  Chromium 分章渲染中（与标准版同一页框）…", flush=True)
        count = pdf_split.render_html(staging, target, engine=engine)
        if linker is _DEFAULT_LINKER:
            # Availability is asked of the environment, not inferred from an import
            # failing: once anything imported the submodule, the import answers from
            # sys.modules and a plain environment would look equipped.
            if importlib.util.find_spec("playwright") is None:
                # a plain environment has no browser engine; the PDF is still usable,
                # the printed TOC just keeps clickable rectangles without targets
                print("  [WARN] 目录链接未写回（playwright 未安装）", flush=True)
                linker = None
            else:
                from render import pdf_toc_links  # noqa: PLC0415 - playwright only here

                linker = pdf_toc_links.add_links
        if linker is not None:
            print("  印刷目录链接写回 PDF 目标…", flush=True)
            linker(pdf_path=target, html_path=staging)
    finally:
        with contextlib.suppress(OSError):
            os.remove(staging)
    print(f"  Rendered: {target}（{count} 页）")
    return count


def main(argv: list[str] | None = None, engine: Any = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--html", help="source HTML (default: merged HTML)")
    parser.add_argument("--pdf", help="target PDF (default: print-grade PDF)")
    parser.add_argument(
        "--skip-html", action="store_true", help="do not regenerate the HTML before printing"
    )
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="solve the printed type from the delivery PDF (font-aware)",
    )
    parser.add_argument(
        "--no-adaptive",
        action="store_true",
        help="keep the screen type even when the config asks for adaptation",
    )
    args = parser.parse_args(argv)

    if not args.skip_html and os.path.exists(generate_script):
        result = subprocess.run(
            [_sys.executable, generate_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=repo_root,
            check=False,
        )
        print(result.stdout)
        if result.returncode != 0:
            print("HTML generation FAILED:", result.stderr, file=_sys.stderr)
            return 1
    wants = args.adaptive or (
        bool(_config.THRESHOLDS.get("layout_print_adaptive")) and not args.no_adaptive
    )
    probe = adaptive_numbers if wants else None
    try:
        build(args.html, args.pdf, engine, probe=probe)
    except Exception as exc:
        print(f"  print-grade PDF FAILED: {exc}", file=_sys.stderr)
        return 1
    print(f"Print-grade PDF: {args.pdf or _config.merged_print_pdf()}")
    return 0


if __name__ == "__main__":
    _sys.exit(_errors.run(main, _sys.argv[1:]))
