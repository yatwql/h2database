# 管理文档索引

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1-dev
> 定位：管理文档的**索引与维护原则**——只登记职责、权威位置与不重复原则，不重述
> 任何文档的内容。
目录结构与归属规则见 [`folder.md`](folder.md)。

按"要什么 → 怎么做 → 谁判、何时判 → 写成什么样 → 目录归属 → 计划 → 变更记录"排列：

| 文档 | 职责 |
| --- | --- |
| `README.md` | 本文件：管理文档索引、维护原则与权威位置划分 |
| `requirements.md` | 第一步：功能需求（FR）、交互需求（IR）、非功能需求（NFR）与验收判据 |
| `review-findings.md` | 问题台账：`rf-N` 编号、待处理按 H1–H3 分档、文件膨胀登记、已修摘要 |
| `testplan.md` | 判据清单：每道门禁的标准、级别与验证命令（验证的唯一权威） |
| `content-quality-policy.md` | 内容质量方针：脚本与模型的判定分工、三种起点、基线生命周期、复核成本 |
| `plan.md` | 计划项清单：`plan-N` 编号、按**时机**分 P1–P4、每项的现状 / 动作 / 验收 / 事实位 |
| `technical.md` | 第二步：技术设计——总体架构、分项设计、架构约束与扩展点 |
| `content-standard.md` | 内容标准（跨项目复用）：信息阶梯、事实要求、章节骨架、图示与练习 |
| `style-guide.md` | 写作规则与检查机制（取值在 `data/config/style.json`） |
| `DESIGN.md` | 设计契约总纲：三界面共有的身份、状态、颜色分工与文案基调 |
| `DESIGN-TUI.md` | 终端交互契约：屏幕分区、键位、反馈四段、确认、光标 |
| `DESIGN-WEB.md` | 网页控制台契约：路由、JSON 形状、页面结构、允许与禁止 |
| `folder.md` | 目录结构、文件归属、清理规则 |
| `changelog.md` | 版本变更记录 |

## 维护原则

- **同一事实只有一个权威位置**：需求看 `requirements.md`，设计看 `technical.md`，
  判据与级别看 `testplan.md`，判定分工与基线流程看 `content-quality-policy.md`，结构看 `folder.md`，写作看
  `style-guide.md`，界面看 `DESIGN*.md`；其余文档只做引用。
- **不重复统计数字**：统计以封面文件为准，任何文档不再抄一份。
- **不重复命令清单**：使用看 [`books/README.md`](../../README.md)，验证命令看
  `testplan.md` §1。
- **工具文档与书无关**：本文档集描述工具本身，不写入某一本书的书名或统计；
  书名、章节与阈值都在 `books/data/` 的配置里。
- **版本号写软件版本**：每份管理文档头都有 `> 版本：vX`，取 `lib/_version.py` 的软件
  版本；书籍版本（`book.toml`）只在书籍产物与封面出现，两者不得混用
  （`version_consistency.py` 强制）。
