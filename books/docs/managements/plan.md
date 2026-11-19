# 实施与维护计划

> 版本：v6.5 · 更新：2026-06-16

## 1. 当前状态

- 手稿由源码事实驱动生成：`ingest/digest.py` → `outline.py` → `chapters.py`。
- 章节采用单主责包映射，非主责章节用跨章索引跳转。
- 四层配置：`data/tmpl/book.toml`（数据组织）、`data/config/base.json`（基础）、
  `data/config/style.json`（风格）、`data/language/zh.json`（语言包）。
- 质量门禁：结构（`audit/structure.py`）、事实（`audit/source_refs.py`）、
  图书质量（`audit/book_quality.py`）、文风（`audit/prose_quality.py`）、
  交付（`render/verify_pdf.py`、`render/verify_epub.py`）。
- 工具链设计说明见 `books/docs/plan/toolchain-design.md`。

## 2. 例行工作流

```bash
python books/src/python/make.py check      # 全部门禁（只读）
python books/src/python/make.py build      # 统计 + 合并 Markdown + HTML
python books/src/python/make.py test       # 单元与集成测试
python books/src/python/make.py deliver    # 按需：PDF + EPUB + 校验
```

源码更新后重生成手稿：

```bash
python books/src/python/ingest/digest.py
python books/src/python/ingest/outline.py
python books/src/python/ingest/chapters.py
python books/src/python/make.py check
```

## 3. 维护策略

- **配置唯一**：路径、阈值、文案、模板只在配置文件中维护，脚本不硬编码。
- **事实优先**：手稿中的源码坐标与 `Class.method(` 断言由脚本核验，上游升级后重生成。
- **基线记账**：已知问题记录在 `data/baselines/`，阈值收紧前先清账。
- **门禁前置**：`make.py check` 通过才允许构建交付物。

## 4. 后续增强项

| 项目 | 说明 | 优先级 |
| --- | --- | --- |
| 语言包扩展 | 支持英文与技术文档双语输出 | P2 |
| 图示增强 | 关键流程由 ASCII 升级为结构化图 | P3 |
| 增量生成 | 仅重渲染变更章节，缩短大书构建时间 | P3 |
| 更多源码语言 | 从 Java 扩展到 Kotlin/Go 等（解析器可插拔） | P4 |

## 6. 在建项

| 项 | 目标 | 交付物 | 约束 |
| ---- | ------ | -------- | ------ |
| A 多入口（已完成） | 同一工具链可从 CLI / TUI / Web 启动 | `app/cli.py`、`app/tui.py`、`app/web.py` | 全部经 `app/` 层，复用 `ingest`/`audit`/`render`，不复制业务逻辑 |
| B LLM 配置（已完成） | 按场景/书籍/章节选择不同 provider | `data/config/llm_settings.json`、`data/config/llm_provider.json`、`lib/_llm.py` | 密钥只读环境变量；默认 mock，离线可跑；模型参数与选择逻辑外置 |
| C 启动脚本（已完成） | Windows / Linux 一键启动 | `scripts/{launch.sh,launch.ps1}` | 脚本只做环境探测与入口转发，不含业务逻辑 |

## 5. 风险与应对

| 风险 | 应对 |
| --- | --- |
| 源码升级导致坐标漂移 | 重跑 stage 1，`source_refs.py` 复核 |
| 统计数字与手稿不一致 | `make.py build` 重新统计，`structure.py` 校验 |
| 章节结构回归 | `book_quality.py` 与 `structure.py` 拦截 |
| 交付物失效 | 交付前运行 PDF/EPUB 校验 |
