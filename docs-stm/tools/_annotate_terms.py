#!/usr/bin/env python3
"""
Add glossary reference note to each chapter's guide block.

Inserts a standardized line into each chapter's existing guide block
(> **本章导读** section) referencing the book-end glossary.

Modes:
  (default) Insert glossary reference into unannotated chapter files.
  --report-missing  Scan chapter files for bold terms not in glossary.
  --check           Like --report-missing, but exits with code 1 if any missing.
"""
import re, os, sys, glob
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

script_dir = os.path.dirname(os.path.abspath(__file__))
docs_dir = os.path.normpath(os.path.join(script_dir, '..'))
glossary_path = os.path.join(docs_dir, 'back', 'glossary.md')


def parse_glossary_terms(path: str) -> dict[str, list[int]]:
    """Parse glossary.md and return a mapping of term names to chapter numbers."""
    terms: dict[str, list[int]] = {}
    term_pattern = re.compile(r'^- \*\*([^*]+)\*\*')
    ch_pattern = re.compile(r'第(\d+)章')
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            m = term_pattern.match(line.strip())
            if m:
                term = m.group(1).strip()
                chapters = [int(c) for c in ch_pattern.findall(line)]
                terms[term] = chapters
    return terms


def report_missing(check_mode: bool = False) -> int:
    """Scan chapter files for bold terms not found in glossary.

    Returns count of missing term occurrences (not unique terms).
    Exits with code 1 in --check mode if any missing terms found.
    """
    terms = parse_glossary_terms(glossary_path)
    # Build normalized lookup: lowercase + strip common suffixes
    known_normalized: dict[str, str] = {}
    # Also build Chinese alias lookup for cross-language matching
    chinese_aliases: dict[str, str] = {}
    # Known Chinese<->English term mappings
    ch_en_map = {
        '写放大': 'Write Amplification',
        '无锁读': 'CAS',
        '快照隔离': 'Snapshot Isolation',
        '写时复制': 'COW',
        '仅追加': 'Append-Only',
        '仅追加写入': 'Append-Only',
        '日志结构存储': 'Log-Structured Storage',
        '日志结构合并树': 'LSM-Tree',
        '递归下降解析器': 'Recursive Descent Parser',
        '递归下降': 'Recursive Descent Parser',
        '预编译语句': 'Prepared Statement',
        '预写日志': 'WAL',
        '撤销日志': 'Undo Log',
        '保存点': 'Savepoint',
        '可串行化': 'Serializable',
        '可重复读': 'Repeatable Read',
        '读已提交': 'Read Committed',
        '索引组织表': 'IOT',
        '变长整数': 'VarInt / VarLong',
        '空闲空间': 'Free Space',
        '文件头': 'File Header',
        '页面分裂': 'PageSplit',
        '页面指针': 'Page Pointer',
        '表索引': 'Table Index',
        '索引条件': 'IndexCondition',
        '元数据锁': 'Meta Lock',
        '兼容模式': 'Mode',
        '词法分析器': 'Tokenizer',
        '事务管理器': 'TransactionStore',
        '紧凑化': 'Compact',
        '死锁': 'Deadlock',
        '会话': 'Session',
        '混合优化策略': 'Hybrid Strategy',
        '遗传算法': 'Genetic Algorithm',
        '连接顺序': 'Hybrid Strategy',
        '后台写入': 'BackgroundWriter',
        '文件存储': 'FileStore',
        '版本化值': 'VersionedValue',
        '写冲突': 'TxDecisionMaker',
        '提交决策': 'CommitDecisionMaker',
        '回滚决策': 'RollbackDecisionMaker',
        '单写入者': 'Single Writer',
        '命令容器': 'CommandContainer',
        '本地结果集': 'LocalResult',
    }
    for t in terms:
        known_normalized[t.lower().rstrip('.')] = t
        # Check if this term has Chinese aliases
        for ch, en in ch_en_map.items():
            if en.lower() == t.lower() or t.lower().startswith(en.lower()):
                chinese_aliases[ch] = t
                # Also add normalized version
                known_normalized[ch.lower()] = t

    chapter_files = sorted(glob.glob(os.path.join(docs_dir, 'ch[0-9]*.md')))

    # Patterns for term-like text in chapter files
    bold_pattern = re.compile(r'\*\*([^*]+)\*\*')

    # Structural markers that should never be glossary terms
    skip_terms = {'本章导读', '前置知识', '章节要点', '注意', '说明', '提示', '警告', '参考',
                  '核心文件', '源码位置', '实现位置', '延展阅读', '待补充', '附录',
                  '术语参考', '性能参考', '阅读策略', '优势', '局限', '关键字', '局限性',
                  '标识符', '运算符', '分隔符', '层定位', '关键类', '写流程',
                  '实现架构', '发展历程与定位', '部署模式与多协议接入',
                  '跨层数据流与编译执行分离', '核心设计哲学', '设计决策关联网络',
                  '测试目录', 'SQL 流程断点入口', '测试服务器启动', 'H2 Console 地址',
                  '平衡树', 'COW', '锁机制', '递归性', 'SQL 解析', 'Row 迭代',
                  '行迭代', '快照读', 'Page 缓存', 'Chunk 分配', 'Chunk 压缩',
                  '文件 truncate', '显式紧凑', '崩溃恢复',
                  # Feature descriptions (not technical terms)
                  '超轻量', '零管理', '纯 Java', '薄封装', '无锁读',
                  # Generic SQL/Java concepts
                  'SQL 注入防护', 'SQL 兼容',
                  # Value names
                  'READ_COMMITTED', 'statementSnapshot', 'snapshot',
                  # Class names already covered by related glossary entries
                  'CommandList', 'Plan', 'PlanItem',
                  # Short state/transition labels
                  'OPEN → STOPPING', 'STOPPING → CLOSED', 'CLOSED',
                  # Heading phrases
                  'JDBC 调用链路', '无锁读取 + COW 写入',
                  '索引组织表 + 二级索引回表', '策略模式 + 装饰器模式',
                  'MVCC 需要保留旧版本', 'Java GC 管理内存',
                  '45 秒保留', 'next 链',
                  'DDL 版本检查优先于缓存查找',
                  'append 批量写入模式',
                  'CAS 防重入', 'DROP', 'GIS 系统',
                  # Deployment mode descriptions
                  'Embedded 模式', 'Client-Server 模式', 'In-Memory 模式',
                  '纯 Java + 可嵌入', 'B-Tree + COW',
                  # Design patterns (named in code but not glossary concepts)
                  'Command Pattern', 'Composite Pattern',
                  # Descriptive compound phrases
                  'Chunk 存储', 'B-Tree 映射', 'COW 写', 'CAS 循环',
                  'B+Tree 变体', 'append 模式', 'MVMap 根页面访问',
                  'DDL 解析', 'Command 接口', 'Prepared 抽象基类',
                  'Index Conditions', 'Filter Condition',
                  # MVStore internal structures (too granular for glossary)
                  'Store Header', 'Chunk Header', 'Chunk Footer',
                  # Phrases, not terms
                  'undo log 用于事务回滚', 'Read-Write Locks 模型',
                  'CAS + Single Writer 模型',
                  # Close enough to Compact (already in glossary)
                  'Compaction 策略',
                  # Class name (too specific for book-level glossary)
                  'FreeSpaceBitSet'}

    def is_glossary_candidate(term: str) -> bool:
        """Return True if this bold term could be a glossary candidate (vs. heading/noise)."""
        if len(term) < 3:
            return False
        # Contains structural function words (phrases, not terms)
        if re.search(r'[的与和及或]', term):
            return False
        # Ends with 层 (layer reference)
        if term.endswith('层'):
            return False
        # Starts with a phase marker
        if re.match(r'^第[一二三四五六七八九十\d]', term):
            return False
        # Contains 详解/追踪/练习/场景
        if re.search(r'(详解|追踪|练习|场景)', term):
            return False
        # Method names (contain parentheses)
        if '()' in term:
            return False
        # Arrow operators (state transitions)
        if '→' in term:
            return False
        # Code/comparison operators
        if '->' in term:
            return False
        # Ends with Chinese colon or English colon (heading style)
        if re.search(r'[：:]$', term):
            return False
        # Pure Chinese with 4+ characters (likely a descriptive heading)
        if re.match(r'^[一-鿿\s，。、；：""''（）()]+$', term) and len(term) >= 4:
            return False
        # Contains file path patterns or code references
        if re.search(r'[/\\]', term) or re.search(r'\.java', term):
            return False
        # Backtick-containing terms (code references)
        if '`' in term:
            return False
        # Parenthesized descriptions (e.g. "DML（数据操作语言）")
        if re.match(r'.+[（(][^）)]+[）)]', term):
            return False
        # Too long to be a single term
        if len(term) > 35:
            return False
        # Version strings
        if re.match(r'^v?\d+[\.x]\d+', term):
            return False
        # Pure English single words shorter than 8 chars (common like Plan, Select)
        if re.match(r'^[A-Z][a-zA-Z]{1,7}$', term):
            return False
        # Method call patterns (name followed by parentheses content)
        if re.match(r'^[a-z]\w+\(', term):
            return False
        # SQL keywords or tips
        if re.match(r'^(SELECT|INSERT|UPDATE|DELETE|JOIN|FROM|WHERE)\s', term):
            return False
        # Descriptive phrases like "每次 put() 导致页面超出容量"
        if re.match(r'^(每次|当|如果|所有|使用)', term):
            return False
        return True

    missing_count = 0
    for fpath in chapter_files:
        fname = os.path.basename(fpath)
        with open(fpath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for lineno, line in enumerate(lines, start=1):
            # Extract bold terms
            for m in bold_pattern.finditer(line):
                term = m.group(1).strip()
                if not is_glossary_candidate(term):
                    continue
                # Skip figure captions, section numbers
                if re.match(r'^图 \d+-\d+', term) or re.match(r'^\d+[.、]', term):
                    continue
                # Skip heading abbreviations
                if re.match(r'^\d+\.\d+\s', term):
                    continue
                # Skip explicit skip terms
                if term in skip_terms:
                    continue

                norm = term.lower().rstrip('.')
                if norm not in known_normalized:
                    print(f"  MISSING: {fname}:{lineno}: **{term}**")
                    missing_count += 1

    if check_mode and missing_count > 0:
        print(f"\nFound {missing_count} missing term(s). Use --report-missing for details.")
        sys.exit(1)

    return missing_count


# ---- Entry point ----

if '--report-missing' in sys.argv:
    count = report_missing(check_mode=False)
    print(f"\nTotal missing term occurrences: {count}")
    sys.exit(0)

if '--check' in sys.argv:
    count = report_missing(check_mode=True)
    print(f"\nNo missing terms found (checked {count} occurrences).")
    sys.exit(0)

# ---- Default: insert glossary reference ----

chapter_files = sorted(glob.glob(os.path.join(docs_dir, 'ch[0-9]*.md')))
glossary_ref = '> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。\n'
count = 0

for fpath in chapter_files:
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()

    if '术语参考' in content:
        print(f"  Already annotated: {os.path.basename(fpath)}")
        continue

    lines = content.split('\n')
    last_guide_line = -1
    in_guide = False
    for i, line in enumerate(lines):
        if line.strip().startswith('> **本章导读**'):
            in_guide = True
        if in_guide and line.strip().startswith('>'):
            last_guide_line = i
        elif in_guide and not line.strip().startswith('>') and line.strip() != '':
            break

    if last_guide_line >= 0:
        lines.insert(last_guide_line + 1, glossary_ref.rstrip('\n'))
        content = '\n'.join(lines)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        count += 1
        print(f"  Added to {os.path.basename(fpath)}")
    else:
        print(f"  No guide block found: {os.path.basename(fpath)}")

print(f"Updated {count} chapter files")