# 依据化：实施计划

> **状态：未开工**——本文是计划文本；判据与分析器均未改动。
>
> 软件：bookwright — 源码分析成书工具 v0.2
> 版本：v0.2
> 定位：**动作与验收**——先上 claims 判据立规矩，再补三类事实块。设计看同目录 `design.md`。

---

## 1. 前提

- 坐标形状已由 `sources.suffixes` 统一（多语言可用）；`audit/source_refs.py` 可解析坐标。
- 事实块机制已在用（`<!-- generated:名字 -->`），新增块不改机制。

## 2. 阶段

### 阶段 1：claims 判据

1. 句式词表进语言包；判据扫正文（跳过代码块、表格、提示块），对「强断言但无依据」的句子报告文件与行号。
2. 用本书跑一次，得到基线（预期数百条），据此决定先补哪几章。

**通过条件**：判据能红（构造一句无依据的断言即失败），本书报告条数可复现。

### 阶段 2：failure 与 invariants 事实块

1. 各语言适配器新增抽取：错误类型与抛出点、断言与 must/never 注释；`chapters.py` 插块，正文可引用。
2. 抽取结果同时作为「常见误区」的候选来源（与编辑风格档联动）。

**通过条件**：两块的条目能在正文被引用；空块（语言不支持或源码无此类）不报错。

### 阶段 3：paths 事实块

1. 从配置的入口点做语言内调用图，产出入口 → sink 的路径骨架；断链显式标注。
2. 本书至少产出 1 条完整链路，作为「实战链路」素材。

**通过条件**：路径首尾坐标可解析；断链处有标注且判据不红。

## 3. 命令

```bash
books/.venv/bin/python books/src/python/make.py check --only claims
books/.venv/bin/python books/src/python/ingest/digest.py
books/.venv/bin/python books/src/python/ingest/chapters.py --refresh-facts
```

## 4. 回退

claims 判据默认按「报告」级进 check；事实块为新增块，删掉插块即恢复原骨架。
