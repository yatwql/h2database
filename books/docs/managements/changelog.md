# 变更日志

格式基于 [Keep a Changelog](https://keepachangelog.com/)。

> 软件：bookwright — 源码分析成书工具 v0.2
> 版本：v0.2
> 定位：**版本变更记录，只留当前开发段**——写“变了什么”；问题编号与修复细节见
> `review-findings.md`，设计理由见 `technical.md`。已发布版本由 git 标签保留。

---

## [0.3-dev] - 开发中（未发布）

### 变更

- **强断言必须有依据（plan-15 阶段 1）**：新增判据 `audit/claims.py`——正文里的强断言（总是/绝不/唯一/保证了…）若句内没有 `文件:行号`、`Class.method(` 或反引号类名，按章计入「未带依据」；先量后治：本书记下 35 条作基线，计数只许降不许升。图注导语、表格与代码块不算正文。断言词表在 `style.json [claims].markers`，书可覆盖。
- **坐标密度立项（plan-19）**：本书每千行仅 5 处坐标、25 处符号引用、84% 的实质段落无可回溯依据；按章设置密度下限的迭代已立项，先只读量化、再补依据、最后开判。

## 版本口径

本文件记录工具链的版本段，版本号取 `lib/_version.py`。书籍版本（`book.toml`）与
封面统计不由本文维护；两者的历史都在 git 中。

## 归档
- [`archived_changelog.0.1.md`](../archive/v0.1/archived_changelog.0.1.md) — 0.1
- [`archived_changelog.0.2.md`](../archive/v0.2/archived_changelog.0.2.md) — 0.2
