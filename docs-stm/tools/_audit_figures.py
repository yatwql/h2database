#!/usr/bin/env python3
"""Audit figure caption format and inline citations."""
import re, os, glob

docs_dir = 'docs-stm'
chapter_files = sorted(glob.glob(os.path.join(docs_dir, 'ch[0-9]*.md')))

total_figs = 0
total_citations = 0
files_with_issues = []

for f in chapter_files:
    with open(f, 'r', encoding='utf-8') as fh:
        content = fh.read()
    figs = re.findall(r'\*\*图 (\d+-\d+):', content)
    citations = re.findall(r'如图 (\d+-\d+) 所示', content)
    total_figs += len(figs)
    total_citations += len(citations)
    fig_nums = set(figs)
    cit_nums = set(citations)
    uncited = fig_nums - cit_nums
    if uncited:
        files_with_issues.append((os.path.basename(f), sorted(uncited)[:8]))

print(f'Total figures: {total_figs}')
print(f'Total inline citations (如图 X-Y 所示): {total_citations}')
print(f'Files with uncited figures: {len(files_with_issues)}')
for fname, uncited in files_with_issues:
    print(f'  {fname}: {len(uncited)} uncited - {uncited}')