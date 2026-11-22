# 配置指南

> 维度：**配置——改哪个文件、改了生效在哪里、改错会怎样**
> 软件：bookwright — 源码分析成书工具 v0.1

所有可调项都来自 `books/data/`，程序只通过配置文件取值，改配置不需要改代码。
三个主文件各有分工：`book.toml` 决定这本书**是什么、怎么组织**，`base.json` 决定
**跑在哪、依据什么**，`style.json` 决定**怎么写、写成什么样**。改完跑一次 `make.py check` 验证。

| 层 | 文件 | 管什么 |
| ---- | ------ | -------- |
| 数据组织 | `data/config/book/book.toml` | 书名、版本、路径、章节清单、章节标题、H1 编号、覆盖归属、章节→包映射 |
| 基础配置 | `data/config/base.json` | 源码树、语言、文件后缀、包前缀、状态与基线路径、工具链预算、日志 |
| 风格配置 | `data/config/style.json` | 展示文案、章节骨架、图注词表、写作与质量阈值、生成能力与模板 |
| 语言包 | `data/language/<code>.json` | 章节骨架名、练习提示语、术语提示行 |
| LLM | `data/config/llm_provider.json`、`llm_settings.json`、`llm_pricing.json` | provider、路由、生成参数与单价 |

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
tmp = "data/tmp"                   # 临时目录：HTML 片段缓存与 --force 备份（已 gitignore）
state = "data/state"               # 派生状态：ingest 每次重建（已 gitignore）
templates = "data/tmpl"            # 叙述模板（templates.toml）
book = "data/config/book"          # 本书专属文件（book.toml / case-studies.toml）
baselines = "data/baselines"       # 已评审存量的账本目录
cover_image = ""                   # 可选：封面图，留空则不生成

[chapters]
files = ["cover.md", "ch1-<主题>.md", "appendix-a-<主题>.md"]  # 阅读顺序
front_glob = "front/*.md"          # 前件
back_glob = "back/*.md"            # 后件（术语表/索引/参考）

[chapters.titles]                  # 每个文件贡献的 H1 标题
"ch1-<主题>.md" = ["总体架构"]

[chapters.numbering]               # H1 编号，跨文件唯一
"ch1-<主题>.md" = [1]

[chapters.coverage]                # 该文件覆盖书中的哪些章（可重复）
"ch1-<主题>.md" = [1]

[chapters.packages]                # 单主责：每个源码包只归一章
"ch1-<主题>.md" = ["org.example", "org.example.core"]
```

要点：`numbering` 必须唯一（决定 H1 顺序），`coverage` 允许重复（用于均衡度量），
`packages` 必须唯一（否则 `gate_trace`/`check_architecture` 会报）。

## 2. 基础配置（base.json）

```json
{
  "sources": {
    "src_main": "../h2/src/main",     // 源码树根
    "pom_root": "../h2/pom.xml",      // 版本来源（可缺省）
    "languages": ["java"],            // 支持 java / python / rust / kotlin / go，可多选
    "file_suffix": ".java",
    "package_prefix": "org.h2"
  },
  "baselines": {"ascii": "data/baselines/ascii-baseline.json"},
  "toolchain": {"coverage_fail_under": 88, "pdf_max_mb": 12, "epub_max_mb": 10},
  "logging": {"level": "INFO", "dir": "logs", "retention_days": 14}
}
```

多语言时 `languages` 写多个，inventory 的包键会加语言前缀（`java:org.h2`、`python:pkg`）。
`toolchain` 段里另有页面几何（`pdf_page_width`/`pdf_page_height`/`pdf_page_tolerance`），
`verify_pdf.py` 按它判定 A4；换纸张尺寸改这里，不改代码。

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
| `clusters` | `min_figures`、`window_lines` | 图簇的张数下限与行距（`figure_clusters.py`、`structure.py` 共用） |
| `quality` | 章节行数、表格行数、重复度、坐标密度、术语与练习下限、`min_figures_per_section`、`min_figure_coverage_pct` | 图书质量门禁阈值 |
| `prose` | 句长/段落/列表/重复度的好与坏锚点、`min_composite`、`forbid_phrases` | 文风评分与禁用语 |
| `generation` | 表格容量、练习数、清单条数 | 生成器的数值上限（文案见 `templates.toml`） |
| `style_rules` | `terminology`（同义词组，检测混用）、`banned_link_text`、`heading`（尾标点/裸标签）、`cjk_latin_spacing`、`list_punctuation`、`max_paragraph_chars` | 术语一致性与排版规则（`style_rules.py`） |
| `content_depth` | `glossary_min_uses`（高频类型须入术语表）、`glossary_ignore`（通用名白名单）、`excerpt_lines`（代码摘录比对行数） | 内容深度规则（`content_depth.py`） |
| `limits` | `sources/tests/docs/manuscript` 的 `limit`/`warn` | 文件长度预算（四档都要显式声明） |
| 可写配置项 | `bookctl settings` / TUI「配置项」逐项列出：书名、版本、手稿/产物目录、语言、日志级别、默认 provider、`llm.daily_cost_limit`、`llm.ingest_prose` | 改完立即写回并重载 |
| `thresholds` | 练习、索引（总数与每章、主/子/see-also）、术语、每章跨章引用下限 | 内容完整性的下限；判据只写“不低于配置下限”，键名与取值归 `technical.md` §3.2 |

改完运行 `python books/src/python/make.py check`：`style_schema.py` 会先校验结构
（未知键、缺字段、区间不合理都会失败），再由各门禁按新阈值执行。

### 风格相关文件的归属（文档是文档，配置是配置）

| 关注点 | 文件 | 属于 |
| -------- | ------ | ------ |
| 判定规则与阈值（图注词表、质量/文风阈值、篇幅预算、必备段落名） | `data/config/style.json` | 配置 |
| 文体文案（四段引言、深读要点等叙述模板） | `data/tmpl/templates.toml` | 文档 |
| 名称与提示语（章节骨架名、练习提示/回顾前缀、术语行） | `data/language/zh.json` | 文档 |
| 书籍身份与展示文案（书名、作者、页眉、产物名） | `data/config/book/book.toml [book]/[project]` | 文档 |

`style_schema.py` 会拒绝把叙述模板塞回 `style.json`（`generation.templates`）
或把展示文案放进配置（`project`），保证两边不串味。

## 3.5 归档与测试报告（base.json）

```json
"archive": {"dir": "data/archive", "retention_days": 45},
"reports": {"dir": "test-reports", "retention_days": 30}
```

- `archive.dir`：手稿与产物的日期归档根目录；`retention_days` 缺省 45 天（只保留最近 45 天）。
- `reports.dir`：测试报告目录；`retention_days` 缺省 30 天。
- 两者都只进不出、不参与构建，已在 `.gitignore` 里。

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

### 源码 → 手稿是否用 LLM

`book.toml` 的开关决定 ingest 阶段要不要让 LLM 起草**导读**与**小结**两段散文：

```toml
[llm]
ingest_prose = false   # 默认关；开则走 chapter-draft / summary 场景
```

事实、源码坐标、表格、练习、交叉索引**永远确定性**，开关只影响这两段叙述文字；
provider 不可用时自动回退到确定性文本并在 stderr 打一行警告，不会中断 ingest。
命令行另有 `--llm`（只影响本次运行），TUI 里是菜单下方单独的 `l` 键（菜单项 `1)` 跑的是确定性路径）。

`llm_provider.json` 定义 provider 与路由，`llm_settings.json` 定义生成参数：

```json
{
  "providers": {
    "deepseek-main": {
      "kind": "anthropic",
      "base_url": "https://api.deepseek.com/anthropic",
      "credentials_ref": "deepseek-main",
      "api_key_env": "DEEPSEEK_MAIN_API_KEY",
      "models": ["deepseek-v4-flash"]
    }
  },
  "default_provider": "deepseek-main",
  "routing": {"scenario": {"summary": "deepseek-main"}, "book": {}, "chapter": {}}
}
```

优先级：`chapter` > `book` > `scenario` > `default_provider`。

`kind` 决定协议：`anthropic` 走 Messages 接口（`POST /v1/messages`、`x-api-key`
鉴权），`openai-compatible` 走 `chat/completions`（`Authorization: Bearer`）。
仓库默认只配置真实 provider：`opencode-go`（`default_provider`）与 `deepseek-main`（`review`
场景）；`mock` 仍由代码支持，需要完全离线时临时加一个 `{"kind": "mock"}` 条目即可。

密钥不写进仓库：环境变量（`api_key_env`）优先，其次 `data/config/llm_key.json`
的 `providers.<credentials_ref>.api_key`，该文件被 `.gitignore` 忽略。端点与模型
只有一个事实来源——`llm_provider.json`；密钥块里写 `endpoint` / `model` 仅作临时
覆盖（例如换网关），不写则完全跟配置走。

**优先级与回退**：`providers.<名>.priority` 数值小者靠前。一次调用先走路由
指定的 provider，失败（无密钥、端点报错、响应不可解析）则按 priority 依次回退，
全部失败才抛出聚合错误。`pacing.min_interval` 是端点级节流：请求前按上一笔时间
自动等待，避免超出订阅节奏；`pacing.max_concurrency` 用于说明在途上限。

**强度（thinking level）**：路由项可写成对象，按场景指定思考强度：

```json
{"routing": {"scenario": {
   "chapter-draft": {"provider": "deepseek-main", "thinking": "medium"},
   "chapter-polish": {"provider": "deepseek-main", "thinking": "high"},
   "review": {"provider": "opencode-go", "thinking": "high"}}},
 "thinking_levels": ["off", "low", "medium", "high"]}
```

缺省强度来自 `llm_settings.json` 的 `defaults.thinking`（默认 `low`），也可在
`thinking.scenario/book/chapter` 覆盖；越界值直接报错。强度会作为
`reasoning_effort` 传给 openai-compatible provider；`mock` 条目会把它回显出来便于测试。

## 5.1 LLM 的计价、用量与上限

每次 LLM 调用都会记账：token 与费用写在结果的最后一行，明细逐行追加到
`books/logs/llm-usage.jsonl`（gitignored，可以按天/按场景统计）。

单价放在 `data/config/llm_pricing.json`，按**百万 token** 计、用 provider 自己的货币：

```json
{"currency": "USD",
 "models": {"deepseek-v4-flash": {"input_per_mtok": 0.28, "output_per_mtok": 0.42}}}
```

- 表里没有的模型照样能调用，只是费用显示 `未定价`——不猜价格。
- **多币种**：每个模型在自己的货币里记价（`models.<名>.currency`），账本按模型货币累加；
  显示统一换成 `display_currency`（缺省 **CNY**），换算走 `fx` 里“货币 → 人民币”的手工锚点。
  锚点缺失时不硬换，直接显示原币种金额（如 `2.5000 USD`）。
- **价格从哪来**：`models` 现直接取自 investor-review 项目的参考表（该表按其官方定价页核对，
  `_source`/`_fetched` 记来源与日期），共 39 个模型；键名以 `-` 结尾的是**前缀规则**，
  覆盖带日期戳的变体（`claude-sonnet-5-` 命中 `claude-sonnet-5-5-20260928`），精确名优先。
  部分模型还带 `peak` 子段（DeepSeek 峰谷价）——**只记录、未计价**，接入峰谷前不会用到。
- **怎么更新**：按厂商定价页核对后改 `models` 与 `_source`/`_fetched`；项目不做联网取价
  （检查与构建零出站），价格永远是人确认过的快照，而不是抓来的数字。
- 调用前的预估：`入 ~N token`（按 3.5 字符/token 估）+ `出 ≤max_tokens`，给出费用区间；
  预估永远在真正请求之前打印，`llm-ask` 与「源码 → 手稿（LLM）」都有。
- 上限：`llm_settings.json` 加 `"daily_cost_limit": 3.0`（0 或缺省 = 不设限）。今日累计
  达到上限后，结果里会多一行 `⚠ 今日 LLM 花费 … 已达上限 …`；它是提醒，不阻断调用。
- 想知道今天花了多少：`books/scripts/bookctl llm-ask ""` 的预估行末尾就带今日累计，
  或直接看 `books/logs/llm-usage.jsonl` 里 `at` 以今天开头的行。

## 6. 改完怎么验证

```bash
python books/src/python/make.py check    # 配置一致性、门禁全量
python books/src/python/make.py doctor   # 依赖与环境
```

## 7. 三个版本

- **工具版本**：`lib/_version.py`（或被 `base.json [sources].tool_version` 覆盖）。
- **源码版本**：`base.json [sources].version` 优先，否则读源码清单（pom/pyproject/Cargo）。
- **书籍版本**：`book.toml [book].version`；封面版本回写自它。管理文档与用户文档写的是**软件版本**（`lib/_version.py`），两者不混用。

`bookctl status` 会打印 `versions : tool … source … doc …`，合并稿首行写
`<!-- versions: … -->` manifest，`make.py check` 里的 `versions` 门禁负责校验。
