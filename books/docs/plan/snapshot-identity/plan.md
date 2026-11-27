# 快照身份：实施计划

> **状态：阶段 1 已落地，阶段 2 待做**——本文记录动作与验收。
>
> 软件：bookwright — 源码分析成书工具 v0.2
> 版本：v0.2
> 定位：**动作与验收**——先让新快照带身份，再补旧快照与跨源报告。设计看同目录 `design.md`。

---

## 1. 前提

- `_config` 已能给出书 slug、源树根与版本、工具版本、配置指纹（`fingerprint()`）。
- 快照归档与校验已存在（`snapshot.py import/verify/baseline`），可直接扩展。

## 2. 阶段

### 阶段 1：身份与归目录（已落地）

1. `manifest.json` 增 `identity` 段（书 / 源树 / 工具 / 语言）。
2. 新快照写入 `data/snapshots/<book-slug>/<date>-<label>`；平铺旧目录保持可读。
3. `list` 输出表格（名称／书／源版本／工具／配置／文件／字节），缺 manifest 的显式标注。
4. `diff A B` 先比身份：同书同源才比内容；不同或身份缺失默认拒绝，`--cross` 放行并写明「不是退化」。

**通过条件**：同日两本书各一份快照不冲突；`list` 一眼可辨；跨书 `diff` 返回 2 且提示 `--cross`。

### 阶段 2：旧快照与跨源报告

1. `snapshot.py adopt <label>`：对旧平铺快照补写身份（书名从手稿 H1 与 manifest 推断，缺证据则标 `unknown`），
   补写后按新目录归位。
2. `diff --cross` 在输出开头给「身份差异摘要」：书名、源版本、工具版本、配置指纹四项并列，再进文件差异。
3. `list --book/--source` 过滤，供多书共用一个 `data/snapshots/` 时按对象查看。

**通过条件**：旧快照经 `adopt` 后能与新快照正常比对；`--cross` 报告首段固定含四项身份差异；过滤参数有可红用例。

## 3. 命令

```bash
books/.venv/bin/python books/src/python/manuscript/snapshot.py list
books/.venv/bin/python books/src/python/manuscript/snapshot.py diff <a> <b> [--cross]
books/.venv/bin/python books/src/python/manuscript/snapshot.py verify <label>
```

## 4. 回退

身份是 manifest 的新增字段，缺失即按 `legacy` 处理；目录新旧布局并存，删除某一份不影响另一份。
