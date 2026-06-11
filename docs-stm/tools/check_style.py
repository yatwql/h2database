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
import re, os, sys, glob, math
from collections import defaultdict

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

script_dir = os.path.dirname(os.path.abspath(__file__))
docs_dir = os.path.normpath(os.path.join(script_dir, '..'))
chapter_files = sorted(glob.glob(os.path.join(docs_dir, 'ch[0-9]*.md')))

# Collect statistics for chapter-level reporting
chapter_stats = defaultdict(lambda: {
    'warnings': [], 'infos': [],
    'sentences': 0, 'cn_chars': 0, 'de_count': 0,
    'sentence_starts': [], 'paragraph_count': 0,
    'long_sentences': [],
})

def warn(fname, line, msg, level='WARN'):
    """Add a warning, defaulting to WARN level."""
    if level == 'WARN':
        chapter_stats[fname]['warnings'].append((line, msg))
    else:
        chapter_stats[fname]['infos'].append((line, msg))


def detect_sentence_monotony(lines, fname):
    """Detect consecutive sentences starting with the same word.

    Works by collecting paragraph-level text outside fences, splitting
    into sentences, and tracking first-word patterns.
    """
    in_fence = False
    paragraphs = []
    current_para = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('```'):
            if not in_fence and current_para:
                paragraphs.append(current_para)
                current_para = []
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r'^#{1,4}\s', stripped):
            if current_para:
                paragraphs.append(current_para)
                current_para = []
            continue
        if not stripped:
            if current_para:
                paragraphs.append(current_para)
                current_para = []
            continue
        if stripped == '---':
            if current_para:
                paragraphs.append(current_para)
                current_para = []
            continue
        if re.match(r'^\|.*\|$', stripped) or stripped.startswith('>') or stripped.startswith('```'):
            continue
        current_para.append(i)

    if current_para:
        paragraphs.append(current_para)

    chapter_stats[fname]['paragraph_count'] += len(paragraphs)

    # For each paragraph, collect sentence starts
    for para_lines in paragraphs:
        # Join paragraph text
        para_text = ''
        para_line_ranges = []
        for idx in para_lines:
            stripped = lines[idx].strip()
            para_text += stripped + ' '
            para_line_ranges.append(idx)

        if not para_text.strip():
            continue

        # Protect periods inside backtick code spans from false sentence splitting
        # e.g., `Tokenizer.java` should not cause a sentence boundary
        protected_text = re.sub(
            r'`([^`]+)`',
            lambda m: '`' + m.group(1).replace('.', chr(0)) + '`',
            para_text.strip()
        )
        # Also protect periods in bare file extensions outside backticks
        protected_text = re.sub(
            r'(\w+)\.(java|html?|md|py|xml|json|txt|sql|php|css|js|ts)',
            lambda m: m.group(1) + chr(0) + m.group(2),
            protected_text
        )

        # Split into sentences by Chinese/English punctuation
        sentences = re.split(r'(?<=[。！？.!?])\s*', protected_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

        # Restore protected periods
        sentences = [s.replace(chr(0), '.') for s in sentences]

        if len(sentences) < 3:
            continue  # Need at least 3 sentences to detect monotony

        # Extract first real word of each sentence (skip parentheticals)
        starts = []
        for s in sentences:
            # Remove leading brackets/parentheses
            s_clean = re.sub(r'^[（(]?', '', s)
            # Get first Chinese or English word
            m = re.search(r'([一-鿿]|[a-zA-Z]\w*)', s_clean)
            if m:
                starts.append(m.group(1))

        if len(starts) < 3:
            continue

        chapter_stats[fname]['sentence_starts'].extend(starts)

        # Check for repeated starts (3+ sentences with same start word)
        for i in range(len(starts) - 2):
            if starts[i] == starts[i+1] == starts[i+2]:
                # Map back to approximate line number
                approx_line = para_line_ranges[0] if para_line_ranges else 0
                warn(
                    fname, approx_line + 1,
                    f'句式单调：连续 3 句以"{starts[i]}"开头，建议变换句式结构',
                    level='INFO'
                )
                break  # One warning per paragraph

        # Check for high same-start ratio (60%+ sentences same start)
        if len(starts) >= 4:
            from collections import Counter
            start_counts = Counter(starts)
            most_common_word, most_common_count = start_counts.most_common(1)[0]
            ratio = most_common_count / len(starts)
            if ratio > 0.6 and most_common_count >= 3:
                approx_line = para_line_ranges[0] if para_line_ranges else 0
                warn(
                    fname, approx_line + 1,
                    f'句式单调：段落内 {int(ratio*100)}% 句子以"{most_common_word}"开头'
                    f'（{most_common_count}/{len(starts)}句），建议调整',
                    level='INFO'
                )


def detect_repeated_connectors(lines, fname):
    """Detect repeated use of same connector within adjacent sentences."""
    connector_words = ['同时', '另外', '此外', '而且', '并且', '因此', '然而', '但是', '不过']
    in_fence = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r'^#{1,4}\s', stripped):
            continue
        if not stripped or stripped.startswith('>') or stripped == '---':
            continue
        if re.match(r'^\|.*\|$', stripped):
            continue

        # Check for repeated connectors within the same line
        for connector in connector_words:
            # Find all occurrences with their positions
            positions = [m.start() for m in re.finditer(re.escape(connector), stripped)]
            if len(positions) >= 2:
                # For "同时", only flag if occurrences are close (same clause context)
                # It has legitimate dual meanings (also vs concurrently)
                if connector in ('同时', '因此', '然而', '而且', '并且'):
                    # Check if occurrences are within the same clause (~40 chars)
                    close_pairs = sum(1 for i in range(len(positions)-1)
                                      if positions[i+1] - positions[i] < 40)
                    if close_pairs == 0:
                        continue  # Legitimate different usages/contexts
                warn(
                    fname, i,
                    f'重复连接词：本行使用"{connector}" {len(positions)} 次，建议替换为不同连接词',
                    level='WARN'
                )


def detect_weak_verb_xing(lines, fname):
    """Detect '进行' + verb constructions ('进行分析', '进行讨论')."""
    in_fence = False
    pattern = re.compile(r'(?<!正在)进行[的]?[一-鿿]{2,4}')

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r'^#{1,4}\s', stripped):
            continue
        if not stripped or stripped.startswith('>') or stripped == '---':
            continue
        if re.match(r'^\|.*\|$', stripped):
            continue

        for m in pattern.finditer(stripped):
            verb = m.group(0)
            # Filter out false positives (e.g., "进行中" = in progress)
            if verb in ('进行中', '进行的', '进行时'):
                continue
            warn(fname, i, f'弱动词构造："{verb}"，建议改为直接表达', level='WARN')


def detect_excessive_de(lines, fname):
    """Detect excessive '的' in a single line as a marker of nested modification."""
    in_fence = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r'^#{1,4}\s', stripped):
            continue
        if not stripped or stripped.startswith('>') or stripped == '---':
            continue
        if re.match(r'^\|.*\|$', stripped):
            continue

        # Count '的' excluding those in code spans
        text = re.sub(r'`[^`]+`', '', stripped)
        de_count = text.count('的')
        if de_count >= 4:
            # Check density: more than 1 '的' per 10 characters
            text_len = len(re.findall(r'[一-鿿\w]', text))
            if text_len > 0 and de_count / text_len > 0.08:
                warn(
                    fname, i,
                    f'过度"的"：该行含 {de_count} 个"的"（密度 {de_count}/{text_len}）'
                    f'，建议简化修饰结构',
                    level='INFO'
                )

        chapter_stats[fname]['de_count'] += de_count


def detect_vague_qi(lines, fname):
    """Detect potentially ambiguous '其' reference."""
    in_fence = False
    # '其' is ambiguous when it could refer to one of multiple
    # candidate subjects in the preceding text.
    # Simple heuristic: flag '其' + verb constructions when the
    # preceding line(s) contain multiple nouns.

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r'^#{1,4}\s', stripped):
            continue
        if not stripped or stripped.startswith('>') or stripped == '---':
            continue
        if re.match(r'^\|.*\|$', stripped):
            continue

        # Find "其" used as a possessive/pronoun (其 + noun/verb)
        for m in re.finditer(r'其[一-鿿]', stripped):
            # Check if preceding non-empty line(s) contain multiple subjects
            # Simple heuristic: if '其' appears near the end of a sentence
            # that references multiple entities
            prev_lines_text = ''
            for j in range(i-2, i):
                if j >= 0 and j < len(lines):
                    pl = lines[j].strip()
                    if pl and not pl.startswith('```') and not pl.startswith('#'):
                        prev_lines_text += pl

            # Count potential noun candidates (simplified: Chinese words before punctuation)
            nouns_before = len(re.findall(r'[一-鿿]{2,}(?:[，,])', prev_lines_text[:100]))
            if nouns_before >= 3:
                phrase = m.group(0)
                warn(
                    fname, i,
                    f'模糊指代："{phrase}"前的上文中出现多个潜在指代对象，建议明确指代',
                    level='INFO'
                )
                break  # One per line


def detect_passive_abuse(lines, fname):
    """Detect overuse of passive voice marker '被'."""
    in_fence = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r'^#{1,4}\s', stripped):
            continue
        if not stripped or stripped.startswith('>') or stripped == '---':
            continue
        if re.match(r'^\|.*\|$', stripped):
            continue

        # Count 被 in this line
        count = stripped.count('被')
        if count >= 2:
            warn(fname, i, f'被动滥用：本行含 {count} 个"被"，建议部分改为主动表达', level='INFO')


def calculate_readability_metrics(lines, fname):
    """Calculate per-chapter readability metrics (non-WARN, stats only)."""
    in_fence = False
    total_chars = 0
    sentence_count = 0
    cn_char_count = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r'^#{1,4}\s', stripped):
            continue
        if not stripped or stripped.startswith('>') or stripped == '---':
            continue
        if re.match(r'^\|.*\|$', stripped):
            continue

        total_chars += len(stripped)
        cn_chars = len(re.findall(r'[一-鿿]', stripped))
        cn_char_count += cn_chars

        # Count sentence boundaries
        sents = len(re.findall(r'[。！？.!?]', stripped))
        sentence_count += sents

    chapter_stats[fname]['cn_chars'] = cn_char_count
    chapter_stats[fname]['sentences'] = sentence_count


def run_standard_checks(lines, fname):
    """Existing colloquial/length/mixed checks (from original check_style.py)."""
    in_fence = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        if stripped.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r'^#{1,4}\s', stripped):
            continue
        if not stripped:
            continue
        if stripped.startswith('>'):
            continue
        if stripped == '---':
            continue
        if re.match(r'^\|.*\|$', stripped):
            continue

        # 1. Colloquial patterns
        colloquial = [
            (r'说白了', '口语化表达"说白了"，建议替换为"换言之"或删除'),
            (r'你会发现', '口语化表达"你会发现"，建议使用"可以观察到"'),
            (r'我们来看', '口语化表达"我们来看"，建议使用"本节分析"'),
            (r'其实就', '口语化表达"其实就"，建议删除"其实"'),
            (r'显而易见', '过于绝对，建议使用"不难看出"'),
            (r'值得一提的是', '冗余表达，建议直接陈述'),
        ]
        for pattern, msg in colloquial:
            if re.search(pattern, stripped):
                warn(fname, i, msg)

        # 1b. Additional colloquial/informal
        additional_informal = [
            (r'说白了', None),  # already handled above
            (r'毫无疑问', '过于绝对，建议使用"显然"'),
            (r'众所周知', '学术写作应避免"众所周知"，直接陈述事实'),
            (r'总的来说', '口语化总结，建议使用"综上所述"'),
        ]
        for pattern, msg in additional_informal:
            if pattern not in [p for p, _ in colloquial]:
                if re.search(pattern, stripped):
                    warn(fname, i, msg)

        # 2. Redundant adverbs
        redundant_adverbs = [
            (r'实际上', '冗余副词"实际上"，建议直接陈述'),
            (r'基本上', '冗余副词"基本上"，建议直接陈述'),
            (r'本质上', '冗余副词"本质上"，建议直接陈述'),
            (r'其实\b', '冗余副词"其实"，建议直接陈述或删除'),
        ]
        for pattern, msg in redundant_adverbs:
            if re.search(pattern, stripped):
                warn(fname, i, msg, level='INFO')

        # 3. Vague modifiers
        vague_modifiers = [
            (r'非常[一-鿿]', '空泛修饰"非常X"，建议使用更具体的描述'),
            (r'十分[一-鿿]', '空泛修饰"十分X"，建议使用更具体的描述'),
            (r'极其[一-鿿]', '空泛修饰"极其X"，建议使用更具体的描述'),
            (r'相当[一-鿿]{1,2}[的\w]', '空泛修饰"相当X"，建议使用更具体的描述'),
        ]
        for pattern, msg in vague_modifiers:
            if re.search(pattern, stripped):
                warn(fname, i, msg, level='INFO')

        # 4. Overly long sentences (>80 Chinese characters without punctuation)
        segments = re.split(r'[，。；！？、]', stripped)
        for seg in segments:
            seg = seg.strip()
            cn_chars = len(re.findall(r'[一-鿿]', seg))
            if cn_chars > 60 and len(seg) > 100:
                warn(
                    fname, i,
                    f'长句（{cn_chars} 个中文字符）："{seg[:50]}..."',
                    level='INFO'
                )
                chapter_stats[fname]['long_sentences'].append((i, cn_chars))

        # 5. Inline code spans with Chinese (mixed language)
        for m in re.finditer(r'`([^`]+)`', stripped):
            code_content = m.group(1)
            has_cn = bool(re.search(r'[一-鿿]', code_content))
            has_en = bool(re.search(r'[a-zA-Z]', code_content))
            if has_cn and has_en:
                warn(fname, i, f'中英混合内联代码: `{code_content[:40]}`')


# ======================================================================
# Main processing
# ======================================================================

for fpath in chapter_files:
    fname = os.path.basename(fpath)
    with open(fpath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Remove trailing newlines for consistent processing
    lines = [l.rstrip('\n\r') for l in lines]

    # Run standard checks (original colloquial/length/mixed)
    run_standard_checks(lines, fname)

    # Run new advanced checks
    detect_sentence_monotony(lines, fname)
    detect_repeated_connectors(lines, fname)
    detect_weak_verb_xing(lines, fname)
    detect_excessive_de(lines, fname)
    detect_vague_qi(lines, fname)
    detect_passive_abuse(lines, fname)
    calculate_readability_metrics(lines, fname)


# ======================================================================
# Chapter-level summary
# ======================================================================

print(f'\n=== Chapter-level style report ===')
print(f'{"Chapter":28s} {"WARN":6s} {"INFO":6s} {"句数":6s} {"的密度":8s} {"段数":6s} {"长句":6s}')
print('-' * 72)

all_warns = 0
all_infos = 0

for fname in sorted(chapter_stats.keys()):
    s = chapter_stats[fname]
    warn_count = len(s['warnings'])
    info_count = len(s['infos'])
    cn_chars = s['cn_chars']
    sents = s['sentences']
    de_density = s['de_count'] / max(cn_chars, 1) * 100
    long_count = len(s['long_sentences'])

    print(f'{fname:28s} {warn_count:<6d} {info_count:<6d} {sents:<6d} {de_density:<7.1f}% {s["paragraph_count"]:<6d} {long_count:<6d}')

    all_warns += warn_count
    all_infos += info_count

print('-' * 72)
print(f'{"TOTAL":28s} {all_warns:<6d} {all_infos:<6d}')

# ======================================================================
# Detailed warning listing
# ======================================================================

print(f'\n=== Detailed warnings: {all_warns} WARN + {all_infos} INFO ===')
if all_warns + all_infos == 0:
    print('  No issues found.')
else:
    for fname in sorted(chapter_stats.keys()):
        s = chapter_stats[fname]
        if s['warnings']:
            print(f'\n  [{fname}] WARN:')
            for line_no, msg in s['warnings']:
                print(f'    L{line_no}: {msg}')
        if s['infos']:
            print(f'\n  [{fname}] INFO:')
            for line_no, msg in s['infos']:
                print(f'    L{line_no}: {msg}')

# ======================================================================
# Summary by type
# ======================================================================

print(f'\n=== Summary by type ===')
type_counts = defaultdict(int)
for fname in chapter_stats:
    for _, msg in chapter_stats[fname]['warnings']:
        # Extract category from message
        cat = msg.split('，')[0][:15]
        type_counts[cat] += 1
    for _, msg in chapter_stats[fname]['infos']:
        cat = msg.split('，')[0][:15]
        type_counts[cat] += 1

for cat, count in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f'  {cat}: {count}')

if all_warns > 0:
    print(f'\n[WARN]  {all_warns} warnings found — review recommended')
else:
    print(f'\n✅ No WARN-level issues found')
