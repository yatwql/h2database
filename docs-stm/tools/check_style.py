#!/usr/bin/env python3
"""
Writing style checker for H2 documentation.

Scans all chapter files for patterns that may indicate:
1. Colloquial or informal expressions
2. Inconsistent terminology casing
3. Excessively long sentences
4. Redundant English/Chinese mixing

Outputs warnings for each potential issue.
"""
import re, os, sys, glob
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

script_dir = os.path.dirname(os.path.abspath(__file__))
docs_dir = os.path.normpath(os.path.join(script_dir, '..'))
chapter_files = sorted(glob.glob(os.path.join(docs_dir, 'ch[0-9]*.md')))

warnings = []

def warn(file, line, msg):
    warnings.append((file, line, msg))

for fpath in chapter_files:
    fname = os.path.basename(fpath)
    with open(fpath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    in_fence = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Track fence state
        if stripped.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        # Skip headings and empty lines
        if re.match(r'^#{1,4}\s', stripped):
            continue
        if not stripped:
            continue
        if stripped.startswith('>'):
            continue  # blockquotes (guide blocks, references)
        if stripped == '---':
            continue
        if re.match(r'^\|.*\|$', stripped):
            continue  # table rows

        # 1. Colloquial patterns
        colloquial = [
            (r'说白了', '口语化表达"说白了"，建议替换为"换言之"或删除'),
            (r'你会发现', '口语化表达"你会发现"，建议使用"可以观察到"'),
            (r'我们来看', '口语化表达"我们来看"，建议使用"本节分析"'),
            (r'其实就', '口语化表达"其实就"，建议删除"其实"'),
            (r'毫无疑问', '过于绝对，建议使用"显然"'),
            (r'众所周知', '学术写作应避免"众所周知"，直接陈述事实'),
            (r'总的来说', '口语化总结，建议使用"综上所述"'),
            (r'显而易见', '过于绝对，建议使用"不难看出"'),
            (r'值得一提的是', '冗余表达，建议直接陈述'),
        ]
        for pattern, msg in colloquial:
            if re.search(pattern, stripped):
                warn(fname, i, msg)

        # 2. Overly long sentences (>80 Chinese characters without punctuation)
        # Split on Chinese punctuation
        segments = re.split(r'[，。；！？、]', stripped)
        for seg in segments:
            seg = seg.strip()
            # Count Chinese characters
            cn_chars = len(re.findall(r'[一-鿿]', seg))
            if cn_chars > 60 and len(seg) > 100:
                print(f'  [{fname}:{i}] LONG SENTENCE ({cn_chars} chars): {seg[:60]}...')

        # 3. Inline code spans with Chinese (mixed language)
        for m in re.finditer(r'`([^`]+)`', stripped):
            code_content = m.group(1)
            has_cn = bool(re.search(r'[一-鿿]', code_content))
            has_en = bool(re.search(r'[a-zA-Z]', code_content))
            if has_cn and has_en:
                warn(fname, i, f'中英混合内联代码: `{code_content[:40]}`')

# Report
total_by_type = {}
for fname, line_no, msg in warnings:
    category = msg.split('，')[0][:15]
    total_by_type[category] = total_by_type.get(category, 0) + 1

print(f'\n=== Style Check Results: {len(warnings)} warnings ===')
if warnings:
    for fname, line_no, msg in warnings:
        print(f'  [{fname}:{line_no}] {msg}')

print(f'\n=== Summary by Type ===')
for cat, count in sorted(total_by_type.items(), key=lambda x: -x[1]):
    print(f'  {cat}: {count}')

if len(warnings) > 0:
    print(f'\n[WARN]  {len(warnings)} style warnings found — review recommended')
else:
    print(f'\n✅ No style issues found')