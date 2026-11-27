# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.2-dev
> 定位：**版本变更记录，只留当前开发段**——写“变了什么”；问题编号与修复细节见
> `review-findings.md`，设计理由见 `technical.md`。已发布版本由 git 标签保留。

---

## [0.2] - 开发中（未发布）

### 变更

- **编辑要素开始可判（plan-14 阶段 1）**：新增书级配置 `data/book/editing.toml`（风格档三选一 +
逐项覆盖）与三档预设 `lib/_editorial.py`（manual / tutorial / hands-on），新增判据 `audit/editorial.py`
量出每章的 学习目标 / 要点回顾 / 常见误区 / 表格密度，并按 `data/baselines/editorial.json` 棘轮判定：
必选元素低于下限、或任一计数低于基线即失败。本书按 tutorial 档登记但三项尚未补齐，缺口已记录在基线里，
补内容按 `docs/plan/editorial-profile/` 推进。
- **印刷版重新省页（plan-17 ③）**：纸面阅读度量与自适应解算改为配置驱动（`layout_print_chars_per_line`
  等），标准版 920 页、印刷版 935 → **829 页（−9.9%，目标 ≤874）**，`DENSITY`、`CODE_LEAD`、`TOC_LINKS` 全绿。
- **章节文件篇幅比的计量范围**：`balance.py` 只量正文各章节文件，附录与前件在报告里列在 `scope.excluded_files`
  下明示不计入——原来的最小值来自附录 B（68 行），比值由参考件而非正文决定。ch7-8 拆成 ch7/ch8 后
  该比值 120.4 → **2.991**，目标经决策定为 **3.0**（再拆 ch4-5 需重编号 105 张图，代价与收益不成比例）；
  比值超目标时判据返回失败，不再只是打印一行。
- **跨章引用有了密度判据（plan-17 ④）**：`crossrefs.py` 新增每章引用下限（`style.json chapters_min_cross_refs
  = 2`），每条 `详见第X章《…》` 仍须解析到存在的章与 H1 标题；索引下限按实测收到 185/112/145/300。实测跨章引用
  29 → **37 处**，索引 331 条全部可达，不留空格子内容。
- **通用性写成约束并机检**：`technical.md` 新增 §2.4「不绑定某一本书，也不绑定某一棵源码树」——书的专有词
  只能存在于 `data/`，仓库路径/语言/后缀只能从 `[sources]` 读。`check_architecture.py` 新增
  `book_vocabulary` 检查：词表由书在 `base.json [toolchain]` 声明（当前为 `MVStore`、`TransactionStore`、
  `JdbcStatement`、`SessionLocal`、`H2 Console`），整词匹配 `src/python/` 全文，命中即报，随架构层一起
  是 P0 门禁（关闭了「书的内容写进工具链」这条长期无门禁的口子）。
- **对比类论述开始表格化（plan-13 阶段 1–2）**：附录 B 的十二项 MVStore 变更与十一项事务子系统变更
  改成两张 3 列表（变更点 / 之前 → 现在 / 读者影响），第 7 章补一张 Statement 与 PreparedStatement
  的 5 行对照表（编译时机、N 次开销、参数传递、注入面、适用场景）。改写只换呈现：每条事实逐条对应，
  图号、坐标与图注未变；`make.py build` 与全量门禁绿。
- **源码变化报告到「变了什么」**：`lib/_source_state.py` 比对 `source-inventory.json` 与
  `source-inventory.prev.json`，给出新增/移除的包与包/文件/行的增减、上次分析日期
  （`已变化（新增包 x 等 4 个，包 +3 / 文件 +12 / 行 +1,204，上次分析 2026-11-24）`）。
  `digest.py` 写完清单后打印、`chapters.py` 刷新事实块前打印、TUI 在按 1/2 前打印；模块自己不绑定
  配置，路径由调用方传入。
- **浏览器启动统一到 `lib/_browser.py`**：core 上限归零、`TMPDIR` 指向书内临时目录。此前一次渲染崩溃
  在仓库根目录留下 36 MB 的 `core.3077190`；现在 `.gitignore` 忽略 `core.*`，已有的那份移到
  `books/data/tmp/`。Playwright 的 `launch()` 既不接受 `cwd` 也不接受 `preexec_fn`，所以只有环境变量与
  进程资源限制两条路（参数名写错曾让 `pdf_toc_links` 在 0.41 秒内失败）。
- **PDF 的 Type3 归零**：练习类型 emoji 与圈号 ①–⑳ 没有可嵌入字体覆盖，浏览器只能描边
  （六月版标准 43、印刷 6,684 个 Type3 对象）。`merge.py` 在投递稿里把 emoji 换成
  `【理解】/【分析】/【动手】`、圈号换成 `(1)–(20)`，手稿不动；两版 PDF 现在均为 **0**。
- **TUI 按产物汇报**：按 6 先给顺序 `Markdown → HTML → EPUB → 标准版 PDF → 印刷版 PDF`，随后
  `Markdown：完成（1.2s）`、`标准版 PDF · 目录链接：完成（3.4s）`、`印刷版 PDF · 校验：完成（18.0s）`；
  静默 10 秒仍有心跳，时长写成「1 分 40 秒」而不是易读错的 `1:40`。
- **印刷版进入步骤表**：`make.py print` = `print_pdf`（渲染后写回目录链接目标）+ `verify_print`
  （`verify_pdf --print`）。实测 944 页 / 7.49 MB / 正文行距比 1.459，死链 0。
- **框线闭合改成存量记账（plan-17 第 1 项）**：`readability.py` 按图统计角字符是否成对，表格底边合并列、
  树形分支（`├──`/`└──`）这类画法每图必中，全库 926 条告警里绝大部分不是可以改一个字符就消失的错。
  判据因此从「零告警」改为按文件记账：`data/baselines/readability-box-drawing.json`（配置项
  `base.json [baselines].readability_box`）记下每个手稿文件的存量条数，某文件条数上涨或出现基线外的文件即
  失败，条数下降则提示收紧记录；`--update-baseline` 写回。存量分布：ch7-8 276、ch9-10 186、ch4-5 137、
  ch6-3 76、ch3 52、ch6-2 52、ch1-2 50、ch11-12 38、ch6-1 38、附录 A 21。同时补齐 ch4-5 一段断开的框线
  （`└─────` 缺 `┘`），该文件 138 → 137。

## 版本口径

本文件记录工具链的版本段，版本号取 `lib/_version.py`。书籍版本（`book.toml`）与
封面统计不由本文维护；两者的历史都在 git 中。

## 归档

> 已发布版本只在上面的归档文件里；本文只留当前开发段。

- [`archived_changelog.0.1.md`](../archive/v0.1/archived_changelog.0.1.md) — v0.1（2026-11-26 发布）
