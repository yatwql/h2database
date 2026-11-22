# 日常使用流程

> 软件：bookwright — 源码分析成书工具 v0.1
> 维度：**任务流水线**——从动笔到交付，每一步做什么、做完怎么确认。

本文只回答"我现在要完成某件事，按什么顺序做"。命令的完整参数见
[CLI 使用](how-to-use-cli.md)，入口清单见[脚本与命令参考](scripts-and-reference.md)。

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

   打开 `books/dist/h2-source-code-analysis.html` 即可查看。

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

3. 到 `books/dist/` 取件：`h2-source-code-analysis.pdf`、`h2-source-code-analysis.epub`，以及可用于二次排版的 `h2-source-code-analysis.md` 与 `h2-source-code-analysis.html`。

**做对的判据**：`deliver` 以 `OK` 结束；PDF 页数与体积在预算内；目录可点击且跳转落在正确章节。

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

## 7. 不要做的事

- 不要直接编辑 `books/dist/` 里的任何文件：那是产物，下次构建会被覆盖。
- 不要手工按顺序调用多个审计脚本：入口已经把顺序与依赖固定下来了。
- 不要把历史版本的稿子放回 `books/data/manuscript/`：用快照方式保留（见[配置指南](how-to-config.md)）。
- 不要为了通过门禁而放宽阈值：先确认是文档该改，还是策略确实需要调整。
- 不要随手重记体量基线：要先提交手稿、要有人具名（`--reviewed-by`）、只能抬高；
  确实要收缩再写明理由（`--accept-shrink --reason`），这些都记在基线文件里，事后能查。
