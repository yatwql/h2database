# 源码摘录优先：实施计划

> **状态：阶段 1 已落地**——动作与验收在此；设计看同目录 `design.md`。
>
> 软件：bookwright — 源码分析成书工具 v0.2
> 版本：v0.2

---

## 1. 前提

- `content_depth.py` 已有 EXCERPT 判据（首行 `// 文件:行号`）。
- `[sources].src_main` 可定位源码；坐标解析与后缀表已统一。

## 2. 阶段

### 阶段 1：判据（已落地）

1. 头行接受 `文件:起-止`；无省略时逐行相等，有 `// ...` 时按顺序子序列校验。
2. 行尾注释允许追加，代码本身改动仍判漂移。
3. 存量一次暴露：16 处摘录引用错行或省略未标注，已记账（`data/baselines/content-depth.json`）。

**通过条件**：人为改动摘录里的一行即失败；本书 16 处存量在基线内不阻塞。

### 阶段 2：生成器

1. 新增 `manuscript/excerpt.py`：`--file <路径> --lines <起>-<止>` 直接从源码打印标准摘录块
   （含头行与省略），作者复制即可，不再手抄。
2. `--check` 模式：对给定摘录做与判据相同的校验，便于编辑器里先验证再粘。

**通过条件**：生成器产出的块直接通过判据；对同一范围两次生成结果一致。

### 阶段 3：铺开

1. 先修 16 处存量；再把 ch6-2、ch6-3 里「叙述代替代码」的段落补成摘录（这两章坐标密度最低）。
2. 目标：`text` 围栏从 978 降到 600 以下，坐标从 232 增到 600 以上。

**通过条件**：`evidence.py` 的坐标/千行与段落依据率逐章上升；`claims` 计数不升。

## 3. 命令

```bash
books/.venv/bin/python books/src/python/audit/content_depth.py --list
books/.venv/bin/python books/src/python/manuscript/excerpt.py --file org/h2/mvstore/Page.java --lines 382-401
```

## 4. 回退

判据只读；摘录是手稿内容，改回原块即恢复。生成器是新增命令，不用即无影响。
