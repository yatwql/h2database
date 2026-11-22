# 多书并行维护：设计与边界

> 定位：让同一套工具链服务于**多本书、每本书的多份手稿**，并说明哪些东西必须按书隔离。
> 面向的实现细节在 `technical.md`，本文只说形态与约束。

## 1. 问题

今天的仓库是「一书一检出」：`_config` 里的 `Config(root)` 已经能解析任意书根，但

- 没有任何入口指定「这次跑哪本书」：`root` 缺省取 `BOOK_ROOT` 或工具链所在 checkout；
- 派生状态（`data/state/`）、基线（`data/baselines/`）、产物（`dist/`）、日志都只有一份，
  第二本书一进来就与第一本互相覆盖；
- 门禁按「工具链与书同仓」写路径（`check_architecture.py` 的字面量白名单含 `books/`，
  测试夹具按工具目录推导书根）。

于是要维护第二本书，只能再检出一次整个工具链。

## 2. 目标形态

分成两级，先做 B，需要时再升到 C。两者共用同一套配置与隔离规则。

### B — 一仓多书

```text
books/
  shared/            # 工具链默认与共享资源（随工具走）
  <slug>/            # 一本书：换书即整个目录替换
    data/book/book.toml
    data/manuscript/…
    data/config/{base,style}.json
    data/language/zh.json
    dist/
```

### C — 工具链独立成包

书目录自包含，工具以命令安装（`bookctl --book <dir>`）；共享默认随包分发
（`importlib.resources`），书里只留覆盖项。

## 3. 必须按书隔离 vs 可以共享

| 归书 | 归共享 |
| --- | --- |
| `data/book/`（身份、章节表、案例流水线） | `src/python/`（工具链） |
| `data/manuscript/`、`dist/` | `templates.toml`、`language/*.json` |
| `data/state/`、`data/baselines/`、`logs/` | `base.json` 的默认值 |
| `data/config/style.json`（写作规则） | — |

判据：**两份书各自有值、且互相比对没有意义的东西，必须按书隔离**。体积基线、术语表、
已知问题账本都属于此类——跨书比对只会产生假差异。

## 4. 配置分层

三层，自下而上覆盖，越靠上越「这本书独有」：

1. 工具链默认（B 阶段放在与各书目录并列的 shared/ 下，C 阶段随包分发）；
2. 共享覆盖（部署方统一调整，如源码树语言）；
3. 本书覆盖（`data/book/book.toml`、`data/config/style.json`）。

今天的实现只有 2 + 3（`base.json` + `style.json`），外加一份兼容用的单文件
`config.json`。加第 1 层是 B 阶段的必要条件：否则 C 阶段要把已经散在书里的默认值收回来。

## 5. 手稿的多版本轴

同一本书出多版（删节版、不同语种、不同年份）时，手稿目录再分一层：
`data/manuscript/<edition>/`，`book.toml [editions]` 声明可选版本，`--edition` 选择。

派生状态与体量基线必须跟着分：`state/<edition>/`、`baselines/<edition>.json`。
否则第二份手稿一进，`content-volume` 就会拿甲版本的体积下限去判乙版本。

## 6. 非目标

- **不做多书合一构建**：一本书一份产物；多本合并成一个 PDF/EPUB 不在范围内
  （`technical.md` §10 已登记）。
- **不做跨书一致性检查**：术语、图号、引用只在本书内判定。
- **不改判定口径**：分层只决定「读哪个文件」，不改变任何阈值语义。

## 7. 迁移路径

1. `_config` 常量 → `Config(root)` 对象（已完成，行为与产物等价）；
2. `--book` 入口 + 向上查找 `data/book/book.toml`；
3. 手稿 edition 轴；
4. （条件成熟时）工具链独立成包：抽 `pyproject`、默认配置进包、`--book` 必填。

第 1 步是其余三步的公共前提；第 2 步做完即可「一个进程读多本书」，
第 3 步才真正解决「多份手稿」。

## 8. 门禁影响

- 每条门禁的扫描根一律取 `cfg.root`，不再从工具目录推导；
- 路径字面量检查（`check_architecture.py`）的白名单改为相对书根的形式；
- 测试夹具按「工具目录」与「书目录」两个独立概念提供根路径；
- 新增用例必须钉住：两本书互不串值、切换失败也还原、缺文件仍报 `ConfigError`。
