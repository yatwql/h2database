# CLI 使用

> 维度：**命令行——入口、参数、退出码与组合用法**
> 软件：bookwright — 源码分析成书工具 v0.1

命令行入口是 `books/src/python/app/cli.py`。日常请用薄封装 `books/scripts/bookctl`
（Windows：`bookctl.ps1`），它会自己找解释器（`books/.venv` → `$PYTHON` → `python3`），
不必输入 python 路径：

```bash
books/scripts/bookctl status              # 书籍 + 配置 + LLM 状态
books/scripts/bookctl analyze             # 源码 → 手稿：默认只刷新事实块，正文不动
books/scripts/bookctl analyze-llm         # 同上，并给新写/重写的章节用 LLM 起草导读/小结
books/scripts/bookctl analyze --refresh-facts   # 显式声明“只刷事实块”（与默认同义，脚本直调时用）
books/scripts/bookctl analyze --force     # 整篇重写（先备份到 data/tmp/generated-backup/）
books/scripts/bookctl build               # 手稿 → 合并 Markdown + HTML
books/scripts/bookctl check               # 全部质量门禁
books/scripts/bookctl test --full         # 含 chromium/pandoc 的完整测试
books/scripts/bookctl deliver             # PDF + EPUB
books/scripts/bookctl llm-ask "解释 MVCC"  # 用配置的 provider 回答
books/scripts/bookctl make check --timings  # make.py 原样透传
books/scripts/bookctl doctor              # 依赖与环境
books/scripts/bookctl settings            # 列出可写配置项
books/scripts/bookctl settings set dist out   # 改配置（写回配置文件并重载）
```

等价的直接调用（CI/调试）：

```bash
books/scripts/launch.sh cli status         # 书籍 + 配置 + LLM 状态
books/scripts/launch.sh cli analyze        # 源码 → 手稿（digest → outline → chapters）
books/scripts/launch.sh cli analyze-llm     # 同上，导读/小结由 LLM 起草
books/scripts/launch.sh cli build          # 手稿 → 合并 Markdown + HTML
books/scripts/launch.sh cli check          # 全部质量门禁
books/scripts/launch.sh cli test           # 测试套件
books/scripts/launch.sh cli deliver        # 按需：PDF + EPUB + 校验
books/scripts/launch.sh cli llm-ask "解释 MVCC" --scenario summary
```

也可以直接调脚本（CI 里更常见）：

```bash
python books/src/python/app/cli.py build
python books/src/python/make.py check --timings
```

## 选择书籍与版本

一份工具链可以服务多本书。选书有三个来源，优先级固定：

| 来源 | 写法 | 说明 |
| --- | --- | --- |
| 命令行 | `--book <书目录>` | 显式指定，缺 `book.toml` 时退出码 2 并给出试过的路径 |
| 环境变量 | `BOOK_ROOT=<书目录>` | 子进程与脚本继承，`bookctl make …` 也用它 |
| 向上查找 | 无 | 从当前目录向上找第一本带 `book.toml` 的书 |

```bash
books/scripts/bookctl status --book ../other-book     # 看另一本书
books/scripts/bookctl check --book ../other-book      # 检查另一本书
books/scripts/bookctl analyze --edition abridged      # 一本书的某个版本
books/scripts/bookctl make build --book ../other-book # 透传给 make.py
```

`--books-dir <目录>` 指向「装多本书的目录」，配合 `--book` 时可临时换书目目录；只给
`--books-dir` 而不给 `--book` 时：目录里只有一本就直接用它，有多本则列出「书名 [目录名]」
并退出码 2（不做猜测），一本都没有同样退出码 2。环境变量 `BOOKS_DIR` 与 `--books-dir`
等价，并且会覆盖 `book.toml [paths].library`。

`--edition` 选版本（`book.toml [editions]` 声明），缺省取 `default_edition`；
指向未声明的版本会报错并列出已声明的版本。产物、手稿、派生状态、体量基线都跟着
「书 + 版本」走，不同书之间互不覆盖。

## 退出码

| 码 | 含义 |
| ---- | ------ |
| 0 | 成功 |
| 1 | 门禁失败（输出里会说明哪一道） |
| 2 | 用法/配置/环境错误（缺配置、缺依赖、provider 不可用） |

## 常用组合

```bash
# 只看某一批门禁
python books/src/python/make.py check --only audit_links,doc_drift

# 构建并计时
python books/src/python/make.py build --timings

# 失败也继续跑完并汇总
python books/src/python/make.py check --keep-going
```

## 与虚拟环境

启动器优先使用 `books/.venv`；直接用 `python` 时请确保依赖已按
`requirements-dev.txt` 安装（见 `how-to-config.md` §6 与 `how-to-use.md`）。
