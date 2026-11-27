# 日常使用流程

> 软件：bookwright — 源码分析成书工具 v0.2-dev
> 维度：**任务流水线**——从动笔到交付，每一步做什么、做完怎么确认。

本文只回答"我现在要完成某件事，按什么顺序做"。命令的完整参数见
[CLI 使用](how-to-use-cli.md)，入口清单见[脚本与命令参考](scripts-and-reference.md)。

## 一次全量构建看到什么

按 `6` 之后，界面先给出产物顺序 `Markdown → HTML → EPUB → 标准版 PDF → 印刷版 PDF`，随后逐步打印
「产物 + 阶段」：`Markdown：完成（1.2s）`、`标准版 PDF · 目录链接：完成（3.4s）`、`印刷版 PDF · 校验：完成（18.0s）`。
子进程静默超过 10 秒会补一行 `… 已用 2 分 10 秒，仍在执行`，所以长时间渲染不会看起来像卡死。
两个 PDF 共用同一套渲染管线，但阶段名按产物归属，能把它们区分开。

按 `1`/`2` 之前，界面会先说被分析树相对上次分析的变化：
`源码清单：已变化（新增包 x 等 4 个，包 +3 / 文件 +12 / 行 +1,204，上次分析 2026-11-24）`。
没变化时显示「与上次一致」，这时重跑分析不会改动任何事实块。

## 1. 三种日常任务

| 我要做的事 | 走哪几节 | 典型耗时 |
| --- | --- | --- |
| 改一段正文、修一处图注 | §2 | 一分钟内 |
| 新增一章或一节 | §3 | 视篇幅 |
| 出一版可交付的 PDF / EPUB | §4 | 数分钟 |

## 2. 改正文

1. 只改 `books/data/manuscript/` 下的手稿。这是唯一的内容源，产物全部由它派生。
2. 跑一次按改动范围选的门禁：

   ```bash
   books/scripts/check-docs.sh      # 只动了手稿/文档
   ```

3. 看结论：出现文件与行号就按提示改；`✅ pass` 表示这一类问题已经没有了。
4. 想立刻看到效果，重新构建一次：

   ```bash
   python books/src/python/make.py build
   ```

   打开 `books/dist/<book>.html` 即可查看（`<book>` 是书名，见 `book.toml [book] slug`）。

**做对的判据**：同一条门禁从失败变成通过，且没有引入新的失败项。

## 3. 新增一章或一节

1. 写手稿文件，放进 `books/data/manuscript/`。
2. 在 `books/data/book/book.toml` 的 `[chapters] files` 里登记顺序；章节清单决定了合并顺序。
3. 章末补齐四段：本章导读、本章小结、延伸思考、延展阅读，顺序固定。延伸思考每章至少 3 题，每题要有提示行与带锚点的回顾行。
4. 如果这一章负责新的源码包，在 `[chapters.packages]` 里登记归属，避免与别的章重复描述。
5. 跑一遍：

   ```bash
   books/scripts/check-docs.sh
   python books/src/python/make.py build
   ```

**做对的判据**：章节结构门禁通过；封面统计里的章数、图数、行数随之更新；合并稿末尾能看到新增内容。

## 4. 交付一版

1. 先确认手稿是完整的：

   ```bash
   python books/src/python/make.py check
   ```

2. 生成并自动校验三种格式：

   ```bash
   python books/src/python/make.py deliver
   ```

   顺序是固定的：渲染 PDF → 补印刷目录链接 → 校验 PDF → 生成 EPUB → 校验 EPUB。中间任一步失败会立刻停下。

3. 到 `books/dist/` 取件：`<book>.pdf`、`<book>.epub`，以及可用于二次排版的 `<book>.md` 与 `<book>.html`。

**做对的判据**：`deliver` 以 `OK` 结束；PDF 页数与体积在预算内；目录可点击且跳转落在正确章节；
`verify_pdf` 的 `FONTS`（没有退化成 Type3 描边）与 `DENSITY`（行距÷字号、文字占可印高度）为 ok；
`verify_epub` 的 `CHAPTERS` 为 ok（每个正文文件恰好一个一级标题）。

**页面松紧不对时**，不要改代码，改配置后重新标定：

```bash
# 先量当前版式，与参照 PDF 或数字目标比
python books/src/python/render/pdf_metrics.py --compare 参照.pdf dist/书.pdf
python books/src/python/render/pdf_metrics.py --target pages=<目标页数>,chars_per_page=<目标字符数> dist/书.pdf

# 标定结果写回 base.json 的 [toolchain]（只替换那一个数）
python books/src/python/render/pdf_metrics.py --write-back layout_spacing_scale=0.7
```

## 5. 提交之前

```bash
books/scripts/check-fast.sh      # 约 16 秒：格式、结构门禁、全量快档测试
```

这一步与提交钩子跑的是同一套内容；通过再提交，可以避免"提交被钩子打回"的往返。

## 6. 出问题时的顺序

1. 先看是**哪一步**失败：构建、检查、还是交付。
2. 失败输出通常已经给出文件与行号；照它改比读日志更快。
3. 需要完整输出时看 `books/logs/` 下的报告文件（含每步退出码与耗时）。
4. 仍然不明就里，查[常见问题](faq.md)。

## 6.1 门禁说“新问题”时，基线是干什么的

门禁里有一部分判据带**已评审存量**：`data/baselines/` 下的文件记着「目前已知且已接受的问题」。
它不是配置，也不是阈值——是账本：条目只许减少，不许变多；多出来的一条就是这次要处理的新问题。

遇到「新增 N 条 / NEW 漂移 / 无门禁认领」时的顺序：

1. **先当成真问题**：按输出里的文件与行号改文本。绝大多数情况到这一步就结束了。
2. **确认是可接受的现状**（上游改名、历史稿无法回改、判定口径本就如此）：用**那道门禁自己的**
   `--update-baseline` 记账，并在提交信息里写清为什么。不要手改 JSON，也不要用另一道门禁的命令。
3. **查账**：`python books/src/python/manuscript/baselines.py` 列出每个文件的形态、条数与归属门禁；
   加 `--check` 会报空账本、读不出的文件、没有门禁认领的文件与旧文件名。

体量下限另有纪律：先提交手稿、要有人具名（`--reviewed-by`）、只能抬高；确需收缩要写理由
（`--accept-shrink --reason`）。这些安排为什么这样定，属于内容质量方针的范围（管理文档），本手册只讲怎么做。

## 7. 不要做的事

- 不要直接编辑 `books/dist/` 里的任何文件：那是产物，下次构建会被覆盖。
- 不要手工按顺序调用多个审计脚本：入口已经把顺序与依赖固定下来了。
- 不要把历史版本的稿子放回 `books/data/manuscript/`：用快照方式保留（见[配置指南](how-to-config.md)）。
- 不要为了通过门禁而放宽阈值：先确认是文档该改，还是策略确实需要调整。
- 不要随手重记体量基线：要先提交手稿、要有人具名（`--reviewed-by`）、只能抬高；
  确实要收缩再写明理由（`--accept-shrink --reason`），这些都记在基线文件里，事后能查。
