#!/usr/bin/env python3
"""Rebuild the merged Markdown from chapter files."""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import glob
import os

from lib import _config, _fsutil

_fsutil.pin_stdout_utf8()

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..', '..'))
docs_dir = _config.BOOK_ROOT
src_dir = _config.MANUSCRIPT_DIR
dist_dir = _config.DIST_DIR

# Collect front matter (preface, copyright, reading guide)
front_dir = os.path.join(src_dir, 'front')
front_matter = sorted(glob.glob(os.path.join(front_dir, '*.md'))) if os.path.isdir(front_dir) else []

# Collect back matter (glossary, references, index)
back_dir = os.path.join(src_dir, 'back')
back_matter = sorted(glob.glob(os.path.join(back_dir, '*.md'))) if os.path.isdir(back_dir) else []

chapters = front_matter + _config.chapter_files() + back_matter

# Tolerate the appendix file being absent during phased delivery: while U10/U11/
# U12 are mid-flight the file may not exist yet. Drop missing entries with a
# warning so pipeline runs that build only the merged doc still succeed.
existing_chapters = []
for path in chapters:
    if os.path.exists(path):
        existing_chapters.append(path)
    else:
        print(f'  [skip missing] {path}')
chapters = existing_chapters

output = _config.merged_md()

_fsutil.ensure_dir(output)

total_lines = 0
parts: list[str] = []
for ch_path in chapters:
    content = _fsutil.read_text(ch_path)
    parts.append(content)
    if not content.endswith('\n'):
        parts.append('\n')
    lines = content.count('\n')
    total_lines += lines
    print(f'{ch_path}: {lines} lines')
versions = _config.versions()
_edition = _config.current().edition or 'main'
_language = _config.current().language_code
manifest = (f"<!-- versions: tool={versions['tool']} source={versions['source']} "
            f"doc={versions['doc']} edition={_edition} language={_language} -->\n\n")
_fsutil.write_text(output, manifest + ''.join(parts))

print(f'\nTotal: {total_lines} lines written to {output}')
