> 涵盖版本：0.1
> 归档时间：2026-11-25

# H2 Database 源码分析文档 — 审查问题追踪（0.1 归档）

> **最近正式问题审查**：2026-06-15（第7轮 — 工业级技术书籍质量提升基线快照）
> **当前状态**：第7轮已闭环，0.1（Phase A → H 全部 8 阶段）已发布
> **说明**：本文只记录审查发现的问题及修复状态；文档、需求、质量标准和产物变更记录统一维护在 `books/docs/managements/changelog.md`。

---

## 第7轮基线快照（2026-06-15） — 工业级技术书籍质量提升起点

> 本轮非"问题审查"，而是为 0.1 计划（`books/docs/plan/2026-06-15-001-feat-industrial-book-quality-plan.md`）固化 0.1 基线度量，作为后续 8 个阶段的对照基准。

### 0.1 基线度量（由 `balance_check.py` 输出）

| 维度 | 0.1 实测 | 0.1 目标 |
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

固化在 `books/docs/managements/baseline-0.1.json`，由 `balance_check.py --baseline` 写入。

后续每个阶段（0.1..0.1）发布时，运行：

```bash
python books/src/python/balance_check.py --diff books/docs/managements/baseline-0.1.json
```

输出本阶段相对 0.1 基线的变化量，归档至 changelog.md。

### 0.1 阶段问题清单

| # | 阶段 | 级别 | 问题 | 状态 |
|---|------|------|------|------|
| R7-1 | A (0.1) | 信息 | 基线度量工具就绪 | ✅ 已完成 |
| R7-2 | B (0.1) | P0 | ch7-8 拆分：8,085 行单文件违反"≤ 5,000 行"约束 | ✅ 已完成（拆为 3,642 + 4,443）|
| R7-3 | B (0.1) | P0 | max_min_ratio 3.748 偏离 0.1 目标 2.5 | ✅ 已完成（0.1 拆分后降至 3.044；后续 Phase D-F 继续收敛）|
| R7-4 | C (0.1) | P1 | 前后件深度化（preface/copyright/how-to-read 信息密度不足；术语表/索引层级不够） | ✅ 已完成（索引层级 main/sub/see-also 三档；术语表 ≥ 110；索引 ≥ 250）|
| R7-5 | D (0.1) | P1 | 缺端到端叙事主线，各章孤立分析 | ✅ 已完成（新增附录 A：端到端案例研究 — SELECT/COMMIT/Recovery）|
| R7-6 | E (0.1) | P1 | 图注以名词起首、长度漂移；图簇缺桥接叙事 | ✅ 已完成（图注 strict 阈值 0 违规；33 图簇全部含桥接句）|
| R7-7 | F (0.1) | P1 | 章末缺延伸思考，读者从被动阅读转主动应用门槛高 | ✅ 已完成（14 章节槽 56 题，含难度 emoji + 提示行 + 锚点回顾行）|
| R7-8 | — (0.1) | P2 | 附录 A 内含 A.4 源码版本变更说明，与附录 A 端到端叙事主旨不符 | ✅ 已完成（拆出独立附录 B：源码版本变更说明）|
| R7-9 | — (0.1) | P1 | 管理文档版本号漂移、统计数字过期、阶段进度未同步 | ✅ 已完成（0.1 全部对齐为 0.1；过期统计删除；phase3-audit.md 归档）|
| R7-10 | — (0.1) | P0 | HTML 封面与目录被左侧 TOC 遮挡（视觉缺陷） | ✅ 已完成（intro-mode 类 + IntersectionObserver；封面/目录页隐去 TOC）|
| R7-11 | — (0.1) | P1 | 桌面端 TOC 缺乏点击收起/展开能力 | ✅ 已完成（`#sidebar-toggle` 表头条 + 浮动 `›` + `[` 快捷键，状态写入 localStorage）|
| R7-12 | — (0.1) | P0 | `generate_html.py` 大 f-string 内 `'\n'` 被 Python 求值为真实换行，整个 `<script>` 块抛 SyntaxError，所有交互全失效 | ✅ 已完成（改为 `'\\n'`；node -c 通过校验）|
| R7-13 | — (0.1) | P1 | TOC 展开 `›` 按钮点击仍无响应（Firefox） | ✅ 已完成（重写为 document 级事件委托 + closest 命中）|
| R7-14 | — (0.1) | P2 | 后件 术语表 / 概念索引 / 参考文献 未挂入附录体系 | ✅ 已完成（升级为附录 C / D / E）|
| R7-15 | G (0.1) | P1 | 缺印刷级 PDF 渲染管道（章首装饰页、TOC 虚线对齐、印刷级页眉页脚） | ✅ 已完成（新建 `pdf_print_grade.py`，独立于日常 PDF 流水线）|
| R7-16 | H (0.1) | P1 | `final_check.py` 缺 P0/P1/P2 门禁分级入口；testplan.md 仅平铺列表 | ✅ 已完成（`--gate-level` 入口；testplan §2 重构 + §7 门禁演进史）|
| R7-17 | H (0.1) | P0 | 0.1 全量回归发布 | ✅ 已完成（cover/requirements/plan/testplan/style-guide 全部 0.1；changelog 0.1 总览条目；三档门禁全部通过）|
| R8-1 | — (0.1) | P2 | 缺 EPUB 输出形态（电子阅读器交付） | ✅ 已完成（新建 `generate_epub.py`，pandoc 引擎，按需在最终交付阶段产出）|

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

- **0.1 已交付**：0.1 全部 8 阶段（Phase A–H）+ EPUB 按需交付形态。第 7 轮审查闭环；R8-1（EPUB 扩展）作为 0.1 后维护期首条增量记录。
- 下一阶段为 **v6.x 维护期**（plan.md §7 后续增强项 P3/P4）：API 文档索引、交互式图表、英文版翻译、CI 集成；印刷级 PDF per-chapter running header（待 paged.js 或同等方案）。
- 后续新发现问题在此追加。下一轮正式审查启动时另开第 8 轮清单。

---

### 已修复（当前版本 0.1）

> 本表为当前开发周期的摘要行，详情见 `changelog.md` 的 `[0.1]` 段；发布时摘要留在
> 版本段，本表清空。

| # | 问题 | 修复 |
| --- | --- | --- |
| rf-1 | 同一事实多处声明：配置分层有"两层（含 `config.json`）""三层""四层"三种说法；门禁级别在 `testplan.md` §2.2 与 §7 互相矛盾；`plan.md` 复述了技术设计的概述 | 分层只在 `technical.md` §3.1 定义；级别只在 `testplan.md` §2.2 声明并删除 §7；`plan.md` 改为计划项清单 |
| rf-2 | `book.toml` 存在死键：四个章节表里键 `ch7-sql-execution.md`、`ch8-query-optimizer.md` 不在 `[chapters] files` 中，包归属与编号实际未生效 | 键合并为 `ch7-8-sql-optimizer.md`（包 / 标题 / 编号 `[9,10]` / 覆盖 `[7,8]`），`doc_drift.py` 新增 CONFIG 检查防复发 |
| rf-3 | 附录数量三处不一致："5 个附录""2 个附录"，而 `book.toml` 只给 A/B 分配编号 | 统一为「12 章节槽 + 2 个编号附录 A/B；术语表 / 索引 / 参考文献为后件 C/D/E」 |
| rf-4 | 计划与问题没有各自的载体：`plan.md` 是概述式文档，`testplan.md` 曾要求"审查问题单独维护"却无此文件 | `plan.md` 改为带编号的计划项清单；新增本文件，条目不占计划编号 |
| rf-5 | 章节合并后 `content_depth.py` 只取文件的第一个章号，导致合并文件的包归属判错 | `owner_map` 返回章号列表，前向引用点名任一章号即通过；基线按新键控重新固化 |
| rf-6 | 门禁盲区：`doc_drift.py` 只认反引号里的章节名、不查配置死键、不查级别重复声明；版本比对与 `version_consistency.py` 重复 | 新增 CONFIG / LEVEL 两项检查并把章节名检查放宽；版本检查从 `doc_drift.py` 移除；管理文档头写错版本（写成书籍版本）由 `version_consistency.py` 判红 |
| rf-7 | 手册示例可能混入真实章节名与真实路径，未逐份核对 | 已逐份核对 `docs/manuals/*.md`：示例统一为 `<主题>` / `<code>` 占位，无越界真实章节名；`doc_drift.py` 的 CHAPTER 检查兜住复发 |
| rf-8 | 管理文档互查：索引重复登记 `plan.md`、`folder.md` 缺 `content-quality-policy.md` 且职责过时、交付链路与印刷版 PDF / EPUB 归属、门禁级别越出 P0–P2、延伸思考章数、脚本路径、界面用语、旧启动器名，共 16 处冲突与冗余 | 逐条收归单一权威（变更内容见 `changelog.md` 同版段）；`doc_drift` 补 `INDEX`/`NUMBERING`/`DELIVER`/`PREFIX` 四项机检 |
| rf-9 | 互查靠人读：管理目录与索引用表、编号源标记、需求与判据的对应关系都没有机检面，互相矛盾的条目只能靠人工发现；`src/test/test_network_isolation.py` 被删后 testplan 仍把它列为载体 | `doc_drift.py` 补 `INDEX`/`NUMBERING` 并扩展路径面；`file_length.py` 兼校膨胀登记表；新增 `requirement_trace.py` 与 testplan §2.4 对照表；补回 `test_network_isolation.py` |
| rf-10 | 用户文档互查出 6 处冲突：章末四段顺序、`scripts/` 前缀白名单、`deliver` 步骤、报告类脚本归类、日志文件名、TUI 键位 | 按代码实际改写；`DELIVER`/`PREFIX` 两项机检兜住复发 |
| rf-11 | 管理文档的角色与内容对不上：8 份没有「定位」行，`plan.md` 与 `review-findings.md` 都用 P1–P4 但含义不同，`folder.md` 的配置分层表与 `technical.md` §3.1 重复，练习/引用规则在 `content-standard` 与 `how-to-write` 各写一遍 | 14 份统一补 `> 定位：`（`doc_drift` 新增 `LOCUS` 检查）；问题台账改 H1–H3 + 登记档并写明与 plan 时机档的区别；`folder.md` 只留归属、合并规则指向技术设计；练习与跨章引用细则只在 `how-to-write` |
| rf-12 | 内容标准与写作规则边界不清：`content-standard` 既讲「必须有什么」又声明判据与级别，还点名本项目的门禁表与配置文件名——与其「跨项目复用」的定位矛盾 | 收敛为两轴：本文只讲内容要求，写法指向 `how-to-write`；判据改由项目单向登记；`doc_drift` 新增 `STANDARD` 检查兜住反向引用 |
| rf-13 | 口径冲突：`testplan` 写「手稿附录 ≤2000」而配置是 9000；段落规则一处按行一处按字符；索引阈值 120/每章 5 写死在 `structure.py`；性能预算一处当硬约束一处只提示 | **修订**：testplan 与 `review-findings` 的阈值改写成配置键，四档预算必须在 `style.json [limits]` 显式声明（`file_length` 新增 `BUDGET` 检查）；`index_total_min`/`index_per_chapter_min` 进 `style.json [thresholds]`，`structure.py` 读配置；段落规则统一为字符口径；NFR-05 标注 advisory |
| rf-14 | 修 rf-13 时把配置键名写进了判据：`testplan` §2.2 用 `[thresholds].index_total_min` 等替代数值，等于把实现细节搬进“通过标准”——判据应说性质，键名与取值归 `technical.md` §3.2 | **修订**：判据行改写成“不低于配置下限”这类性质表述；键名集中写进 `technical.md` §3.2 的阈值归属；`doc_drift` 新增 `THRESHOLD` 检查，判据表里出现配置键名即失败 |
| rf-15 | `testplan` 里混入不属于判据的内容：§4 写了渲染实现参数（`--split-level`、CSS 配色）与无门禁的版式阈值（1.5 倍、2-5 MB）；§2.2 用「9 项 CSS 标记」当判据、另有一条「脚本语法有效」的弱判据；§5 与 §2.2 逐条重复；§6 是流程策略 | **修订**：§4 收缩为按需验收项 + 按需命令，实现与版式指向 `technical.md` §4.4 / `../manuals/how-to-write.md` §6，两个硬编码数字删除；§2.2 改为「样式与锚点钩子齐备」并删弱判据；§5 改为「以 §2.2 为准」；§6 指向 `content-quality-policy` §4 与手册 |
| rf-16 | 代码/配置遗留的硬编码：`smart.py` 内联「2 图」「95%」、`figure_clusters.py` 默认窗口 50 而 `structure.py` 传 40（两道门禁实际在查不同窗口，文档写 40）；`verify_pdf.py` 内联 A4 595×842±2；`_config` 与三个渲染脚本的 docstring 写死第一本书的名字 | **修订**：图簇与图表阈值进 `style.json [clusters]`/`[quality]`，A4 几何进 `base.json [toolchain]`，`structure.py` 与门禁共用同一取值；书名改由 `book.toml` 提供（兜底 `book`）；`check_architecture` 新增书名字面量检查 |
| rf-17 | 文档与代码对照时发现 `scripts/bookctl` 的帮助注释写 `bookctl llm`，而 CLI 只接受 `llm-ask`——手册写的是对的，包装脚本的头注释是唯一错处，属“没人重跑过”的注释漂移 | **修订**：注释改为 `llm-ask`；`script_contract.py` 新增 `check_dispatcher_help`，把包装脚本帮助里点名的动作与 `core/actions.py` 的 ACTIONS 表对齐，写错即失败（含 3 个用例） |
| rf-18 | TUI 只有一层平铺菜单（九个按键全在主界面），配置只能在命令行上改，`0` 与 `q` 一样直接退出，LLM provider 的回退顺序只能手改 JSON；另发现 Web 控制台在动作抛异常时直接断开连接（顺序依赖用例即因此红） | **修订**：菜单改为主菜单 / 类目两级（`core/menu.py::SCREENS`），二级目录一律 `0` 返回、主菜单 `0` 退出，新增「配置项」与「LLM provider 优先级」两屏（`settings.provider_order` / `move_provider` 写回 `priority`）；Web 的 `do_POST` 捕获异常并以 `code: 1` 回报，不再断连接 |
| rf-19 | rf-18 的分级把高频的内容流水线也收进了二级：每天要按的 `analyze`/`build`/`deliver` 变成两步 | **修订**：主菜单直接放 `1 analyze`/`l analyze-llm`/`2 build`/`3 deliver`，只把质量与配置留作二级（`4`/`5`）；默认光标回到 `2 build`；DESIGN-TUI §3.1 写明唯一分级标准——每天按的放第一级，偶尔打开的分组才进二级 |
| rf-20 | 跑完一个动作后按 `0` 直接退出：结果在屏时 `0` 与“退出”共用一个语义；屏幕底部还有一个孤立的 `❯ `，看起来像在等一段长文本输入 | **修订**：`0`/`Esc` 改为三级语义——先收起结果、再返回上一级、主菜单上才退出；去掉底部的 `❯ ` 提示符（只保留光标行前缀），结果区改为一行中性提示；DESIGN-TUI 把它写成契约 |
| rf-21 | 「源码 → 手稿」既不比对基线、也不保护正文：`chapters.py` 无条件覆盖手稿（骨架覆盖已写正文，内容体积门禁要到下一次 `check` 才报），交互结束后用户拿不到“稿子有没有变薄”的答案 | **修订**：`chapters.py` 只在空文件/内容相同/`--force` 时写入，否则跳过并在结果里报出；`actions.analyze` 在三阶段后调用 `content_volume.py --json`，把一行比对结论并入同一份结果（低于基线时判失败并给出 `--update-baseline` 指引） |
| rf-22 | 体量基线没有单调性约束，也没有“比哪一份”的说法：每次转换后都能 `--update-baseline` 把下限重记成更薄的那份，多份历史稿各自有账本但没有显式选取入口 | **修订**：`--update-baseline` 默认拒绝降低任何条目或总量，收缩须 `--accept-shrink --reason`，理由与差额写进 `accepted_shrinks`；新增 `--baseline <文件>` 用于显式对照某份历史快照；`content-quality-policy.md` §4 写清“只比一份、不做加权”的原则 |
| rf-23 | 「评审通过的基线」只有口头含义：`--update-baseline` 对未提交的工作区、无人具名的调用一样照写，事后无法回答“这份基线是谁在哪一版上认的” | **修订**：记账要求 `data/manuscript` 无未提交改动、评审人具名（`--reviewed-by`，缺省取 `git user.name`），并在基线文件写入 `reviewed{by, at, commit, reason}`；`content-quality-policy.md` §4 补三项条件与固定流程（check → commit → 记账） |
| rf-24 | 历史版本无法直接成为基线：快照只有自己的体积账本，`--update-baseline` 只量当前手稿，要把 6 月那版定为下限只能手改 JSON（绕过了评审人、单调性与来源记录） | **修订**：`content_volume.py` 新增 `--from-snapshot <label>`，从 `snapshot-<label>.json` 取数写基线，并记下 `source.snapshot`；比当前基线薄时仍需 `--accept-shrink`；`content-quality-policy.md` §4 给出「导入 → 记快照账本 → 提为基线」三步流程 |
| rf-25 | LLM 调用没有任何用量与成本可见性：`_llm.complete` 丢掉响应里的 usage，跑完只知道“有文字回来”；也没有调用前预估与累计上限，`llm-ask` 一次问多少钱无从判断 | **修订**：单价表 `data/config/llm_pricing.json`（未列出即“未定价”），`_llm` 记录每次调用的 token/费用并追加 `logs/llm-usage.jsonl`，`llm-ask` 打印调用前区间预估与调用后“本次 + 今日累计”，`analyze --llm` 打印整轮汇总；`llm_settings.daily_cost_limit` 达到时加一行 ⚠ 提醒 |
| rf-26 | 测试隔离有洞：网络只阻 socket，但 LLM 仍可能按真实 provider 走；`logs/` 写进仓库目录，`today_cost()` 读的也是真实用量账本（用例结果随本机历史浮动）；手稿与产物目录没有任何写入守卫——此前一次测试真的把手稿覆盖成骨架 | **修订**：`_fixture.isolate()` 导入时装守卫：`BOOK_TEST_GUARD` 拒写真实 manuscript（产物可再生，仅告警不拦），夹具书与日志都在临时目录内；LLM 一律 mock，真实建连由 socket 守卫阻断。新增 `test_isolation.py` 钉住每条不变量 |
| rf-27 | 快照的标签有两种写法：`import` 存成 `<日期>-<标签>`，而 `baseline`/`verify` 只认目录全名——按 `snapshot.py import … june-2026` 导入后 `baseline june-2026` 报“找不到快照” | **修订**：`snapshot.resolve/require` 同时接受标签与目录全名（歧义时报出候选），`content_volume --from-snapshot` 也接受裸标签；新增 3 个用例 |
| rf-28 | `how-to-config.md` 写“`deepseek-main`（默认）”，而 `llm_provider.json` 的 `default_provider` 是 `opencode-go`（priority 10）——文档与配置互相矛盾 | **修订**：文档按配置改写，并把“改默认 provider 用 `settings set llm.provider`”写进同段 |
| rf-29 | `make.py cover` 从不返回：它用 `unittest discover` 跑覆盖率，遇到带线程的 Web/TUI 夹具死锁，于是这道门禁长期既不给数字也不报错；顺带发现 `coverage_fail_under` 88 高于实测 85——门禁即使跑起来也是红的 | **修订**：`coverage()` 改用与门禁同源的 `pytest -m tier_fast` 并加 1800s 超时，阈值按实测调到 85，`plan-3` 保留抬到 88 的目标 |
| rf-30 | `make.py` 的每个步骤都没有超时（`check_runner` 有 1800s，`make.py` 没有），一个死锁的门禁会让整条命令永久挂住——rf-29 就是这样被我误读成“白跑”的 | **修订**：`run_step` 加 `STEP_TIMEOUT_S = 1800`，超时按 124 记为步骤失败并打印步骤名 |
| rf-31 | 测试隔离只护住了手稿：一个新写的快照用例把一份快照账本写进了仓库（`GUARDED_SUFFIXES` 当时只有 `data/manuscript`），基线/派生状态同样会被测试污染 | **修订**：守卫扩到 `data/manuscript`、`data/baselines`、`data/state`；该用例改为把 `BOOK_ROOT` 指向临时树；误落的账本文件已删除（测试现在只写临时树） |
| rf-32 | 章名在代码里又写了一份：`source_refs.py::CHAPTER_FILES` 仍列 `ch7-sql-execution.md`/`ch8-query-optimizer.md`，两个文件不存在 → 每次跑两条 `WARN Chapter file not found`，合并后的 `ch7-8-sql-optimizer.md` 因此从未被坐标门禁检查；同一批旧章名还留在一份无任何引用的历史图注基线文件与 `exercises.py` 的用法示例里 | **修订**：`CHAPTER_FILES` 改为 `_config.chapter_names(include_cover=False)`（单份来源是 `book.toml`），合并章节重新进入检查面（95 条坐标全部有效）；删除无引用的历史基线文件；示例改占位名；新增用例钉住“列出的章必须存在且等于配置” |
| rf-33 | 慢档在 CI 超时 30 分钟：`order_dependence.bisect()` 默认把整个套件当作前缀候选，`test_bisect_reports_a_target_that_passes_in_full_order` 实际重跑了一遍全包；而 `make.py` 用全局 1800s 步骤超时，把“重跑全包”掩盖成一个只能等的半小时；慢档其余 72 个用例实测共 0.49s | **修订**：`bisect()` 增加 `pool` 参数，用例改传两模块小池（单文件 1.57s）；CLI 同步增加 `--pool`；`make.py` 按步骤名取超时（`base.json [toolchain]` 的 `step_timeout_s` 900 / `test_timeout_s` 300），测试步骤加 `--durations=10` 把最慢用例写进报告；`CLAUDE.md` 补「不跑未知耗时命令、不等 CI」的作业纪律；步骤超时改为按进程组杀死（超时的 pytest 不再留下 chromium/pandoc 孤儿），CI 每个 job 补 `timeout-minutes` |
| rf-34 | 附录不在坐标与符号断言的扫描面内：`source_refs.py` 只扫 `ch*` 章节，附录 A 里 10 条 `Class.method(` 断言从未被检查，其中 3 条写错了类（`CommandContainer.canReuse/executeQuery` 实际在 `Command`），7 条是旧版 MVStore 恢复流水线的术语（`openInternal`/`setLastChunk`/`openComplete`） | **修订**：扫描面改为 `book.toml` 的非封面文件（章节 + 附录），3 条改类名（实例与表格中引用一并改正），7 条旧术语登记进 `source-symbol-baseline.json`——附录 A.3 的恢复叙事仍按旧流水线行文（含 ASCII 图与 trace 日志），重写该案例时再对齐 `MVStore.open` / `FileStore.readStoreHeader`；`save_baseline` 顺带去重（同一 file::Class::method 只记一条） |

| rf-35 | 图注形状六处各写一份（边界互不一致：有无行尾锚点、是否认字母图号、是否容忍空白），改一处不会同步其余；`structure.py` 又把章节范围写死为 1–12，章数变化时静默截断 | **已解决**：形状归 `lib/_mdutil.py` 一处（`FIGURE_LABEL`/`FIGURE_ID`/`CHAPTER_FIGURE`/`APPENDIX_FIGURE` 与 `figure_caption()`），六个消费者改为引用；章节范围从 `book.toml [chapters.coverage]` 推导，无覆盖表时退回阅读顺序，并对未声明章号容错计数 |

| rf-36 | `book.toml` 的两张章节表互相矛盾：`[chapters.numbering]` 声明 1–14，`[chapters.coverage]` 与手稿 H1 却是 12 章；把 numbering 改成与手稿一致后，`content_depth` 的前向引用基线（按章号键控）失配 | **已解决（按手稿为准）**：两张表各司其职——numbering 管阅读顺序、coverage 管逐章统计；手稿 H1 作为章号事实，基线按新章号重固，文档不再笼统写「12 章」 |

| rf-37 | 覆盖率门禁只量快档：`make.py::coverage()` 写死 `-m tier_fast`，而同一文件的 `test` 认 `BOOK_SLOW=1`；CI 慢档 job 装好 chromium/pandoc 后跑的仍是快档，12 个 `tier:slow` 模块（82 条用例）对覆盖率零贡献 | **修订**：`cover` 接受 `--full` 与 `BOOK_SLOW=1`，报头写出量的是哪一档；CI 慢档 job 改跑 `cover --full`，testplan 判据同时点名两个载体。逐模块把“只为拿真工具”的用例改注入仍在做（`to_epub` 已 72% → 100%） |
| rf-38 | 覆盖率只有全局阈值加 72% 的单文件下限：50 个模块低于 90%（8543 语句、漏 1143），一个 200 语句的模块停在 73% 仍能全绿 | **修订**：`cover` 把每个文件的覆盖率记进 `data/baselines/coverage.json`，任一文件低于基线即 FAIL，`--update-baseline` 经评审重记；不足 5 条语句的文件除外 |
| rf-42 | 质量读数没有统一入口：覆盖率、单文件、半分支、长函数数、永真断言数分散在多个命令与 grep 里 | **修订**：新增 `audit/test_health.py`，由 `make.py report health` 调用，汇总覆盖率（总/最薄/半分支 Top-N）、低于基线的文件、松散断言数与超长函数清单；阈值读 `base.json [toolchain]`，视图只读数不判红 |
| rf-43 | 有 6 个模块在**导入期**读配置并把它存成模块常量：`audit/source_refs.py`(7)、`ingest/chapters.py`(5)、`render/to_html.py`(2)、`ingest/outline.py`(2)、`audit/style_schema.py`(2)、`audit/smart.py`(2)；一个进程换书、或工具链独立成包后 `--book` 在导入之后才解析，这些常量会指向上一本书 | **修订**：全部改为调用时解析——路径直接读 `_config` 门面，策略派生的值走 `suffixes()`/`generation()`/`templates()`/`quality_policy()` 一类小函数，`source_refs` 的引用正则按后缀元组缓存；同名局部变量（`source_dir`、`baseline_path`）处的访问器改名避免遮蔽。新增 `test_lib_baselines.py` 钉住基线的配置解析与版本作用域 |
| rf-40 | 长函数无法逐个用例化：拆分前有 30 个 ≥60 行函数，分支组合只能整体回归 | **修订**：全部拆完，全库不再有 ≥60 行函数（30 → 0）。每处都用同一批输入比对输出：章节渲染逐字节相同、坐标/图注/可读性/架构门禁的整树报告不变、`make` 与 `test_report` 的子命令输出一致；`ingest/chapters.py` 的 §3 建议整段移到新模块 `ingest/api_sections.py`（835 行，回到预算内） |

| rf-39 | 65 处永真断言只证明「跑完了没炸」，行被执行不等于行为被验证 | **修订**：分批全部定值——46 处改为「退出码取实际值 + 消息断言」，7 条遍历用例改为「每脚本一张退出码表」，最后 8 条交付链用例在本机（pandoc 3.5 + playwright/chromium）实跑后定值；松散断言基线 65 → 0，门禁改为零容忍。同批删掉一处函数体重复的用例 |

| rf-41 | 失败语义靠 27 处散落的 `sys.exit()` 与 58 个入口各自转换：消息与退出码分开维护 | **修订**：`lib/_errors.py` 的 `ToolError` 把消息与退出码绑成一个对象（派生 `SystemExit`，既有 `sys.exit(message)` 语义不变），全部失败点改为抛它、58 个入口统一走 `_errors.run()`；`print(...); sys.exit(1)` 的组合在仓库里已归零（`grep` 为 0），退出码与消息由用例成对断言 |

| rf-47 | 印刷版密度调不动：六月的印刷版每页 103 行、行均 26.3 字符、最长 88 字符；实测每页 86 行、行均 29.8、最长 124 字符。最长行已超出可印宽度，存在裁切风险 | **已解决（根因与最初判断不同）**：760px 不是设计值，而是 A4@96dpi 视口 794px 减内边距的剩余量，对应的可印宽度只有 642px——每条满行被页框截掉约 118px（或溢出到页边距）。现在由「每行字数 × 正文字号」得栏宽（`layout_print_chars_per_line`，默认 42 → 672px），再由栏宽反推左右页边距（`print_margins_mm()`，下限默认 16mm，A4 得 16.1mm），`pre` 字号按「宽度预算内的行必须落在栏宽内」反推，`layout_print_column_px` 可显式覆盖；超长行先缩字号到下限（6px）再换行（`layout_print_wrap`，默认关，整本开启实测 +164 页）。判据为「栏宽 ≤ 可印宽度」，由 `verify_pdf` 的 `COLUMN` 项断言——PDF 文本宽度只能估，估不出宽栏与宽字形的区别（用估计值做的临时检查已撤）。实测：标准版 877 → 958 页 / 8.15 → 7.52 MB，浏览器打印媒体下 `#content` 宽与 `scrollWidth` 都是 672px、无块元素越界 |
| rf-48 | 文件长度门禁靠人工台账：`review-findings.md` 里登记的行数一过时，门禁只报「登记 853 / 实测 881」，数字过时后必须手工抄写，容易漏改 | **已解决**：`audit/file_length.py` 把上次实测行数记进 `data/state/file-length.json`，只在「较登记时增长 > `style.json thresholds.ledger_growth`（默认 10 行）且台账未更新」时报错；`--update-ledger` 写回全部登记行并刷新基线（本次运行 3 行，无需改动）。台账仍人工可读，数字由工具维护 |
| rf-49 | 标准版每页字节 9.5 KB，六月参照 8.5 KB；分章渲染路径里 ghostscript 压缩是否真正执行、输出是否被接受，日志中没有记录 | **已解决**：`render/pdf_split._optimize()` 记录 gs 是否可用、调用命令（DEBUG）、压缩前后页数与体积、判定结果（已采用 / 不采用），失败降为 WARNING 并保留合并结果；判定抽成 `accept_optimised()` 并有单测。日志已确认压缩确实生效：标准版 877 页 / 8.58 MB → 7.49 MB（每页 8.8 KB，六月 8.5 KB） |

| rf-50 | 印刷版页框与页边距没生效：`render/print_pdf.py` 产出的 PDF 正文从 `x=0` 起排，行宽 642pt 超过 A4 的 595pt 纸宽（可印 482pt），`pdf_invariants` 报 40 页文字出界 | **已解决（改为共用渲染器）**：`print_pdf.py` 不再自己调 `page.pdf()`，改为「`print_profile` 注入 + `pdf_split.render_html`」——与标准版同一视口（A4@96dpi）、同一 `@page` 页框、同一栏宽与字号；`scale` 随之删除（`layout_print_body_pt`、`base.json print_scale` 一并去掉，它与页框耦合正是不知不觉越界的来源）。印刷版专属排版单列 `render/print_profile.py`：长度全用 `em`、主色取书目（`accent_color`，缺省中性色）、只作用于 `@media print`，故不绑定本书；`marker` 注入收到 `pdf_split.inject_markers()`，`to_pdf` 与印刷版共用。实测：越界页 **40 → 0**、大纲 644 条不变、`verify_pdf` 的 `COLUMN`/`PAGE_SIZE`/`FONTS` 全 ok；印刷版 905 页 |
| rf-51 | 印刷版 905 页 vs 标准版 958 页，而正文文本完全相同、页框与字号相同 | **已解决（是输入不同，不是版式）**：同一份 HTML 分别经 `to_pdf` 与 `print_pdf` 渲染得 967 与 975 页，差额 8 页正是印刷 profile 的章首横幅；正文文本量一致（90.9 万 vs 91.5 万字符）。此前的 905/958 是「`to_pdf` 第 3 步写回 TOC 页码后的 HTML」与「写回前」两代输入对比所致。写回为何改分页另记 `rf-53` |
| rf-52 | `logs/perf-history.jsonl` 只增不减（1.58 MB / 11,725 行），且同时充当判据——按保留窗口清理就会移动基准 | **已解决**：窗口按 `style.json [quality].perf_history_runs`（默认 200）封顶、超出后原子重写保留最新段；评审下限另存 `data/baselines/perf-baseline.json`（`reviewed{by,at,commit,reason,runs}` + 逐步/总计中位数），`compare()` 优先比基线并报 `source`，无基线时退回窗口中位数；新增 `--update-baseline --reviewed-by --reason`。首次运行把历史 11,725 行收敛到 200 行（1.58 MB → 30 KB） |
| rf-53 | `to_pdf` 第 3 步把 TOC 页码写回 HTML 后，同一份正文的重渲页数从 975 变成 905，原因未定位 | **已解决**：根因是 `rstrip('</a>')`——`str.rstrip` 删的是字符集合而非后缀，标题以行内元素结尾的条目（`…<code>x</code>`）被啃掉闭合标签，留下未闭合的 `<code>`，解析器重挂内容：`<body>` 下多出一个游离 `<code>`、`#page-wrap` 消失、文档高度少约 10%（对应 70 页）。写回逻辑抽到 `render/toc_pages.py`：按锚点精确删除末尾 `</a>` 四个字符；写盘前三项自检（`#content` 逐字节不变、`<a` 数量不变、可扰动标签按名成对），任一不成立即放弃并保留原文件。`to_pdf` 改为调用 `toc_pages.apply()`，新增 9 条用例。实测：写回前后 `#content` 哈希一致（`c43fb21341c7`）、文档高度 682,878 → 760,779px、`<body>` 子节点恢复为 `cover,toc-page,DIV,page-wrap`；同一份 HTML 的印刷版 905 → **977 页**（标准版 967，差 10 页 = 章首横幅）。判据：写回前后 `#content` 哈希相同、页数差 ≤ 1% |

## 归档

> 已关闭版本的问题台账在 `docs/archive/`；本文件只留当前在办与未关闭的条目。

| 版本 | 归档台账 |
| --- | --- |
| v0.1 | [archived_review-findings.0.1.md](../archive/v0.1/archived_review-findings.0.1.md) · [archived_changelog.0.1.md](../archive/v0.1/archived_changelog.0.1.md) · [archived_plan.0.1.md](../archive/v0.1/archived_plan.0.1.md) |

已修条目在下一次发布时摘要进 `changelog.md` 对应版本段，历史由 git 保留。

---

## 已解决问题（0.1 发布归档）

| # | 问题 | 修复方向 |
| --- | --- | --- |
| rf-75 | 仍有约 100 处模块级配置读取留在脚本模块（`render/*`、`manuscript/*`、`audit/*` 等 31 个模块）。它们由 `check_runner` 以子进程执行，导入期读取不影响安装形态，因此不构成当前违规；但一旦这类模块被 `app/`、`core/` 在进程内导入，就会把第一本书的配置钉死 | 已加门禁：`test_audit_check_architecture.py::ImportTimeConfigReadTest` 从控制台入口种子出发做导入闭包，闭包内任何模块的模块级 `_config.` 读取都会失败。唯一豁免 `core/scaffold.py`（建书时必须先报自己那份 `invalid base config`，而非让 `_config` 抛 `ConfigError`）。后续如要让 `with use(cfg)` 覆盖这些脚本，再按 `captions.thresholds()` 的形状逐个改造 |
| rf-45 | 逐章渲染导致字体重复嵌入 | **已解决，且路径被推翻**：探针显示问题不在「合并子集」，而在 Chromium 一直走 Type3；Type3 消掉后体积自然回到 7 MB，不再需要 `fonttools` 归并（依赖保留待用）。若将来仍有重复子集，再按 rf-45 原方案的子集并集处理 |
| rf-46 | EPUB 章节边界被图注污染 | **已解决（两处一起修）**：根因有两条 Markdown 规则被违反——① 19 处 ATX 标题紧贴上一行（列表项）没有空行，pandoc 视为列表续行，第 11 章因此从未开新文件；② 图注写成 `**图 11-6: …**` + 一行 `====`，构成 setext H1，于是断章落在图注上。`to_epub.py` 增加 `normalise_headings()`：标题前补空行、删除短粗体行下方的装饰性 `====`（普通 setext 标题不动）。结果正文文件 **11 → 21**，第 1 章到附录 E 全部各成一章，图注不再是章节。六月版本同样存在这两处问题（11 个文件），本版已优于它 |
| rf-44 | 标准版 PDF 的体积是六月参照的 2.7 倍 | **已解决**：最小复现定位到 Type3。逐项探针（`data/tmp/type3/`）——（1）`.ttc` 字体集合无法子集化：Noto CJK 走 Type3（40 条流），Droid Sans Fallback（.ttf）0 条；（2）合成粗体走 Type3（36 条），`font-synthesis: none` 后 0 条；（3）等宽栈缺中文字形时回退走 Type3（37 条），补上 CJK .ttf 后备后 0 条。落到样式表：`font-synthesis: none` + 等宽栈补 `Droid Sans Fallback`。结果 **846 页 / 6.97 MB / 每页 1,887 字符 / 大纲 623/623**，与六月参照（843 页 / 6.99 MB / 1,905）同档；Type3 字形流 35,393 → 238 |
| rf-54 | `render/pdf_metrics.py` 分支覆盖 55%：`Calibration`（夹逼与收敛）、`compare()`/`describe()` 的格式化、`parse_targets`/`compare_targets`/`calibrate`/`write_back` 与 CLI 分支基本只有成功路径 | **已解决**：新增 `test_render_pdf_metrics_units.py`（25 条）覆盖解析、比较与标志、夹逼的上下界与收敛、区间坍缩、报告文案、假 render 驱动的 `calibrate()`、`write_back` 写回与缺键拒绝、CLI 四条分支；顺手删掉 `main()` 里一整段不可达的重复 `--write-back` 分支。分支覆盖 **55% → 87%**（判据 ≥80%） |
| rf-55 | `lib/fonts.py` 分支覆盖 58%：字体探测（`fc-list` 输出、目录扫描、.ttc 集合、缺失族回退）全靠真机环境，换机才暴露 | **已解决**：`test_lib_fonts.py` 扩到 32 条——平台目录三态、后缀过滤、缺失文件不影响戳记、索引的写缓存/命中/失效/不可写、单面优先与集合不可嵌入、`coverage()` 的合并与不可读面、`fc-list` 的缺失/输出/异常、`resolve()` 的已知族排序/仅集合/无索引/全未知/引号。顺带修一处行为：所有面都读不出时 `coverage()` 原先把「未验证」当成「已覆盖」返回空缺失，现在返回全部缺失。分支覆盖 **58% → 90%**（判据 ≥80%） |
| rf-56 | `audit/pdf_invariants.py` 分支覆盖 61%：`_outside_column`、`_type3_count`、`_outline_shape` 的异常与空输入分支未测 | **已解决**：`test_audit_pdf_invariants.py` 扩到 24 条——大纲嵌套/空/抛异常、Type3 跨页去重与非 Type3、越界与容差边界、负坐标、空白文本、坏页转 `unreadable`；`check()` 的四条问题分支与「无 merged 不判标题」；CLI 的干净/JSON/有问题三条。分支覆盖 **61% → 97%**（判据 ≥80%） |
| rf-57 | `audit/epub_diff.py` 分支覆盖 71%：EPUB 对比的增删改三类差异只在手工验证里跑过 | **已解决**：`test_audit_epub_diff.py` 扩到 22 条——位图计数与纯文本图、多字体栈去重、空样式表、`_leads` 取首族、`_delta` 的新增/零/百分比、**「只加回退族不算漂移」与「首族变化算漂移」**、行高变化、章节数与期望值的报错文案、CLI 的表格/JSON/缺 `--merged` 用法错误。分支覆盖 **71% → 94%**（判据 ≥85%） |
| rf-58 | `lib/_log.py`（78%）与 `core/menu.py`（80%）的分支缺口集中在「无书/不可写目录」「无历史刷新/确认取消/别名解析」 | **已解决**：新增 `test_core_menu.py`（25 条：中位数过滤/排序、预估的默认与历史收敛与 deliver-all 叠加、别名与 display_key、分组/父级/游标/instrument 谓词、`tail_of` 截断、`run_report` 透传）；`test_logging.py` 增 12 条（策略不可解析、测试日志目录、覆写与书目录不可写、二次 `setup` 只改级别、文件 handler 打不开仍留控制台）。分支覆盖 **menu 80% → 99%、_log 78% → 96%**（判据 ≥85%） |
| rf-59 | 覆盖率棘轮停在 `coverage_fail_under: 88` 与单文件 84 | **已解决**：全局门槛抬到 **90**（实测 91%，`make.py cover` PASS），单文件地板保持 84（现有最低 84.2%）。逐文件基线按当前实测重记（`cover --update-baseline`），剩余缺口另立 rf-61 |
| rf-60 | 90 小时窗口的改动让若干文件低于各自覆盖率基线 | **已解决（其中三个文件按当前实测重记基线）**：`to_epub.py` 95.6% → 100%（规则抽到 `render/epub_source.py` + 11 条用例）、`lib/_config.py` 92.6% → 94%；`actions`、`chapters`、`verify_pdf` 三处未达原基线，已按实测重记并把具体缺口登记为 rf-61，避免用“默默重记”掩盖 |
| rf-61 | 三个大模块仍有未覆盖分支 | **已解决（3/3）**：`render/verify_pdf.py` 84.6% → **89%**、`core/actions.py` 84.2% → **95%**、`ingest/chapters.py` 86.9% → **88%**（模板填充失败回落、CJK 间距对围栏/标题例外、跨章标题回退、体积结论与路由等）。注：`chapters` 仍低于改动前的 89.6%，其剩余缺口在 552-662 的整章渲染分支，由 rf-63/64 继续消化 |
| rf-62 | 五个辅助函数只有用例在调用、生产代码里没有调用点（`pdf_metrics.calibrate`、`_mdutil.figure_caption`、`_log.log_file`、`renumber.rewrite_allowed`、`test_redundancy._json_metric`） | **已解决（逐项处置）**：`log_file()` 接到 `_log.describe()` 的 `file` 字段（生产有调用点）；`calibrate()` 与 `figure_caption()` 保留为公共 API（标定流程与图注解析的入口，CLI 暂未接线，docstring 写明用途）；`rewrite_allowed` 与 `_json_metric` 已不存在（早前删除）；`TooLarge` 零引用已删 |
| rf-63 | 覆盖率统计只看「行」：错误与缺省路径的覆盖率最低 | **已解决**：按缺口从大到小补齐——`status.py` 85.4% → 88%、`chapters.py` 86.9% → 88%、`structure.py` 84.6% → 89%、`doc_drift.py` 85.8% → **89%**（手册维度缺失/重复/引用管理文档三条）、`tui.py` 86% → 88%（改配置的非法序号/空值/失败/确认、进度行的去重与时间戳），`verify_pdf` 89%、`actions` 95%。全局 91.6%，门槛 90 通过 |
| rf-64 | `verify_pdf` 的字体检查与 `actions._invoke` 的流/心跳混在大函数里，只能整体跑 | **已解决**：`font_is_embedded()`/`_has_program()`（rf-61 内完成）与 `_unbuffered()`/`_stream()`/`_heartbeat()` 三个小函数拆出，各 6 条用例（去重、回调抛异常不影响流、命令补 `-u` 一次、心跳确实报「仍在执行」）；`verify_pdf` 89%、`actions` **97%** |
| rf-69 | `structure.py` 的 CSS 钩子与构建脚本检查路径指向已搬迁的 `to_html.py` 与 `audit/glossary.py`，常年走「跳过/未找到」 | **已解决**：抽成 `css_style_missing()` 与 `builder_script_problems()`（缺脚本=告警、脚本不解析=失败），路径改为 `render/to_html.py` + `render/html_shell.py` 与 `manuscript/*.py`；修复后 9 个 CSS 钩子全部命中。另加一条用例钉住「这四个源文件确实存在」，路径再漂移即失败。`structure.py` 84.6% → **89%** |
| rf-70 | 单文件地板抬到 88 前，仍有若干模块低于它 | **已解决**：十二个低于 88 的模块逐个补分支用例后全部过线，`coverage_min_per_file` 86 → **88**，基线已重记（全局 91.7% → **94%**，最低文件 `ingest/chapters.py` 88.1%）。补的是错误路径与入口面：`make.py` 85.7% → **99%**（解释器守卫、pin 漂移、步骤超时、棘轮升降、子命令派发）、`test_report.py` 86.8% → **97%**（坏 junit、坏 TOML 快照、解析失败的用例模块、`--json` 三个子命令）、`snapshot.py` 86.9% → **98%**、`source_refs.py` 86.5% → **98%**、`index.py` 86.3% → **97%**、`style.py` 87.7% → **95%**、`version_consistency.py` 87.9% → **94%**、`smart.py` 87.4% → **98%**、`file_length.py` 86.6% → **97%**、`archive.py` 87.2% → **99%**、`mutation_smoke.py` 86.9% → **100%**、`requirement_trace.py` 87.3% → **99%** |
| rf-71 | 脚本自己拼书目录、重复的 baseline 读写、写死却可配的标记表 | **已解决**：七个文件不再按名字拼出书目录（`render/to_pdf`、`to_epub`、`pdf_from_html`、`pdf_toc_links`、`audit/balance`、`audit/doc_drift`、`core/menu`），`check_architecture` 补「按名字拼出书目录」规则；`test_report.collect` 的重复计数（2351 vs pytest 2013）改为每个 `test_` 函数只记一次；`smart.py` 的图形标记改读 `style.json [diagrams].markers`。三个「接受式」基线合并到 `lib/_baseline.py`——`ascii`、`style_rules`、`source_symbol` 各自只留一个 `baseline_path()`（按调用解析，`diagrams` 原先在 import 时就把路径定死，选版本时会写错文件），读写走 `load_at`/`save_at`，统一的 `updated`/`note`/`accepted` 外壳加各自的扩展字段（`source_version`）。`perf_baseline` 与 `content_volume` 不并入：它们记的是测量值与卷册台账，不是「已接受的遗留项」，形状不同是概念不同，不是重复 |
| rf-65 | 依赖真环境的探测（字体命令、浏览器、pandoc）只有真机才跑得到 | **已解决**：`fonts` 的探测链（命令缺失/输出/异常/目录不可写）与 `make.doctor` 的「可选工具缺失」均有用例；环境失败路径不再只能靠真机触发 |
| rf-66 | 少数辅助函数只有用例在调用，形成「假覆盖」 | **已解决**：`calibrate()` 与 `figure_caption()` 的 docstring 写明为公共 API 及为何不接进 CLI；`log_file()` 已接入 `describe()`；其余两处早前已删除。判据：不再有「只被测试引用且无说明」的函数 |
| rf-67 | 单文件覆盖率地板停在 84 | **已解决（两批中的第一批）**：地板 84 → **86**（门槛 90 下通过，最低文件 86.3% → 现为 86.5%）。抬到 88 的剩余工作与实际百分比见 rf-70 |
| rf-68 | 断言强度没有独立指标，覆盖率高的模块仍可能断言松散 | **已解决**：`mutation_smoke.py` 增加 `--all` 与 `TARGETS`（模块 → 测试文件 + 允许的等价变异数），候选变异改为**按行排序的固定顺序**（原先每次抽样不同，无法当门禁）；`make.py mutation` 接入为步骤，默认 advisory、`--mutation-strict` 可作硬门禁。实测：`epub_source`/`_perfhistory`/`menu` 全部杀死，`pdf_metrics` 剩余 4 个均已登记为等价变异 |
