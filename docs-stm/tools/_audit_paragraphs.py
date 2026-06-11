#!/usr/bin/env python3
"""
U4: Reading Experience Audit Script — One-time analysis tool.

Audits four dimensions across all 9 chapter source files:
1. Paragraph length distribution — flag paragraphs > 15 lines (excl. code fences & lists)
2. Chapter transitions — check each chapter boundary for bridging sentences
3. Progressive disclosure — verify "what > why > how" progression for key concepts
4. Example completeness — check each chapter has >=1 complete code example

Usage:
    python docs-stm/tools/_audit_paragraphs.py

Output:
    Prints report to stdout. Exit code 0 = all checks pass, 1 = issues found.
"""

import os
import re
import sys

CHAPTER_FILES = [
    "docs-stm/ch1-2-architecture.md",
    "docs-stm/ch3-packages.md",
    "docs-stm/ch4-5-modules-processes.md",
    "docs-stm/ch6-1-data-structures.md",
    "docs-stm/ch6-2-storage-algorithms.md",
    "docs-stm/ch6-3-query-algorithms.md",
    "docs-stm/ch7-8-sql-optimizer.md",
    "docs-stm/ch9-10-persistence-locking.md",
    "docs-stm/ch11-12-guide-summary.md",
]

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def is_code_fence_line(line: str) -> bool:
    """Check if line is a code fence boundary."""
    return line.strip().startswith("```")


def is_list_item(line: str) -> bool:
    """Check if line is a list item (bullet or numbered)."""
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("- ") or stripped.startswith("* "):
        return True
    if re.match(r'^\d+[\.\)]\s', stripped):
        return True
    return False


def is_blockquote(line: str) -> bool:
    """Check if line is a blockquote."""
    return line.strip().startswith(">")


def is_heading(line: str) -> bool:
    """Check if line is a heading."""
    return line.strip().startswith("#")


def is_table_line(line: str) -> bool:
    """Check if line is part of a markdown table."""
    stripped = line.strip()
    if stripped.startswith("|") or stripped.startswith("|---"):
        return True
    return False


def is_figure_caption(line: str) -> bool:
    """Check if line is a figure caption."""
    return line.strip().startswith("**图 ") and line.strip().endswith("**")


def is_horizontal_rule(line: str) -> bool:
    """Check if line is a horizontal rule."""
    stripped = line.strip()
    return stripped in ("---", "***", "___")


def analyze_paragraphs(lines):
    """
    Analyze paragraph length for prose paragraphs only.
    Returns list of dicts with start_line, end_line, length, text.
    """
    paragraphs = []
    current_para = []
    current_start = None
    in_code_block = False

    for i, line in enumerate(lines):
        if is_code_fence_line(line):
            in_code_block = not in_code_block
            if current_para:
                paragraphs.append({
                    "start": current_start,
                    "end": i - 1,
                    "length": len(current_para),
                    "text": " ".join(current_para)[:100],
                })
                current_para = []
                current_start = None
            continue

        if in_code_block:
            continue

        stripped = line.strip()

        if not stripped:
            if current_para:
                paragraphs.append({
                    "start": current_start,
                    "end": i - 1,
                    "length": len(current_para),
                    "text": " ".join(current_para)[:100],
                })
                current_para = []
                current_start = None
            continue

        # Skip certain non-prose lines
        if is_horizontal_rule(line):
            continue

        if is_list_item(stripped) or is_table_line(line) or is_blockquote(stripped) or is_figure_caption(stripped):
            if current_para:
                paragraphs.append({
                    "start": current_start,
                    "end": i - 1,
                    "length": len(current_para),
                    "text": " ".join(current_para)[:100],
                })
                current_para = []
                current_start = None
            continue

        if current_start is None:
            current_start = i
        current_para.append(stripped)

    if current_para:
        paragraphs.append({
            "start": current_start,
            "end": len(lines) - 1,
            "length": len(current_para),
            "text": " ".join(current_para)[:100],
        })

    return paragraphs


def audit_paragraph_length(filepath):
    """Audit 1: Check paragraph length distribution. Return list of violations."""
    violations = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    paragraphs = analyze_paragraphs(lines)
    file_short = os.path.relpath(filepath, REPO_ROOT)

    for p in paragraphs:
        if p["length"] > 15:
            violations.append({
                "file": file_short,
                "start": p["start"] + 1,
                "end": p["end"] + 1,
                "length": p["length"],
                "text": p["text"],
                "severity": "OVER_15_LINES",
            })
        elif p["length"] == 1:
            violations.append({
                "file": file_short,
                "start": p["start"] + 1,
                "end": p["end"] + 1,
                "length": 1,
                "text": p["text"],
                "severity": "SINGLE_LINE",
            })

    return violations


def audit_chapter_transitions():
    """
    Audit 2: Check each chapter boundary for bridging sentences.
    Returns list of issues.
    """
    issues = []

    chapter_pairs = [
        ("ch1-2-architecture.md", "ch3-packages.md",
         "第1-2章结束 -> 第3章开始"),
        ("ch3-packages.md", "ch4-5-modules-processes.md",
         "第3章结束 -> 第4-5章开始"),
        ("ch4-5-modules-processes.md", "ch6-1-data-structures.md",
         "第4-5章结束 -> 第6章开始"),
        ("ch6-1-data-structures.md", "ch6-2-storage-algorithms.md",
         "6.1结束 -> 6.2开始"),
        ("ch6-2-storage-algorithms.md", "ch6-3-query-algorithms.md",
         "6.2结束 -> 6.3开始"),
        ("ch6-3-query-algorithms.md", "ch7-8-sql-optimizer.md",
         "第6章结束 -> 第7-8章开始"),
        ("ch7-8-sql-optimizer.md", "ch9-10-persistence-locking.md",
         "第7-8章结束 -> 第9-10章开始"),
        ("ch9-10-persistence-locking.md", "ch11-12-guide-summary.md",
         "第9-10章结束 -> 第11-12章开始"),
    ]

    transition_patterns = [
        r"为后续.*章.*奠定",
        r"构成了.*第.*章.*基础",
        r"将在第.*章",
        r"将在.*第.*章",
        r"第.*章.*将.*深入",
        r"第.*章.*将.*展开",
        r"第.*章.*将在.*基础上",
        r"后续章节",
        r"后续.*第.*章",
        r"下一章",
        r"本章为.*第.*章",
        r"为理解.*第.*章",
        r"详见第.*章",
        r"承接.*6\.\d",
        r"建立在前.*篇.*基础",
        r"本篇承接",
        r"本篇是第.*章.*部分",
        r"全书从.*已经展开",
    ]

    for prev_file, next_file, label in chapter_pairs:
        prev_path = os.path.join(REPO_ROOT, prev_file)
        next_path = os.path.join(REPO_ROOT, next_file)

        if not os.path.exists(prev_path) or not os.path.exists(next_path):
            issues.append({
                "label": label,
                "issue": "MISSING: file not found",
                "transition_found": False,
            })
            continue

        with open(prev_path, "r", encoding="utf-8") as f:
            prev_lines = f.readlines()
        with open(next_path, "r", encoding="utf-8") as f:
            next_lines = f.readlines()

        prev_text = "".join(prev_lines)
        next_intro = "".join(next_lines[:30])

        found_in_prev = False
        found_in_next = False

        # Check last 3000 chars of previous chapter
        tail = prev_text[-3000:] if len(prev_text) > 3000 else prev_text
        for pattern in transition_patterns:
            if re.search(pattern, tail):
                found_in_prev = True
                break

        # Check first 30 lines of next chapter
        for pattern in transition_patterns:
            if re.search(pattern, next_intro):
                found_in_next = True
                break

        if not (found_in_prev or found_in_next):
            issues.append({
                "label": label,
                "transition_found": False,
            })

    return issues


def audit_progressive_disclosure(filepath):
    """
    Audit 3: Check if sections follow "what > why > how" progression.
    Returns list of issues.
    """
    issues = []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    file_short = os.path.relpath(filepath, REPO_ROOT)

    what_patterns = [
        r"(?:是|属于|表示|定义|指)",
        r"(?:一种|一类|一个)",
        r"(?:即|也就是|意为)",
    ]
    why_patterns = [
        r"(?:用于|目的是|为了|以便|旨在)",
        r"(?:之所以|原因|因为|因此|从而|所以)",
        r"(?:优势|重要性|关键|核心|价值|意义)",
    ]
    how_patterns = [
        r"(?:实现|过程|步骤|流程|算法|机制)",
        r"(?:首先|然后|接着|最后|具体)",
        r"(?:通过|采用|借助|利用|包含)",
    ]

    # Find H2 and H3 headings
    headings = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("## "):
            pass
        if stripped.startswith("## "):
            headings.append((i, stripped.lstrip("# ").strip(), "h2"))
        elif stripped.startswith("### "):
            headings.append((i, stripped.lstrip("# ").strip(), "h3"))

    # Check substantial sections for progression
    for i, (head_idx, head_title, head_type) in enumerate(headings):
        next_idx = headings[i + 1][0] if i + 1 < len(headings) else len(lines)
        section_text = "\n".join(lines[head_idx:next_idx])

        # Skip summary/reference sections
        if "本章小结" in head_title or "延展阅读" in head_title or "术语参考" in head_title:
            continue

        section_lines_count = next_idx - head_idx
        if section_lines_count < 15:
            continue

        has_what = any(re.search(p, section_text) for p in what_patterns)
        has_why = any(re.search(p, section_text) for p in why_patterns)
        has_how = any(re.search(p, section_text) for p in how_patterns)

        missing = []
        if not has_what:
            missing.append("what")
        if not has_why:
            missing.append("why")
        if not has_how:
            missing.append("how")

        if missing:
            issues.append({
                "file": file_short,
                "section": head_title,
                "line": head_idx + 1,
                "missing": missing,
            })

    return issues


def audit_example_completeness(filepath):
    """
    Audit 4: Check for complete Java/SQL code examples.
    Returns list of issues.
    """
    issues = []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    file_short = os.path.relpath(filepath, REPO_ROOT)

    java_blocks = []
    in_java_block = False
    block_start = 0
    block_lines = 0

    for i, line in enumerate(lines):
        if line.strip().startswith("```java"):
            in_java_block = True
            block_start = i
            block_lines = 0
        elif in_java_block and line.strip().startswith("```"):
            if block_lines >= 3:
                java_blocks.append({
                    "start": block_start,
                    "end": i,
                    "lines": block_lines,
                })
            in_java_block = False
        elif in_java_block:
            stripped = line.strip()
            if stripped and not stripped.startswith("//") and not stripped.startswith("/*"):
                block_lines += 1

    if not java_blocks:
        issues.append({
            "file": file_short,
            "has_java": False,
        })

    return issues


def main():
    print("=" * 70)
    print("U4: Paragraph/Transition/Disclosure/Example Audit")
    print("=" * 70)

    issues_found = 0
    all_issues = {
        "paragraph_length": [],
        "chapter_transitions": [],
        "progressive_disclosure": [],
        "example_completeness": [],
    }

    # 1. Paragraph Length Audit
    print("\n## 1. Paragraph Length Audit\n")
    for cf in CHAPTER_FILES:
        filepath = os.path.join(REPO_ROOT, cf)
        if not os.path.exists(filepath):
            print(f"  [SKIP] {cf} not found")
            continue

        violations = audit_paragraph_length(filepath)
        all_issues["paragraph_length"].extend(violations)

        long_paras = [v for v in violations if v["severity"] == "OVER_15_LINES"]
        orphans = [v for v in violations if v["severity"] == "SINGLE_LINE"]

        if long_paras:
            print(f"  [{cf}] {len(long_paras)} paragraph(s) > 15 lines:")
            for v in long_paras:
                print(f"    L{v['start']}-{v['end']} ({v['length']} lines): {v['text'][:80]}")
            issues_found += len(long_paras)
        else:
            print(f"  [OK] {cf}: no paragraphs > 15 lines")

        if orphans:
            print(f"  [{cf}] {len(orphans)} single-line prose paragraph(s):")
            for v in orphans[:5]:
                print(f"    L{v['start']}: {v['text'][:80]}")
            if len(orphans) > 5:
                print(f"    ... and {len(orphans)-5} more")
        else:
            print(f"  [OK] {cf}: no single-line paragraphs")

    # 2. Chapter Transition Audit
    print("\n## 2. Chapter Transition Audit\n")
    transition_issues = audit_chapter_transitions()
    all_issues["chapter_transitions"] = transition_issues

    if transition_issues:
        for issue in transition_issues:
            print(f"  [ISSUE] {issue['label']}: no transition found")
            issues_found += 1
    else:
        print("  [OK] All chapter transitions found")

    # 3. Progressive Disclosure Audit
    print("\n## 3. Progressive Disclosure Audit\n")
    for cf in CHAPTER_FILES:
        filepath = os.path.join(REPO_ROOT, cf)
        if not os.path.exists(filepath):
            continue
        issues = audit_progressive_disclosure(filepath)
        all_issues["progressive_disclosure"].extend(issues)

        if issues:
            print(f"  [{cf}] {len(issues)} section(s) with progression gaps:")
            for v in issues:
                print(f"    L{v['line']} '{v['section']}': missing {', '.join(v['missing'])}")
            issues_found += len(issues)
        else:
            print(f"  [OK] {cf}: all sections have progression coverage")

    # 4. Example Completeness Audit
    print("\n## 4. Example Completeness Audit\n")
    for cf in CHAPTER_FILES:
        filepath = os.path.join(REPO_ROOT, cf)
        if not os.path.exists(filepath):
            continue
        issues = audit_example_completeness(filepath)
        all_issues["example_completeness"].extend(issues)

        for v in issues:
            print(f"  [{cf}] No complete Java code examples found (```java)")
            issues_found += 1

    # Summary
    print("\n" + "=" * 70)
    print("Summary Report")
    print("=" * 70)
    print(f"  Long paragraphs (>15 lines):      {len([v for v in all_issues['paragraph_length'] if v['severity'] == 'OVER_15_LINES'])}")
    print(f"  Single-line prose paragraphs:     {len([v for v in all_issues['paragraph_length'] if v['severity'] == 'SINGLE_LINE'])}")
    print(f"  Missing chapter transitions:      {len(all_issues['chapter_transitions'])}")
    print(f"  Progressive disclosure gaps:      {len(all_issues['progressive_disclosure'])}")
    print(f"  Missing Java examples:            {len(all_issues['example_completeness'])}")
    print(f"  Total issues:                     {issues_found}")

    if issues_found > 0:
        print("\n  !! Issues found that need fixing !!")
    else:
        print("\n  All checks passed!")

    return 1 if issues_found > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
