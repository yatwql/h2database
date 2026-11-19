# 管理文档索引

工具链与项目概况见仓库上层的 [`books/README.md`](../../README.md)；
目录结构与归属规则见 [`folder.md`](folder.md)。

按"要做什么 → 怎么验 → 依据什么约束 → 怎么改 → 变更记录"排列：

| 文档 | 职责 |
| --- | --- |
| `requirements.md` | 当前需求、交付物、内容范围 |
| `plan.md` | 实施计划、维护策略、风险与后续增强 |
| `testplan.md` | 质量门禁、交付分档与验证命令（验证的唯一权威） |
| `technical.md` | 工具链架构约束：分层、依赖矩阵、渠道纯净、勾稽到机检 |
| `toolchain-design.md` | 流水线与配置模型的设计说明（为什么这样分阶段） |
| `analysis-doc-standard.md` | 源码分析文档的通用内容标准与验收清单 |
| `style-guide.md` | 写作与格式规范 |
| `tui-interaction.md` | TUI 交互契约：键位、反馈、确认、光标 |
| `folder.md` | 目录结构、文件归属、清理规则 |
| `changelog.md` | 版本变更记录 |

## 维护原则

- **同一事实只有一个权威位置**：验证看 `testplan.md`，结构看 `folder.md`，
  写作看 `style-guide.md`，其余文档只做引用。
- **不重复统计数字**：以 `cover.md` 自动更新结果与 `structure.py` 输出为准。
- **版本号对齐**：管理文档版本与 `books/data/manuscript/cover.md` 一致。
- **改动留痕**：正式评审按架构师／文档工程师／程序员（源码引用）／图书编辑
  四视角并行，结论与改动记入 `changelog.md`。
