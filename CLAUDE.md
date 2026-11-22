# CLAUDE.md

本仓库中 Claude Code 的工作约定。**只放两样东西**：这一层才知道的判断（工作节奏、编辑边界），
以及"去哪读"的索引。命令、参数、流程步骤一律不在这里复述——正文在 `books/`，改了那边也不必回来同步。

## 仓库范围

1. `h2/` —— 当前被分析的上游源码树（H2 v2.x）。它只是输入，不是工具链的一部分：
   换一本书就把 `base.json [sources]` 指向另一棵源码树。
2. `books/` —— **通用的源码分析成书工具链**，外加它正在服务的这本书（H2 内部实现分析，中文）。
   源码树、包前缀、文件后缀在 `base.json [sources]`；语言适配器在 `ingest/languages/`
   （java / python / rust / kotlin / go）；新书用 `bookctl new <目录>` 由脚手架生成。

## 去哪里读

| 要做什么 | 读哪里 |
| --- | --- |
| 跑命令（日常 / 验证） | `books/README.md`；验证命令见 `books/docs/managements/testplan.md` §1 |
| 按顺序完成一件事（动笔 → 交付） | `books/docs/manuals/how-to-use.md` |
| 门禁判据与级别 | `books/docs/managements/testplan.md` §2 |
| 目录结构与文件归属 | `books/docs/managements/folder.md` |
| 写作与格式约定 | `books/docs/managements/style-guide.md` |
| 内容组织（章节、图号、包映射） | `books/data/book.toml` |
| 工具链策略（阈值、预算、基线） | `books/data/config/base.json`、`style.json` |
| 单项迭代的设计与计划 | `books/docs/plan/<topic>/`（`design.md`、`plan.md`） |

## 工作节奏（这一层的事，文档里没有）

- **先量后跑，取能定论的最小命令。** 先拿量级（`--collect-only`、单文件、子集 `--durations`）；
  整套快档约 25 秒，出现"几分钟"就说明某个用例卡住了。单文件或单用例优先，全量只在收尾跑一次。
- **同一时刻只跑一个重活，且不长占前台。** 预计超过约 2 分钟的放后台、先说预计时间、等退出信号，
  不用 `sleep` 轮询；被超时杀掉的任务会留下子进程，先 `ps` 清理孤儿再重来。
- **测试红了看报告，不要直接重跑全套。** `test_report.py run` 写报告，`test_report.py last`
  解出失败用例并给出只重跑这些模块的命令；修完先重跑单条。
- **CI 是独立任务。** 推完就回到手头的工作，本地门禁才是判据；除非操作者专门问 CI，否则不轮询。
- **改动做完就自己发出去。** 除非另有要求：写进 `changelog.md`、用说明"为什么"的信息提交、推送。

## 硬性规则（编辑边界）

- 配置只存在于 `book.toml`、`base.json`、`style.json`、`data/language/*.json`；脚本一律经 `_config` 读取。
- 手稿只存在于 `books/data/manuscript/`；产物只存在于 `books/dist/`（已 gitignore，可再生）。
- 工具链只放 `books/src/python/`（薄封装可放 `books/scripts/`）；测试只放 `books/src/test/`。
- 会话产物放 `books/data/tmp/`（已 gitignore）。`.claude/` 属于运行工具的运行时数据，不主动写入。
- 证据目录（`books/test-reports/`、`books/data/archive/`）是日期副本，不是正文：已 gitignore，
  并由 `_config.excluded_dirs()` 从门禁排除，不得当手稿或文档判。
- 文档与代码注释不留过程痕迹（评审过程、批次编号、带日期的计划、完成清单）；版本历史只写
  `changelog.md`。追踪编号（`rf-N`、`plan-N`）只属于 `review-findings.md` 与 `plan.md`：
  其他文档与注释不得引用，标识符与文件名不得编码这些编号。`audit/traces.py` 与
  `audit/doc_drift.py` 共同保证这条，以及路径、脚本、章节、版本的漂移检查。
