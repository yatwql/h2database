# CLI 使用

命令行入口是 `books/src/python/app/cli.py`。日常请用薄封装 `books/scripts/bk`
（Windows：`bk.ps1`），它会自己找解释器（`books/.venv` → `$PYTHON` → `python3`），
不必输入 python 路径：

```bash
books/scripts/bk status              # 书籍 + 配置 + LLM 状态
books/scripts/bk analyze             # 源码 → 手稿
books/scripts/bk build               # 手稿 → 合并 Markdown + HTML
books/scripts/bk check               # 全部质量门禁
books/scripts/bk test --full         # 含 chromium/pandoc 的完整测试
books/scripts/bk deliver             # PDF + EPUB
books/scripts/bk llm "解释 MVCC"      # 用配置的 provider 回答
books/scripts/bk make check --timings  # make.py 原样透传
books/scripts/bk doctor              # 依赖与环境
books/scripts/bk settings            # 列出可写配置项
books/scripts/bk settings set dist out   # 改配置（写回配置文件并重载）
```

等价的直接调用（CI/调试）：

```bash
books/scripts/launch.sh cli status         # 书籍 + 配置 + LLM 状态
books/scripts/launch.sh cli analyze        # 源码 → 手稿（digest → outline → chapters）
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
