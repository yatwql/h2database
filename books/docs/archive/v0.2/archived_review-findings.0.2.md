> 涵盖版本：0.2
> 归档时间：2026-11-27
### 本版本已修复（0.2）

| # | 问题 | 修复方向 |
| --- | --- | --- |
| rf-73 | **已修（导入期读配置部分）**：`audit/captions.py`、`audit/exercises.py`、`audit/balance.py`、`release.py` 的模块级配置读取改为调用时读取（`exercises` 的槽位标题与提示/回顾正则改为 `language_shapes()`）。剩下的一半——「`manuscript/`、`audit/` 不得出现本书专有词」的门禁规则——转记 rf-74 | — |
| rf-74 | 本书专有词写进工具链没有门禁拦 | **已解决**：`check_architecture.py` 新增 `book_vocabulary` 检查，词表由书在 `base.json [toolchain]` 声明（词表见 `data/config/base.json [toolchain]`），按整词匹配 `src/python/` 全文，命中即报；配套用例覆盖「命中」「子串不算」「未声明词表不报」。同一条 `technical.md` §2.4 写明「不绑定某一本书、也不绑定某一棵源码树」的两条通用性约束 |
| rf-72 | 慢档（`make.py cover --full`）有一处低于单文件地板 | **已解决**：`audit/order_dependence.py` 原只在 p2 顺序依赖探测里被驱动，快档不测量它。新增 `test_audit_order_dependence_units.py`（tier:fast）覆盖 `compare`、`bisect`、`run_prefix`、`collect`、worker IPC 与 CLI 分支，模块在快档回到地板之上；慢档端到端用例保留 |

## 归档

> 已关闭版本的问题台账只在上面的归档文件里；本文只留在办与未关闭的条目。

- [`archived_review-findings.0.1.md`](../v0.1/archived_review-findings.0.1.md) — v0.1（2026-11-26 发布）
