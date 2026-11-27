# 坐标密度底线：实施计划

> **状态：未开工**——动作与验收在此；设计看同目录 `design.md`。
>
> 软件：bookwright — 源码分析成书工具 v0.2
> 版本：v0.2

---

## 1. 前提

- `claims` 判据已能逐句报告「强断言无依据」（35 条已记账）。
- 坐标与符号的解析规则已统一（`lib/_mdutil.source_ref_re`、`audit/source_refs.py`）。

## 2. 阶段

### 阶段 1：量化（只读）

1. 新增 `audit/evidence.py`：按章算三个密度，进 `make.py check`，只报数不判红。
2. 阈值占位进 `style.json [evidence]`（`min_coords_per_1000_lines` 等），先写 0 表示不判。
3. 用本书跑一次，记录每章现状（预期：分析章 3–8 处/千行，清单章 0–1）。

**通过条件**：三个数可复现；`--json` 给出每章数值；对没有坐标的章不报错。

### 阶段 2：补证据

1. 先补 `claims` 报出的 35 条，再按密度最低的五章补坐标与符号。
2. 每次只补「已在正文里说过的事」的依据，不新增断言；补完重跑 `claims` 与密度报告。

**通过条件**：每章坐标密度不低于阈值的 80%，`claims` 计数不升。

### 阶段 3：开判

1. 依据实测把阈值写成「现状的 80%」，进 verify 组：低于即失败。
2. 为密度判据记一份基线（届时由 `base.json [baselines]` 声明路径），每章数值只许升不许降。

**通过条件**：门禁能红（构造一章无坐标的正文即失败）；本书全绿。

## 3. 命令

```bash
books/.venv/bin/python books/src/python/audit/evidence.py
books/.venv/bin/python books/src/python/audit/claims.py --list
```

## 4. 回退

判据只读；阈值在 `style.json`，写成 0 即关闭，手稿不动。
