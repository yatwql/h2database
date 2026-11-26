# 目录结构（books/）

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1-dev
> 定位：**目录与文件归属的唯一说明**——哪里放什么、什么不入库；不重复命令清单（看
> `testplan.md` §1）、不重复配置合并规则（看 `technical.md` §3.1）。`CLAUDE.md` 只保留指向本文的链接，
> 结构与归属变更时只改这一份。

## 1. 顶层结构

```text
books/
  data/                      # 输入数据：配置 + 手稿 + 机器维护的状态
    book/                    # 本书专属：换一本书就整份替换
      book.toml              # 文档·结构：身份、路径、章节顺序、标题与编号、包映射（也可直接放在书根）
      case-studies.toml      # 文档·案例：案例流水线（scenario -> steps）与附录标题/开篇，按书可选
      glossary.toml          # 文档·术语：中英别名与「不算术语」词表，按书可选
    config/                  # 工具链策略：换一本书也照用
      base.json              # 配置·基础：源码树、语言与后缀、包前缀、基线路径、预算、日志
      style.json             # 配置·规则：图注词表、质量/文风阈值、禁用语、必备段落、预算上限
      llm_provider.json      # 配置·LLM：provider、路由与回退优先级
      llm_settings.json      # 配置·LLM：生成参数与每日费用上限
      llm_pricing.json       # 配置·LLM：各模型单价（未列出的模型费用记为未定价）
    tmpl/
      templates.toml         # 文档·表述：四段引言与深读要点模板（占位符不可改）
    srcref/                    # 克隆的源码仓库（fetch_source.py 写入；内容不入库）
    language/
      zh.json                # 文档·名词：章节骨架名、练习提示语、术语行
    baselines/                 # 机器维护的已知问题账本（非人写文档）
      *-baseline.json          # 各类已评审存量：ASCII 图、符号漂移、风格、体积
      *-findings.json          # 已评审的图注与深度存量
      coverage.json            # 逐文件覆盖率下限（只升不降，除非评审后重记）
      perf-baseline.json       # 已评审的耗时下限：逐步/总计中位数 + reviewed{by,at,commit,reason}
      loose-assertions.json    # 松散断言存量（目标为零，残留即登记）
      snapshot-<快照>.json     # 历史快照的体积基线（比对用）
    state/                     # 机器维护的派生状态：ingest 重建，人别手改
      source-inventory.json    # 被分析源码的快照事实；事实类门禁与渲染都读它
      outline.json             # 章节与主题的派生大纲；只有渲染器读它
      file-length.json         # 文件长度台账的上次实测值（file_length 只报超阈值的增长）
      source-inventory.prev.json  # 上一次清单（只为告知“源码是否变化”，不入库）
    archive/                   # 本书手稿与产物的滚动副本（自动、保留窗口取配置、gitignored）
    tmp/                       # 一次性脚本与临时文件（不入库）
    snapshots/                 # 只读历史快照：人工挑选的对照点（可来自 zip 或 data/archive 的日期目录），入库
      <日期>-<标签>/
        manifest.json        # 来源压缩包哈希、逐文件字节/行数/哈希
        manuscript/          # 快照正文
    manuscript/              # 手稿（唯一可编辑的内容源）
      cover.md
      front/                 # 前件：序、版权、阅读指南
      ch<章号>-<主题>.md     # 章节：文件名与顺序由 book.toml [chapters.files] 给出
      appendix-<字母>-<主题>.md
      back/                  # 后件：glossary.md / references.md / index.md
  src/
    python/                  # 工具链：lib/ core/ ingest/ manuscript/ audit/ render/ app/
                             #   + make.py（单入口）、check_runner.py（档位编排）、release.py
    test/                    # unittest 测试套件（单元 + 集成 + 真实书稿回归）
  logs/                      # 运行日志（按天回滚，gitignored）
  test-reports/              # 测试报告（每次一份日期目录 + latest.json，gitignored）
  dist/                      # 交付产物（生成物，gitignored）
    <book>.md / .html / .pdf / .epub
    <book>-print.pdf         # 印刷版（按需）
  docs/
    managements/             # 全部管理与规范文档（见 §2）
    manuals/                 # 使用手册：任务流水线、CLI/TUI/Web、配置、新建书、写作手法、
                             #   脚本与参数清单、FAQ（每份声明自己的「维度」）
    plan/                    # 单项迭代的设计与计划（<主题>/design.md 与 <主题>/plan.md，见 §2）
    archive/                 # 已关闭版本：v<major>.<minor>/ 下三份归档台账 + 已完成的迭代目录
                             #   （布局由 audit/doc_archive.py 机检，见 §3）
```

## 2. 管理文档

```text
books/docs/managements/        # 管理文档；总索引在 books/README.md「文档总索引」
  requirements.md            # 当前范围与交付物
  plan.md                    # 计划项清单（plan-N，按 P1–P4 分档，每项现状/动作/验收/事实位）
  review-findings.md         # 问题记录（rf-N，待处理 / 已修摘要 / 文件膨胀登记）
  testplan.md                # 质量门禁与验证命令（验证的唯一权威；门禁级别只在 §2.1/§2.2 声明）
  content-quality-policy.md  # 内容质量方针（判定分工、三种起点、基线生命周期、成本）
  changelog.md               # 版本历史
  folder.md                  # 本文件：目录结构
  technical.md               # 工具链架构约束（可机检部分由 check_architecture 守卫）
  content-standard.md        # 内容标准（跨项目复用）
  DESIGN.md                  # 设计契约总纲（三处呈现面共有规则）
  DESIGN-TUI.md              # 终端交互契约
  DESIGN-WEB.md              # 网页控制台契约
```

## 2.1 配置分四层

四个文件各管一段，**合并顺序、读取入口与别名在 `technical.md` §3.1**，本文只记归属：
`data/book/book.toml`（数据组织与本书读哪棵源树）、`data/config/base.json`（基础配置与分析口径）、
`data/config/style.json`（书籍风格）、`data/language/zh.json`（语言资源）。

## 3. 归属规则

- **文档与配置分离**：判定规则/阈值在 `style.json`，叙述模板在 `templates.toml`，
  名称与提示语在 `language/`，书籍身份与展示文案在 `book.toml`。
- **书身份文件两种布局都认**：`<书根>/data/book/book.toml`（标准）或 `<书根>/book.toml`
  （扁平）。判定「这里是一本书」只看能否读到 `book.toml`，与它放在哪一层无关；两种布局下
  `[paths]` 都相对**书根**解析，产物与手稿仍在各自书根下，不按书再分层。
- **配置分四层**：内容组织 `data/book/book.toml`、基础设施 `data/config/base.json`、
  写作规则 `data/config/style.json`、语言资源 `data/language/zh.json`。合并规则只在
  `technical.md` §3.1 定义；脚本统一通过 `_config` 读取，禁止硬编码。
- **基线与状态归 data**：`data/baselines/` 存放机器维护的已知问题记账，不放人写文档。
- **手稿只在 `data/manuscript/`**：`dist/` 里的合并 Markdown 是生成物，不手改。
- **产物只在 `dist/`**：`*.html`、`*.pdf`、`*.epub`、`*.log` 全部 gitignored，
  由 `make.py build` / `make.py deliver` 重新生成。
- **被分析的源码是外部输入，但归书声明**：书读哪棵源树写在 `data/book/book.toml [sources]`
  （`src_main`/`pom_root`/`roots[]`/`version`）——换一本书就是换一棵树，这是书的身份而非工具链
  策略；分析口径（`languages`、`suffixes`、`package_prefix`）留在 `base.json [sources]`，两处按
  书级覆盖共享合并。源码本身仍在书根之外，仓库里不需要它。
- **工具链只在 `src/python/`**：正式交付脚本；临时脚本不得入库。
- **测试只在 `src/test/`**：`make.py test` 跑全部；`make.py cover` 带覆盖率棘轮。
  共享的 fixture 基类（`Base`、`ScriptTestBase`、`FixtureCase`、`TempFile`）只在 `_cases.py`，
  夹具书与进程内脚本运行器在 `_fixture.py`——各 suite 不再自带副本。
- **管理文档只在 `docs/managements/`**：要求、判定、做法各一份，互不重复；总索引在
  `books/README.md` 的「文档总索引」，本文只管位置。
- **怎么用、怎么写只在 `docs/manuals/`**：每份手册声明自己的「维度」，不引用管理文档；
  配置键的含义也在这边（`how-to-config.md` §3），管理文档只写"归属哪个文件"。
- **单项迭代的设计与计划只在 `docs/plan/<主题>/`**：一个主题一个目录，里面放
  `design.md`（迭代设计）与 `plan.md`（实施计划），可附 `README.md`。目录名与文件名
  一律用小写连字符的语义名（如 `diagram-upgrade/`），**不得把 `plan-N`、`rf-N` 等编号
  写进目录名或文件名**——编号属于 `docs/managements/plan.md` 的计划项与
  `review-findings.md` 的问题项，是追踪键，不是文件名。两条入口都适用：`plan.md` 新开
  一项需要详设时放这里，`review-findings.md` 里某项需要专文时也放这里。
  `doc_drift.py` 的 `PLANNAME` 检查搂住这条规则（目录必须含 `plan.md`、只允许
  `design.md`/`plan.md`/`README.md`、不得含编号）。

## 3.1 两份稿子副本的分界

仓库里有两处按日期存手稿的地方，形态相似、职责不同，不得互相代替：

| | `data/archive/<书>/<日期>/` | `data/snapshots/<日期>-<标签>/` |
| --- | --- | --- |
| 谁写 | `make.py build` / `deliver` 自动写入 | 人手动 `snapshot.py import` |
| 存什么 | 本书手稿 **+ `dist/` 里的产物** | 只存手稿 |
| 存多久 | 滚动，默认保留 45 天（`base.json [archive] retention_days`） | 永久，人工删除 |
| 入不入库 | gitignored | 入库，作为可引用的证据 |
| 谁读它 | 不读，纯回滚用 | `content_volume --from-snapshot` 取来当体量基线；`snapshot.py verify` 校哈希 |
| 门禁 | `_config.excluded_dirs()` 排除，不当正文扫 | 同左 |

用法边界：

- `archive` 只管“刚才那一版还能拿回来”。它会被窗口自动删掉，所以**不能当长期对照点**。
- 真正要被基线引用的版本，用
  `python books/src/python/manuscript/snapshot.py import data/archive/<书>/<日期>/manuscript <标签>`
  固化进 `snapshots/`。`import` 同时接受 zip 与目录，目录来源不必重新打包（manifest 用内容摘要代替 zip 哈希）。
- 快照只读：`verify` 只比对哈希不改文件；过期快照由人删除，没有自动清理。
- 两种快照：`import` 存手稿（后续构建的来源），`import-artifacts` 存**成品**（HTML/Markdown/EPUB/PDF）。
  只剩成品、手稿已丢的版本也能留下对照：成品只按哈希校验，不解码文本，`kind: "artifacts"` 标明其身份。

## 4. 常用入口

入口清单只有两份：使用者看 [`books/README.md`](../../README.md) 的「快速开始」与「文档总索引」，
验证命令看 [`testplan.md`](testplan.md) §1。本文不重复命令。

## 5. 不入库的临时产物

临时修复脚本、压缩包、`__pycache__`、过程性产物一律不入库：正式脚本只进
`src/python/`，一次性脚本与会话产物只进 `data/tmp/`（已 gitignore）。

`data/tmp/` 与 `data/cache/` 是两种不同的承诺，不要混放：

| 目录 | 承诺 | 放什么 |
| --- | --- | --- |
| `data/tmp/` | 随时可被清空 | 一次性脚本、会话产物、临时对照文件 |
| `data/cache/` | 可重建但有重建成本 | 字体索引（扫描全机字体）、HTML 分片缓存 |

两者都由 `_config.excluded_dirs()` 排除、都在 `.gitignore` 里；`cache` 不可写时自动退回 `tmp`，
只读检出也能构建。

历史手稿不进 `data/manuscript/`：用 `src/python/manuscript/snapshot.py` 导入到
`data/snapshots/<日期>-<标签>/`，生成 manifest 后即可用
`snapshot.py baseline` 出体积基线。快照只读，门禁不扫描它。
