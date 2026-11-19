# 管理文档索引

工具链与项目概况见仓库上层的 [`books/README.md`](../../README.md)；
目录结构与归属规则见 [`folder.md`](folder.md)。

| 文档 | 职责 |
|------|------|
| `requirements.md` | 当前需求、交付物、内容范围 |
| `plan.md` | 实施计划、维护策略、风险与后续增强 |
| `testplan.md` | 质量门禁与验证命令（验证的唯一权威） |
| `changelog.md` | 版本变更记录 |
| `review-findings.md` | 审查问题清单与修复状态 |
| `style-guide.md` | 写作与格式规范 |
| `folder.md` | 目录结构、文件归属、清理规则 |
| `archive/` | 已归档的计划与历史审计快照 |

## 维护原则

- **同一事实只有一个权威位置**：验证看 `testplan.md`，结构看 `folder.md`，
  写作看 `style-guide.md`，其余文档只做引用。
- **不重复统计数字**：以 `cover.md` 自动更新结果与 `final_check.py` 输出为准。
- **版本号对齐**：管理文档版本与 `books/data/manuscript/cover.md` 一致。
- **评审留痕**：正式评审按架构师／文档工程师／程序员（源码引用）／图书编辑
  四视角并行，问题记入 `review-findings.md`（CRITICAL/HIGH/MEDIUM/LOW），
  完成的改动记入 `changelog.md`。
