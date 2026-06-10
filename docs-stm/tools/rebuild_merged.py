#!/usr/bin/env python3
"""Rebuild h2-source-code-analysis.md from chapter files."""
import os, sys, glob
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(script_dir, '..', '..'))
docs_dir = os.path.join(repo_root, 'docs-stm')

# Collect front matter (preface, copyright, reading guide)
front_dir = os.path.join(docs_dir, 'front')
front_matter = sorted(glob.glob(os.path.join(front_dir, '*.md'))) if os.path.isdir(front_dir) else []

chapter_names = [
    'cover.md',
    'ch1-2-architecture.md',
    'ch3-packages.md',
    'ch4-5-modules-processes.md',
    'ch6-1-data-structures.md',
    'ch6-2-storage-algorithms.md',
    'ch6-3-query-algorithms.md',
    'ch7-8-sql-optimizer.md',
    'ch9-10-persistence-locking.md',
    'ch11-12-guide-summary.md',
]

# Collect back matter (glossary, references, index)
back_dir = os.path.join(docs_dir, 'back')
back_matter = sorted(glob.glob(os.path.join(back_dir, '*.md'))) if os.path.isdir(back_dir) else []

chapters = front_matter + [os.path.join(docs_dir, name) for name in chapter_names] + back_matter

output = os.path.join(docs_dir, 'h2-source-code-analysis.md')

os.makedirs(os.path.dirname(output), exist_ok=True)

with open(output, 'w', encoding='utf-8') as out:
    total_lines = 0
    for ch_path in chapters:
        with open(ch_path, 'r', encoding='utf-8') as f:
            content = f.read()
            out.write(content)
            if not content.endswith('\n'):
                out.write('\n')
            lines = content.count('\n')
            total_lines += lines
            print(f'{ch_path}: {lines} lines')

print(f'\nTotal: {total_lines} lines written to {output}')
