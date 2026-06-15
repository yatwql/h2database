# 管理文档索引

本目录包含 H2 源码分析文档的项目管理文档，各文档职责如下：

| 文档 | 职责 | 权威内容 |
|------|------|---------|
| `requirements.md` | 当前需求、交付物、内容范围 | 需求摘要、非目标、版本历史引用 |
| `plan.md` | 当前实施计划、维护策略、风险 | 已完成阶段、后续增强项、维护策略 |
| `testplan.md` | 质量标准与验证流程 | 权威验证命令、质量门禁、拒绝标准 |
| `changelog.md` | 版本变更记录 | 从 v1.0 至今的完整版本历史 |
| `review-findings.md` | 审查问题追踪 | 各轮审查发现的问题清单及修复状态、v6.0 阶段问题清单 |
| `style-guide.md` | 写作风格指南 | 术语选用、句式风格、图注、图簇、延伸思考等约定 |
| `baseline-*.json` | 基线度量快照 | `balance_check.py --baseline` 写入，作为 v6.0 各阶段对照基准 |
| `captions-baseline-*.json` | 图注质量基线快照 | `_audit_captions.py` 输出的图注度量基线 |
| `archive/` | 已归档计划与历史审计 | 已完成阶段的旧版计划文档、历史审计快照 |

## 核心原则

- **同一事实只维护在一个权威位置**：各管理文档职责分离，避免重复维护。
- **统计数据以 `cover.md` 自动更新结果和 `final_check.py` 输出为准**：不在多个管理文档中重复维护数字。
- **验证流程以 `testplan.md` §1 为唯一权威来源**：`requirements.md` 和 `plan.md` 只保持引用关系。
- **版本号保持一致**：所有管理文档版本号与 `cover.md` 对齐。

## 目录结构

```text
docs-stm/
├── management/                    ← 本目录
│   ├── README.md                  — 本文件（管理文档索引）
│   ├── requirements.md            — 需求文档
│   ├── plan.md                    — 实施计划
│   ├── testplan.md                — 质量标准与测试计划
│   ├── changelog.md               — 变更记录
│   ├── review-findings.md         — 审查问题追踪
│   ├── style-guide.md             — 写作风格指南
│   ├── baseline-v5.0.json         — v5.0 基线度量快照
│   ├── captions-baseline-*.json   — 图注质量基线快照
│   └── archive/                   — 已归档计划与历史审计
├── plan/                          — 阶段性实施计划（版本路线 PRD/任务清单）
├── front/                         — 书籍前件（前言、版权、阅读指南）
├── back/                          — 书籍后件（术语表、参考文献、索引）
├── ch*.md                         — 12 章源章节文件（10 个源文件）
├── appendix-a-case-studies.md     — 附录 A：端到端案例研究
├── appendix-b-version-changes.md  — 附录 B：源码版本变更说明
├── cover.md                       — 封面与统计数据
├── h2-source-code-analysis.md     — 合并 Markdown 交付物
└── tools/                         — 正式生成、审计和验证工具
```
