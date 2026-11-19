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
