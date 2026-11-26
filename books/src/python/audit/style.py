#!/usr/bin/env python3
"""
Writing style checker for H2 documentation.

Scans all chapter files for patterns that may indicate:
1. Colloquial or informal expressions
2. Inconsistent terminology casing
3. Excessively long sentences
4. Redundant English/Chinese mixing
5. Monotonous sentence starts
6. Redundant adverbs and vague modifiers
7. Weak verb constructions ("进行" + verb)
8. Excessive "的" density
9. Vague pronoun references ("其")
10. Repeated connectors
11. Passive voice overuse ("被")

Outputs warnings for each potential issue, organized by WARN (should fix)
and INFO (suggestion, for reference).
"""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import os
import re
from collections import Counter, defaultdict
from typing import TypedDict

from lib import _config, _fsutil

_fsutil.pin_stdout_utf8()

docs_dir = _config.BOOK_ROOT
src_dir = _config.MANUSCRIPT_DIR
dist_dir = _config.DIST_DIR
chapter_files = _config.chapter_files(include_cover=False)


class ChapterStats(TypedDict):
    """Per-chapter counters; a TypedDict keeps the mixed int/list fields honest."""

    warnings: list[tuple[int, str]]
    infos: list[tuple[int, str]]
    sentences: int
    cn_chars: int
    de_count: int
    sentence_starts: list[str]
    paragraph_count: int
    long_sentences: list[tuple[int, int]]


def _empty_stats() -> ChapterStats:
    return {
        "warnings": [],
        "infos": [],
        "sentences": 0,
        "cn_chars": 0,
        "de_count": 0,
        "sentence_starts": [],
        "paragraph_count": 0,
        "long_sentences": [],
    }


# Collect statistics for chapter-level reporting
chapter_stats: defaultdict[str, ChapterStats] = defaultdict(_empty_stats)


def warn(fname, line, msg, level="WARN"):
    """Add a warning, defaulting to WARN level."""
    if level == "WARN":
        chapter_stats[fname]["warnings"].append((line, msg))
    else:
        chapter_stats[fname]["infos"].append((line, msg))


def _paragraph_line_groups(lines) -> list[list[int]]:
    """Line indices grouped into prose paragraphs, skipping fences, headings and tables."""
    in_fence = False
    paragraphs: list[list[int]] = []
    current: list[int] = []

    def flush() -> None:
        if current:
            paragraphs.append(list(current))
            current.clear()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_fence:
                flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,4}\s", stripped) or not stripped or stripped == "---":
            flush()
            continue
        if re.match(r"^\|.*\|$", stripped) or stripped.startswith((">", "```")):
            continue
        current.append(i)
    flush()
    return paragraphs


def _sentence_starts(lines, para_lines) -> list[str]:
    """First word of each sentence in one paragraph, in reading order."""
    para_text = " ".join(lines[idx].strip() for idx in para_lines)
    if not para_text.strip():
        return []

    # Periods inside code spans and file extensions are not sentence boundaries
    protected = re.sub(
        r"`([^`]+)`", lambda m: "`" + m.group(1).replace(".", chr(0)) + "`", para_text.strip()
    )
    protected = re.sub(
        r"\b(\w+)\.(java|html?|md|py|xml|json|txt|sql|php|css|js|ts)\b",
        lambda m: m.group(1) + chr(0) + m.group(2),
        protected,
    )

    endings = re.escape(_config.sentence_endings()) + r".!?"
    sentences = [
        s.strip().replace(chr(0), ".") for s in re.split(rf"(?<=[{endings}])\s*", protected)
    ]
    sentences = [s for s in sentences if len(s) > 5]

    starts = []
    for sentence in sentences:
        clean = re.sub(r"^[（(]?", "", sentence)
        match = re.search(r"([一-鿿]|[a-zA-Z]\w*)", clean)
        if match:
            starts.append(match.group(1))
    return starts


def _warn_monotony(starts, line_number: int, fname) -> None:
    """One warning per paragraph: three in a row, or two thirds of it the same."""
    for i in range(len(starts) - 2):
        if starts[i] == starts[i + 1] == starts[i + 2]:
            warn(
                fname,
                line_number,
                f'句式单调：连续 3 句以"{starts[i]}"开头，建议变换句式结构',
                level="INFO",
            )
            break

    if len(starts) >= 4:
        start_counts = Counter(starts)
        word, count = start_counts.most_common(1)[0]
        ratio = count / len(starts)
        if ratio > 0.6 and count >= 3:
            warn(
                fname,
                line_number,
                f'句式单调：段落内 {int(ratio * 100)}% 句子以"{word}"开头'
                f"（{count}/{len(starts)}句），建议调整",
                level="INFO",
            )


def detect_sentence_monotony(lines, fname):
    """Detect consecutive sentences starting with the same word.

    Works by collecting paragraph-level text outside fences, splitting
    into sentences, and tracking first-word patterns.
    """
    paragraphs = _paragraph_line_groups(lines)
    chapter_stats[fname]["paragraph_count"] += len(paragraphs)

    for para_lines in paragraphs:
        starts = _sentence_starts(lines, para_lines)
        if len(starts) < 3:
            continue  # fewer than three sentences cannot be monotonous
        chapter_stats[fname]["sentence_starts"].extend(starts)
        _warn_monotony(starts, (para_lines[0] if para_lines else 0) + 1, fname)


def detect_repeated_connectors(lines, fname):
    """Detect repeated use of same connector within adjacent sentences."""
    connector_words = ["同时", "另外", "此外", "而且", "并且", "因此", "然而", "但是", "不过"]
    in_fence = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue
        if not stripped or stripped.startswith(">") or stripped == "---":
            continue
        if re.match(r"^\|.*\|$", stripped):
            continue

        # Check for repeated connectors within the same line
        for connector in connector_words:
            # Find all occurrences with their positions
            positions = [m.start() for m in re.finditer(re.escape(connector), stripped)]
            if len(positions) >= 2:
                # For "同时", only flag if occurrences are close (same clause context)
                # It has legitimate dual meanings (also vs concurrently)
                if connector in ("同时", "因此", "然而", "而且", "并且"):
                    # Check if occurrences are within the same clause (~40 chars)
                    close_pairs = sum(
                        1 for i in range(len(positions) - 1) if positions[i + 1] - positions[i] < 40
                    )
                    if close_pairs == 0:
                        continue  # Legitimate different usages/contexts
                warn(
                    fname,
                    i,
                    f'重复连接词：本行使用"{connector}" {len(positions)} 次，建议替换为不同连接词',
                    level="WARN",
                )


def detect_weak_verb_xing(lines, fname):
    """Detect '进行' + verb constructions ('进行分析', '进行讨论')."""
    in_fence = False
    pattern = re.compile(r"(?<!正在)进行[的]?[一-鿿]{2,4}")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue
        if not stripped or stripped.startswith(">") or stripped == "---":
            continue
        if re.match(r"^\|.*\|$", stripped):
            continue

        for m in pattern.finditer(stripped):
            verb = m.group(0)
            # "进行中" (in progress) is a state, not a "进行+verb" construction;
            # the pattern can only match four characters or more, so the skip has
            # to look at the match's prefix rather than at the whole of it.
            if verb.startswith(("进行中", "进行的", "进行时")):
                continue
            warn(fname, i, f'弱动词构造："{verb}"，建议改为直接表达', level="WARN")


FORBID_PHRASES = list((_config.STYLE_POLICY.get("prose") or {}).get("forbid_phrases") or [])


def detect_forbidden_phrases(lines, fname):
    """Flag phrases banned by style.json [prose].forbid_phrases."""
    if not FORBID_PHRASES:
        return
    in_fence = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith((">", "#", "|")):
            continue
        for phrase in FORBID_PHRASES:
            if phrase in stripped:
                warn(fname, i, f'禁用语："{phrase}"，改用客观陈述', level="WARN")


def detect_excessive_de(lines, fname):
    """Detect excessive '的' in a single line as a marker of nested modification."""
    in_fence = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue
        if not stripped or stripped.startswith(">") or stripped == "---":
            continue
        if re.match(r"^\|.*\|$", stripped):
            continue

        # Count '的' excluding those in code spans
        text = re.sub(r"`[^`]+`", "", stripped)
        de_count = text.count("的")
        if de_count >= 4:
            # Check density: more than 1 '的' per 10 characters
            text_len = len(re.findall(r"[一-鿿\w]", text))
            if text_len > 0 and de_count / text_len > 0.08:
                warn(
                    fname,
                    i,
                    f'过度"的"：该行含 {de_count} 个"的"（密度 {de_count}/{text_len}）'
                    f"，建议简化修饰结构",
                    level="INFO",
                )

        chapter_stats[fname]["de_count"] += de_count


def detect_vague_qi(lines, fname):
    """Detect potentially ambiguous '其' reference."""
    in_fence = False
    # '其' is ambiguous when it could refer to one of multiple
    # candidate subjects in the preceding text.
    # Simple heuristic: flag '其' + verb constructions when the
    # preceding line(s) contain multiple nouns.

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue
        if not stripped or stripped.startswith(">") or stripped == "---":
            continue
        if re.match(r"^\|.*\|$", stripped):
            continue

        # Find "其" used as a possessive/pronoun (其 + noun/verb)
        for m in re.finditer(r"其[一-鿿]", stripped):
            # Check if preceding non-empty line(s) contain multiple subjects
            # Simple heuristic: if '其' appears near the end of a sentence
            # that references multiple entities
            prev_lines_text = ""
            for j in range(i - 2, i):
                if j >= 0 and j < len(lines):
                    pl = lines[j].strip()
                    if pl and not pl.startswith("```") and not pl.startswith("#"):
                        prev_lines_text += pl

            # Count potential noun candidates (simplified: Chinese words before punctuation)
            nouns_before = len(re.findall(r"[一-鿿]{2,}(?:[，,])", prev_lines_text[:100]))
            if nouns_before >= 3:
                phrase = m.group(0)
                warn(
                    fname,
                    i,
                    f'模糊指代："{phrase}"前的上文中出现多个潜在指代对象，建议明确指代',
                    level="INFO",
                )
                break  # One per line


def detect_passive_abuse(lines, fname):
    """Detect overuse of passive voice marker '被'."""
    in_fence = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue
        if not stripped or stripped.startswith(">") or stripped == "---":
            continue
        if re.match(r"^\|.*\|$", stripped):
            continue

        # Count 被 in this line
        count = stripped.count("被")
        if count >= 2:
            warn(fname, i, f'被动滥用：本行含 {count} 个"被"，建议部分改为主动表达', level="INFO")


def calculate_readability_metrics(lines, fname):
    """Calculate per-chapter readability metrics (non-WARN, stats only)."""
    in_fence = False
    total_chars = 0
    sentence_count = 0
    cn_char_count = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue
        if not stripped or stripped.startswith(">") or stripped == "---":
            continue
        if re.match(r"^\|.*\|$", stripped):
            continue

        total_chars += len(stripped)
        cn_chars = len(re.findall(r"[一-鿿]", stripped))
        cn_char_count += cn_chars

        # Count sentence boundaries
        sents = len(re.findall(rf"[{re.escape(_config.sentence_endings())}.!?]", stripped))
        sentence_count += sents

    chapter_stats[fname]["cn_chars"] = cn_char_count
    chapter_stats[fname]["sentences"] = sentence_count


def detect_colloquial(lines, fname):
    """Detect colloquial/informal expressions in chapter text."""
    patterns = [
        (r"说白了", '口语化表达"说白了"，建议替换为"换言之"或删除'),
        (r"你会发现", '口语化表达"你会发现"，建议使用"可以观察到"'),
        (r"我们来看", '口语化表达"我们来看"，建议使用"本节分析"'),
        (r"其实就", '口语化表达"其实就"，建议删除"其实"'),
        (r"显而易见", '过于绝对，建议使用"不难看出"'),
        (r"值得一提的是", "冗余表达，建议直接陈述"),
        (r"毫无疑问", '过于绝对，建议使用"显然"'),
        (r"众所周知", '学术写作应避免"众所周知"，直接陈述事实'),
        (r"总的来说", '口语化总结，建议使用"综上所述"'),
    ]
    in_fence = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue
        if stripped.startswith(">") or stripped == "---":
            continue
        if re.match(r"^\|.*\|$", stripped):
            continue
        for pattern, msg in patterns:
            if re.search(pattern, stripped):
                warn(fname, i, msg)


def detect_redundant_adverbs(lines, fname):
    """Detect redundant adverbs that should be replaced with direct statements."""
    patterns = [
        (r"实际上", '冗余副词"实际上"，建议直接陈述'),
        (r"基本上", '冗余副词"基本上"，建议直接陈述'),
        (r"本质上", '冗余副词"本质上"，建议直接陈述'),
        (r"其实\b", '冗余副词"其实"，建议直接陈述或删除'),
    ]
    in_fence = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue
        if stripped.startswith(">") or stripped == "---":
            continue
        if re.match(r"^\|.*\|$", stripped):
            continue
        for pattern, msg in patterns:
            if re.search(pattern, stripped):
                warn(fname, i, msg, level="INFO")


def detect_vague_modifiers(lines, fname):
    """Detect vague modifiers like '非常', '十分', '极其', '相当' that lack specificity."""
    patterns = [
        (r"非常[一-鿿]", '空泛修饰"非常X"，建议使用更具体的描述'),
        (r"十分[一-鿿]", '空泛修饰"十分X"，建议使用更具体的描述'),
        (r"极其[一-鿿]", '空泛修饰"极其X"，建议使用更具体的描述'),
        (r"相当[一-鿿]{1,2}[的\w]", '空泛修饰"相当X"，建议使用更具体的描述'),
    ]
    in_fence = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue
        if stripped.startswith(">") or stripped == "---":
            continue
        if re.match(r"^\|.*\|$", stripped):
            continue
        for pattern, msg in patterns:
            if re.search(pattern, stripped):
                warn(fname, i, msg, level="INFO")


def detect_long_sentences(lines, fname):
    """Detect overly long sentences (>60 Chinese chars without punctuation)."""
    in_fence = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue
        if stripped.startswith(">") or stripped == "---":
            continue
        if re.match(r"^\|.*\|$", stripped):
            continue
        segments = re.split(r"[，。；！？、]", stripped)
        for seg in segments:
            seg = seg.strip()
            cn_chars = len(re.findall(r"[一-鿿]", seg))
            if cn_chars > 60 and len(seg) > 100:
                warn(fname, i, f'长句（{cn_chars} 个中文字符）："{seg[:50]}"...', level="INFO")
                chapter_stats[fname]["long_sentences"].append((i, cn_chars))


def detect_mixed_code(lines, fname):
    """Detect inline code spans containing mixed Chinese and English."""
    in_fence = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            continue
        if re.match(r"^#{1,4}\s", stripped):
            continue
        if stripped.startswith(">") or stripped == "---":
            continue
        if re.match(r"^\|.*\|$", stripped):
            continue
        for m in re.finditer(r"`([^`]+)`", stripped):
            code_content = m.group(1)
            has_cn = bool(re.search(r"[一-鿿]", code_content))
            has_en = bool(re.search(r"[a-zA-Z]", code_content))
            if has_cn and has_en:
                warn(fname, i, f"中英混合内联代码: `{code_content[:40]}`")


# ======================================================================
# Main processing
# ======================================================================

for fpath in chapter_files:
    fname = os.path.basename(fpath)
    lines = _fsutil.read_lines(fpath)

    # Remove trailing newlines for consistent processing
    lines = [line.rstrip("\n\r") for line in lines]

    # Run all detection modules (colloquial/redundant/vague/length/mixed)
    detect_colloquial(lines, fname)
    detect_redundant_adverbs(lines, fname)
    detect_vague_modifiers(lines, fname)
    detect_long_sentences(lines, fname)
    detect_mixed_code(lines, fname)

    # Run advanced checks
    detect_sentence_monotony(lines, fname)
    detect_repeated_connectors(lines, fname)
    detect_weak_verb_xing(lines, fname)
    detect_excessive_de(lines, fname)
    detect_forbidden_phrases(lines, fname)
    detect_vague_qi(lines, fname)
    detect_passive_abuse(lines, fname)
    calculate_readability_metrics(lines, fname)

# ======================================================================
# Chapter-level summary
# ======================================================================

print("\n=== Chapter-level style report ===")
print(f"{'Chapter':28s} {'WARN':6s} {'INFO':6s} {'句数':6s} {'的密度':8s} {'段数':6s} {'长句':6s}")
print("-" * 72)

all_warns = 0
all_infos = 0

for fname in sorted(chapter_stats.keys()):
    s = chapter_stats[fname]
    warn_count = len(s["warnings"])
    info_count = len(s["infos"])
    cn_chars = s["cn_chars"]
    sents = s["sentences"]
    de_density = s["de_count"] / max(cn_chars, 1) * 100
    long_count = len(s["long_sentences"])

    print(
        f"{fname:28s} {warn_count:<6d} {info_count:<6d} {sents:<6d} {de_density:<7.1f}% {s['paragraph_count']:<6d} {long_count:<6d}"
    )

    all_warns += warn_count
    all_infos += info_count

print("-" * 72)
print(f"{'TOTAL':28s} {all_warns:<6d} {all_infos:<6d}")

# ======================================================================
# Detailed warning listing
# ======================================================================

print(f"\n=== Detailed warnings: {all_warns} WARN + {all_infos} INFO ===")
if all_warns + all_infos == 0:
    print("  No issues found.")
else:
    for fname in sorted(chapter_stats.keys()):
        s = chapter_stats[fname]
        if s["warnings"]:
            print(f"\n  [{fname}] WARN:")
            for line_no, msg in s["warnings"]:
                print(f"    L{line_no}: {msg}")
        if s["infos"]:
            print(f"\n  [{fname}] INFO:")
            for line_no, msg in s["infos"]:
                print(f"    L{line_no}: {msg}")

# ======================================================================
# Summary by type
# ======================================================================

print("\n=== Summary by type ===")
type_counts = defaultdict(int)
for fname in chapter_stats:
    for _, msg in chapter_stats[fname]["warnings"]:
        # Extract category from message
        cat = msg.split("，")[0][:15]
        type_counts[cat] += 1
    for _, msg in chapter_stats[fname]["infos"]:
        cat = msg.split("，")[0][:15]
        type_counts[cat] += 1

for cat, count in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {count}")

if all_warns > 0:
    print(f"\n[WARN]  {all_warns} warnings found — review recommended")
else:
    print("\n✅ No WARN-level issues found")
