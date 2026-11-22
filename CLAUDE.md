# CLAUDE.md

本仓库中 Claude Code 的工作约定。保持简短——细节都在 `books/` 里。

## 仓库范围

1. `h2/` —— 上游 H2 v2.x Java SQL 数据库源码（Maven，JDK 11+）。
2. `books/` —— 面向 H2 内部实现的源码分析书（中文），以及审阅手稿、渲染
   HTML/PDF/EPUB 的工具链。

## 常用命令

`books/scripts/bookctl` 会自行解析项目虚拟环境；请用它，不要用裸 `python`
（只有 `books/.venv` 才允许运行工具链）。

```bash
cd h2 && ./mvnw compile                    # 引擎构建
books/scripts/bookctl check                # 全部门禁（只读）
books/scripts/bookctl build                # 封面统计 + 合并稿 + HTML + 当日归档
books/scripts/bookctl test                 # 快档（约 25 秒）；--full 加浏览器与 pandoc
books/scripts/bookctl deliver              # PDF + 目录链接 + 校验 + EPUB + 校验 + 归档
books/scripts/bookctl make cover           # 覆盖率棘轮与单文件下限
books/scripts/bookctl doctor               # 可选依赖自检
```

## 去哪里查

| 主题 | 权威文件 |
| --- | --- |
| 目录结构与文件归属 | `books/docs/managements/folder.md` |
| 命令：日常使用 | `books/README.md`（快速开始） |
| 命令：验证流程 | `books/docs/managements/testplan.md` §1 |
| 流程：先做什么后做什么 | `books/docs/manuals/how-to-use.md` |
| 门禁判据与级别 | `books/docs/managements/testplan.md` §2 |
| 写作与格式约定 | `books/docs/managements/style-guide.md` |
| 内容组织（路径、章节顺序） | `books/data/tmpl/book.toml` |
| 工具链策略（阈值、预算、基线） | `books/data/config/base.json`、`books/data/config/style.json` |
| 单项迭代的设计与计划 | `books/docs/plan/<topic>/`（`design.md`、`plan.md`） |

## 工作节奏

- **先量后跑，取能定论的最小命令。** 先拿到量级（`--collect-only`、单文件、
  子集 `--durations`）。整套快档约 25 秒，出现"几分钟"就说明某个用例卡住了；
  单文件或单个用例优先，全量只在收尾跑一次。
- **同一时刻只跑一个重活，且不长占前台。** 预计超过约 2 分钟的放到后台，先说
  预计时间，再等退出信号——不用 `sleep` 轮询。被超时杀掉的任务会留下子进程：
  先 `ps` 清理孤儿，再重新开始。
- **测试红了看报告，不要直接重跑全套。** `python books/src/python/test_report.py run`
  会把结果写进 `books/test-reports/<时间戳>/`，`test_report.py last` 解出失败
  用例并给出只重跑这些模块的命令；修完先重跑单条，再决定是否跑全量。
- **CI 是独立任务。** 推完就回到手头的工作：本地门禁才是判据。除非操作者专门
  问 CI，否则不轮询 `gh run`。
- **改动做完就自己发出去。** 除非操作者另有要求，每次改动的收尾是：写进
  `books/docs/managements/changelog.md`、用说明"为什么"的信息提交、推送。

## 硬性规则

- 配置只存在于 `books/data/tmpl/book.toml`、`books/data/config/base.json`、
  `books/data/config/style.json` 与 `books/data/language/*.json`；脚本一律通过
  `_config` 读取。
- 手稿只存在于 `books/data/manuscript/`。
- 交付产物只存在于 `books/dist/`（已 gitignore，可再生）。
- 工具链代码只放在 `books/src/python/`（薄封装可放 `books/scripts/`）；测试只放在
  `books/src/test/`。
- 会话产物（临时脚本、草稿、导出物）放 `books/data/tmp/`（已 gitignore）。
  `.claude/` 属于运行工具的运行时数据，不属于仓库，不主动往里写东西。
- 证据目录只做日期副本，不是正文：`books/test-reports/` 与 `books/data/archive/`
  已 gitignore，并通过 `_config.excluded_dirs()` 从所有门禁中排除；不得把它们当
  手稿或文档来判。
- 文档与代码注释里不留过程痕迹（评审过程、批次编号、带日期的计划、完成清单）；版本历史
  只写在 `changelog.md`。追踪编号（`rf-N`、`plan-N`）只属于 `review-findings.md`
  与 `plan.md`：其他文档与代码注释都不得引用，标识符与文件名也不得编码这些编号。
  `audit/traces.py`（docs 与 code 两个范围）与 `audit/doc_drift.py` 共同保证这条，
  以及路径、脚本、章节、版本的漂移检查。
