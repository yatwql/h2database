# 克隆的源码仓库

`[sources].repo` 指向一个 git 仓库时，`core/fetch_source.py` 把仓库克隆到本目录下的
`<owner>__<name>/`，分析读的就是那份代码。目录内容有意不入库（见 `.gitignore`），
只有这份说明随仓库走。

```bash
books/scripts/bookctl --help          # 或直接用下面的脚本
python books/src/python/core/fetch_source.py            # 按 book.toml [sources] 克隆/更新
python books/src/python/core/fetch_source.py --dry-run  # 只打印将执行的 git 命令
```

规则：

- 目标目录已存在时**不覆盖**；`--update` 才会 `git fetch` 并切到配置的 `ref`。
- 仓库标识取 URL 的 `owner/name`（去掉 `.git`），重名会加上序号而不是互相覆盖。
- 克隆失败时保留半成品目录并给出原因，下一次运行先清理再试。
