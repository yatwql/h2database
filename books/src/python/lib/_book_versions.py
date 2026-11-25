#!/usr/bin/env python3
"""The book's versions and the dates its parts last changed.

Mixed into :class:`lib._config.Config`: this is the one group that shells out
(``git log``) and reads file timestamps, and it answers two questions the
manuscript asks for its front matter — which tool/document/source versions this
book records, and when the toolchain and the manuscript were last touched.
"""

from __future__ import annotations

import datetime
import os
import subprocess

_MANIFEST_PATTERNS = {
    "pom.xml": r"<version>\s*([^<\s]+)\s*</version>",
    "pyproject.toml": r'^\s*version\s*=\s*"([^"]+)"',
    "Cargo.toml": r'^\s*version\s*=\s*"([^"]+)"',
}


class BookVersions:
    """Versions and last-change dates, resolved against the book's own tree."""

    # Provided by the book that mixes this in (lib._config.Config).
    root: str
    version: str
    sources: dict
    manuscript_dir: str
    _change_stamps: dict[str, str]

    def source_roots(self) -> list[dict[str, str]]: ...

    def _last_change(self, rel_path: str) -> str:
        """ISO date of the last change under ``rel_path`` (git first, then mtime)."""
        cached = self._change_stamps.get(rel_path)
        if cached:
            return cached
        stamp = ""
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%cs", "--", rel_path],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            stamp = (result.stdout or "").strip()
        except (OSError, subprocess.SubprocessError):
            stamp = ""
        if not stamp:
            newest = 0.0
            root = os.path.join(self.root, rel_path)
            for base, _dirs, files in os.walk(root):
                for name in files:
                    try:
                        newest = max(newest, os.path.getmtime(os.path.join(base, name)))
                    except OSError:
                        continue
            stamp = datetime.date.fromtimestamp(newest).isoformat() if newest else ""
        self._change_stamps[rel_path] = stamp
        return stamp

    def tool_updated(self) -> str:
        """Date the toolchain code last changed (version bumps are not required)."""
        return self._last_change("src/python")

    def book_updated(self) -> str:
        """Date the manuscript last changed."""
        return self._last_change(os.path.relpath(self.manuscript_dir, self.root))

    def tool_version(self) -> str:
        """The toolchain's own version (independent of book and source)."""
        from lib._version import TOOL_VERSION

        return str(self.sources.get("tool_version") or TOOL_VERSION)

    def doc_version(self) -> str:
        """The document/manuscript version (book.toml [book].version)."""
        return self.version

    def source_versions(self) -> dict[str, str]:
        """Per-root source versions, keyed by label."""
        out: dict[str, str] = {}
        for entry in self.source_roots():
            out[entry["label"]] = entry["version"] or self.source_version()
        return out

    def source_version(self, root: str | None = None) -> str:
        """Version of the analyzed source tree.

        Resolution order: explicit ``[sources].version`` in base.json, then the
        language manifest of the configured source root (pom.xml /
        pyproject.toml / Cargo.toml). Returns 'unknown' when nothing is read.
        """
        explicit = self.sources.get("version")
        if explicit:
            return str(explicit)
        base = root or os.path.join(self.root, self.sources.get("src_main", ""))
        # manifests may sit next to the source root (maven) or inside it (rust/python)
        candidates: list[str] = []
        pom_root = self.sources.get("pom_root")
        if pom_root:
            candidates.append(os.path.join(self.root, pom_root))
        for folder in (base, os.path.dirname(base)):
            for name in ("pom.xml", "pyproject.toml", "Cargo.toml"):
                candidates.append(os.path.join(folder, name))
        for path in candidates:
            if not os.path.isfile(path):
                continue
            detail = _source_version_from(path, _MANIFEST_PATTERNS[os.path.basename(path)])
            if detail:
                return detail
        return "unknown"

    def versions(self) -> dict:
        """The three versions the toolchain tracks.

        ``source`` is a string while one tree is digested and a label -> version map
        once several are, which is what the callers that print it already handle.
        """
        roots = self.source_roots()
        source = self.source_version() if len(roots) == 1 else self.source_versions()
        return {"tool": self.tool_version(), "source": source, "doc": self.doc_version()}

def _source_version_from(path: str, pattern: str) -> str:
    """First regex capture in a manifest file (empty string when absent)."""
    import re as _re

    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ""
    match = _re.search(pattern, text, _re.MULTILINE)
    return match.group(1).strip() if match else ""
