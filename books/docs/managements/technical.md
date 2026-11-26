# 技术设计

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.2-dev
> 定位：**系统怎么划分与约束**——分层、依赖矩阵、配置合并、关键决策、扩展点；
> 不写使用步骤（看 `docs/manuals/`），也不写写作规则（看 `../manuals/how-to-write.md`）。

本文件是工程的第二步：由需求文档推出**技术设计**——系统怎么划分、各部件承担什么、
彼此如何依赖、哪些约束不可违反。它自成体系：读完即可理解实现结构，不需要参考其他
文档。它不描述使用者的操作步骤，也不引用任何面向用户的文档。

编号约定：`C-xx` 架构约束，`D-xx` 关键设计决策。

## 1. 从需求到设计

需求只说要什么；每一条需求都要落到某个机制上，否则就是空话。主要映射如下：

| 需求 | 设计回应 |
| --- | --- |
| 12 章节槽 + 2 附录文件、固定章末结构 | 章节清单由配置给出（阅读顺序与内容覆盖两张表各司其职）；章末四段由 `audit/exercises.py`、`audit/structure.py` 判定 |
| 图号、图注、图簇桥接 | 编号与形态由脚本判定；措辞由人或模型改写，改完仍需过脚本 |
| 源码坐标可核对 | 手稿中的 `Class.method` 断言对到源码树，漂移进基线 |
| 三种输出格式 | `render/` 三条独立管线，各有自己的校验器 |
| 内容不得静默塌陷 | `audit/content_volume.py`：逐章体积与交付页数设下限 |
| 可复现 | 渲染全链路确定性；构建幂等由 CI 比对哈希 |
| 环境唯一 | 依赖全量 pin，入口拒绝非项目解释器 |
| 分档检查 | `check_runner.py` 的模式表：按改动域选步骤，提交/发布档跑全集 |
| 无过程痕迹 | `audit/traces.py` 扫描文档、注释、脚本、钩子与配置备注 |

## 2. 总体架构

### 2.1 系统边界与数据流

```text
   被分析的源码树 (可配置的外部输入)
            │  ingest
            ▼
   data/state/*.json  ──►  data/manuscript/*.md  ◄── 人工撰写
            │                      │
            │  audit/*（只读）      │  render/merge
            ▼                      ▼
   data/baselines/*       dist/<book>.md ──► .html
                                   ├──────► .pdf  (to_pdf → toc_links → verify)
                                   └──────► .epub (to_epub → verify → archive)
```

三条不变量决定了整张图：

1. **手稿是唯一可编辑的内容源**。状态、基线、产物都由它派生，改动只能发生在手稿。
2. **门禁只读**。任何门禁只读输入、只写自己的基线，绝不修改手稿或产物。
3. **产物可再生**。`dist/` 随时可以删除重建；不可再生的只有手稿与基线。

### 2.2 分层结构

| 层 | 职责 | 可写 | 可导入 |
| --- | --- | --- | --- |
| `lib/` | 配置读取、文件读写原语、日志、版本、LLM 客户端、基线存储、字体解析（`fonts`）、版式参数（`layout`）、封面与正文切分（`frontmatter`） | 由调用方决定 | 仅标准库 |
| `core/` | 领域动作：`actions`、可改配置 `settings`、菜单模型 `menu`、新书脚手架 `scaffold` | 经由 `actions` | `lib` |
| `ingest/` | 源码 → 手稿：扫描源码树、切分章节、语言适配 | `data/state`、手稿 | `lib` |
| `manuscript/` | 手稿维护：封面统计、术语、索引、案例、快照 | 手稿、`data/state`、`data/snapshots` | `lib` |
| `audit/` | 质量门禁：判定、统计、报告、复核包、快照校验（基线除外不写文件） | `data/baselines` | `lib` |
| `render/` | 交付渲染：合并、HTML、PDF、EPUB 及各自校验 | `dist/` | `lib` |
| `app/` | 渠道：`cli`、`tui`、`web`、`keys` | 不写 | `lib`、`core`、`app` |

### 2.3 依赖矩阵（唯一权威）

| 从 \ 到 | lib | core | ingest | manuscript | audit | render | app |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lib | – | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| core | ✓ | – | ✗ | ✗ | ✗ | ✗ | ✗ |
| ingest | ✓ | ✗ | – | ✗ | ✗ | ✗ | ✗ |
| manuscript | ✓ | ✗ | ✗ | – | ✗ | ✗ | ✗ |
| audit | ✓ | ✗ | ✗ | ✗ | – | ✗ | ✗ |
| render | ✓ | ✗ | ✗ | ✗ | ✗ | – | ✗ |
| app | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |

同层不互相导入；唯一的上行边是 `app → core`。矩阵的代码形态是
`audit/check_architecture.py::DEPENDENCY_MATRIX`，新增边必须先改矩阵再改代码。

```text
        app ──► core ──► lib
         │                ▲
         └────────────────┘
  ingest · manuscript · audit · render ──► lib   （四层平级，彼此不导入）
```

三条最容易踩的线，各由矩阵的一格守着：`render` 不得导入 `audit`（渲染不能顺便判质量）、
`audit` 不得导入 `render`（判定不能依赖产物实现）、`core` 不得导入 `app`（领域动作不认识渠道）。
依赖方向一变，替换与测试隔离就同时失效——这是把矩阵写成数据而不是写成注释的原因。

### 2.4 通用性：不绑定某一本书，也不绑定某一棵源码树

工具链交付的是**通用方案**，任何一本技术书、任何一棵被分析源码树都只是它的输入。两条硬约束：

| 约束 | 含义 | 机检 |
| --- | --- | --- |
| 不依赖具体书籍 | 书名、章节名、术语、案例、图注词表、提示词表一律只存在于 `data/book/`、`data/config/`、`data/language/`；代码里出现本书专有词即为违规 | `check_architecture.py` 的 `book_vocabulary` 检查：词表由书在 `base.json [toolchain]` 声明，命中即报 |
| 不依赖具体源码仓库 | 仓库路径、包前缀、语言与后缀只从 `[sources]` 读；新增一门语言＝一个适配器 + 注册表一行；坐标形状按 `sources.suffixes` 现建 | 路径字面量检查 + 依赖矩阵 + 坐标形状单一实现（`lib/_mdutil.source_ref_re`） |

判据的取向是「换一本就换配置」：书级内容缺失时按「未配置」处理并报告，不静默套用另一本书的东西；
让这两条失效的唯一方式是有人把书的内容写进代码，而那正是机检要拦的。

### 2.4 目录与数据布局

目录树、文件归属与清理规则只有一处：`folder.md`。本节只说明设计上依赖它的两个事实——
`data/` 下同名文件按书解析（`_config` 的路径层），`dist/` 与 `data/cache/` 可再生、
`data/manuscript/` 与 `data/baselines/` 不可再生。

### 2.5 两段式流水线

```text
  外部源码树 ──digest──► state/source-inventory.json
        │        └─outline──► state/outline.json ──chapters──► 手稿骨架
        └── audit/*（只读）   手稿 data/manuscript ◄── 人工撰写
                                       │
                     merge ─► dist/<book>.md ─► .html ─► .pdf / .epub
```

阶段 1 的产物只有「事实」（清单、大纲、骨架与事实块），阶段 2 的输入只有手稿与配置。
两段之间不共享内存状态，也不通过环境变量传递结果：重跑渲染不读源码树，重跑抽取不覆盖已写正文。

| 阶段 | 环节 | 输入 → 输出 |
| --- | --- | --- |
| 1 | `ingest/digest.py` | 源码树 → `data/state/source-inventory.json` |
| 1 | `ingest/outline.py` | 清单 + 章节映射 → `data/state/outline.json`（含覆盖矩阵与归属冲突） |
| 1 | `ingest/chapters.py` | 大纲 + 模板 → `data/manuscript/*.md` |
| 2 | `render/*` | 手稿 → 合并 Markdown / HTML / PDF / EPUB |
| 全程 | `audit/*` | 质量判定与事实核验（只读） |

阶段之间有硬边界：阶段 1 只产出结构与骨架，阶段 2 只消费手稿。因此重跑渲染不会
触碰源码，重跑抽取也不会覆盖已写好的正文。

### 2.6 章节与包：单主责

`book.toml [chapters.packages]` 中每个源码包只归属一个章节。非主责章节通过跨章
指向主责章节，不重复描述同一个包。归属冲突在大纲阶段就报出，不留到成书之后。

## 3. 配置设计

### 3.1 四层配置与合并规则

| 文件 | 管什么 | 谁读 |
| --- | --- | --- |
| `data/book/book.toml`（或书根的 `book.toml`，扁平布局） | 这本书的身份：标题、版本、路径、章节清单、包归属、必备段落 | `lib/_config.py` 直接解析 |
| `data/config/base.json` | 基础设施与**分析口径**：源码语言与后缀、包前缀、路径映射、基线路径、工具链预算、日志 | 合并进 `POLICY`；`[sources]` 与书级的同名键合并，书级优先 |
| `data/config/style.json` | 写作与形态规则：阈值、词表、图注规则、篇幅预算、语言骨架 | 合并进 `POLICY` |
| `data/language/zh.json` | 语言资源：章节骨架名、练习提示语、术语行 | `_config.language()` |
| `data/config/llm_pricing.json` | 各模型单价（每百万 token，provider 货币）；缺表即“未定价” | `_llm.pricing()` |

```text
  book.toml（身份/章节/包归属）─┐
  base.json（分析口径/预算）   ─┼─► Config(root) ─┬─► POLICY/thresholds ─► 各层脚本
  style.json（写作/形态规则）  ─┤                 └─► 路径解析
  language/<语种>.json（文案）  ─┘                      state/cache/tmp/dist/baselines
  同名键：base.json < style.json；书级 [sources] 覆盖 base.json
```

合并顺序固定：`base.json` → `style.json`，同名字典逐键覆盖；`toolchain` 段的预算
额外以 `thresholds` 别名暴露，供门禁统一读取。若两个 JSON 都不存在，退化为读取
`data/config/` 下的单文件 `config.json`（兼容形态，仓库不带）。解析失败一律抛
`ConfigError` 并指明文件，不允许静默降级。

配置按书解析成对象：`_config.Config(root)` 读的是那一本书自己的四个文件与
配置在**动作运行时**读取，不在导入期读取：模块级的 `X = _config.Y` 会把第一本书的值
钉死，破坏 `use(cfg)` 与安装形态。这条只对控制台入口的导入闭包强制——`app/`、`core/`
与它们传递依赖的模块不得有模块级配置读取，由
`test_audit_check_architecture.py::ImportTimeConfigReadTest` 判定；以子进程执行的脚本
模块不在闭包内，按需再逐个收敛（台账在 `review-findings.md`）。唯一例外是 `core/scaffold.py`：建书时必须先报
自己那份 `invalid base config`，早于 `_config` 可能抛出的 `ConfigError`。

`data/language/`，`root` 缺省取 `BOOK_ROOT` 或工具链所在 checkout。模块级名字
（`_config.BOOK_ROOT`、`_config.state_path(...)`、`_config.POLICY`）不再是一次算
死的常量，而是转发到当前活动书的属性与方法——`with _config.use(cfg):` 期间切换，
退出即还原，异常也不漏。同一进程要读多本书时用 `Config(root)` 或 `for_root(root)`，
不要改环境变量再重导入。

### 3.2 阈值归属

阈值只允许出现在配置里，代码里不得内联。已知归属：

- 内容体量与交付下限：`base.json [toolchain]` 的 `content_floor_ratio`、`pdf_page_ratio`、`epub_size_ratio`、`pdf_max_mb`、`epub_max_mb`、`ascii_max_cols`。
- 质量下限：`style.json [thresholds]`（练习题量、索引总数与每章条数、索引主/子/see-also 条数、术语条数、每章跨章引用数）。
- 写作规则：`style.json [content_depth]`（如 `glossary_min_uses`、`excerpt_lines`）、`[captions]`、`[style_rules]`、`[limits]`。
- 篇幅预算：`style.json [limits]` 的 `sources`/`tests`/`docs`/`manuscript` 四档；`file_length` 要求四档都显式声明，不靠默认值。
- 图表与图簇：`style.json [quality]` 的 `min_figures_per_section`、`min_figure_coverage_pct`，`[clusters]` 的 `min_figures`、`window_lines`——`smart.py`、`figure_clusters.py`、`structure.py` 共用这一处，不再各自内联。
- 页面几何：`base.json [toolchain]` 的 `pdf_page_width`、`pdf_page_height`、`pdf_page_tolerance`（`verify_pdf.py` 按此判定 A4）。
- 章节骨架与必备段落：只在 `book.toml [sections]`（`style.json` 不再接受 `sections`，重复声明会被 `style_schema` 判为未知键）。
- 书目目录：`--books-dir`／`BOOKS_DIR` > `book.toml [paths] library` > 书的父目录；
  `books_in()` 列出该目录下的书，`candidate_books()` 在其下找
  `data/book/book.toml`——「其他书放在哪」是配置事实，不是目录约定；
- 临时目录：`book.toml [paths] tmp`（缺省 `data/tmp/…`，读 `_config.tmp_dir()`），
  放一次性脚本与 `--force` 备份，随时可清空；
- 缓存目录：`book.toml [paths] cache`（缺省 `data/cache`，读 `_config.cache_dir()`），
  放字体索引与 HTML 分片缓存——可重建但有重建成本；不可写时退回临时目录。
  两者都 gitignore，并由 `_config.excluded_dirs()` 从门禁扫描中排除。
- 派生状态：`book.toml [paths] state`（缺省 `data/state`，读 `_config.state_dir()` /
  `state_path(name)`）；ingest 每次重建，不入库。
- 归档与报告：`base.json [archive]` 的 `dir`、`retention_days`（默认 45 天，读 `archive.settings()`）；
  `base.json [reports]` 的 `dir`、`retention_days`（默认 30 天，读 `test_report.settings()`）。
  两者都是“只进不出”的证据目录，已 gitignore。
- 覆盖率红线：`base.json [toolchain] coverage_fail_under`（**分支覆盖**口径：`coverage run --branch` 的总百分比）与 `coverage_min_per_file`（单文件行覆盖下限）。
- 步骤超时：`base.json [toolchain]` 的 `step_timeout_s`（普通步骤）与 `test_timeout_s`（测试与覆盖率步骤）；`make.py` 按步骤名取值，超时按 124 记为步骤失败。取值是“谨注定能跑完”的上限而非预算，故与实测耗时保留十数倍余量。

判据文档（`testplan.md`）只说“不低于配置下限”，不引用这里的键名：键名与取值属于本节，`doc_drift` 的 `THRESHOLD` 检查守着这条边界。

### 3.3 语言与模板

`data/language/zh.json` 提供章节骨架名与练习提示语，`_config.language()` 负责读取；
语种由 `BOOK_LANGUAGE` 环境变量或配置决定。模板（章节引言、深读要点）放在
`data/tmpl/templates.toml`，占位符由渲染层填充，模板本身不含判定逻辑。

## 4. 分项设计

### 4.1 `lib/` 基础层

| 模块 | 职责 | 关键约定 |
| --- | --- | --- |
| `_config` | 每本书一个 `Config`：TOML/JSON 三层配置、路径解析、章节清单、语言与模板读取 | `Config(root)` 解析一本书；模块属性转发到活动书（`use()` 切换）；`excluded_dirs()` 给出产物与快照目录 |
| `_fsutil` | 读写原语：`read_text`、`read_lines`、`write_text`、`load_json`、`ensure_dir`、`pin_stdout_utf8` | 统一 UTF-8；失败抛 `ToolError`（消息与退出码同源） |
| `_errors` | 失败的唯一载体：`ToolError`（派生 `SystemExit`，`str(exc)` 是消息、`exit_code` 是状态）与入口处的 `run()` | 内层只管抛，转换只在入口发生一次；`raise … from` 保留原始异常 |
| `_log` | 按天滚动的文件日志 + 控制台摘要 | 级别取 `BOOK_LOG_LEVEL` > 配置 > INFO |
| `_mdutil` | Markdown 结构解析：标题、围栏、图注 | 围栏内的内容不参与结构判定 |
| `core/docs_archive.py` | 把已发布版本的台账与完成的迭代设计移入 `docs/archive/` | 纯文本变换 + 目录搬迁；幂等，`--dry-run` 只打印动作 |
| `audit/doc_archive.py` | 归档布局门禁 | 版本目录名、三份台账与头行、索引可打开、已归档版本不得留在主文档 |
| `audit/plan_coverage.py` | 计划覆盖门禁 | 每个 `docs/plan/<主题>/` 恰好一个所有者；计划项四段齐备；编号与概述一致 |
| `manuscript/renumber.py` | 版本重编号与引用改写 | 由书级/版本 `[chapters.numbering]` 之差算映射，写 `state/<edition>/renumber.json` |
| `_version` | 工具链语义化版本（唯一定义处） | 与书籍版本（`book.toml`）、被分析源码版本三向分离 |
| `_llm` | LLM 客户端：provider 路由、密钥只读环境变量 | 只有 `app` 与 ingest 散文场景可导入 |
| `_baseline` | 已评审问题清单的读写与差集 | 键由调用方定义；新增即失败，消失即提示收缩 |
| `_source_state` | 被分析树的两次清单比对：新增/移除的包、包/文件/行增减、上次分析日期 | 路径由调用方传入，模块自己不绑定配置（否则换书后读到上一本的状态） |
| `_browser` | 渲染用的无头浏览器启动点 | core 上限归零、`TMPDIR` 指到书内临时目录；Playwright 不接受 `cwd`/`preexec_fn`，只能用这两条 |

`lib` 只依赖标准库，保证任何一层都能在最小环境下运行。

### 4.2 `ingest/` 输入层

把外部源码树变成可写作的手稿骨架与状态：

1. 读取源码位置（`base.json [sources] src_main` 等），扫描包与文件，落 `data/state/source-inventory.json`。
2. 按章节的包归属（`book.toml [chapters.packages]`）切分主题，落 `data/state/outline.json`。
3. 语言适配器（`ingest/languages/`）提供按语言解析符号的能力：现支持 java / python / rust /
   kotlin / go / c，新增一门语言＝加一个模块 + 注册表一行，`detect()` 的后缀映射从注册表推导。
   C 没有包声明，包按目录切（头文件与同名 `.c` 同包），只有引号形式 `#include` 成为包级依赖，
   头文件声明过的类型与原型才算 public。

该层只写 `data/state` 与手稿骨架，不参与质量判定：判定属于 `audit/`。

两条硬规则：**骨架可重建，正文不可重建**——`chapters.py` 对已有章节默认**只刷新事实块**
（标记块之外一字不动），无标记块时跳过并报出行数；只有显式 `--force` 才整篇重写（重写前先把旧文件
备份到 `data/tmp/`），`--refresh-facts` 是只刷块的显式形态。阶段开始时它先说一句源码清单是否
与上次一致（`digest.py` 保留 `source-inventory.prev.json`），结束时由 `core/actions.analyze`
调用 `audit/content_volume.py` 做一次基线比对，把"这次 ingest 有没有让稿子变薄"放进
同一次运行的结果里，而不是留给之后的门禁。

夹在这两条之间的第三种情形是**事实块**：包表、类型表、源码坐标与依赖方向随源码变化，
却不属于正文。渲染器把它们写在 `<!-- generated:<块名> -->` … `<!-- /generated -->` 之间，
`--refresh-facts` 只替换这些标记块，块外一字不动；文件里没有标记块时退化为“跳过并提示”。
`--force` 覆盖前把旧文件备份到 `data/tmp/generated-backup/<时间戳>/`，并先打印 `-a/+b`
行数，让“整篇重写”的代价在执行前可见。

标记只属于渲染器产出的骨架：人手写的章节不插标记，`--refresh-facts` 对其跳过并报数，
这是正确降级而非缺陷。手写章节的源码坐标多嵌在正文句子里（而非表格），本就不在块级
刷新的射程内，维护方式仍是随上游升级逐处改（由 `source_refs.py` 判定）。

`chapters.py` 只负责章节骨架；附录的坐标表与练习由 `ingest/appendix.py` 渲染，
表格排版共用 `lib/_mdutil.table()`。

### 4.3 `manuscript/` 手稿维护层

- `cover.py`：统计章节数、图数、行数并回写封面，是"统计数字唯一来源"。
- `glossary.py`、`index.py`、`terms.py`：术语表、索引与术语标注的生成与校验。
- `case_studies.py`：附录 A 的案例骨架，按 `data/book/case-studies.toml` 展开。
- `snapshot.py`：把历史稿导入只读快照（见第 7 节）。

生成器只产出骨架与派生内容，正文语义由人负责。三处细节决定了这一层能反复运行：

- **统计只有一个来源**：封面数字由 `cover.py` 从手稿算，任何文档不得自己再统计一遍——
  两处统计必然漂移，读者会先发现矛盾再发现正文。
- **生成物可识别**：生成器写的段落带 `<!-- generated:… -->` 标记；`--refresh-facts` 只替换
  标记块，人能分清「机器写的」与「我写的」。
- **快照只读**：`snapshot.py` 导入的稿子不被构建读取，也不进任何门禁的扫描面（`excluded_dirs()`），
  只用于比对与取基线。

### 4.4 `render/` 交付层

| 步骤 | 输入 → 输出 | 设计要点 |
| --- | --- | --- |
| `merge.py` | 手稿 → `dist/<book>.md` | 顺序来自 `book.toml`；前件、后件按 glob 展开；投递稿里把练习类型 emoji 与圈号换成文字（`【理解】`、`(1)`），手稿不动——这两类字形没有可嵌入字体覆盖，落到浏览器的末位兜底就会写成 Type3 描边 |
| `to_html.py` | 合并稿 → `dist/<book>.html` | 单一 HTML：侧边栏目录 + 印刷目录 + 锚点；正文按章缓存 |
| `html_shell.py` | `to_html.py` 的样式表 | CSS 单列一份；搬动它不得改动产物一个字节（以构建哈希为验收） |
| `to_pdf.py` | HTML → PDF | 无头浏览器渲染；随后用 pypdf 写入大纲 |
| `pdf_split.py` | HTML → PDF | 按 H1 逐章渲染再合并（每章 1:1，不受整页 fit-to-scale 影响）；marker 注入、大纲条目与 gs 压缩的唯一入口 |
| `pdf_metrics.py` | PDF | 版式测量：正文字号、行距、每页行数/字符数（ 80 页抽样，不做全本提取）、比对与标定 |
| `pdf_toc_links.py` | PDF | 按目录条目与大纲的**位置对应关系**补链接注释，不靠标题文本匹配；它是交付链的最后一个写入者，压缩在这里收尾 |
| `toc_pages.py` | HTML | 把印刷目录的页码写回 `#toc-page-nav`：按锚点精确替换，写盘前自检 `#content` 不变、标签成对，不满足即放弃 |
| `print_pdf.py` | HTML → 印刷版 PDF | 与标准版同一分章渲染器与同一页框，只额外注入 `print_profile`（章首横幅、点线目录）；渲染后用暂存 HTML 写回目录链接目标（分章拼接会让跨部分锚点只剩无目标矩形），无 playwright 时降级为警告；不带自己的边距/缩放 |
| `print_profile.py` | 印刷版专属样式 | 全部长度用 `em`、颜色取书目的主色；只影响 `@media print`，不改磁盘上供屏幕阅读的那份 HTML |
| `pdf_from_html.py` | 现成 HTML → PDF | 不重建 HTML 的旁路；独立工具，不进 `deliver` 组 |
| `verify_pdf.py` | PDF + HTML | 校验页数、A4、旋转、字体嵌入、体积、大纲与标题一一对应、目录链接落点、以及 `COLUMN`（每行 em 数在阅读区间内、栏宽 ≤ 可印宽度） |
| `to_epub.py` | 合并稿 → EPUB | pandoc 生成，元数据经 `--metadata-file` 传入 |
| `archive.py` | 手稿 + `dist/` → `data/archive/<书>/<日期>/` | 只进不出、不入构建；保留窗口取 `base.json [archive] retention_days`（默认 45 天） |
| `verify_epub.py` | EPUB | 校验 mimetype 首条未压缩、容器与 OPF 可解析、清单与阅读顺序、导航可达、体积 |

#### 4.4.1 PDF 交付链：谁写、谁压、谁判

```text
  dist/<book>.html
        │ to_pdf：pdf_split 按 H1 切章 → 逐章 1:1 渲染 → 合并 → 写大纲（不压缩）
        ▼
  dist/<book>.pdf ──toc_pages──► HTML 印刷目录补页码（自检不过则放弃）
        │ pdf_toc_links：按 outline 位置补链接注释（一次全量重写）
        ▼
  dist/<book>.pdf ──gs 压缩一次──► verify_pdf（只读）
  印刷版：print_profile 注入 + 同一分章渲染 + 结尾同样一次压缩
```

压缩只由**最后一个写入者**做：pypdf 的每次重写都会让已有压缩失效，提前压缩不产生收益。
gs 的临时文件是同目录的隐藏名（`.＜pdf＞.gs.tmp`），中断不会在 `dist/` 留下半截 PDF。

#### 4.4.2 版式：一组推导出来的数

```text
  阅读度量 40em ──× 正文字号 16px──► 栏宽 640px
                                         │
   纸张宽 210mm（A4） ──────────────────┘
        ▼
  左右边距 = max(下限 16mm, (纸宽 − 栏宽)/2) = 20.3mm ──► 可印宽度 = 栏宽
  COLUMN 判据：每行 em 在区间内、栏宽 ≤ 可印宽度（放不下则裁到可印宽度并报错）
  代码：ascii_max_cols × 等宽步距 × 字号 ≤ 可印宽度 → 印刷代码字号
        低于可读下限则改换行（layout_print_wrap）
```

没有一个是手填的：改字号、改字数、换纸张都只改一个入参，其余跟着走。`em` 是字体自己的单位，
所以同一组数字在另一套字体、另一个系统上仍然表示「每行这么多字」。

渲染链的确定性由两点保证：输入只有手稿与配置；渲染器不引入随机与时间戳。

```text
  合并稿 ──按 H1 切片──► 每章一片 ──哈希(内容 + 渲染器)──► data/cache/html-cache/
                                                  命中：直接拼接（字节不变）
                                                  未命中：渲染后写回
  --full 忽略缓存；缓存被删或损坏只影响速度
```

正文渲染按 H1 章节切片缓存（`render/html_cache.py`）：目录、锚点与章编号在切片前已定稿，
一片只依赖自己的 markdown 与渲染器源码，所以复用旧片不会改一个字节（缓存键就是内容哈希，
`--full` 可强制全量）。缓存落在 `data/cache/html-cache/`（已 gitignore），被删或损坏只是
重新渲染，不会影响产物。合并步不缓存——它只是纯拼接。

### 4.5 `audit/` 门禁层

门禁按"判什么"分组，全部只读；每条的判据与级别由编排层统一登记。

| 组 | 门禁 | 判据要点 |
| --- | --- | --- |
| 结构 | `structure.py` | 章节齐全、标题层级连续、图号唯一、围栏配对、合并稿行数一致、TOC 与标题一一对应 |
| 体量 | `content_volume.py`、`balance.py` | 逐章字节/行数下限、手稿总量、交付页数与体积下限；章间体量分布 |
| 引用 | `links.py`、`crossrefs.py`、`figures.py`、`index_xrefs.py` | 相对链接与锚点可解析、章间互引真实存在、图号引用可解析、索引条目指向真实章节 |
| 事实 | `source_refs.py`、`content_depth.py` | 源码坐标可解析（扫描面含章节与附录）、代码摘录与源码一致、前向引用需点名主责章节 |
| 形态 | `captions.py`、`figure_clusters.py`、`diagrams.py`、`style_rules.py`、`style.py`、`exercises.py`、`smart.py`、`readability.py`、`style_schema.py` | 图注结构、图簇桥接、ASCII 图宽度与行尾、术语与排版规则、章末练习结构、图表覆盖密度、可读性、配置结构 |
| 工程 | `check_architecture.py`、`script_contract.py`、`file_length.py`、`traces.py`、`doc_drift.py`、`version_consistency.py`、`llm_policy.py`、`portability.py`、`typecheck.py`、`test_redundancy.py`、`perf_baseline.py`、`gate_trace.py`、`order_dependence.py` | 依赖方向、入口契约、文件长度预算、过程痕迹、文档与仓库一致、三版本一致、LLM 边界、跨平台、类型、测试质量、性能基线、门禁登记、顺序依赖（慢档） |
| 复核 | `review_packet.py`、`scorecard.py`、`prose_quality.py`、`failure_extract.py` | 只输出失败集合与上下文；六维评分与文风度量作为整改视图；失败日志收敛 |

`audit/style.py` 保持单文件：13 个检测器共用一份 `chapter_stats` 与 `warn()`；拆开要把状态对象
穿透每个调用点，风险大于收益。

图注与图号的形状只定义一次：`lib/_mdutil.py` 的 `FIGURE_*` 形状与
`figure_caption()` 助手，六个 audit 模块只引用不重写；章节范围由
`book.toml [chapters.coverage]` 推导。

**基线机制**：可枚举的存量问题允许登记（`data/baselines/*.json`），登记项不判失败，
但同类别的新问题必须失败；登记项消失时报告 `stale`，提示收缩。基线键按内容而非
行号生成，插入小节不会把旧账重算成新账。

```text
  输入（只读）                     判定                       输出
  手稿 / state/*.json ──┐
  源码树（核坐标时）  ──┼─► 门禁（纯函数）─┬─► 退出码 0/1 ─► 编排层
  baselines/*.json   ──┘                 └─► 报告（人读 + --json）
                                          └─► 基线差集：存量 pass、新增 fail
```

三个约定让门禁可以独立运行、也可以被编排：

- **纯函数形状**：读文件、算、返回退出码；除自身基线外不写任何东西（`check_architecture`
  扫描写操作调用守着这条）。
- **失败可定位**：输出必须给出文件与行号，或给出可执行待办；`--json` 给机器消费。
- **基线只记「已评审存量」**：键按内容生成，插入小节不会把旧账重算成新账；新问题一律失败。

**判定与生成分离**：门禁不做语义判断；语义判断交给人与模型，模型产出的修改必须再过
门禁。`audit/llm_policy.py` 用导入关系在结构上锁定这条边界。

### 4.6 编排层

`make.py` 是唯一入口，持有步骤表：

```text
STEPS  = [(名称, 脚本, 额外参数, 分组)]       # 分组 ∈ build | verify | deliver
GROUPS = {build, verify, deliver, check, test, cover, report}
```

- `check` = `verify` 全集；`build` 只产物化（`cover` → `merge` → `to_html` → `archive`）；
  `deliver` 顺序固定：渲染 → 补链接 → 校验 → EPUB → 校验 → `archive_release`。
  两个归档步骤共用 `manuscript/archive.py`，把当天的手稿与产物存进 `data/archive/<书>/<日期>/`。
- 命令行支持 `--only`、`--skip`、`--keep-going`、`--timings`；失败时打印该步骤输出的末 30 行。
- 入口先校验解释器：不是项目虚拟环境即拒绝执行（`BOOK_ALLOW_SYSTEM_PYTHON=1` 可临时放行，交付流程不使用）。

`check_runner.py` 负责"什么时候跑什么"：

lint 的规则集只在书的 `pyproject.toml` 声明（`line-length`、`select`、`external`），编排器显式传
`--config`：ruff 默认从工作目录找配置，而编排器在仓库根执行，不传就会静默回退到 ruff 的默认规则，
让判据随安装的版本漂。

| 模式 | 场景 | 步骤 |
| --- | --- | --- |
| `docs` | 只改文档/手稿/配置 | 改动文件 lint + 受影响门禁 |
| `code` | 只改工具链源码 | 改动文件 lint + 受影响门禁 + 同名测试 |
| `tests` | 只改测试 | 测试 lint + 改动测试 |
| `quick` | 混合改动 | 上述并集 + 快档结构门禁；单步上限 300 秒 |
| `p0` | 提交前 | lint + 快档门禁 + 全量快档测试 |
| `p1` | 合并前 | lint + 全部门禁 + 测试 |
| `p2` | 发布 | p1 + 慢档 + 顺序依赖 + 交付 |

```text
  改动文件 ──path_scopes──► 域（docs/code/tests）──► 门禁 + 同名测试
                              │
                   --mode ────┴──► 步骤序列（p0 快档 / p1 全集 / p2 + 慢档）
  分档只改「跑多少」，不改「怎么算过」
```

领域与门禁的映射塌在一张表里：`path_scopes()` 给出「路径片段 → 域 → 门禁」，分类器与
门禁选择从同一份数据派生（两张表会在目录搬迁时失配），路径片段由配置推导，不用字面量。
`p0` 及以上的档位始终跑全集，分档只节省本地的等待时间，不改变通过标准。

### 4.7 渠道层

三个渠道共用 `core/actions.py`（动作执行）、`core/menu.py`（菜单模型与回报）、
`core/settings.py`（可改配置与校验）。参数也只在一处定义：会改写手稿的 `analyze` 类动作
接受 `refresh` / `force`，CLI 用 `--refresh-facts` / `--force`，TUI 用配置屏的
「刷新事实块」项，Web 用 `{"action":"analyze","refresh":true}`，三者都落到
`actions.run()` 的同一分支。终端交互的细节契约（键位、反馈、确认、光标）
是本章的子设计，单独成文以便频繁修订。渠道内禁止：导入下层业务层、驱动编排层、
出现子进程或写文件调用、持有业务规则。由此 CLI、TUI、Web 的状态与结果天然一致。

## 5. 架构约束

每条约束给出动机与强制方式；"强制"一栏写的是会让违规变红的机制。

| 编号 | 约束 | 动机 | 强制方式 |
| --- | --- | --- | --- |
| C-01 | 依赖只能沿矩阵方向；同层不互相导入 | 分层的唯一价值是替换与测试隔离 | `check_architecture` 的矩阵检查 |
| C-02 | 门禁只读，仅可写自身基线 | 判定与修改混在一起时，事故无法定位 | `check_architecture` 的写操作检查 |
| C-03 | 程序不得内联仓库路径与阈值 | 路径与策略是可配置项，写死即失去可移植性 | `check_architecture` 的字面量检查 + 配置读取审计 |
| C-04 | 每个 CLI 入口必须是编排步骤或显式声明为独立工具 | 脚本写了没人调用等于没写 | `check_architecture::check_wiring` |
| C-05 | 编排分组必须引用真实步骤，且校验排在生产者之后 | 顺序错则门禁验证的是旧产物 | `test_toolchain_contract` 的顺序契约 |
| C-06 | 只有项目虚拟环境可执行交付 | 依赖漂移会让同一命令在不同机器上产生不同结果 | `make.enforce_venv`（入口拒绝） |
| C-07 | 依据预算限制源文件与文档长度 | 单文件过长即失去可审阅性 | `file_length` |
| C-08 | 模块名不得遮蔽标准库；入口不得以下划线开头 | 导入解析与调用可预期 | `check_architecture` 的命名检查 |
| C-09 | 报告类脚本支持 `--json`，退出码语义固定 | 机器消费与人工阅读都需要稳定契约 | `script_contract`、`check_architecture` |
| C-10 | 文档、注释、脚本、钩子、配置备注不得叙述项目过程 | 过程记录会陈旧并与事实冲突 | `traces`（docs/code 两个范围） |
| C-11 | 文档引用的路径、脚本、版本必须与仓库一致 | 文档漂移比缺文档更有害 | `doc_drift`、`version_consistency` |
| C-12 | 编排层每个步骤都要在质量清单登记，反向亦然 | 未登记的门禁等于不存在 | `gate_trace` |

## 6. 关键设计决策

| 编号 | 决策 | 取舍 |
| --- | --- | --- |
| D-01 | 判定用脚本，生成用模型 | 脚本可复现、零成本；模型只做语义与措辞。门禁层禁止导入 LLM 客户端 |
| D-02 | 基线而非静音 | 静音会让问题永久消失；基线让存量可见、新增必红、修复可收缩 |
| D-03 | 单一入口 + 步骤表 | 20 多个脚本的调用顺序不该靠记忆；步骤表让顺序与分组成为数据 |
| D-04 | 手稿是唯一可编辑源，产物可再生 | 产物入版本库只会制造冲突；所有派生物都能重建 |
| D-05 | 历史稿以只读快照存在 | 比对需求真实存在，但历史稿不该进入构建或被门禁扫描 |
| D-06 | 分档只优化等待，不改变标准 | 提交与发布始终全集，本地分档不得成为漏检通道 |
| D-07 | 版式由一个阅读度量（每行 `em`）推导，屏幕与纸面同一规则 | 手填栏宽会让「屏幕宽、纸面溢出」同时成立；`em` 与字体、系统无关，换书只换一个入参 |
| D-08 | 印刷版与标准版共用同一渲染器，差异只在 `print_profile` | 两套渲染路径会长出两套页框；差异收进一个只作用于 `@media print` 的样式模块，印刷版不再自带边距与缩放 |
| D-09 | 压缩只由最后一个写入者做一次 | 每次重写 PDF 都会让已有压缩失效；顺序写进 `deliver` 步骤表，压缩挂在链尾 |
| D-10 | 耗时判据读评审基线，读数进滚动窗口 | 只增不减的日志既读不动也会被清理移动判据；基线要有人署名，窗口只做样本 |

## 7. 状态与持久化

| 位置 | 内容 | 生命周期 |
| --- | --- | --- |
| `data/state/source-inventory.json` | 被分析源码的快照事实（文件、包、规模） | 每次 ingest 重建 |
| `data/state/outline.json` | 章节与主题的派生大纲 | 每次 ingest 重建 |
| `data/baselines/*.json` | 已评审问题清单：`accepted` 数组、生成方式、备注 | 只在评审后重设，收缩优先 |
| `data/baselines/content-volume.json` | 逐章字节/行数、手稿总量、交付页数与体积；`reviewed` 记评审人 / 提交 / 时间 / 理由，`source.snapshot` 记它取自哪份历史快照，`accepted_shrinks` 记每次经批准的收缩 | 定稿评审后重设；要求稿子已提交、有人具名、不降低下限 |
| `data/baselines/snapshot-<标签>.json` | 某个历史快照的体积事实 | 导入快照时生成 |
| `data/snapshots/<日期>-<标签>/` | `manifest.json`（压缩包哈希、逐文件字节/行数/哈希）+ 只读正文 | 只读；`snapshot.py verify` 校验 |
| `logs/check-<档位>-<YYYY-MM-DD>.{log,jsonl}` | 当天的运行日记（每次追加一段带表头的输出）与同名摘要行（`git{commit,dirty}`、每步 `argv`、pytest 计数、`log_offset/log_len`） | 按 `logging.retention_days` 整日清理 |
| `data/baselines/perf-baseline.json` | 评审过的耗时下限：逐步与总计中位数 + `reviewed{by,at,commit,reason,runs}`；`logs/perf-history.jsonl` 只做滚动窗口（`style.json [quality].perf_history_runs`，默认 200） | `perf_baseline.py --update-baseline` 固化 |

```text
  可随时重建 ──► data/state/*、data/cache/*、dist/*、logs/*、test-reports/*
  需评审重设 ──► data/baselines/*（reviewed{by,at,commit}）
  不可再生 ───► data/manuscript/*、data/snapshots/*（只读）、book.toml
```

这条分界的用处只有一个：删 `dist/` 与 `data/cache/` 永远是安全的；动 `data/baselines/` 必须有人署名。

体积基线的严格度由 `base.json [toolchain] content_profile` 决定：`baseline` 严格、
`rewrite` 严格但允许评审后重设、`cold-start` 仅提示（尚无存量可保护）。

## 8. 扩展点

| 目标 | 做法 |
| --- | --- |
| 新增门禁 | 在 `audit/` 写脚本（docstring、`main(argv)`、`--json`）→ 进 `STEPS` 的 `verify` 组 → 在质量清单登记一行 |
| 新增章节 | 写手稿文件 → 加入 `book.toml [chapters] files` → 补包归属 → 章末四段齐全 |
| 新增输出格式 | 在 `render/` 写生成器 + 独立校验器 → 进 `deliver` 组，校验排在生成之后 |
| 新增语言 | 提供 `ingest/languages/<语言>.py` 适配器与 `data/language/<语种>.json` 资源 |
| 新建一本同类书 | `core/scaffold.py` 生成目录骨架与配置，再把内容写进 `data/manuscript/` |
| 接收历史稿 | `manuscript/snapshot.py import` 导入只读快照（源可以是 zip，也可以是 `data/archive/` 下的日期目录，无需重新打包），再生成其体积基线 |

## 9. 失败模式与诊断

| 现象 | 设计上的定位路径 |
| --- | --- |
| 门禁失败 | 输出给出文件与行号，或给出可执行待办；完整输出落 `logs/` |
| 交付失败 | 编排层打印失败步骤的输出末 30 行；报告文件包含每步退出码与耗时 |
| 任何工具层失败 | 一律抛 `lib/_errors.ToolError`（消息 + 退出码），由入口的 `_errors.run()` 打印并返回；判据是「仓库内不再有『先打印再 `sys.exit(1)`』的失败路径」 |
| 版本不一致 | `version_consistency` 列出工具、源码、文档三处版本与不一致项 |
| 依赖漂移 | `make.py doctor` 报告解释器、pin 漂移与可选工具可用性 |
| 测试顺序依赖 | `order_dependence.py` 以正序/逆序两轮比对，`--bisect` 收缩到最小污染前缀 |
| 内容疑似缩水 | `content_volume` 直接指出文件与下限差额，并提示是否需要重设基线 |

## 9.x 分支与版本

- `dev`：开发分支，日常提交在此；工具版本为 `X.Y-dev`。
- `master`：只接收发布合并——`dev` → `master`，版本去掉 `-dev`，打标签；发布流程的机械步骤见
  `core/docs_archive.py`（迁出台账与已完成的迭代设计）。
- 版本唯一定义处是 `lib/_version.py` 的 `TOOL_VERSION`；`versions()` 的另外两项（被分析源码、
  书籍）分别来自 `book.toml [sources]` 与 `[book]`。

## 10. 非目标

- 不做通用静态站点生成器：渲染只服务本书的结构与排版。
- 不追求门禁的语义智能：无法枚举的判断留给人和模型，不写进门禁。
- 不提供多书合一的构建：快照只用于比对，不参与合并。
- 不替代版本控制：基线只记录"已评审的问题"，不记录历史正文。
