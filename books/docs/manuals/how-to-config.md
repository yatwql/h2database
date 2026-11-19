# 配置指南

工具链的所有可调项都来自 `books/data/`。**文件职责的权威定义**见
[`technical.md §13`](../spec/technical.md)——那里区分「文档（结构/表述/名词）」与
「配置（规则/基础/外部服务）」，并给出每个文件改错的后果。本文只讲怎么改。脚本通过 `lib/_config.py` 读取，
不在代码里硬编码；改配置不需要改代码，改完跑 `make.py check` 验证。

| 层 | 文件 | 管什么 |
| ---- | ------ | -------- |
| 数据组织 | `data/tmpl/book.toml` | 书名、版本、路径、章节清单、章节标题、H1 编号、覆盖归属、章节→包映射 |
| 基础配置 | `data/config/base.json` | 源码树、语言、文件后缀、包前缀、状态与基线路径、工具链预算、日志 |
| 风格配置 | `data/config/style.json` | 展示文案、章节骨架、图注词表、写作与质量阈值、生成能力与模板 |
| 语言包 | `data/language/<code>.json` | 章节骨架名、练习提示语、术语提示行 |
| LLM | `data/config/llm_provider.json`、`llm_settings.json` | provider、路由与生成参数 |

## 1. 数据组织（book.toml）

```toml
[book]
title = "某系统源码剖析"
version = "1.0"
merged_name = "code-analysis"      # 产物文件名前缀

[paths]
manuscript = "data/manuscript"     # 手稿目录
dist = "dist"                      # 产物目录
docs = "docs"
tools = "src/python"

[chapters]
files = ["cover.md", "ch1-overview.md", "appendix-a-cases.md"]  # 阅读顺序
front_glob = "front/*.md"          # 前件
back_glob = "back/*.md"            # 后件（术语表/索引/参考）

[chapters.titles]                  # 每个文件贡献的 H1 标题
"ch1-overview.md" = ["总体架构"]

[chapters.numbering]               # H1 编号，跨文件唯一
"ch1-overview.md" = [1]

[chapters.coverage]                # 该文件覆盖书中的哪些章（可重复）
"ch1-overview.md" = [1]

[chapters.packages]                # 单主责：每个源码包只归一章
"ch1-overview.md" = ["org.example", "org.example.core"]
```

要点：`numbering` 必须唯一（决定 H1 顺序），`coverage` 允许重复（用于均衡度量），
`packages` 必须唯一（否则 `gate_trace`/`check_architecture` 会报）。

## 2. 基础配置（base.json）

```json
{
  "sources": {
    "src_main": "../h2/src/main",     // 源码树根
    "pom_root": "../h2/pom.xml",      // 版本来源（可缺省）
    "languages": ["java"],            // 支持 java / python / rust，可多选
    "file_suffix": ".java",
    "package_prefix": "org.h2"
  },
  "baselines": {"ascii": "data/baselines/ascii-baseline.json"},
  "toolchain": {"coverage_fail_under": 86, "pdf_max_mb": 12, "epub_max_mb": 10},
  "logging": {"level": "INFO", "dir": "logs", "retention_days": 14}
}
```

多语言时 `languages` 写多个，inventory 的包键会加语言前缀（`java:org.h2`、`python:pkg`）。

## 3. 风格配置（style.json）

```json
{
  "project": {"display_title_zh": "……", "author": "……", "running_head": "……"},
  "sections": {"per_chapter": ["本章导读", "本章小结", "延伸思考", "延展阅读"]},
  "captions": {"leading_verbs": ["展示", "对比"], "vague_trailing": ["过程"],
               "presets": {"strict": {"min_chars": 8, "max_chars": 30, "fail_at": 0}}},
  "quality": {"min_coords_per_chapter": 15, "min_chapter_lines": 150, "max_table_rows": 20},
  "prose": {"avg_sentence_good": 28, "min_composite": 80},
  "generation": {"max_packages_per_table": 12, "exercises_per_chapter": 4},
  "limits": {"sources": {"limit": 900, "warn": 700}}
}
```

阈值只在这里改；`min_composite`、`max_duplicate_ratio` 等是棘轮，收紧前先清账。

### style.json 键一览

| 段 | 键 | 作用 |
| ---- | ---- | ------ |
| `project` | `display_title_*`、`author`、`running_head` | 渲染文案（HTML/PDF/EPUB） |
| `sections` | `per_chapter`、`optional` | 必备段落（结构门禁按此检查）与允许的可选段落 |
| `captions` | `leading_verbs`、`vague_trailing`、`presets.{strict,normal,loose}` | 图注动宾词表与阈值预设（min_chars < max_chars、fail_at ≥ 0） |
| `diagrams` | `markers` | ASCII 图的框线/箭头字符集 |
| `quality` | 章节行数、表格行数、重复度、坐标密度、术语与练习下限 | 图书质量门禁阈值 |
| `prose` | 句长/段落/列表/重复度的好与坏锚点、`min_composite`、`forbid_phrases` | 文风评分与禁用语 |
| `generation` | 表格容量、练习数、清单条数 | 生成器的数值上限（文案见 `templates.toml`） |
| `style_rules` | `terminology`（同义词组，检测混用）、`banned_link_text`、`heading`（尾标点/裸标签）、`cjk_latin_spacing`、`list_punctuation`、`max_paragraph_chars` | 术语一致性与排版规则（`style_rules.py`） |
| `limits` | `sources/tests/docs/manuscript` 的 `limit`/`warn` | 文件长度预算 |

改完运行 `python books/src/python/make.py check`：`style_schema.py` 会先校验结构
（未知键、缺字段、区间不合理都会失败），再由各门禁按新阈值执行。

### 风格相关文件的归属（文档是文档，配置是配置）

| 关注点 | 文件 | 属于 |
| -------- | ------ | ------ |
| 判定规则与阈值（图注词表、质量/文风阈值、篇幅预算、必备段落名） | `data/config/style.json` | 配置 |
| 文体文案（四段引言、深读要点等叙述模板） | `data/tmpl/templates.toml` | 文档 |
| 名称与提示语（章节骨架名、练习提示/回顾前缀、术语行） | `data/language/zh.json` | 文档 |
| 书籍身份与展示文案（书名、作者、页眉、产物名） | `data/tmpl/book.toml [book]/[project]` | 文档 |

`style_schema.py` 会拒绝把叙述模板塞回 `style.json`（`generation.templates`）
或把展示文案放进配置（`project`），保证两边不串味。

## 4. 语言包（language/zh.json）

```json
{"code": "zh",
 "sections": {"guide": "本章导读", "summary": "本章小结",
              "exercises": "延伸思考", "further": "延展阅读"},
 "exercise": {"hint_prefix": "提示", "review_prefix": "回顾"},
 "terms": {"reference_line": "术语参考", "glossary_title": "术语表",
           "glossary_link": "back/glossary.md"}}
```

换语言 = 换一份 JSON；审计脚本按包里写的名字匹配手稿。

## 5. LLM 配置

`llm_provider.json` 定义 provider 与路由，`llm_settings.json` 定义生成参数：

```json
{"providers": {"mock": {"kind": "mock"},
               "openai": {"kind": "openai-compatible",
                          "base_url": "https://api.openai.com/v1",
                          "api_key_env": "OPENAI_API_KEY",
                          "models": ["gpt-4o-mini"]}},
 "default_provider": "mock",
 "routing": {"scenario": {"summary": "openai"}, "book": {}, "chapter": {}}}
```

优先级：`chapter` > `book` > `scenario` > `default_provider`。密钥只读环境变量
（`api_key_env` 指向的变量名），不写进仓库；`mock` 可离线跑通全链路。

**强度（thinking level）**：路由项可写成对象，按场景指定思考强度：

```json
{"routing": {"scenario": {
   "chapter-draft": {"provider": "openai", "thinking": "medium"},
   "chapter-polish": {"provider": "openai", "thinking": "high"},
   "summary": {"provider": "mock", "thinking": "low"}}},
 "thinking_levels": ["off", "low", "medium", "high"]}
```

缺省强度来自 `llm_settings.json` 的 `defaults.thinking`（默认 `low`），也可在
`thinking.scenario/book/chapter` 覆盖；越界值直接报错。强度会作为
`reasoning_effort` 传给 openai-compatible provider，`mock` 会把它回显出来便于测试。

## 6. 改完怎么验证

```bash
python books/src/python/make.py check    # 配置一致性、门禁全量
python books/src/python/make.py doctor   # 依赖与环境
```

## 7. 三个版本

- **工具版本**：`lib/_version.py`（或被 `base.json [sources].tool_version` 覆盖）。
- **源码版本**：`base.json [sources].version` 优先，否则读源码清单（pom/pyproject/Cargo）。
- **文档版本**：`book.toml [book].version`；管理文档头的 `> 版本：vX` 必须与之一致。

`bookctl status` 会打印 `versions : tool … source … doc …`，合并稿首行写
`<!-- versions: … -->` manifest，`make.py check` 里的 `versions` 门禁负责校验。
