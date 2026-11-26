# 出炉收口：实施计划

> **状态：已交付**——四项均已落地，成果见 `docs/managements/changelog.md`；本文保留为验收口径的记录。
>
> 软件：bookwright — 源码分析成书工具 v0.2-dev
> 版本：v0.2-dev
> 定位：**动作与验收**——四项分别独立提交、独立验收。设计看同目录 `design.md`。

---

## 1. 前提

- `balance.py` 已有 max/min 判据与目标值（配置项），只是当前值远超目标。
- `manuscript/renumber.py` 能按 `[chapters.numbering]` 的差异重编号并改写引用。
- 印刷版自适应解算已可用（`print_pdf.py --adaptive`），纸面阅读度量是配置。

## 2. 动作与验收

### 2.1 章节均衡

1. 在 `book.toml` 里把过长的一章拆成两章（只改章节清单与编号映射），跑 `renumber.py` 迁移章号引用。
2. 拆后重跑 `balance.py`，比值逐次降低；目标先 ≤3.0，再 ≤2.5。

**验收**：`balance.py` 绿；`structure.py`、`index_xrefs.py`、`source_refs.py` 不变红。

### 2.2 印刷版密度

1. 调低纸面阅读度量（配置项，单位是正文每行字符数），重跑自适应印刷。
2. 目标：印刷版页数低于标准版 5% 以上，且 `DENSITY`、`CODE_LEAD`、`TOC_LINKS` 全绿。

**验收**：`make.py print` 全绿；两版页数与体积记录进变更日志。

### 2.3 图示闭合

1. 修 5 处框线角字符不配对的 ASCII 图；`readability.py` 的示意图判据归零。

**验收**：`readability.py` 无 box-drawing 告警；三出口渲染无错位。

### 2.4 索引与交叉引用密度

1. 索引条目按配置下限补二级条目；交叉引用按编辑风格档的密度目标补。
2. 两者都只加「目标可达」的条目（`index_xrefs.py`、`crossrefs.py` 已判可达性）。

**验收**：密度达标且两个判据绿。

## 3. 命令

```bash
books/.venv/bin/python books/src/python/audit/balance.py
books/.venv/bin/python books/src/python/manuscript/renumber.py
books/.venv/bin/python books/src/python/make.py print
books/.venv/bin/python books/src/python/make.py check --keep-going
```

## 4. 回退

四项各自独立提交：拆章回退即恢复 `book.toml` 的章节清单；印刷参数是配置项；图示与索引是正文改动。
