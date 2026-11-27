# 基线目录归一：实施计划

> **状态：实施中**——动作与验收在此；设计看同目录 `design.md`。
>
> 软件：bookwright — 源码分析成书工具 v0.2-dev
> 版本：v0.2-dev

---

## 1. 前提

- `base.json [baselines]` 已能把名字映射到文件；`lib/_baseline.py` 是唯一的写入方。
- `manuscript/baselines.py` 已能列出每个文件的形态、条数与归属。

## 2. 阶段

### 阶段 1：信封与命名（本次）

1. `_baseline.save_at` 写统一信封（`schema/gate/kind/keyed_by`）；计数型与读数型基线走同一个写入函数。
2. `base.json [baselines]` 为全部十个文件声明 `<gate>.json` 命名；磁盘文件随之迁移，旧名保留读取回退。
3. `captions` 的键去掉 `data/manuscript/` 前缀，与其余门禁对齐。
4. `source_symbol` 校验 `source_version`：不符时打印复核提示。

**通过条件**：迁移前后每个文件的条数一致；`make.py check --keep-going` 与 `cover` 全绿；
`manuscript/baselines.py --check` 零告警。

### 阶段 2：清理旧名（发布前）

1. 删除旧名回退代码与遗留文件（约定：迁移完成一个发布周期后）。
2. `baselines.py --check` 增「旧名残留」一项，发布前必须为零。

**通过条件**：`grep -r "findings.json\|-baseline.json" src/` 只命中历史文档。

## 3. 命令

```bash
books/.venv/bin/python books/src/python/manuscript/baselines.py --check
books/.venv/bin/python books/src/python/make.py check --keep-going
```

## 4. 回退

文件名与信封都在配置与一个写入函数里；回退只需改回 `base.json [baselines]` 的路径，文件内容仍可读。
