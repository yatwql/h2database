# 工具链架构约束

> 本文件是工具链的**架构约束**（可机检的部分由 `audit/check_architecture.py` 守卫）。
> 目录职责见 `../managements/folder.md`；用法见 `../manuals/how-to-use.md`；
> 内容标准见 `analysis-doc-standard.md`。

## 1. 分层与职责

```text
lib/        公共库：配置读取、文件 IO、Markdown 工具。无业务判断，不写文件。
ingest/     源码 → 手稿：只读源码树，只写 data/state 与 data/manuscript。
manuscript/ 手稿维护：只读写 data/manuscript 与 data/state。
audit/      质量门禁：只读；输出报告到 stdout，不修改仓库。
render/     交付渲染：只写 dist/，可读 manuscript 与 data/state。
app/        入口层：cli.py / tui.py / web.py + actions.py，只编排，不含业务逻辑。
```

**入口层约束**：三个渠道共用 `app/actions.py`；渠道层不得直接实现分析、渲染或
校验逻辑，只能调用 `actions`（其内部调用 `make.py` 与 stage 1 脚本）。

**依赖方向**：`lib ← ingest/manuscript/audit/render`。同层之间不得互相 import，
下层不得反向依赖上层。

## 2. 配置与常量

- 路径、阈值、文案、词表、模板只来自 `_config`（`book.toml` + `base.json` +
  `style.json` + `language/*.json`）。
- 脚本内不得出现仓库路径字面量（`books/…`、`data/manuscript`）、阈值数字或书名文案。
- 已知问题只记入 `data/baselines/`，不得散落在代码或文档注释里。

## 3. 命名

- 目录定类别，文件名写对象：`audit/links.py` 而不是 `audit/audit_links.py`。
- 下划线前缀只表示"内部模块"（`lib/_config.py`）；CLI 入口不加下划线。
- 文件名不得与标准库模块同名（避免与标准库同名的模块遮蔽）。
- 同一目录内不得混用 `check_*` / `*_check` / `_audit_*` 三套风格。

## 4. 入口契约

- 每个入口脚本：模块 docstring + `main(argv)`（或在 `__main__` 下执行）。
- 退出码语义：`0` 通过、`1` 门禁失败、`2` 使用/配置错误。
- 报告类脚本必须支持 `--json`（供 `make.py` 与 CI 汇总）。

## 5. 事实与内容

- 手稿中的源码引用必须可解析（`Class.java:行号`、`Class.method(`）。
- 每个源码包只有一个主责章节（`book.toml [chapters.packages]`）。
- 手稿不写过程性记录；版本历史只在 `changelog.md`。

## 6. 规模与复杂度

- 文件行数上限：源码 900、测试 1200、文档 1200、手稿附录 2000（含提醒线）。
- 单函数以"一屏可读"为目标；超长逻辑拆成具名步骤。

## 7. 测试

- fixture 书覆盖 stage 1 与 stage 2；`test_generic_source` 用第二份源码树守住通用性。
- 快慢分档：`make.py test` 默认快速档，`--full` 加 chromium/pandoc 档。

## 8. 门禁

- `make.py check` 是唯一入口；新增门禁必须同时登记 `testplan.md`，由
  `audit/gate_trace.py` 校验双向可追溯。
- 门禁只读；任何会改仓库的动作都属于 `manuscript/` 或 `render/`，不进 `check`。

## 9. 日志

- 位置：`books/logs/books.log`，按天回滚（`books.log.YYYY-MM-DD`），默认保留 14 天。
- 级别：`BOOK_LOG_LEVEL` 环境变量 > `data/config/base.json [logging].level` > INFO；DEBUG 记录每步参数、耗时与计数。
- 出口：文件记录全部（INFO 起），控制台只输出 WARNING 及以上，避免刷屏。
- 实现：`lib/_log.py`（DailyRotatingHandler 幂等初始化），入口（`make.py`、`app/actions.py`、`ingest/*`）只调用 `_log.get_logger(...)`。

## 10. 环境与依赖

- 运行环境：`books/.venv`（由 `scripts/bootstrap.sh|ps1` 创建），启动脚本优先使用它。
- 依赖清单：`requirements.txt`（运行时可选）与 `requirements-dev.txt`（开发/CI）；
  文档与代码不再各自列依赖表。
- 核心链路（ingest/audit 结构门禁）只依赖标准库；PDF/EPUB 相关脚本在缺少
  `pypdf`/`playwright`/`pandoc` 时必须以清晰信息退出（码 2），不得抛裸 traceback。

## 11. LLM 使用边界（用在刀刃上）

- **允许**：散文生成与评审（`chapter-draft`、`chapter-polish`、`summary`、`review`）。
- **禁止**：任何事实与结构判断——章节结构、源码坐标、跨章引用、链接、重复度、
  文风度量、图注、索引、术语、表格，全部保持确定性。
- **执行**：`audit/llm_policy.py` 检查只有 `app/` 与 `ingest/` 可导入 `lib._llm`，
  `audit/` 门禁一律不得调用；策略清单在 `llm_settings.json [policy]`。
- **强度**：路由可按场景/书籍/章节指定 `thinking`（`off|low|medium|high`），
  缺省 `low`；强度随请求传为 `reasoning_effort`。

## 12. 三个版本

| 版本 | 来源 | 含义 | 谁改 |
| ------ | ------ | ------ | ------ |
| 工具版本 | `lib/_version.py`（或被 `[sources].tool_version` 覆盖） | 工具链自身 | 改工具的开发者，semver |
| 源码版本 | `[sources].version`，否则读源码清单（pom.xml / pyproject.toml / Cargo.toml） | 被分析的那份源码 | 上游升级时自动变化 |
| 文档版本 | `book.toml [book].version` | 这本书/这份手稿 | 内容迭代时 |

约束：

- 合并 Markdown 首行写 manifest：`<!-- versions: tool=… source=… doc=… -->`；
  该行与空白分隔不计入手稿行数（`structure.py` 已排除）。
- 管理文档头 `> 版本：vX` 必须等于文档版本。
- `audit/version_consistency.py` 校验三者可解析且一致；`make.py check` 必跑。
- `app/cli.py status` 与 TUI 顶部同时显示三者：`工具 / 源码 / 文档`。

## 13. 文件职责分类（权威定义）

工具链只通过 `lib/_config.py` 读配置，但"配置"与"文档"严格分开，且"文档"里
还要再分**结构 / 表述 / 名词**。下表是唯一权威定义，其他文档只做引用。

| 文件 | 回答的问题 | 内容 | 归类 | 读取方 | 改错的后果 |
|------|-----------|------|------|--------|-----------|
| `data/tmpl/book.toml` | 这本书**是什么、怎么组织** | 书名/版本/产物名、`[project]` 展示文案、目录、章节清单与顺序、每条 H1 标题、H1 编号、覆盖归属、包→章节映射 | 文档·结构 | 规划期（outline）与全部阶段 | 章节/编号/索引/跨章引用错位，结构门禁直接拦 |
| `data/tmpl/templates.toml` | 这本书**怎么表述** | 版图/类型/入口/路径四段引言 + 深读要点，含 `{num}{pkgs}{top}{dep}{share}` 占位符 | 文档·表述 | `ingest/chapters.py` 渲染章节时 | 措辞变化，不影响判定；占位符写错会被 `style_schema.py` 拒绝 |
| `data/language/<code>.json` | 章节与练习的**名词与提示语** | 本章导读/小结/延伸思考/延展阅读的名字、`提示`/`回顾` 前缀、术语行与术语表链接 | 文档·名词 | 门禁匹配与生成器 | 门禁找不到段落，判为缺失 |
| `data/config/style.json` | **判定规则与阈值** | 图注词表与预设、图示标记、质量/文风阈值、禁用语、必备段落名、篇幅预算、生成数量上限、`style_rules`（术语一致性/排版） | 配置·规则 | 全部门禁 | 阈值失效或误报；`style_schema.py` 先校验结构 |
| `data/config/base.json` | **基础设施** | 源码树、语言与后缀、包前缀、状态/基线路径、日志、PDF/EPUB/ASCII/覆盖率预算 | 配置·基础 | 全部门禁与入口 | 找不到源码或产物路径 |
| `data/config/llm_*.json` | **模型路由与参数** | provider、模型、场景/书籍/章节路由、thinking 强度、密钥环境变量名 | 配置·外部服务 | `lib/_llm.py` 与 `app/` | 调用越界或被 `llm_policy.py` 拦下 |

记忆法：**结构看 `book.toml`，说法看 `templates.toml`，名词看语言包，判分看 `style.json`，
找源码看 `base.json`，找模型看 `llm_*.json`。**

边界由两道门禁强制：

- `audit/style_schema.py`：`style.json` 不得含 `generation.templates` 或 `project`；
  `templates.toml` 只允许已知键、占位符合法。
- `audit/check_architecture.py`：脚本不得硬编码仓库路径，一律经 `_config` 取。
