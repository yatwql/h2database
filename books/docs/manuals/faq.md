# 常见问题

> 维度：**排障——出了问题按症状查原因与处理动作**
> 软件：bookwright — 源码分析成书工具 v0.1

## 运行环境

**Q：`pandoc`/`chromium` 没装，能跑吗？**
能。核心链路（digest → outline → chapters → 结构门禁）只依赖标准库；缺
`pypdf`/`playwright`/`pandoc` 时相关脚本以退出码 2 报错并给出安装提示，
`make.py check` 不受影响。

**Q：能不能不写 python 路径？**
可以。用 `books/scripts/bookctl <动作>`（Windows：`bookctl.ps1`），它自动选择
`books/.venv` 里的解释器；`bookctl make …` 透传 `make.py`。

**Q：为什么启动器找不到 Python？**
先跑 `books/scripts/bootstrap.sh`（Windows：`bootstrap.ps1`）创建 `books/.venv`。
启动器查找顺序：`books/.venv` → `$PYTHON` → `python3`。

**Q：`BOOK_ROOT` 是什么？**
`lib/_config.py` 用它把整条链路指向另一份书籍目录（测试与多书场景用）。
默认是 `books/`，一般不需要手动设置。

## 配置

**Q：改书名/章节顺序要改代码吗？**
不用。书名、章节清单、标题、H1 编号、章节→包映射都在 `data/book/book.toml`；
见 `how-to-config.md`。

**Q：阈值/预算/词表在哪改？**
`data/config/style.json`（风格与质量阈值）与 `data/config/base.json`
（源码树、预算、日志）。改完跑 `make.py check`。

**Q：新增一门语言要改哪里？**
`ingest/languages/` 里加一个分析器模块并在 `__init__.py` 注册，然后在
`base.json [sources].languages` 加上它。其余阶段无需改动。

## 质量门禁

**Q：`make.py check` 报了 `doc_drift`，怎么修？**
文档里引用的路径/脚本/章节名/版本号与仓库不一致。按报告里的位置改成实际路径，
或把过时文字删掉；`--json` 可拿到结构化列表。

**Q：`gate_trace` 说某道门禁没有登记？**
每个检查步骤都要在质量计划里登记一行（编号、判据、级别、脚本）。加门禁时补上这一行，
门禁与文档才能双向对上；漏登记等于这道门禁对外不存在。

**Q：测试红了，怎么知道挂了哪几条？**
跑 `python books/src/python/test_report.py run`，再用 `test_report.py last`：它列出失败用例
与断言首行，并给出 `python -m pytest books/src/test/<模块>.py -q` 的只重跑命令；不要动辄重跑全量。

**Q：`prose_quality` 分数不够？**
按报告里最低的维度改生成器或配置（句长、列表占比、小节深度等），阈值在
`style.json [prose]`；不要为凑分放水阈值。

**Q：`source_refs` 报 NEW 漂移？**
上游源码变了。跑 `source_refs.py --suggest` 看改名建议，复核后用
`--update-baseline` 记账（基线在 `data/baselines/`）。

## 版本

**Q：三个版本分别在哪改？**
工具版本在 `lib/_version.py`（semver，改工具时 bump）；源码版本自动取
`[sources].version` 或源码清单（pom/pyproject/Cargo），也可显式覆盖；书籍版本在
`book.toml [book].version`。三者由 `version_consistency.py` 校验，`bookctl status`
与 TUI 顶部都会显示 `工具 / 源码 / 文档`。

## 交付

**Q：产物在哪？为什么 `git status` 看不到？**
`books/dist/`（HTML/PDF/EPUB/合并 Markdown 的部分文件）与 `books/logs/` 是
生成物，已 gitignore；需要时用 `make.py build|deliver` 重新生成。

**Q：PDF 校验失败说 outline 数量不对？**
PDF 是旧稿。重新 `make.py build` 后再 `to_pdf`（或 `make.py deliver`）。

**Q：手稿与产物的历史副本在哪？**
`books/data/archive/<书>/<日期>/{manuscript,dist}/`，由 `make.py build` 与 `deliver` 各存一份；
保留窗口取 `base.json [archive] retention_days`（缺省 45 天），过期目录自动清理。

## 日志

**Q：日志在哪、怎么更详细？**
`books/logs/bookwright.log`，每天回滚、默认保留 14 天。要更详细：
`BOOK_LOG_LEVEL=DEBUG`（或改 `base.json [logging].level`）。控制台只打印
WARNING 以上，避免刷屏。

## LLM

**Q：没有 API key 能跑吗？**
能。加一个 `{"kind": "mock"}` provider 并把它设为默认即可离线返回确定性文本；真实 provider 的密钥只从
`api_key_env` 指定的环境变量读取，不落盘。

**Q：怎么让某一章用不同 provider？**
在 `llm_provider.json` 的 `routing.chapter` 里按章节文件名指定；优先级
`chapter > book > scenario > default_provider`。

## 一套工具链能同时管几本书吗？

能。每本书是一个**书根**（目录里有 `book.toml`），互不共享 `dist/`、`data/manuscript/`、
`data/state/` 与体量基线。切换方式：`--book <书目录>`、`BOOK_ROOT`，或在 TUI 主菜单按
`6`、在 Web 顶部下拉框选择（候选来自 `book.toml [paths].library` 指定的目录）。

## `data/book/` 下有两个 toml，哪个才算「这本书」？

`book.toml`。它是身份文件（标题、路径、章节表、源树、版本表），`case-studies.toml` 只是
它的一份内容数据（附录 A 的案例流水线），缺了不影响这本书成立。

## 被分析的源码路径在哪配？换书会不会换源？

在 `data/book/book.toml [sources]`（`src_main` 或 `roots[]`），路径相对书根、可以指向书外。
换书就换源——「读哪棵树」属于书的身份；语言与后缀这类分析口径留在 `base.json [sources]`。

