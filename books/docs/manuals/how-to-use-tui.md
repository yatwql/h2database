# TUI 使用

终端界面把同一批动作做成菜单，适合在服务器或本地交互操作。

```bash
books/scripts/launch.sh            # 默认进入 TUI
books/scripts/launch.sh tui
python books/src/python/app/tui.py # 等价
```

## 菜单

```text
书籍工具链
  1. analyze   源码 → 手稿（digest → outline → chapters）
  2. build     手稿 → 合并 Markdown + HTML
  3. check     运行全部质量门禁
  4. deliver   构建 PDF 与 EPUB（按需）
  5. llm-ask   用配置的 provider 回答一个问题
  6. status    显示书籍、配置与 LLM 状态
  7. test      运行测试套件
  q. 退出
```

输入序号回车执行，执行完打印输出与 `[退出码 N]`；`q` 或空行退出。

## 非交互（脚本化）

```bash
python books/src/python/app/tui.py --once status   # 跑一个动作就退出
echo 3 | python books/src/python/app/tui.py        # 管道输入也能用
```

## 说明

- TUI 与 CLI、Web 共用 `app/actions.py`，行为完全一致（无独立业务逻辑）。
- 长动作（analyze/deliver）会把子进程输出原样打印；日志另写 `books/logs/`。
- 在无 stdin 的环境（部分 CI）请用 `--once` 或改用 CLI。
