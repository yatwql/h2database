# 配置指南

> 维度：**配置——改哪个文件、改了生效在哪里、改错会怎样**
> 软件：bookwright — 源码分析成书工具 v0.1

所有可调项都来自 `books/data/`，程序只通过配置文件取值，改配置不需要改代码。
三个主文件各有分工：`book.toml` 决定这本书**是什么、怎么组织**，`base.json` 决定
**跑在哪、依据什么**，`style.json` 决定**怎么写、写成什么样**。改完跑一次 `make.py check` 验证。

| 层 | 文件 | 管什么 |
| ---- | ------ | -------- |
| 数据组织 | `data/book/book.toml` | 书名、版本、路径、章节清单、章节标题、H1 编号、覆盖归属、章节→包映射 |
| 基础配置 | `data/config/base.json` | 源码树、语言、文件后缀、包前缀、状态与基线路径、工具链预算、日志 |
| 风格配置 | `data/config/style.json` | 展示文案、章节骨架、图注词表、写作与质量阈值、生成能力与模板 |
| 语言包 | `data/language/<code>.json` | 章节骨架名、练习提示语、术语提示行 |
| LLM | `data/config/llm_provider.json`、`llm_settings.json`、`llm_pricing.json` | provider、路由、生成参数与单价 |

## 1. 数据组织（book.toml）

```toml
[book]
defaults = false                    # true：缺的键取包内默认值（新书可只写差异）
title = "某系统源码剖析"
version = "1.0"
merged_name = "code-analysis"      # 产物文件名前缀

[paths]
manuscript = "data/manuscript"     # 手稿目录
dist = "dist"                      # 产物目录
docs = "docs"
tmp = "data/tmp"                   # 临时目录：一次性脚本、--force 备份（随时可清空）
cache = "data/cache"               # 缓存：字体索引、HTML 分片（可重建但有成本）
state = "data/state"               # 派生状态：ingest 每次重建（已 gitignore）
templates = "data/tmpl"            # 叙述模板（templates.toml）
book = "data/book"                 # 本书专属文件（book.toml / case-studies.toml / glossary.toml / editing.toml）
library = ".."                     # 其他书所在的目录（缺省＝本书的父目录）
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

`[sources]` 声明**这本书读哪棵树**（属于书的身份，不是工具链策略）：

```toml
[sources]
src_main = "../h2/src/main"        # 单根；路径相对书根，可以指向书外
pom_root = "../h2/pom.xml"         # 可选：清单文件位置
version = "2.5.259-SNAPSHOT"       # 可选：逐一解析不到时用
# roots = [{ label = "h2", path = "../h2/src/main" }]   # 多根时用这个，label 必填且唯一
repo = "https://github.com/owner/project"   # 可选：源码在 git 仓库里时，克隆到 data/srcref/
ref = "main"                               # 可选：分支/标签/提交
```

`repo` 声明后，`core/fetch_source.py` 把仓库克隆到 `books/data/srcref/<owner>__<name>/`
（目录不入库），分析读那份副本；还未克隆时 `source_tree()` 直接报错并给出要执行的命令。
`--update` 会 fetch + checkout 到 `ref`，已存在的目录不会被覆盖。

分析口径（`languages`、`suffixes`、`package_prefix`）仍在 `data/config/base.json [sources]`，
书级同名键覆盖它。

`[editions]` 声明手稿版本（不声明即单版本，目录与产物名都不变）：

```toml
default_edition = "main"           # 多于一个版本时必填
[editions]
main = "主版本"
[editions.abridged]                # 版本也可以是表：display / merged_name / chapters 覆盖
display = "删节版"
```

书身份文件两种布局等价：`<书根>/data/book/book.toml` 与 `<书根>/book.toml`；判定只看能否
读到 `book.toml`，`[paths]` 一律相对**书根**解析。

要点：`numbering` 必须唯一（决定 H1 顺序），`coverage` 允许重复（用于均衡度量），
`packages` 必须唯一（否则 `gate_trace`/`check_architecture` 会报）。

## 2. 基础配置（base.json）

```json
{
  "sources": {
    "src_main": "../h2/src/main",     // 源码树根
    "pom_root": "../h2/pom.xml",      // 版本来源（可缺省）
    "languages": ["java"],            // 支持 java / python / rust / kotlin / go / c，可多选
    "file_suffix": ".java",
    "package_prefix": "<包前缀>"
  },
  "baselines": {"ascii": "data/baselines/ascii-baseline.json"},
  "toolchain": {"coverage_fail_under": 90, "pdf_max_mb": 12, "epub_max_mb": 10},
  "logging": {"level": "INFO", "dir": "logs", "retention_days": 14}
}
```

### 版式与字体（`toolchain.layout_*`、`font_stack_*`）

密度只在一处配置，PDF、HTML、EPUB 共用同一套解析：

| 键 | 作用 |
| --- | --- |
| `layout_chars_per_line` | 每行容纳的 `em` 数（阅读度量，默认 40）；栏宽由它 × 正文字号得出 |
| `layout_chars_per_line_min` / `_max` | 阅读区间（默认 36–46）；栏宽或度量落在区间外，`verify_pdf` 的 `COLUMN` 项判失败 |
| `layout_column_px` | 栏宽覆盖；写 `0`（默认）表示由度量推导，屏幕与纸面同一规则 |
| `layout_body_px` | 正文字号；写 `0` 表示「按栏宽 ÷ 度量推导」 |
| `layout_page_size` / `layout_page_margin` | 纸面尺寸与页边距：竖边距用于 `@page`，左右边距由栏宽反推 |
| `layout_print_margin_min_mm` | 纸面最小左右边距（默认 16mm）；栏宽放不下时裁到它，不侵占页边 |
| `layout_print_code_min_px` / `layout_print_mono_advance` | 代码可读下限与等宽字符步距（按 `ascii_max_cols` 反推印刷代码字号） |
| `layout_print_wrap` | 超长代码行换行（默认 `0` 关）；开启后用换行而非继续缩字号 |
| `layout_code_px` / `layout_code_line_height` | 代码块字号与行距；行距写 `0` 表示「与正文一致」 |
| `layout_prose_line_height` | 正文行距系数（默认 1.6）；`DENSITY` 判的就是它：正文行距÷字号须在 1.15–1.75 |
| `layout_lead_ratio` | 代码清单行距增量（`1 + ratio`，默认 0.23）；`CODE_LEAD` 只要求 ≥ 1.0 |
| `layout_print_chars_per_line` | 纸面阅读度量（默认 22），单位是**正文每行字符数**（中文算 1 个，实测约 18–19）；自适应印刷据此解算纸面正文字号；合理区间 10–40，越界时保留默认 22 并记为配置问题 |
| `layout_print_adaptive` | 印刷版默认开启自适应（默认关，也可用 `print_pdf.py --adaptive` 临时开）：按 `layout_print_chars_per_line` 解算纸面字号 |
| `layout_print_lead_target` / `layout_print_code_lead_target` | 纸面正文与代码清单的行距增量（`1 + target`）；正文默认 0.4，代码默认跟随正文。两者分开是因为清单占页面大部分，`DENSITY` 与 `CODE_LEAD` 分别判它们 |
| `layout_epub_code_em` / `layout_epub_line_height` | 重排版面的相对字号与行高（`em`，读者可缩放） |
| `layout_spacing_scale` + `layout_*_gap_em` | 段距/标题距/表距等，全部相对行高，由一个倍数统一缩放 |
| `font_stack_sans` / `font_stack_mono` | 候选字体族（逗号分隔或数组）；按本机可用性排序，缺字体时逐级回退 |

`pdf_split_by_chapter`、`pdf_bytes_per_page`、`pdf_type3_max`、`pdf_leading_ratio_min/max`
控制 PDF 侧判据：按章分页渲染、体积预算随页数增长、Type3 字体上限、行距松紧区间。

多语言时 `languages` 写多个，inventory 的包键会加语言前缀（`java:<包前缀>`、`python:<包前缀>`）。
`toolchain` 段里另有页面几何（`pdf_page_width`/`pdf_page_height`/`pdf_page_tolerance`），
`verify_pdf.py` 按它判定 A4；换纸张尺寸改这里，不改代码。

## 3. 风格配置（style.json）

```json
{
  "captions": {"leading_verbs": ["展示", "对比"], "vague_trailing": ["过程"],
               "presets": {"strict": {"min_chars": 8, "max_chars": 30, "fail_at": 0}}},
  "quality": {"min_coords_per_chapter": 15, "min_chapter_lines": 150, "max_table_rows": 20},
  "prose": {"avg_sentence_good": 28, "min_composite": 80},
  "generation": {"max_packages_per_table": 12, "exercises_per_chapter": 4},
  "limits": {"sources": {"limit": 900, "warn": 700}}
}
```

base.json 的 `[toolchain]` 段另有两类键：`balance_max_min_ratio`（正文各章节文件篇幅比上限，
`audit/balance.py` 超限即失败）与 `book_vocabulary`（本书专有词表，工具链代码里出现即失败，
`audit/check_architecture.py`）；`layout_*` 一族见上一节。

阈值只在这里改；`min_composite`、`max_duplicate_ratio` 等是棘轮，收紧前先清账。

### style.json 键一览

键名即参考；每个键的语义只有这一处说明，管理文档只写"归属哪个文件"。

| 段 | 键 | 作用 |
| ---- | ---- | ------ |
| `captions` | `leading_verbs`、`vague_trailing`、`presets` | 图注动宾词表、含糊尾词、三档预设（`strict`/`normal`/`loose`，各含 `min_chars` < `max_chars`、`fail_at`） |
| `clusters` | `min_figures`、`window_lines` | 图簇的张数下限与判定行距（`figure_clusters.py` 与 `structure.py` 共用） |
| `quality` | `max_duplicate_ratio`、`max_avg_sentence`、`max_long_lines`、`min_coords_per_chapter`、`min_chapter_lines`、`max_chapter_lines`、`max_table_rows`、`min_terms_per_chapter`、`min_exercises_per_chapter`、`min_figures_per_section`、`min_figure_coverage_pct`、`perf_history_runs` | 质量门禁阈值；最后一项是耗时读数保留的窗口次数 |
| `generation` | `max_packages_per_table`、`max_classes_per_package`、`max_api_rows`、`exercises_per_chapter`、`checklist_items` | 生成器的容量上限（文案见 `templates.toml`） |
| `thresholds` | `exercises_min_total`、`index_total_min`、`index_per_chapter_min`、`index_main_min`、`index_sub_min`、`index_see_also_min`、`chapters_min_cross_refs`、`glossary_min_entries`、`exercises_min_per_chapter`、`ledger_growth` | 内容完整性下限；`index_*` 是索引各层条目数下限（`manuscript/index.py` 与 `structure.py` 读同一组键），`chapters_min_cross_refs` 是每章「详见第X章《…》」引用数下限（`audit/crossrefs.py`），`ledger_growth` 是文件长度台账允许增长的行数 |
| `prose` | `avg_sentence_good`/`avg_sentence_bad`、`long_ratio_good`/`long_ratio_bad`、`paragraph_good_min`/`paragraph_good_max`、`bullet_good`/`bullet_bad`、`coords_good`/`coords_bad`、`h3_good`/`h3_bad`、`dup_good`/`dup_bad`、`table_good`/`table_bad`、`min_composite`、`forbid_phrases`、`tone`、`audience`、`sections` | 文风评分的好/坏锚点（`good` 应不劣于 `bad`）、禁用语、语气与读者定位、分节覆盖（`sections.body`/`caption`/`exercise`） |
| `style_rules` | `terminology`、`banned_link_text`、`heading`、`cjk_latin_spacing`、`list_punctuation`、`max_paragraph_chars` | 术语一致性、链接文字、标题尾标点、中英间距、列表标点、段落长度（`style_rules.py`） |
| `content_depth` | `glossary_min_uses`、`glossary_ignore`、`excerpt_lines` | 术语覆盖下限与白名单、代码摘录比对行数（`content_depth.py`） |
| `limits` | `sources`、`tests`、`docs`、`manuscript` 各自的 `limit`/`warn` | 文件长度预算（四档都要显式声明） |
| `_schema` / `_note` | — | 结构版本与说明；`_schema` 由 `style_schema.py` 校验，未知键即失败 |

改完运行 `python books/src/python/make.py check`：`style_schema.py` 会先校验结构
（未知键、缺字段、区间不合理都会失败），再由各门禁按新阈值执行。

### 风格相关文件的归属（文档是文档，配置是配置）

| 关注点 | 文件 | 属于 |
| -------- | ------ | ------ |
| 判定规则与阈值（图注词表、质量/文风阈值、篇幅预算、必备段落名） | `data/config/style.json` | 配置 |
| 文体文案（四段引言、深读要点等叙述模板） | `data/tmpl/templates.toml` | 文档 |
| 名称与提示语（章节骨架名、练习提示/回顾前缀、术语行） | `data/language/zh.json` | 文档 |
| 术语中英别名与「不算术语」词表 | `data/book/glossary.toml`（按书可选） | 文档 |
| 案例流水线、附录标题/开篇、思考题 | `data/book/case-studies.toml`（按书可选，`[headers.<scenario>]` 可只给部分键） | 文档 |
| 编辑风格档（哪些要素必选、下限多少） | `data/book/editing.toml`（按书可选；`[profile].name` 三选一：`manual`/`tutorial`/`hands-on`，`[elements.<名>]` 逐项覆盖） | 文档 |
| 书籍身份与展示文案（书名、作者、页眉、产物名） | `data/book/book.toml [book]/[project]` | 文档 |

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
