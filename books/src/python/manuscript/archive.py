#!/usr/bin/env python3
"""Archive the generated manuscript and the delivered book, and age them out.

Layout (one directory per run date, so a day's copy is never interleaved):

  data/archive/<book>/<YYYY-MM-DD>/manuscript/...
  data/archive/<book>/<YYYY-MM-DD>/dist/<merged>.{md,html,pdf,epub}
  data/archive/<book>/<YYYY-MM-DD>/manifest.json

The archive is a safety net, not a build input: nothing reads it back, and it is
gitignored. Retention is a policy value (``base.json [archive] retention_days``,
45 by default); pruning removes whole date directories older than the window.

Usage:
  python archive.py                    # archive manuscript + delivered artefacts
  python archive.py --kind manuscript  # only the manuscript
  python archive.py --dry-run          # report what would be copied and pruned
  python archive.py --json             # machine-readable summary

Exit codes: 0 ok, 1 nothing to archive, 2 bad usage.
"""

from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil

DATE_FMT = "%Y-%m-%d"
DIST_SUFFIXES = (".md", ".html", ".pdf", ".epub")
MANUSCRIPT_SKIP = ("__pycache__",)


def settings() -> dict:
    """Archive policy from ``base.json [archive]`` with conservative defaults."""
    raw = _config.POLICY.get("archive") or {}
    rel = str(raw.get("dir") or "data/archive")
    days = raw.get("retention_days", 45)
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 45
    return {"dir": rel, "retention_days": max(1, days)}


def book_slug() -> str:
    """Directory name for this book, including the edition when one is selected."""
    name = (_config.MERGED_NAME or "").strip()
    if not name:
        name = _config.TITLE or "book"
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in name)
    return safe.strip("-.") or "book"


def _files_to_copy(kind: str) -> list[str]:
    if kind == "manuscript":
        return [
            path
            for path in _config.all_manuscript_files()
            if os.path.isfile(path)
            and not any(part in MANUSCRIPT_SKIP for part in path.split(os.sep))
        ]
    found: list[str] = []
    for suffix in DIST_SUFFIXES:
        found += sorted(glob.glob(os.path.join(_config.DIST_DIR, f"*{suffix}")))
    return [path for path in found if os.path.isfile(path)]


def _copy(files: list[str], source_root: str, target: str) -> dict:
    """Copy files under ``target``; returns relative path -> bytes."""
    copied: dict[str, int] = {}
    for path in files:
        rel = os.path.relpath(path, source_root)
        if rel.startswith(".."):
            rel = os.path.basename(path)
        destination = os.path.join(target, rel)
        _fsutil.ensure_dir(destination)
        shutil.copy2(path, destination)
        copied[rel.replace(os.sep, "/")] = os.path.getsize(path)
    return copied


def _digest(files: dict[str, int]) -> str:
    payload = json.dumps(files, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _date_dirs(book_dir: str) -> list[tuple[datetime.date, str]]:
    """(date, path) for every YYYY-MM-DD directory of one book."""
    found: list[tuple[datetime.date, str]] = []
    try:
        names = sorted(os.listdir(book_dir))
    except OSError:
        return found
    for name in names:
        path = os.path.join(book_dir, name)
        if not os.path.isdir(path):
            continue
        try:
            found.append((datetime.datetime.strptime(name, DATE_FMT).date(), path))
        except ValueError:
            continue
    return found


def prune(
    book_dir: str, retention_days: int, today: datetime.date, dry_run: bool = False
) -> list[str]:
    """Remove date directories older than the retention window."""
    cutoff = today - datetime.timedelta(days=retention_days)
    removed: list[str] = []
    for day, path in _date_dirs(book_dir):
        if day >= cutoff:
            continue
        removed.append(os.path.basename(path))
        if dry_run:
            continue
        try:
            shutil.rmtree(path)
        except OSError as exc:
            print(f"  [warn] 无法清理旧归档 {path}：{exc}", file=sys.stderr)
    return removed


def take(kinds: list[str], today: datetime.date, dry_run: bool = False) -> dict:
    """Archive the requested kinds for ``today``; prune what fell out of range."""
    policy = settings()
    book_dir = os.path.join(_config.book_subdir(settings()["dir"]), book_slug())
    day_dir = os.path.join(book_dir, today.strftime(DATE_FMT))
    copied: dict[str, dict[str, int]] = {}
    for kind in kinds:
        files = _files_to_copy(kind)
        if not files:
            continue
        source_root = _config.MANUSCRIPT_DIR if kind == "manuscript" else _config.DIST_DIR
        if dry_run:
            copied[kind] = {os.path.relpath(p, source_root).replace(os.sep, "/"): 0 for p in files}
            continue
        copied[kind] = _copy(files, source_root, os.path.join(day_dir, kind))
    removed = prune(book_dir, policy["retention_days"], today, dry_run)
    summary = {
        "book": book_slug(),
        "edition": _config.current().edition,
        "date": today.strftime(DATE_FMT),
        "root": book_dir,
        "kinds": sorted(copied),
        "files": {kind: len(items) for kind, items in copied.items()},
        "bytes": {kind: sum(items.values()) for kind, items in copied.items()},
        "retention_days": policy["retention_days"],
        "pruned": removed,
        "dry_run": dry_run,
    }
    if not dry_run and copied:
        manifest = os.path.join(day_dir, "manifest.json")
        _fsutil.write_text(
            manifest,
            json.dumps(
                {
                    **summary,
                    "digest": _digest(
                        {f"{k}/{n}": b for k, items in copied.items() for n, b in items.items()}
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--kind", choices=("manuscript", "dist", "all"), default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="machine-readable summary")
    parser.add_argument("--today", help="override the date (YYYY-MM-DD), for tests")
    args = parser.parse_args(argv)

    if args.today:
        try:
            today = datetime.datetime.strptime(args.today, DATE_FMT).date()
        except ValueError:
            print(f"error: --today expects YYYY-MM-DD, got {args.today!r}", file=sys.stderr)
            return 2
    else:
        today = datetime.date.today()

    kinds = ["manuscript", "dist"] if args.kind == "all" else [args.kind]
    summary = take(kinds, today, args.dry_run)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        counts = ", ".join(f"{kind} {n} 个文件" for kind, n in summary["files"].items())
        verb = "将归档" if args.dry_run else "已归档"
        print(
            f"{verb}: {os.path.relpath(summary['root'], _config.BOOK_ROOT)}"
            f"/{summary['date']}  {counts or '（无内容）'}"
        )
        if summary["pruned"]:
            action = "将清理" if args.dry_run else "已清理"
            print(
                f"{action}过期归档 {len(summary['pruned'])} 份："
                f"{', '.join(summary['pruned'])}（保留 {summary['retention_days']} 天）"
            )
    return 0 if summary["files"] else 1


if __name__ == "__main__":
    sys.exit(_errors.run(main, sys.argv[1:]))
