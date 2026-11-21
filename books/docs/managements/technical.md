# 技术设计

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1
> 定位：**系统怎么划分与约束**——分层、依赖矩阵、配置合并、关键决策、扩展点；
> 不写使用步骤（看 `docs/manuals/`），也不写写作规则（看 `style-guide.md`）。

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
   data/state/*.json   ──►   data/manuscript/*.md   ◄── 人工撰写
            │                       │
            │                       │  render/merge
            │                       ▼
            │              dist/<book>.md ──► dist/<book>.html
            │                       │              │
            │                       │              ├─► to_pdf ─► pdf_toc_links ─► verify_pdf
            │                       │              └─► to_epub ─► verify_epub
            ▼                       ▼
        audit/*（只读门禁）      data/baselines/*（已评审存量）
```

三条不变量决定了整张图：

1. **手稿是唯一可编辑的内容源**。状态、基线、产物都由它派生，改动只能发生在手稿。
2. **门禁只读**。任何门禁只读输入、只写自己的基线，绝不修改手稿或产物。
3. **产物可再生**。`dist/` 随时可以删除重建；不可再生的只有手稿与基线。

### 2.2 分层结构

| 层 | 职责 | 可写 | 可导入 |
| --- | --- | --- | --- |
| `lib/` | 配置读取、文件读写原语、日志、版本、LLM 客户端、基线存储 | 由调用方决定 | 仅标准库 |
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

### 2.4 目录与数据布局

```text
books/
  data/
    tmpl/         book.toml（身份/路径/章节顺序/包归属）、案例与模板配置
    config/       base.json（基础设施策略）、style.json（写作与形态规则）
    language/     章节骨架名、练习提示语等语言资源
    manuscript/   手稿：封面、前件、章节、附录、后件
    state/        机器维护的派生状态：outline、source-inventory
    baselines/    已评审问题清单与体积基线（可 diff）
    snapshots/    只读历史快照：别的书的稿子，仅供比对
    tmp/          一次性脚本与临时文件（不入库）
  dist/           交付产物（可再生，不入库）
  docs/           工程文档：需求、技术、规范、计划、质量
  src/python/     工具链七个层
  src/test/       测试：与工具链同构的分层测试
  logs/           运行报告：门禁与检查的完整输出与摘要
```

### 2.5 两段式流水线

```text
源码树 --阶段1（事实抽取）--> 手稿 data/manuscript --> 阶段2（渲染与校验）--> dist/{md,html,pdf,epub}
```

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
| `data/tmpl/book.toml` | 这本书的身份：标题、版本、路径、章节清单、包归属、必备段落 | `lib/_config.py` 直接解析 |
| `data/config/base.json` | 基础设施策略：源码位置、路径映射、基线路径、工具链预算、日志 | 合并进 `POLICY` |
| `data/config/style.json` | 写作与形态规则：阈值、词表、图注规则、篇幅预算、语言骨架 | 合并进 `POLICY` |
| `data/language/zh.json` | 语言资源：章节骨架名、练习提示语、术语行 | `_config.language()` |
| `data/config/llm_pricing.json` | 各模型单价（每百万 token，provider 货币）；缺表即“未定价” | `_llm.pricing()` |

合并顺序固定：`base.json` → `style.json`，同名字典逐键覆盖；`toolchain` 段的预算
额外以 `thresholds` 别名暴露，供门禁统一读取。若两个 JSON 都不存在，退化为读取
`data/config/` 下的单文件 `config.json`（兼容形态，仓库不带）。解析失败一律抛
`ConfigError` 并指明文件，不允许静默降级。

### 3.2 阈值归属

阈值只允许出现在配置里，代码里不得内联。已知归属：

- 内容体量与交付下限：`base.json [toolchain]` 的 `content_floor_ratio`、`pdf_page_ratio`、`epub_size_ratio`、`pdf_max_mb`、`epub_max_mb`、`ascii_max_cols`。
- 质量下限：`style.json [thresholds]`（练习题量、索引总数与每章条数、索引主/子/see-also 条数、术语条数、每章跨章引用数）——这些值以前硬编码在 `structure.py`，现均从此处读取。
- 写作规则：`style.json [content_depth]`（如 `glossary_min_uses`、`excerpt_lines`）、`[captions]`、`[style_rules]`、`[limits]`。
- 篇幅预算：`style.json [limits]` 的 `sources`/`tests`/`docs`/`manuscript` 四档；`file_length` 要求四档都显式声明，不靠默认值。
- 图表与图簇：`style.json [quality]` 的 `min_figures_per_section`、`min_figure_coverage_pct`，`[clusters]` 的 `min_figures`、`window_lines`——`smart.py`、`figure_clusters.py`、`structure.py` 共用这一处，不再各自内联。
- 页面几何：`base.json [toolchain]` 的 `pdf_page_width`、`pdf_page_height`、`pdf_page_tolerance`（`verify_pdf.py` 按此判定 A4）。
- 章节骨架与必备段落：`book.toml [sections]`、`style.json [sections]`。
- 临时目录：`book.toml [paths] tmp`（缺省 `data/tmp`，读 `_config.tmp_dir()`）；
  HTML 片段缓存与 `--force` 备份都在它下面，已 gitignore。
- 派生状态：`book.toml [paths] state`（缺省 `data/state`，读 `_config.state_dir()` /
  `state_path(name)`）；ingest 每次重建，不入库。
- 覆盖率红线：`base.json [toolchain] coverage_fail_under`。
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
| `_config` | TOML/JSON 三层配置、路径解析、章节清单、语言与模板读取 | 派生 `MANUSCRIPT_DIR`、`DIST_DIR`、`thresholds`；`excluded_dirs()` 给出产物与快照目录 |
| `_fsutil` | 读写原语：`read_text`、`read_lines`、`write_text`、`load_json`、`ensure_dir`、`pin_stdout_utf8` | 统一 UTF-8；失败即退出并说明动作 |
| `_log` | 按天滚动的文件日志 + 控制台摘要 | 级别取 `BOOK_LOG_LEVEL` > 配置 > INFO |
| `_mdutil` | Markdown 结构解析：标题、围栏、图注 | 围栏内的内容不参与结构判定 |
| `_version` | 工具链语义化版本（唯一定义处） | 与书籍版本（`book.toml`）、被分析源码版本三向分离 |
| `_llm` | LLM 客户端：provider 路由、密钥只读环境变量 | 只有 `app` 与 ingest 散文场景可导入 |
| `_baseline` | 已评审问题清单的读写与差集 | 键由调用方定义；新增即失败，消失即提示收缩 |

`lib` 只依赖标准库，保证任何一层都能在最小环境下运行。

### 4.2 `ingest/` 输入层

把外部源码树变成可写作的手稿骨架与状态：

1. 读取源码位置（`base.json [sources] src_main` 等），扫描包与文件，落 `data/state/source-inventory.json`。
2. 按章节的包归属（`book.toml [chapters.packages]`）切分主题，落 `data/state/outline.json`。
3. 语言适配器（`ingest/languages/`）提供按语言解析符号的能力：现支持 java / python / rust /
   kotlin / go，新增一门语言＝加一个模块 + 注册表一行，`detect()` 的后缀映射从注册表推导。

该层只写 `data/state` 与手稿骨架，不参与质量判定：判定属于 `audit/`。

两条硬规则：**骨架可重建，正文不可重建**——`chapters.py` 只在目标文件为空、内容相同
或显式传 `--force` 时写入，否则跳过并报出行数；阶段结束时由 `core/actions.analyze`
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

### 4.3 `manuscript/` 手稿维护层

- `cover.py`：统计章节数、图数、行数并回写封面，是"统计数字唯一来源"。
- `glossary.py`、`index.py`、`terms.py`：术语表、索引与术语标注的生成与校验。
- `case_studies.py`：附录 A 的案例骨架，按 `data/tmpl/case-studies.toml` 展开。
- `snapshot.py`：把历史稿导入只读快照（见第 7 节）。

生成器只产出骨架与派生内容，正文语义由人负责。

### 4.4 `render/` 交付层

| 步骤 | 输入 → 输出 | 设计要点 |
| --- | --- | --- |
| `merge.py` | 手稿 → `dist/<book>.md` | 顺序来自 `book.toml`；前件、后件按 glob 展开 |
| `to_html.py` | 合并稿 → `dist/<book>.html` | 单一 HTML：侧边栏目录 + 印刷目录 + 锚点；CSS 内联；正文按章缓存 |
| `to_pdf.py` | HTML → PDF | 无头浏览器渲染；随后用 pypdf 写入大纲 |
| `pdf_toc_links.py` | PDF | 按目录条目与大纲的**位置对应关系**补链接注释，不靠标题文本匹配 |
| `print_pdf.py` | HTML → 印刷级 PDF | 章首装饰页、点线目录、页眉页脚；独立工具，不进 `deliver` 组 |
| `pdf_from_html.py` | 现成 HTML → PDF | 不重建 HTML 的旁路；独立工具，不进 `deliver` 组 |
| `verify_pdf.py` | PDF + HTML | 校验页数、A4、旋转、字体嵌入、体积、大纲与标题一一对应、目录链接落点 |
| `to_epub.py` | 合并稿 → EPUB | pandoc 生成，元数据经 `--metadata-file` 传入 |
| `verify_epub.py` | EPUB | 校验 mimetype 首条未压缩、容器与 OPF 可解析、清单与阅读顺序、导航可达、体积 |

渲染链的确定性由两点保证：输入只有手稿与配置；渲染器不引入随机与时间戳。

正文渲染按 H1 章节切片缓存（`render/html_cache.py`）：目录、锚点与章编号在切片前已定稿，
一片只依赖自己的 markdown 与渲染器源码，所以复用旧片不会改一个字节（缓存键就是内容哈希，
`--full` 可强制全量）。缓存落在 `data/tmp/html-cache/`（已 gitignore），被删或损坏只是
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

图注与图号的形状只定义一次：`lib/_mdutil.py` 的 `FIGURE_*` 形状与
`figure_caption()` 助手，六个 audit 模块只引用不重写；章节范围由
`book.toml [chapters.coverage]` 推导。

**基线机制**：可枚举的存量问题允许登记（`data/baselines/*.json`），登记项不判失败，
但同类别的新问题必须失败；登记项消失时报告 `stale`，提示收缩。基线键按内容而非
行号生成，插入小节不会把旧账重算成新账。

**判定与生成分离**：门禁不做语义判断；语义判断交给人与模型，模型产出的修改必须再过
门禁。`audit/llm_policy.py` 用导入关系在结构上锁定这条边界。

### 4.6 编排层

`make.py` 是唯一入口，持有步骤表：

```text
STEPS  = [(名称, 脚本, 额外参数, 分组)]       # 分组 ∈ build | verify | deliver
GROUPS = {build, verify, deliver, check, test, cover, report}
```

- `check` = `verify` 全集；`build` 只产物化；`deliver` 顺序固定：渲染 → 补链接 → 校验 → EPUB → 校验。
- 命令行支持 `--only`、`--skip`、`--keep-going`、`--timings`；失败时打印该步骤输出的末 30 行。
- 入口先校验解释器：不是项目虚拟环境即拒绝执行（`BOOK_ALLOW_SYSTEM_PYTHON=1` 可临时放行，交付流程不使用）。

`check_runner.py` 负责"什么时候跑什么"：

| 模式 | 场景 | 步骤 |
| --- | --- | --- |
| `docs` | 只改文档/手稿/配置 | 改动文件 lint + 受影响门禁 |
| `code` | 只改工具链源码 | 改动文件 lint + 受影响门禁 + 同名测试 |
| `tests` | 只改测试 | 测试 lint + 改动测试 |
| `quick` | 混合改动 | 上述并集 + 快档结构门禁；单步上限 300 秒 |
| `p0` | 提交前 | lint + 快档门禁 + 全量快档测试 |
| `p1` | 合并前 | lint + 全部门禁 + 测试 |
| `p2` | 发布 | p1 + 慢档 + 顺序依赖 + 交付 |

领域与门禁的映射由配置推导，不用字面量；`p0` 及以上的档位始终跑全集，分档只节省
本地的等待时间，不改变通过标准。

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

## 7. 状态与持久化

| 位置 | 内容 | 生命周期 |
| --- | --- | --- |
| `data/state/source-inventory.json` | 被分析源码的快照事实（文件、包、规模） | 每次 ingest 重建 |
| `data/state/outline.json` | 章节与主题的派生大纲 | 每次 ingest 重建 |
| `data/baselines/*.json` | 已评审问题清单：`accepted` 数组、生成方式、备注 | 只在评审后重设，收缩优先 |
| `data/baselines/content-volume.json` | 逐章字节/行数、手稿总量、交付页数与体积；`reviewed` 记评审人 / 提交 / 时间 / 理由，`source.snapshot` 记它取自哪份历史快照，`accepted_shrinks` 记每次经批准的收缩 | 定稿评审后重设；要求稿子已提交、有人具名、不降低下限 |
| `data/baselines/snapshot-<标签>.json` | 某个历史快照的体积事实 | 导入快照时生成 |
| `data/snapshots/<日期>-<标签>/` | `manifest.json`（压缩包哈希、逐文件字节/行数/哈希）+ 只读正文 | 只读；`snapshot.py verify` 校验 |
| `logs/check-<档位>-<时间戳>.{log,json}` | 每次检查的完整输出与摘要 | 保留最近若干次 |

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
| 接收历史稿 | `manuscript/snapshot.py import` 导入只读快照，再生成其体积基线 |

## 9. 失败模式与诊断

| 现象 | 设计上的定位路径 |
| --- | --- |
| 门禁失败 | 输出给出文件与行号，或给出可执行待办；完整输出落 `logs/` |
| 交付失败 | 编排层打印失败步骤的输出末 30 行；报告文件包含每步退出码与耗时 |
| 版本不一致 | `version_consistency` 列出工具、源码、文档三处版本与不一致项 |
| 依赖漂移 | `make.py doctor` 报告解释器、pin 漂移与可选工具可用性 |
| 测试顺序依赖 | `order_dependence.py` 以正序/逆序两轮比对，`--bisect` 收缩到最小污染前缀 |
| 内容疑似缩水 | `content_volume` 直接指出文件与下限差额，并提示是否需要重设基线 |

## 10. 非目标

- 不做通用静态站点生成器：渲染只服务本书的结构与排版。
- 不追求门禁的语义智能：无法枚举的判断留给人和模型，不写进门禁。
- 不提供多书合一的构建：快照只用于比对，不参与合并。
- 不替代版本控制：基线只记录"已评审的问题"，不记录历史正文。
