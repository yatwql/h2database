# TUI 使用

> 维度：**终端界面——屏幕分区、按键与状态回报**

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

两级菜单：主菜单选类目，类目里选动作。每一屏顶部都有路径带，任何时候都知道自己在第几层。

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
 主菜单

   [1]  源码 → 手稿
   [L]  源码 → 手稿（LLM 润色导读/小结）  LLM
 ❯ [2]  手稿 → Markdown + HTML
   [3]  PDF + EPUB（按需）
   [4]  质量：门禁与测试
   [5]  配置：状态、配置项与 LLM
   [0]  退出

   [0] 返回上一级  [q] / [Ctrl+C] 退出
   [↑/↓] 选择 · [Enter] 执行 · 数字键直达 · [?] 帮助
```

菜单只有两层：

高频动作在第一级，分组才进第二级：

```text
主菜单   1 analyze  l analyze-llm  2 build  3 deliver  0 退出
         4 质量  5 配置与状态
质量     1 check  2 test  0 返回
配置     1 status  2 llm-ask  3 配置项  4 LLM provider 优先级  5 doctor  0 返回
配置项   逐项列出可写键（书名、版本、手稿目录、产物目录、语言、日志级别、默认 provider）  0 返回
优先级   按回退顺序列出 provider，选中后按 u 上移 / d 下移  0 返回
```

## 按键

一次按键一次响应，不需要回车：按下的键立即生效，界面立刻回音；回车只表示
"执行光标所指项"。

| 键 | 作用 |
| ---- | ------ |
| `↑` / `↓` | 移动光标（首尾循环）；每屏各自记住位置 |
| `Enter` | 执行光标所指项（主菜单默认停在 `2 手稿 → Markdown + HTML`） |
| `1`–`9` | 直达执行对应项，光标随之移动 |
| `0` / `Esc` | 先收起结果 → 再返回上一级 → 在主菜单上按 `0` 才退出 |
| `q` / `Ctrl+C` | 任何层级直接退出 |
| `c` | 直接跳到「配置项」屏（省去一次 `5` → `3`） |
| `?` | 帮助 |
| `l` / `L` | 源码 → 手稿（LLM 润色）；菜单里带琥珀色 `LLM` 徽标 |

每次执行都会回显：执行中的状态行 → 输出尾部 15 行 → `✓/✗` + 用时 + 退出码 +
输出行数 → 日志位置。带 LLM 的动作还会多两行：调用前的 `预计：… 入 ~N token / 出 ≤M token ≈ 费用`，调用后的 `LLM：本次 … token ≈ 费用；今日累计 ≈ …`（达到 `daily_cost_limit` 时再加一行 ⚠ 提醒）。结果留在屏上直到你按下一个键；此时按 `0` 是**收起结果回到菜单**，
不会退出程序。

「源码 → 手稿」跑完会多做两件事，都在同一份结果里：

- 已有正文的章节文件**不会被覆盖**，只在结果里报 `skipped …（已有正文，--force 才覆盖）`；
  确实要按源码重生成时才加 `--force`（`bookctl` / 直接调脚本均可）。
- 末尾给一行**基线比对**：`内容体积：与基线一致`，或 `内容体积：N 项低于基线`。
  后者会把这次运行判为失败（`✗`），并提示下一步：先复核是不是某章被覆盖或删减；
  确认是有意收缩后再 `audit/content_volume.py --update-baseline` 重新记账。

想看逐项明细就跑「质量」屏的 `1`（全部质量门禁），或用
`python books/src/python/audit/content_volume.py` 单独看。`deliver` 这类重建全部产物的动作会先问一次 `[y/N]`。

颜色只在真实终端启用，`NO_COLOR=1` 可关闭。顶部两行身份信息用不同颜色区分：
第一行（青）是**软件本身**——英文名 `bookwright`、中文名、工具版本；第二行（黄）
是**正在生成的书籍**（行首标注「书籍」）——书名与书籍版本。其下是源码目录与源码版本、手稿目录、
产物目录、语言/日志级别/LLM provider。

## 在界面里改配置

按 `5` → `3`（或直接按 `c`）进入「配置项」，列出可写项，输入序号再输入新值；`0` 返回。
每一项都写回它所属的配置文件，写后立即重载，头部随之更新：

```text
可修改项：
  1) title          <书名>                    来自 book.toml 的 [book].title
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
`data/config/base.json`；默认 LLM provider 与优先级 → `data/config/llm_provider.json`。
写后会立即重载配置，头部随之更新；非法值会被拒绝并提示原因。

### 调整 LLM provider 优先级

「配置」屏按 `5` → `4` 进入优先级屏，列表按**回退顺序**排列（上面的先用）：

```text
 1. deepseek-main  priority 10
 2. opencode-go    priority 20
 0. 返回上一级
```

选中编号后按 `u` 上移、`d` 下移；改动写回 `llm_provider.json` 的 `priority` 字段
（按 10 递增重排），下次调用即按新顺序回退。`0` 返回，回车取消。

## 非交互（脚本化）

```bash
python books/src/python/app/tui.py --once status   # 跑一个动作就退出
books/scripts/bookctl status                            # 更快：直接用 CLI
echo 4 | python books/src/python/app/tui.py        # 管道输入也能用
```

TUI、CLI、Web 共用 `core/actions.py`（动作）与 `core/settings.py`（配置），
三者行为一致。
