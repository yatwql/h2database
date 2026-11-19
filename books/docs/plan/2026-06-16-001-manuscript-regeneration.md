# 手稿重生成：事实驱动流水线与十轮质量复盘

> 版本：v1.0 · 2026-06-16
> 关联：`plan.md` §9、`folder.md`、`manuals/how-to-use.md`

## 1. 目标

上游源码更新后，手稿不再靠人工逐章重写，而是把"源码事实"沉淀成可复现的生成链，
并用可度量的十轮复盘把质量逐轮抬高：

1. 结构完整性：章节、必备段落、练习、跨章引用 100% 合规。
2. 事实可核验：`Class.java:line` 坐标、包职责、公开方法清单全部由脚本核验。
3. 可读性：版图 → 类型 → 入口 → 阅读路径的信息阶梯，读者可按需下钻。
4. 可复现：同一份源码 + 配置，任意时刻重生成得到相同手稿。

## 2. 生成链（阶段一）

```text
源码树 ──digest_source.py──▶ data/state/source-inventory.json
                                    │
book.toml[chapters.packages] ──plan_outline.py──▶ data/state/outline.json
                                    │
                                    └──build_manuscript.py──▶ data/manuscript/*.md
```

- `digest_source.py`：包/文件的规模、`package-info` 首句、核心类型与公开方法。
- `plan_outline.py`：章节 → 包的映射，输出覆盖矩阵（缺包即报）。
- `build_manuscript.py`：按章节渲染 §模块版图、§核心类型、§关键 API 与源码坐标、
  §阅读路径、§本章小结、§延伸思考、§延展阅读。

## 3. 十轮复盘设计

每轮固定四步，产出只进生成器与配置，**不写入手稿正文，也不在代码里留复盘痕迹**。

| 轮次 | 关注点 | 度量口径 | 通过线 |
|---|---|---|---|
| R1 | 结构合规 | `make.py check` 通过项数 | 全绿 |
| R2 | 事实密度 | 每章 `.java:line` 坐标数、包覆盖数 | 坐标 ≥ 15/章，覆盖 100% 映射包 |
| R3 | 信息阶梯 | 每章"版图→类型→入口→路径"四段齐备 | 4/4 |
| R4 | 读者负担 | 单章行数、单表行数、平均段长 | 章节 150–400 行，表 ≤ 20 行 |
| R5 | 术语衔接 | 术语表命中率、首次出现是否有指引 | 每章 ≥ 5 术语命中 |
| R6 | 交叉引用 | 跨章引用数、断链数 | ≥ 1/章，断链 0 |
| R7 | 练习质量 | 每章题量、难度分布、回顾锚点 | 4 题/章，★/★★/★★★ 齐备 |
| R8 | 图注与图示 | 图注动宾违规、ASCII 宽度违规 | 0 新增 |
| R9 | 交付一致性 | 合并 md/HTML/PDF/EPUB 与源一致 | 全绿 |
| R10 | 复现性 | 两次重生成哈希一致 | 100% 一致 |

## 4. 度量实现

- 结构类：`make.py check`（14 道门禁）。
- 事实类：`source_freshness_check.py`（坐标与 `Class.method` 断言）、
  `plan_outline.py` 的覆盖矩阵。
- 文本类：`check_style.py`、`readability_check.py`、`_audit_captions.py`、
  `_audit_ascii.py`、`balance_check.py`。
- 复现类：连续两次 `make.py build` 的 HTML 哈希比对（CI 已接入）。

## 5. 约束

- 手稿与代码中不出现"第 N 轮复盘/评审记录"等过程性文本。
- 复盘结论只落到：生成器代码、`book.toml`/`config.json`、本目录下的设计文档。
- 上游源码变动后执行：`digest_source.py` → `plan_outline.py` → `build_manuscript.py`
  → `make.py check` → `make.py build`。
