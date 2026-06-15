# H2 Database 源码分析文档 — 审查问题追踪

> **最近正式问题审查**：2026-06-15（第7轮 — 工业级技术书籍质量提升基线快照）
> **当前状态**：第7轮已闭环，v6.0（Phase A → H 全部 8 阶段）已发布
> **说明**：本文只记录审查发现的问题及修复状态；文档、需求、质量标准和产物变更记录统一维护在 `docs-stm/management/changelog.md`。

---

## 第7轮基线快照（2026-06-15） — 工业级技术书籍质量提升起点

> 本轮非"问题审查"，而是为 v6.0 计划（`docs-stm/plan/2026-06-15-001-feat-industrial-book-quality-plan.md`）固化 v5.0 基线度量，作为后续 8 个阶段的对照基准。

### v5.0 基线度量（由 `balance_check.py` 输出）

| 维度 | v5.0 实测 | v6.0 目标 |
|------|-----------|-----------|
| 章节文件数 | 9 | 10（ch7-8 拆分后） |
| 总行数 | 36,314（源文件聚合） | ≥ 38,000 |
| 总图数 | 579 | ≥ 595 |
| 总源引用 | 185 | ≥ 185（不退步） |
| glossary 条目（按章累计命中） | 77 | ≥ 110 |
| index 条目（按章累计命中） | 141 | ≥ 350 |
| 最大单文件行数 | 8,085（ch7-8） | ≤ 5,000 |
| 最小单文件行数 | 2,157（ch1-2） | ≥ 2,000 |
| **max_min_ratio** | **3.748** | **≤ 2.7** |
| 行数标准差 | 1,951 | ≤ 1,500 |
| `final_check.py` 检查项 | 88/88 | ≥ 100，全部通过 |
| `check_style.py` | 0 警告 | 0 警告 |
| `_audit_smart.py` | 零缺图 | 零缺图 |

### 基线 JSON

固化在 `docs-stm/management/baseline-v5.0.json`，由 `balance_check.py --baseline` 写入。

后续每个阶段（v5.1..v6.0）发布时，运行：

```bash
python docs-stm/tools/balance_check.py --diff docs-stm/management/baseline-v5.0.json
```

输出本阶段相对 v5.0 基线的变化量，归档至 changelog.md。

### v6.0 阶段问题清单

| # | 阶段 | 级别 | 问题 | 状态 |
|---|------|------|------|------|
| R7-1 | A (v5.1) | 信息 | 基线度量工具就绪 | ✅ 已完成 |
| R7-2 | B (v5.2) | P0 | ch7-8 拆分：8,085 行单文件违反"≤ 5,000 行"约束 | ✅ 已完成（拆为 3,642 + 4,443）|
| R7-3 | B (v5.2) | P0 | max_min_ratio 3.748 偏离 v6.0 目标 2.5 | ✅ 已完成（v5.2 拆分后降至 3.044；后续 Phase D-F 继续收敛）|
| R7-4 | C (v5.3) | P1 | 前后件深度化（preface/copyright/how-to-read 信息密度不足；术语表/索引层级不够） | ✅ 已完成（索引层级 main/sub/see-also 三档；术语表 ≥ 110；索引 ≥ 250）|
| R7-5 | D (v5.4) | P1 | 缺端到端叙事主线，各章孤立分析 | ✅ 已完成（新增附录 A：端到端案例研究 — SELECT/COMMIT/Recovery）|
| R7-6 | E (v5.5) | P1 | 图注以名词起首、长度漂移；图簇缺桥接叙事 | ✅ 已完成（图注 strict 阈值 0 违规；33 图簇全部含桥接句）|
| R7-7 | F (v5.6) | P1 | 章末缺延伸思考，读者从被动阅读转主动应用门槛高 | ✅ 已完成（14 章节槽 56 题，含难度 emoji + 提示行 + 锚点回顾行）|
| R7-8 | — (v5.7) | P2 | 附录 A 内含 A.4 源码版本变更说明，与附录 A 端到端叙事主旨不符 | ✅ 已完成（拆出独立附录 B：源码版本变更说明）|
| R7-9 | — (v5.7) | P1 | 管理文档版本号漂移、统计数字过期、阶段进度未同步 | ✅ 已完成（v5.0 全部对齐为 v5.7；过期统计删除；phase3-audit.md 归档）|
| R7-10 | — (v5.7) | P0 | HTML 封面与目录被左侧 TOC 遮挡（视觉缺陷） | ✅ 已完成（intro-mode 类 + IntersectionObserver；封面/目录页隐去 TOC）|
| R7-11 | — (v5.7) | P1 | 桌面端 TOC 缺乏点击收起/展开能力 | ✅ 已完成（`#sidebar-toggle` 表头条 + 浮动 `›` + `[` 快捷键，状态写入 localStorage）|
| R7-12 | — (v5.7) | P0 | `generate_html.py` 大 f-string 内 `'\n'` 被 Python 求值为真实换行，整个 `<script>` 块抛 SyntaxError，所有交互全失效 | ✅ 已完成（改为 `'\\n'`；node -c 通过校验）|
| R7-13 | — (v5.7) | P1 | TOC 展开 `›` 按钮点击仍无响应（Firefox） | ✅ 已完成（重写为 document 级事件委托 + closest 命中）|
| R7-14 | — (v5.7) | P2 | 后件 术语表 / 概念索引 / 参考文献 未挂入附录体系 | ✅ 已完成（升级为附录 C / D / E）|
| R7-15 | G (v5.8) | P1 | 缺印刷级 PDF 渲染管道（章首装饰页、TOC 虚线对齐、印刷级页眉页脚） | ✅ 已完成（新建 `pdf_print_grade.py`，独立于日常 PDF 流水线）|
| R7-16 | H (v6.0) | P1 | `final_check.py` 缺 P0/P1/P2 门禁分级入口；testplan.md 仅平铺列表 | ✅ 已完成（`--gate-level` 入口；testplan §2 重构 + §7 门禁演进史）|
| R7-17 | H (v6.0) | P0 | v6.0 全量回归发布 | ✅ 已完成（cover/requirements/plan/testplan/style-guide 全部 v6.0；changelog v6.0 总览条目；三档门禁全部通过）|
| R8-1 | — (v6.1) | P2 | 缺 EPUB 输出形态（电子阅读器交付） | ✅ 已完成（新建 `generate_epub.py`，pandoc 引擎，按需在最终交付阶段产出）|

---

## 第4轮审查问题清单（2026-06-07）

| # | 级别 | 问题 | 状态 |
|---|------|------|------|
| R4-1 | CRITICAL | PDF Outline/目录链接缺失（PDF 验证失败） | ✅ 已修复 |
| R4-2 | HIGH | ch4 小结出现在第5章 H1 之后，章节边界错位 | ✅ 已修复 |
| R4-3 | HIGH | ch1-2 FilePathDisk.java/FilePathEncrypt.java 路径错误 | ✅ 已修复 |
| R4-4 | HIGH | ch9-10 FilePathEncrypt 路径不一致 | ✅ 已修复 |
| R4-5 | MEDIUM | ch3-packages 图 3-11 引用指向错误的图（应为图 3-13） | ✅ 已修复 |
| R4-6 | MEDIUM | ch11-12 交叉引用标题别名与实际 H1 不符 | ✅ 已修复 |
| R4-7 | MEDIUM | ch6-3 章节标题别名 `核心算法篇`→`核心算法分析` | ✅ 已修复 |
| R4-8 | MEDIUM | requirements.md 第6章算法序号与实际章节不对应 | ✅ 已修复 |
| R4-9 | MEDIUM | plan.md Server 层排序与架构定义不一致 | ✅ 已修复 |
| R4-10 | MEDIUM | CLAUDE.md 管理文档版本号集合描述缺失 cover/changelog | ✅ 已修复 |
| R4-11 | MEDIUM | testplan.md C 类问题标准自相矛盾（"允许存在"vs零容忍） | ✅ 已修复 |

## 第5轮审查 — 写作风格增强（2026-06-11）

| # | 级别 | 问题 | 状态 |
|---|------|------|------|
| R5-1 | HIGH | check_style INFO 级别问题 82 条需修复（全书 9 章：被动滥用/句式单调/空泛修饰/冗余副词/模糊指代/过度"的"） | ✅ 已修复 |
| R5-2 | MEDIUM | `check_style.py` 句式单调检测对 `.java`/`.html` 句点产生假阳性，需保护反引号和文件扩展名中的句点 | ✅ 已修复 |
| R5-3 | MEDIUM | `check_style.py` 检测函数集中在 `run_standard_checks()` 中，未使用模块化 `detect_*()` 模式 | ✅ 已修复（抽取为独立模块） |
| R5-4 | MEDIUM | `final_check.py` 图号检测对字母后缀（6-72b）误判为重复 | ✅ 已修复 |
| R5-5 | MEDIUM | ch6-3 §6.8.4 缺第二幅图，`_audit_smart` 建议补图 | ✅ 已修复（图 6-72b） |
| R5-6 | LOW | 缺少写作风格参考文档，后续润色无据可依 | ✅ 已修复（`style-guide.md`） |
| R5-7 | LOW | 管理文档版本号/统计数字冲突 | ✅ 已修复 |
| R5-8 | LOW | 临时文件残留（`.claude/_insert_diagram.py`、全局 `~/.claude/` 会话目录） | ✅ 已清理 |

## 第3轮审查问题清单（2026-06-06）

| # | 级别 | 问题 | 状态 |
|---|------|------|------|
| C-0 | CRITICAL | HTML 图例渲染质量差 | ✅ 已修复 |
| C-1 | CRITICAL | ch4-5 图注在围栏内部 | ✅ 已修复 |
| C-2 | CRITICAL | ch1-2/ch3 正文在围栏 | ✅ 已修复 |
| C-3 | CRITICAL | ch3 源码统计偏差 | ✅ 已修复 |
| C-4 | CRITICAL | Engine.java 行号矛盾 | ✅ 已修复 |
| C-5 | CRITICAL | ch4-5 空围栏块 | ✅ 已修复 |
| H-1 | HIGH | 五层/八层模型映射 | ✅ 已修复 |
| H-2 | HIGH | 源码引用行号不准确 | ✅ 已修复 |
| H-3 | HIGH | 全局缺图号内联引用 | ✅ 已修复（201 处） |
| H-4 | HIGH | ch11-12 交叉引用+路径 | ✅ 已修复 |
| M-1 | MEDIUM | ch4-5 缺章节总结 | ✅ 已修复 |
| M-2 | MEDIUM | ch7-8 图注格式 | ✅ 已修复 |
| M-3 | MEDIUM | 图 9-8 粗体闭合 | ✅ 已修复 |
| M-4 | MEDIUM | 交叉引用格式 | ✅ 已修复 |
| M-5 | MEDIUM | ch6-3 重复段落 | ✅ 已修复 |
| M-6 | MEDIUM | Chunk 大小写 | ✅ 已修复 |
| M-7 | MEDIUM | 引言格式不一致 | ✅ 已修复 |

---

## 第2轮审查问题清单（2026-06-05）

| # | 级别 | 问题 | 状态 |
|---|------|------|------|
| R2-1 | CRITICAL | ch1-2 首段重复 | ✅ 已修复 |
| R2-2 | CRITICAL | ch4-5 字母后缀图号（7处） | ✅ 已修复 |
| R2-3 | CRITICAL | ch6 节号跨文件不连续 | ✅ 已修复 |
| R2-4 | HIGH | ch7-8 图注格式统一（31处重复图号） | ✅ 已修复 |
| R2-5 | HIGH | 管理文档统计数字不同步 | ✅ 已修复 |
| R2-6 | MEDIUM | ch6-1/ch6-2 章末总结缺失 | ✅ 已修复 |
| R2-7 | MIXED | 共 37 项问题修复（CRITICAL 8, HIGH 11, MEDIUM 10, LOW 8） | ✅ 已修复 |

---

## 当前未解决问题

- **v6.1 已交付**：v6.0 全部 8 阶段（Phase A–H）+ EPUB 按需交付形态。第 7 轮审查闭环；R8-1（EPUB 扩展）作为 v6.0 后维护期首条增量记录。
- 下一阶段为 **v6.x 维护期**（plan.md §7 后续增强项 P3/P4）：API 文档索引、交互式图表、英文版翻译、CI 集成；印刷级 PDF per-chapter running header（待 paged.js 或同等方案）。
- 后续新发现问题在此追加。下一轮正式审查启动时另开第 8 轮清单。
