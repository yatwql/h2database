# 脚本与命令参考

> 维度：**参考——全部可执行入口与参数的唯一清单**
> 软件：bookwright — 源码分析成书工具 v0.1
> 全部可执行入口的唯一清单。日常优先用 `books/scripts/` 下的封装脚本，不必直接
> 和 Python 解释器打交道；需要细粒度控制时再用 `make.py` 或分层脚本。

## 1. 命名约定

| 位置 | 约定 | 例 |
| --- | --- | --- |
| `books/scripts/` | 动词前缀 + 对象：`check-*` 验证（退出码决定成败）、`eval-*` 度量（出报告）、`new-*` 生成 | `check-fast.sh`、`eval-score.sh`、`new-book.sh` |
| `src/python/<层>/` | 目录定类别、文件名写对象，不加动词前缀 | `audit/links.py`、`render/to_pdf.py` |
| `src/python/lib/` | 内部模块用下划线前缀 | `lib/_config.py` |
| `src/python/mutation_smoke.py` | 变异抽查（评审用）：把工具链与测试复制到临时目录，逐条施加条件/布尔变异并跑该模块的用例，列出存活的变异 | `python src/python/mutation_smoke.py --module audit/content_volume.py --tests test_audit_content_volume_branches.py` |

`books/scripts/` 的文件名由 `audit/check_architecture.py` 机检：只允许下列前缀：
`bookctl`、`launch`、`bootstrap`、`check`、`eval`、`new`、`test`、`release`、`install`
（可用后缀区分对象，如 `check-fast.sh`、`test-eval-order.sh`）。

## 2. 日常封装脚本（`books/scripts/`）

| 脚本 | 作用 |
| --- | --- |
| `bookctl` / `bookctl.ps1` | 统一分发器：`bookctl <action>` 转发到 `app/cli.py`，自己找解释器（`.venv` → `$PYTHON` → `python3`） |
| `launch.sh` / `launch.ps1` | 交互入口：默认进 TUI，`launch.sh cli <action>` / `launch.sh web` 切渠道 |
| `bootstrap.sh` / `bootstrap.ps1` | 建 `.venv`、装依赖、装 chromium（首次使用跑一次） |
| `new-book.sh` / `.ps1` | 脚手架：生成新书（或翻译版）的四份文档侧配置 + 按目标语言派生的 `style.json` |
| `check-fast.sh` / `.ps1` | P0：ruff + 结构门禁 + 单元套件（约 16 秒），每次提交跑 |
| `check-full.sh` / `.ps1` | P1：全部门禁（合入前跑） |
| `check-release.sh` / `.ps1` | P2：完整档 + 慢档（chromium/pandoc）+ 顺序依赖探测 + `make.py deliver` |
| `check.sh` / `check.ps1` | 档位入口：`check.sh p0\|p1\|p2`（也接受 fast/full/release），其余参数透传 |
| `release.sh` / `.ps1` | 发布流程：`status` / `gate`（P2）/ `publish --title`（P2 + 写发布清单）/ `manifest` |
| `install-hooks.sh` / `.ps1` | 把 `core.hooksPath` 指到仓库内的 `.githooks/`（pre-commit=P0，pre-push=P1） |
| `eval-score.sh` / `.ps1` | 六维发布评分（功能/稳定/交互/代码/文档风格/文档质量），`--json` 出机读 |
| `test-eval-coverage.sh` / `.ps1` | 测试覆盖率 + 棘轮（低于 `base.json [toolchain].coverage_fail_under` 失败） |
| `test-eval-order.sh` / `.ps1` | 测试顺序依赖探测：正序/逆序各跑一次并对比（慢档，约 2 倍测试时间） |

全部支持 `PYTHON=/path/to/python` 覆盖解释器。

### 测试报告与归档

| 脚本 | 作用 |
| --- | --- |
| `src/python/test_report.py run` | 跑测试并把报告写进 `books/test-reports/<时间戳>/`（`report.json`、`report.md`、`report.html`、`junit.xml`、`pytest.log`），更新 `latest.json`，按保留窗口清理旧报告 |
| `src/python/test_report.py last` | 解出最新报告里的失败用例（跳过不计），并给出只重跑这些模块的命令 |
| `src/python/test_report.py collect` | 只收集不执行：按模块的 `TAGS` 统计 fast/slow/未分层用例数，写一份快照 |
| `src/python/test_report.py perf` | 最近一次运行的各步骤耗时 vs 前几次中位数，标出回退（判定仍由 `audit/perf_baseline.py` 做） |
| `src/python/test_report.py list` / `prune` | 列出报告目录 / 按窗口清理（`--dry-run` 只报告） |
| `src/python/manuscript/archive.py` | 把手稿与 `dist/` 产物按日期归档到 `data/archive/<书>/<日期>/`，并按 `base.json [archive] retention_days` 清理过期归档 |

### 档位编排器 `src/python/check_runner.py`

`check.sh` 只是它的薄封装；本地与 CI 共用同一份编排。

```bash
python books/src/python/check_runner.py --mode p0            # 提交门禁（约 16 秒）
python books/src/python/check_runner.py --mode p1 --json     # 合入门禁，机读输出
python books/src/python/check_runner.py --mode p2 --only gates,tests
python books/src/python/check_runner.py --mode p0 --skip slow --timeout 600
```

- 每次运行写 `books/logs/check-<模式>-<时间戳>.log` 与同名 `.json`，并刷新
  `books/logs/check-latest.json`（失败可直接回看，不必重跑）
- `.json` 里带 `machine` 段（python/平台/CPU/locale/仓库路径），排查"本机能过 CI 不能过"先看它
- `--only` / `--skip` 选步骤，`--timeout` 是每步超时（默认 1800 秒，超时记为 124）
- 测试步骤按档位自动带 marker：P0=`tier_fast`、P1=`not tier_slow`、P2=全量；
  `--marker "<expr>"` 可覆盖，环境缺 pytest 时退回 `make.py test`

### 发布 `src/python/release.py`

```bash
books/scripts/release.sh status                 # 三个版本 + 产物是否存在
books/scripts/release.sh gate                   # 跑 P2 档
books/scripts/release.sh publish --title "6.5"  # 干净树才允许；P2 通过后写发布清单
books/scripts/release.sh manifest               # 按当前产物重写清单
```

发布清单写到 `books/dist/release-<书籍版本>.json`：三个版本、commit、产物字节数与
SHA-256。`publish` 只写清单并提示 `git tag`，不代替你打标签。

### 失败提取（CI 日志）

```bash
python books/src/python/audit/failure_extract.py books/logs/check-p0-*.log
python books/src/python/audit/failure_extract.py --json < log.txt
```

把长日志收敛成"哪个用例、什么原因"的清单，`--summary` 只列用例名。

### Git 钩子

```bash
books/scripts/install-hooks.sh     # core.hooksPath=.githooks
```

- `pre-commit` 跑 P0（约 16 秒），`pre-push` 跑 P1
- 临时绕过：`git commit --no-verify` / `git push --no-verify`
- 钩子里的档位与 `src/python/check_runner.py` 同源，由 `books/src/test/test_release_and_runner.py` 守住不漂移

## 3. 单入口 `src/python/make.py`

日常默认走这里，它按组串起下层脚本：

| 命令 | 内容 |
| --- | --- |
| `check` | 全部门禁（只读，不写产物；清单见本文 §8，登记一致性由 `gate_trace.py` 校验） |
| `build` | `cover.py` → `merge.py` → `to_html.py` → `archive.py` |
| `verify` | `check` 的语义别名 |
| `test` | 单元套件；`--full` 加慢档，`--timings` 出耗时 |
| `cover` | 覆盖率 + 棘轮 |
| `report` | 六维评分（`eval-score.sh` 的实现） |
| `deliver` | `to_pdf` + `pdf_toc_links` + `verify_pdf` + `to_epub` + `verify_epub` + `archive_release` |
| `doctor` | 可选依赖与环境自检 |

参数：`--only NAME[,NAME]`、`--skip NAME[,NAME]`、`--timings`、`--keep-going`、
`--full`。退出码：`0` 通过、`1` 失败、`2` 用法/环境错误。

## 4. 渠道入口 `src/python/app/`

| 脚本 | 作用 |
| --- | --- |
| `app/cli.py <action>` | 单次执行动作；`llm-ask` 支持 `--scenario` |
| `app/tui.py` | 交互菜单（方向键 + 单键）；`--once <action>` 脚本化 |
| `app/web.py --port N` | 本机 Web 控制台；`GET /`、`GET /api/status`、`POST /api/run` |
| `app/keys.py` | 键位层（库模块，不是入口） |

三个渠道共用 `core/actions.py`，行为一致。

## 5. 领域层 `src/python/core/`

| 模块 | 作用 |
| --- | --- |
| `core/actions.py` | 动作执行（库）；`analyze(use_llm=…)` 等 |
| `core/menu.py` | 菜单模型、确认策略、运行回报（库） |
| `core/settings.py` | 可改配置项的读写与校验（库） |
| `core/scaffold.py <目标目录>` | 新书脚手架：四份文档侧配置 + 派生 `style.json`；`--lang`、`--title`、`--from-manuscript` |

## 6. 源码 → 手稿 `src/python/ingest/`

| 脚本 | 作用 |
| --- | --- |
| `ingest/digest.py` | 源码树 → `data/state/source-inventory.json`（`--json`） |
| `ingest/outline.py` | 清单 → 章节大纲 `data/state/outline.json`（`--json`） |
| `ingest/chapters.py` | 大纲 → 手稿；`--only FILE`、`--dry-run`、`--llm`（导读/小结交给 LLM）、`--force`（覆盖已有正文；默认跳过） |
| `ingest/languages/{java,python,rust}.py` | 语言分析器（库），由 digest 按 `[sources]` 选择 |

## 7. 手稿维护 `src/python/manuscript/`

| 脚本 | 作用 |
| --- | --- |
| `cover.py` | 更新 `cover.md` 的版本、更新日期、行数、图数、引用数 |
| `glossary.py` | 术语表：`--check` 覆盖率、`--validate` 章节引用、`--update` 补录 |
| `index.py` | 索引：生成与层级检查 |
| `terms.py` | 给每章导读块补术语表引用；`--check` 只报告 |
| `case_studies.py` | 案例研究章节大纲 |
| `snapshot.py` | 历史稿只读快照：`import <zip 或目录> <label> --date`（目录来源无需重新打包）、`list`、`verify <label>`、`baseline <label>`（写 `data/baselines/snapshot-<label>.json`，供 `content_volume.py --from-snapshot` 提为基线） |

## 8. 质量门禁 `src/python/audit/`

默认只读；带 `--update-baseline` 的脚本仅在显式传参时写 `data/baselines/`。
`--json` 表示机读输出（下表 `●` 为支持）。

| 门禁 | 检查什么 | `--json` |
| --- | --- | --- |
| `structure.py` | 图号、跨章引用、代码围栏、标题层级、必需小节、合并稿一致性 | ● |
| `links.py` | 链接与锚点是否可解析 | ● |
| `crossrefs.py` | `详见第X章《...》` 是否指向真实章节 | ● |
| `diagrams.py` | ```text 围栏内 ASCII 图的宽度与闭合 | ● |
| `readability.py` | 可读性：围栏、宽度、图块闭合 | ● |
| `smart.py` | 图表覆盖与子章节密度 | ● |
| `captions.py` | 图注动词开头、长度、含糊后缀（`--threshold`、`--fix`） | ● |
| `figures.py` | 图号格式与正文引用（`--strict`） | ● |
| `figure_clusters.py` | 图簇与桥接句（`--min`/`--window` 默认取 `style.json [clusters]`） | ● |
| `balance.py` | 章间体量分布（行数/图数/坐标数） | ● |
| `exercises.py` | 延伸思考的数量、难度、提示、锚点 | ● |
| `index_xrefs.py` | 索引条目、see-also 解析、层级 | ● |
| `glossary.py`（manuscript） | 术语覆盖（见第 7 节） | – |
| `style.py` | 写作风格：句长、重复、表格规模 | ● |
| `style_rules.py` | `style.json [style_rules]`：术语、空格、标题、列表标点 | ● |
| `style_schema.py` | `style.json` 结构合法性（文档/配置分离） | ● |
| `content_depth.py` | 前向引用、术语覆盖、摘录新鲜度、练习指向 | ● |
| `source_refs.py` | 源码坐标与符号是否仍然有效（`--suggest`、`--update-baseline`、`--baseline`） | ● |
| `version_consistency.py` | 工具/源码/文档三版本一致 | ● |
| `check_architecture.py` | 分层、依赖矩阵、渠道纯净、命名、docstring | ● |
| `script_contract.py` | 每个脚本的 docstring / `main()` / 退出码 / `--json` 契约 | ● |
| `llm_policy.py` | LLM 只在允许的层与场景使用；密钥文件不入库 | ● |
| `traces.py` | 过程/历史痕迹：`--kind docs`（文档）、`--kind code`（代码注释）、`--kind all`（默认） | ● |
| `doc_drift.py` | 文档提到的路径/脚本/章节是否仍存在 | ● |
| `file_length.py` | 文件行数预算 | ● |
| `gate_trace.py` | 质量计划登记与 `make.py` 步骤双向可追溯 | ● |
| `typecheck.py` | pyright 静态检查（可选依赖，缺失时跳过） | ● |
| `portability.py` | 移植性：`open()` 必须显式 encoding；`LC_ALL=C` + ASCII 输出下入口不得崩 | ● |
| `test_redundancy.py` | 测试卫生：重复用例体 / 无断言 / 非 TestCase 的 test_* / 同名遮蔽 | ● |
| `perf_baseline.py` | 交付速度：每步耗时对比历史中位数，超阈值提示；`--strict` 变成失败 | ● |
| `order_dependence.py` | 顺序依赖：正序/逆序两跑对比（P2 档自动执行，也可用 `test-eval-order.sh` 单独跑） | ● |

报告类不是门禁，不进 `make.py check`：`scorecard.py`（六维评分汇总）、
`prose_quality.py`（文风度量）、`book_quality.py`（质量度量）、`review_packet.py`
（失败集合）、`failure_extract.py`（从日志提取失败项）。

## 9. 交付渲染 `src/python/render/`

| 脚本 | 作用 |
| --- | --- |
| `merge.py` | 章节 → 合并 Markdown（写版本清单注释） |
| `to_html.py` | 合并 Markdown → HTML（侧边栏 TOC、锚点、样式） |
| `to_pdf.py` | HTML → 标准 PDF（Chromium 打印 + 大纲 + 页内目录页码） |
| `pdf_toc_links.py` | 给印刷版 TOC 加可点击链接（按位置映射，重名标题安全） |
| `print_pdf.py` | 印刷级 PDF：章封面横幅、点线目录、页眉页脚；`--html`、`--pdf`、`--skip-html` |
| `pdf_from_html.py` | 不重建 HTML，直接出 PDF；`--html`、`--pdf` |
| `to_epub.py` | HTML → EPUB（pandoc） |
| `verify_pdf.py` | PDF 交付校验：页数、大纲、目录链接、A4、旋转、字体嵌入（`--json`） |
| `verify_epub.py` | EPUB 结构校验（`--json`） |

## 10. 公共库 `src/python/lib/`（不是入口）

`_config`（配置与路径）、`_fsutil`（读写原语）、`_mdutil`（Markdown/HTML 工具）、
`_llm`（provider 路由与客户端）、`_log`（日志）、`_version`（产品名与版本）。
脚本一律经 `_config` 取路径，不写死仓库路径。

## 11. 该用哪个

| 场景 | 命令 |
| --- | --- |
| 日常提交前 | `books/scripts/check-fast.sh` |
| 合入前 | `books/scripts/check-full.sh` |
| 想看看质量分数 | `books/scripts/eval-score.sh` |
| 发布前 | `books/scripts/check-release.sh` |
| 改了源码树 | `bookctl analyze`（确定性）或 `bookctl analyze-llm`（导读/小结用 LLM） |
| 只重建文档 | `bookctl build` |
| 单独查某个问题 | `make.py check --only <step>`，或直接跑对应 `audit/*.py --json` |
| 新建一本书 / 翻译版 | `books/scripts/new-book.sh ../new-book --title "…"`（翻译加 `--lang en`） |

## 按需执行的工具脚本

不是 `make.py` 的一步，需要时手工调用；都不改写判定口径。

| 脚本 | 何时用 |
| --- | --- |
| `core/docs_archive.py --version X.Y [--topic <迭代目录>] [--dry-run]` | 发布一个版本后，把该版本台账与已完成的迭代设计移入 `docs/archive/` 下以版本命名的目录；`--dry-run` 先看动作，重复执行无副作用 |
| `manuscript/renumber.py --write/--apply` | 声明了 `[editions]` 且章号有变化时，算映射并改写 `详见第X章《…》` 一类引用 |
| `audit/doc_archive.py`、`audit/plan_coverage.py` | 归档布局与计划覆盖的门禁，已包含在 `make.py check` 里，可单独运行排查 |

