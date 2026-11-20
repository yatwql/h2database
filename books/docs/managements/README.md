# 管理文档索引

> 软件：bookwright — 源码分析成书工具 v0.1

工具链与项目概况见仓库上层的 [`books/README.md`](../../README.md)；
目录结构与归属规则见 [`folder.md`](folder.md)。

按"要什么 → 怎么做 → 谁判、何时判 → 写成什么样 → 目录归属 → 计划 → 变更记录"排列：

| 文档 | 职责 |
| --- | --- |
| `requirements.md` | 第一步：功能需求（FR）、交互需求（IR）、非功能需求（NFR）与验收判据 |
| `plan.md` | 实施计划、维护策略、风险与后续增强 |
| `testplan.md` | 判据清单：每道门禁的标准、级别与验证命令（验证的唯一权威） |
| `quality-model.md` | 质量策略：脚本与模型的判定分工、三种起点、基线生命周期、复核成本 |
| `technical.md` | 第二步：技术设计——总体架构、分项设计、架构约束与扩展点 |
| `analysis-doc-standard.md` | 源码分析文档的通用内容标准与验收清单 |
| `style-guide.md` | 写作规则与检查机制（取值在 `data/config/style.json`） |
| `tui-interaction.md` | 技术设计·渠道层子契约：键位、反馈、确认、光标 |
| `folder.md` | 目录结构、文件归属、清理规则 |
| `changelog.md` | 版本变更记录 |

## 维护原则

- **同一事实只有一个权威位置**：需求看 `requirements.md`，设计看 `technical.md`，
  判据看 `testplan.md`，策略看 `quality-model.md`，结构看 `folder.md`，写作看
  `style-guide.md`；其余文档只做引用。
- **不重复统计数字**：统计以封面文件为准，任何文档不再抄一份。
- **工具文档与书无关**：本文档集描述工具本身，不写入某一本书的书名或统计；
  书名、章节与阈值都在 `books/data/` 的配置里。
- **版本对齐**：管理文档头的版本与 `book.toml` 的文档版本一致。
