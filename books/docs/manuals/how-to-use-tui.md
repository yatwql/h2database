# TUI 使用

终端界面把动作、状态与常用配置放在一屏里，适合服务器或本地交互操作。

```bash
books/scripts/bookctl                 # 等价于 books/scripts/launch.sh tui
books/scripts/launch.sh tui
python books/src/python/app/tui.py
```

## 配色

界面只有一处定义调色板（`app/tui.py` 的 `PALETTE`），按“界面骨架安静、身份信息明亮、
可按键唯一高饱和”分层：

| 元素 | 颜色 | 作用 |
| --- | --- | --- |
| 边框与分隔线 | 暗灰 | 只做结构，不抢视线 |
| 字段标签（源码/手稿/产物/语言） | 中灰 | 次信息 |
| 软件名（第一行） | 亮青 + 粗体 | 界面最强的一处，直接回答“这是什么工具” |
| 书名（第二行） | 亮黄 + 粗体 | 与软件行区分，回答“在生成哪本书” |
| 菜单分组标题 | 亮青 | 分组边界 |
| 动作按键 | 亮绿 | 唯一饱和的操作色 |

`NO_COLOR=1` 时全部退化为纯文本，布局不变。

## 界面

```text
┌──────────────────────────────────────────────────────────────┐
│ bookwright · 源码分析成书工具  v0.1                           │ ← 青色：软件
│ 书籍 某系统源码剖析  v1.0                                    │ ← 黄色：书籍
├──────────────────────────────────────────────────────────────┤
│ 源码 /path/to/src  (源码版本)                                 │
│ 手稿 /path/to/books/data/manuscript                           │
│ 产物 /path/to/books/dist                                      │
│ 语言 java  日志 INFO  LLM deepseek-main                        │
└──────────────────────────────────────────────────────────────┘

 内容
   1) 源码 → 手稿
   2) 手稿 → Markdown + HTML
   3) PDF + EPUB（按需）
 质量
   4) 全部质量门禁
   5) 测试套件（快档）
 配置与状态
   6) 书籍 / 配置 / LLM 状态
   7) 用配置的 provider 提问
   8) 查看与修改配置
   9) 依赖与环境

   c) 修改配置      r) 刷新      ? 帮助      q) 退出
```

## 按键

| 键 | 作用 |
| ---- | ------ |
| `1`–`9` | 执行对应动作（输出与退出码就地显示） |
| `c` | 进入配置修改（见下） |
| `r` | 重新读取配置（改过文件后刷新头部） |
| `?` | 帮助 |
| `q` / `0` / 空行 / `Ctrl+C` | 退出（三者等价，界面底栏同时列出 `q / 0 退出` 与 `Ctrl+C 退出`） |

颜色只在真实终端启用，`NO_COLOR=1` 可关闭。顶部两行身份信息用不同颜色区分：
第一行（青）是**软件本身**——英文名 `bookwright`、中文名、工具版本；第二行（黄）
是**正在生成的书籍**（行首标注「书籍」）——书名与文档版本。其下是源码目录与源码版本、手稿目录、
产物目录、语言/日志级别/LLM provider。

## 在界面里改配置

按 `c` 会列出可写项（书名、版本号、手稿目录、产物目录、源码语言、日志级别、
默认 LLM provider），输入序号再输入新值即可：

```text
可修改项：
  1) title          H2 数据库引擎源码剖析     书名
  2) version        6.5                      版本号
  3) manuscript     data/manuscript          手稿目录
  4) dist           dist                     产物目录
  5) languages      java                     源码语言
  6) log.level      INFO                     日志级别
  7) llm.provider   deepseek-main            默认 LLM provider
选择要修改的序号（回车取消）: 4
dist 的新值（当前 dist）: out
已更新 dist = out
```

写入位置：书名/版本/目录 → `data/tmpl/book.toml`；语言/日志级别 →
`data/config/base.json`；LLM provider → `data/config/llm_provider.json`。
写后会立即重载配置，头部随之更新；非法值会被拒绝并提示原因。

## 非交互（脚本化）

```bash
python books/src/python/app/tui.py --once status   # 跑一个动作就退出
books/scripts/bookctl status                            # 更快：直接用 CLI
echo 4 | python books/src/python/app/tui.py        # 管道输入也能用
```

TUI、CLI、Web 共用 `app/actions.py`（动作）与 `app/settings.py`（配置），
三者行为一致。
