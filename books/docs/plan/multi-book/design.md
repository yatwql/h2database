# 多书并行维护：设计与边界

> 定位：让同一套工具链服务于**多本书、每本书的多份手稿**，并说明哪些东西必须按书隔离、
> 哪些可以共享。实现细节在 `technical.md`，本文只说形态、约束与判定边界。
>
> 术语：**书根**指含 `data/book/book.toml` 的目录（当前就是 `books/`，多书形态下是
> 每个书目录）；**活动书**指 `_config.current()` 此刻指向的那一本；**版本**（edition）指
> 同一本书的一份手稿。书的目录标识沿用 `manuscript/archive.py::book_slug()` 的取值
> （合并名优先，否则由标题生成），不另造一套命名。
>
> 对应需求：`requirements.md` IR-10（一本书一份配置，书间不共享派生状态、基线与产物），
> 判据载体见 `testplan.md` §2.4。

## 1. 现状与真实缺口

配置已经能按书解析：`lib/_config.py` 的 `Config(root)` 读的是那一本书自己的文件，
模块级名字转发到「活动书」（`with _config.use(cfg):` 期间切换）。目录也已经是可配的：
`book.toml [paths]` 的 `state`、`baselines`、`manuscript`、`dist`、`tmp`、`book`、`templates`
各自可指到任意位置，`_log.log_dir()` 落在书根下。

真正缺的三件事：

1. **没有入口指定「这次跑哪本书」**——`Config()` 的缺省根由 `_default_root()` 从工具链
   所在 checkout 推导（或读 `BOOK_ROOT`），命令行、TUI、Web 都没有「选书」的位置；
2. **一次运行只有一个活动书**：`use()` 切换的是模块级活动书，`app/web.py` 用
   `ThreadingHTTPServer` 并发处理请求，同一进程里两本书并行处理的请求会互相串；
3. **没有手稿的多版本轴**：`[paths].manuscript` 只有一个目录，同一本书的第二份手稿
   只能靠另建一本「书」来装，于是身份、章节表、案例全都要复制一份。

门禁侧的耦合只有两处，且都不在门禁逻辑里：`_default_root()`（工具位置 → 书根）与
测试夹具的 `BOOK_ROOT`（同样由工具目录推导）。`check_architecture.py` 的
`PATH_LITERALS` 是**禁止表**——它禁止源码里出现 `books/`、`data/manuscript` 这类字面量，
正是「不硬编码路径」的执行者，不是耦合点。

## 2. 目标形态

### B — 一仓多书

```text
books/
  shared/                    # 工具链默认与共享资源
  <slug>/                    # 一本书：换书即整目录替换
    data/book/book.toml
    data/manuscript/
    data/config/{base,style}.json
    data/language/zh.json
    data/tmpl/templates.toml   # 默认取 shared/ 的那份，需要时才覆盖
    data/baselines/  data/state/
    dist/  logs/
  src/python/                # 工具链（B 阶段仍在仓内）
  docs/                      # 工程文档
```

### C — 工具链独立成包

书目录自包含并可单独复制；工具以命令安装（`bookctl --book <dir>`），共享默认随包分发
（`importlib.resources`），书里只留覆盖项。

## 3. 归属边界

| 归书（按书隔离） | 归共享 |
| --- | --- |
| `data/book/`（身份、章节表、案例流水线） | `src/python/`（工具链） |
| `data/manuscript/`、`dist/` | `data/tmpl/templates.toml`（可被本书覆盖） |
| `data/state/`、`data/baselines/`、`logs/` | `data/language/*.json` |
| 版本目录 `state/<edition>/`、`baselines/<edition>/` | — |
| `data/snapshots/`（本书用来比对的既往稿） | — |
| `data/config/base.json`、`style.json`（本书的取值） | `base.json` 的默认值（C 阶段随包分发） |

判据：**两本书各自有值、且互相比对没有意义的东西，必须按书隔离**。体积基线、术语表、
已知问题账本都属于此类——跨书比对只会产生假差异。

隔离由**书根**实现，不靠给文件加前缀：书根不同，`state/`、`baselines/`、`dist/`、`logs/`
自然不重叠。因此不引入「日志文件名带书标识」这类改法——它会在同一目录里把两本书的
日志混在一起，反而更难分辨。

## 4. 两个不同的「层」

容易混淆，先分清：

- **文件四层**（`folder.md` §3）：`data/book/book.toml`、`data/config/base.json`、
  `data/config/style.json`、`data/language/zh.json`。各层管什么、按什么顺序合并，**只在
  `technical.md` §3.1 定义**，本文不重复。
- **覆盖三层**（本文）：工具链默认 → 共享覆盖 → 本书覆盖。这是**多书形态**下的来源顺序，
  第 1 层目前不存在（默认值直接写在每本书的 `base.json` 里）。

第 1 层不是 B 阶段的前提：B 阶段每本书各自持有完整配置也能跑。它的价值只有一个——
让 C 阶段不必把散在各书里的默认值「收回来」。因此本文把它列为 C 阶段的准备工作，
而不是 B 的阻塞项。

## 5. 源目录怎么绑

源是这本书的输入，声明在书级的 `data/config/base.json [sources]`（`src_main`、`pom_root`、
`languages`、`suffixes`、`version`）。多书形态下每本书自带一份，隔离不需要额外机制。

**不做运行期切换源**：NFR-02 要求同一输入两次构建产物一致，体量下限又是对「某一版源 +
某一版稿」的评审结论。随手换源会让坐标断言、体量比对、术语摘录同时失去含义。要比两个源，
用归档与快照，不引入 `--source` 参数。

**一棵树不够时用多根**（一本书同时分析多个源）：

```json
"sources": {
  "roots": [
    {"label": "h2", "path": "../h2/src/main", "language": "java"},
    {"label": "client", "path": "../client/src", "language": "java"}
  ]
}
```

单根写法（`src_main`）继续有效，`source_tree('src_main')` 返回首根；`roots` 存在时按
`label` 解析。`source-inventory.json`、坐标报告与日志都要带 `label`，否则跨根的同名类无法区分。

**源指纹进基线**：体量基线写入 `source{label, version, digest}`。换源后指纹不匹配，
`content_volume.py` 报「基线来自另一个源，需复核」，不静默通过。

**导入期冻结是当前的真实障碍**：`source_refs.SOURCE_DIR`、`content_depth.source_root`、
`chapters.SOURCE_ROOT` 在模块导入时就把源根固定，`Config` 切书对它们无效。步骤二之前
必须把它们改成调用时读取——这是多书能力的前置，不是可选项。

## 6. 手稿的多版本轴

只有一本书要出第二份手稿时才引入，单版本时目录形态保持现状：

```text
data/manuscript/            # 单版本：维持现状，不建子目录
data/manuscript/<edition>/  # 多版本：每版本一个子目录，含该版本的章节与后件
```

`book.toml [editions]` 只声明**有哪些版本**与各自的显示名，不复制身份：

```toml
default_edition = "main"

[editions]
main = "主版本"
abridged = "删节版"
```

缺省版本写在顶层 `default_edition`，不放进 `[editions]` 表——否则与名为 `default`
的版本冲突。

**章节清单归书，版本可覆盖**：`[chapters]` 仍是书级的（阅读顺序、编号、包归属），
版本默认继承；只有当某版本确实有不同章节时，才在自己的表里覆盖：

```toml
[editions.abridged.chapters]
files = ["cover.md", "ch1-2-architecture.md"]
```

**图号与章号不因版本重排**：删节版沿用被保留章节的编号，避免同一张图在两个版本里
叫两个号。

派生状态与体量基线跟着版本分键：`state/<edition>/`、`baselines/<edition>/`，
目录内的键与当前一致。否则第二份手稿一进，`content_volume.py` 会拿甲版本的下限判乙版本。
`quality-model.md` §4「只比一份、不做加权」的原则不变：每个版本仍然只与**自己那一份**
基线比，不引入跨版本平均。

## 7. 并发与「活动书」

`use()` 改的是进程级活动书，因此：

- **一次运行服务的是一本书**：`--book` 选定的书在整次运行内不变；命令行工具、`make.py`
  的每个步骤都满足这一点。
- **并发场景不共享活动书**：Web 控制台（多线程）一个进程只服务一本书，启动时选定；
  若将来要在一个进程里服务多本，处理函数必须接收显式的 `Config` 实例，而不是依赖
  `current()`。
- 测试里可以安全地连续切换（单线程、串行），已有用例覆盖嵌套与异常还原。

## 8. 非功能需求怎么适用

- **体积预算（NFR-06）按书算**：每本书的 PDF/EPUB 各自受上限约束，不做跨书合计。
- **环境唯一（NFR-03）不变**：多书共用同一个隔离环境，不为某本书单独装依赖。
- **可移植（NFR-09）要覆盖新行为**：向上查找必须走到文件系统根为止、路径比较用
  `realpath`、在大小写不敏感的文件系统上按不敏感比较，且不依赖盘符书写。
- **无过程痕迹（NFR-12）不变**：多书形态不引入「上一版书」这类过程产物。
- **不做跨书汇总检查**：`make.py check` 一次只判一本书；要多书一起判，按书写循环调。

## 9. 非目标

- **不做多书合一构建**：一本书一份产物；多本合并成一个 PDF/EPUB 不在范围内
  （`technical.md` §10 已登记）。
- **不做跨书一致性检查**：术语、图号、引用只在本书内判定。
- **不引入跨书快照**：`data/snapshots/` 仍只放「本书用来比对的既往稿」；别的书的稿子不再
  作为快照来源，需要横向比较时人工取用，避免快照目录变成多书混合区。
- **不改判定口径**：选书与分层只决定「读哪个文件、写到哪里」，不改变任何阈值语义。
- **不做旧布局兼容**：`lib/_config.py` 只认 `data/book/book.toml`。仍把 `book.toml` 放在
  旧位置的书，报错时直接给出期望路径，不自动回退——猜位置比报错更难排查。

## 10. 迁移路径

四步，顺序不可换：步骤一只提供「按书解析」的能力，步骤二才让人指定跑哪本书，
步骤三解决同一本书的多份手稿，步骤四只换工具链的交付形态。每步的动作、验收与回滚
写在 `plan.md`，这里只记顺序与等价条件：

| 步骤 | 内容 | 合并前必须成立 |
| --- | --- | --- |
| 一 | 配置按书解析 | 调用形式与取值不变；渲染文本哈希不变 |
| 二 | `--book` 入口 + 向上查找 | 不带 `--book` 时产物、日志位置、门禁结论与当前逐字一致 |
| 三 | 手稿 edition 轴 | 未声明 `[editions]` 的书完全不受影响 |
| 四 | 工具链独立成包 | 仓外书目录上 `bookctl check` 的结论与仓内一致 |

四步都不产生数据迁移，因此都能单独撤销：步骤二去掉入口、步骤三删 `[editions]` 表、
步骤四回退到仓内工具链。

**自举不在四步内，但会被触发**：一旦本仓按 B 形态组织，仓库自己也要变成「各书目录 + 并列的 shared 目录」，
需要一次 `git mv` 与 `_default_root()` 兜底值的调整。这一步单独做、
单独提交，结论必须仍是「门禁全绿、产物不变」。

## 11. 门禁影响

- `_default_root()` 降级为兜底：给了 `--book` 时不再参与解析，也不被任何门禁依赖；
- 测试夹具把「工具目录」与「书目录」当两个独立概念：夹具书根不再从工具目录推导；
- 已有用例继续守住配置对象本身（两本书互不串值、切换失败也还原、缺 `book.toml` 仍报
  `ConfigError`）；`--book` 的入口行为由步骤二的用例覆盖，不在这里重复。
