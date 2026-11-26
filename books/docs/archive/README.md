# 版本归档

> 一版一个目录：`v<major>.<minor>/`，如 `v0.1/`。这里是**已发布版本**的台账与**已完成**
> 迭代设计的唯一存放处；主文档只留当前开发段与索引。

## 目录内容

```text
v0.1/
  archived_changelog.0.1.md        # 该版本的变更段（从 changelog.md 迁出）
  archived_plan.0.1.md             # 发布时的计划快照
  archived_review-findings.0.1.md  # 该版本「已修复」表（从台账迁出）
  <迭代主题>/                       # 已完成的迭代设计，整目录移入
    design.md
    plan.md
```

前三份由 `core/docs_archive.py` 迁出，迁移是机械动作、可重复执行、幂等；**哪些迭代算完成
由人指定**（`--topic`），脚本不替你判断。第四类目录只放 `design.md`、`plan.md`、`README.md`；
版本目录顶层除三份台账外，还允许随它们一起归档的历史快照（`.md`），其余文件视为多余。

## 规则

1. 每份归档文件头部有两行自述：`> 涵盖版本：X.Y` 与 `> 归档时间：YYYY-MM-DD`。
2. 主文档 `changelog.md`、`plan.md`、`review-findings.md` 各有一个 `## 归档` 小节，
   列出全部版本目录；链接必须能打开。
3. 已归档的版本不得再以 `## [X.Y]` 或「本版本已修复（X.Y）」形式留在主文档。
4. 迭代目录名一律小写连字符语义名，不含 `plan-N`、`rf-N` 等追踪编号。
5. 布局由 `audit/doc_archive.py` 机检（`make.py check` 的一步），空归档视为通过。

## 用法

```bash
python books/src/python/core/docs_archive.py --version 0.1 --dry-run          # 先看动作
python books/src/python/core/docs_archive.py --version 0.1 --topic <迭代目录>  # 再执行
```
