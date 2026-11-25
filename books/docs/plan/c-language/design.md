# C 语言迭代设计：源码解析与成书

> **状态：阶段 1–4 已落地，阶段 5 待执行**——分析器、注册表、后缀表与夹具已随仓库交付；
> 尚未用一棵真实 C 树跑完整流水线。
>
> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1
> 定位：**C 语言分析器的设计说明**——C 没有包声明时"包"按什么切、头文件与实现文件
> 怎么配对、`#include` 怎样变成依赖方向、哪些判据里还写着 Java 的后缀。不写排期与
> 逐项动作（看同目录 `plan.md`），不重复全书架构（看 `managements/technical.md`）。

---

## 0. 术语

| 术语 | 在此处的含义 |
| --- | --- |
| 分析器 | `src/python/ingest/languages/<lang>.py`，实现 `name` / `suffixes` / `analyze(root)` |
| 包（package） | 分析器输出的一级分组键；Java 是 `package` 声明，C 只能是目录 |
| 单元（unit） | 一个声明类型：`struct` / `union` / `enum` / `typedef`，对应 `Unit` |
| 头文件对 | 同一目录下同名的 `.h` 与 `.c`，前者是接口、后者是定义 |
| 源码坐标 | 手稿里的 `文件.c:行号`，由 `audit/source_refs.py` 核验新鲜度 |

---

## 1. 目标与非目标

**目标**：把 `base.json [sources] languages` 设为 `c` 后，一棵普通 C 源码树能走完
`digest.py → outline.py → chapters.py`，产出的 inventory 形状与 Java/Python 一致，
手稿里的 `foo.c:123` 坐标能被 `source_refs.py` 核验。

**非目标**：不做 C 的完整语法分析（不建 AST、不解析表达式）；不做宏展开；不解析
预处理分支；不追求头文件与实现的语义一致性判定；不改写作体例。

**硬约束**：只有 `.c` / `.h` 两种后缀进入统计（`.m`、`.mm`、`.hpp` 不算）；
同一棵树里 C 与 C++ 混放时只按配置的语言取值；分析器只读树，不写任何文件。

---

## 2. 起点事实（阶段 1 之前的注册表与判据，供对照；现状见文首状态行与 `plan.md`）

**注册表即全部入口**：`ingest/languages/__init__.py` 的 `ANALYZERS` 收了 java / python /
rust / kotlin / go；`detect()` 由注册表的 `suffixes` 反推后缀表，所以"加一个语言"目前等于
"加一个模块 + 一行注册"。指向 C 源码树时，`detect()` 找不到已知后缀，直接
`SystemExit('no known source files under ...')`。

**inventory 形状是语言无关的**（`_base.py`）：`{package: {path, summary, files, lines,
depends_on, classes: [{name, file, lines, public, kind, summary, public_methods, api}]}}`。
C 缺的只是"怎样从一棵树填出这个形状"的判断，形状本身不用动。

**配置里已有后缀表**：`data/config/base.json [sources]` 有 `languages` 与
`suffixes`（java/python/rust/kotlin/go），`file_suffix` 是回退值。`sources.suffixes` 缺失的
语言 `_config.source_suffixes()` 会退化到 `file_suffix`，所以先加 `"c": ".c"` 一项。

**判据里还有写死的 Java 后缀**：`audit/source_refs.py` 已按配置取值，但
`manuscript/cover.py`（统计源码引用）、`audit/balance.py`（引用密度）、
`audit/book_quality.py` 与 `audit/prose_quality.py`（`COORD_RE`）、`audit/smart.py`
（摘录后计数）、`manuscript/terms.py`（术语过滤）仍按 `.java:` 字面量匹配。
C 的坐标是 `.c:`，这些位置不改成按后缀取值，覆盖率与摘录判据就会把 C 的书判成
"没有源码坐标"。

---

## 3. C 的特殊处与取舍

| 问题 | C 的事实 | 本设计的取舍 |
| --- | --- | --- |
| 包怎么切 | 没有 `package` 声明 | 按**目录相对 `[sources].root` 的路径**切，`src/driver/...` → `driver`，根目录文件 → `root`；路径分隔符统一成 `.`（与其它语言键名同形） |
| 头与实现怎么归 | 一个 `.h` 常配一个同名 `.c` | 同目录同名文件归**同一包**；单元只从 `.h` 抽（接口），实现文件只贡献行数与依赖 |
| 依赖怎么来 | `#include "x.h"` / `#include <x.h>` | 只把**引号形式**映射到本树内的文件，转成包级 `depends_on`；尖括号（系统头）丢弃 |
| 什么算 public | C 没有 `public` 关键字 | 在**同名 `.h` 中声明过**的函数/类型算 public；只在 `.c` 里出现（含 `static`）算私有 |
| 单元是什么 | 没有 `class` | `struct` / `union` / `enum` / `typedef` 各算一个单元，`kind` 对应小写名 |
| api 怎么取 | 函数声明在头文件里 | `.h` 中的顶层函数原型 → `api`，名字取标识符，行号进 `api_lines` |
| 摘要怎么来 | 常见 `/* ... */` 文件头或结构体上方块注释 | 取最近的块注释首句（`first_sentence`）；没有就是空串，**不编造** |

---

## 4. 输出映射

```text
package   = 目录路径，'.' 连接，根目录为 'root'
path      = 目录相对 [sources].root 的路径
files     = 该目录下 .c/.h 的文件数
lines     = 这些文件总行数
summary   = 目录内最长的块注释首句（无则空串）
depends_on= {包: 引用次数}，来自引号形式的 #include，跨包才计
classes[] = struct/union/enum/typedef 各一项
  name / file / lines / public / kind / summary / api / api_lines / rel
```

`rel` 保持"相对源码根的路径"，`api_lines` 只对头文件里的原型填行号：摘录与坐标核验都靠它。

---

## 5. 风险与回退

- **包粒度**：C 工程的目录层级常比 Java 深（`src/net/http/...`），按目录切会产生很多只有一个
  文件的包。章节映射（`book.toml [chapters.packages]`）由人指定，允许把多个包归一章，
  所以粒度问题在配置层解决，不引入"猜测合并"。
- **宏生成的结构体**：`DECLARE_STRUCT(x)` 之类看不到名字，抽不到就算缺，不用正则硬猜。
- **同一棵树的 C/C++ 混放**：`detect()` 只在显式未配置语言时用；配置了 `languages: ["c"]`
  就只读 `.c`/`.h`，C++ 文件不参与。
- **回退**：新增分析器与注册表行都是新增文件/新增行，删除即恢复原状；配置项
  `sources.suffixes.c` 未配置时其它语言行为不变。
