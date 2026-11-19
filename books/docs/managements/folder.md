# 目录结构（books/）

> 本文是 `books/` 下目录与文件职责的唯一说明。`CLAUDE.md` 只保留指向本文的链接，
> 结构与归属变更时只改这一份。

## 1. 顶层结构

```text
books/
  data/                      # 输入数据：配置 + 手稿 + 机器维护的状态
    tmpl/
      book.toml              # 内容组织：路径、章节顺序、必备段落、书籍元信息
    config/
      config.json            # 工具链策略：阈值、图注词表、源码树位置、覆盖率棘轮
    baselines/
      ascii-baseline.json    # ASCII 图已知问题基线（--update-baseline 生成）
      source-symbol-baseline.json  # 源码符号漂移基线
    manuscript/              # 手稿（唯一可编辑的内容源）
      cover.md
      front/                 # 前件：序、版权、阅读指南
      ch1-2-architecture.md
      ch3-packages.md
      ch4-5-modules-processes.md
      ch6-1-data-structures.md
      ch6-2-storage-algorithms.md
      ch6-3-query-algorithms.md
      ch7-sql-execution.md
      ch8-query-optimizer.md
      ch9-10-persistence-locking.md
      ch11-12-guide-summary.md
      appendix-a-case-studies.md
      appendix-b-version-changes.md
      back/                  # 后件：glossary.md / references.md / index.md
  src/
    python/                  # 交付工具链（27 个脚本 + _config/_fsutil/_mdutil）
    test/                    # unittest 测试套件（单元 + 集成 + 真实书稿回归）
  dist/                      # 交付产物（生成物，gitignored）
    h2-source-code-analysis.md
    h2-source-code-analysis.html
    h2-source-code-analysis.pdf
    h2-source-code-analysis-print.pdf
    h2-source-code-analysis.epub
  docs/
    managements/             # 项目管理文档（见 §2）
    manuals/                 # 使用手册（how-to-use.md：脚本用法唯一说明）
    plan/                    # 带日期的计划文档
```

## 2. 管理文档

```text
books/docs/managements/
  README.md                  # 索引与职责说明
  requirements.md            # 当前范围与交付物
  plan.md                    # 工作流、维护策略、风险、后续工作
  testplan.md                # 质量门禁与验证命令（验证的唯一权威）
  changelog.md               # 版本历史
  review-findings.md         # 评审问题与关闭状态
  folder.md                  # 本文件：目录结构
  archive/                   # 历史文档
```

## 3. 归属规则

- **配置分两层、只有一个入口**：内容组织看 `data/tmpl/book.toml`，工具链策略看
  `data/config/config.json`；脚本统一通过 `_config` 读取，禁止硬编码。
- **基线与状态归 data**：`data/baselines/` 存放机器维护的已知问题记账，不放人写文档。
- **手稿只在 `data/manuscript/`**：`dist/` 里的合并 Markdown 是生成物，不手改。
- **产物只在 `dist/`**：`*.html`、`*.pdf`、`*.epub`、`*.log` 全部 gitignored，
  由 `make.py build` / `make.py deliver` 重新生成。
- **工具链只在 `src/python/`**：正式交付脚本；临时脚本不得入库。
- **测试只在 `src/test/`**：`make.py test` 跑全部；`make.py cover` 带覆盖率棘轮。
- **管理文档只在 `docs/managements/`**：需求、计划、测试、变更、评审批次分文件维护，
  互不重复。

## 4. 常用入口

```bash
python books/src/python/make.py check      # 全部质量门禁（不写产物）
python books/src/python/make.py build      # cover 统计 + 合并 md + HTML
python books/src/python/make.py test       # 单元 + 集成测试
python books/src/python/make.py cover      # 覆盖率（带棘轮阈值）
python books/src/python/make.py deliver    # build + PDF + verify + EPUB（按需）
python books/src/python/make.py doctor     # 可选依赖（pandoc / playwright / pypdf）
```

## 5. 不入库的临时产物

临时修复脚本、压缩包、`__pycache__`、过程性产物一律不入库：正式脚本只进
`src/python/`，仓库级会话产物只进 `.claude/`。
