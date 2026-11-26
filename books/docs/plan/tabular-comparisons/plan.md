# 对比类论述表格化：实施计划

> **状态：未开工**——本文是计划文本；正文尚未改动。
>
> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1
> 定位：**动作与验收**——先选点、再试点、再铺开，每步带能红的判据。设计理由看同目录
> `design.md`。

---

## 1. 前提

- 表格渲染已就绪：HTML 用样式表、PDF 由 Chromium 排版、EPUB 由 pandoc 转换；三处都不需要新代码。
- 判据已就绪：交付校验（PDF、EPUB 两个出口）与 `content_depth`、`readability`、`smart`
  都能对改动前后出结论，不需要新写判据。
- 一次只改一处，独立提交：任何一处引发出口问题，回退该处即可。

## 2. 阶段

### 阶段 1：选点与判据冻结

1. 盘点候选：附录 B（相邻小版本差异）、附录 E（升级与回滚）、ch7 的优化器参数取舍、
   附录 A 的案例链路对照——用「同一维度、两侧并列取值」的标准筛，列出最终 3–5 处。
2. 冻结判据：按 `design.md` §3 的四条，先对**改动前**的版本跑一遍 `make.py check` 并留基线。

**通过条件**：候选清单落盘，改动前基线与 `readability` 指标已记录。

### 阶段 2：试点两处

1. 改 2 处（优先附录 B 与 ch7 参数取舍），表格 3 列以内。
2. 逐处验证：`make.py build`、`make.py deliver`、`make.py print` 全绿；EPUB 里表格不溢出；
   `readability` 与 `content_depth` 的结论与基线一致（允许指标在区间内浮动）。

**通过条件**：两处在 PDF/EPUB 上目视与判据都成立；若 3 列在 EPUB 已溢出，则先修列宽策略再继续。

### 阶段 3：铺开与门禁回归

1. 改剩余候选，每处一次提交。
2. 全量回归：`make.py check --keep-going`、`deliver`、`print`；`coverage` 保持 100%。

**通过条件**：所有候选改写完成，三出口与全部门禁绿；无新增登记项。

### 阶段 4：收尾

1. `changelog.md` 记一条（改写了哪几处、判据结论、页数/体积变化）。
2. 若列宽或样式有调整，同步 `how-to-write.md` 的表格体例一节。

## 3. 命令

```bash
books/.venv/bin/python books/src/python/make.py build
books/.venv/bin/python books/src/python/make.py deliver
books/.venv/bin/python books/src/python/make.py print
books/.venv/bin/python books/src/python/make.py check --keep-going
```

## 4. 回退

每处改写一个提交；样式或列宽改动单独一笔。任一处让出口或判据变红，先回退该处再看是否需要改判据。
