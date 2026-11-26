# C 语言实施计划：源码解析与成书

> **状态：阶段 1–4 已落地，阶段 5 待执行**——阶段 1–4 的产物已随仓库交付；下面的阶段 5
> 是尚未完成的那一段。
>
> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1
> 定位：**C 语言的动作与判据**——分几个阶段做、每阶段的产物与通过条件、命令与回退。
> 设计理由看同目录 `design.md`，门禁与阈值归属看 `managements/testplan.md`。

---

## 1. 前提

- 分析器契约已定（`ingest/languages/_base.py`）：新增语言 = 一个模块 + 一行注册，
  流水线其余部分不动。
- 判据取后缀一律走 `_config.source_suffixes()`；不新增第二个"语言清单"，
  否则配置与代码会各说一套。
- 先让分析器产出正确的 inventory，再改判据里的 `.java:` 字面量：顺序反了会把
  "没有坐标"错判成"坐标过期"。

依赖关系：阶段 1 独立；阶段 2 依赖 1 的分析器能跑；阶段 3 依赖 2 的夹具；
阶段 4 最后，用真实 C 树验收。

---

## 2. 阶段与动作

### 阶段 1：包与单元的抽取

#### 动作
1. 新增 `src/python/ingest/languages/<lang>.py`（本次 `<lang>` 为 `c`）：`name = 'c'`、
   `suffixes = ('.c', '.h')`，`analyze(root)` 按设计文档 §3、§4 的映射填 inventory。
2. `ingest/languages/__init__.py` 注册 `'c': CAnalyzer`（`detect()` 自动跟着变）。
3. `data/config/base.json [sources]`：`suffixes` 加 `"c": ".c"`；`languages` 由书的作者
   按书切换，模板不改。
4. `core/scaffold.py` 的 `suffixes` 模板补 `.c`，新书脚手架不再只认三种语言。

#### 通过条件
- `languages.get('c')` 可用；`languages.detect()` 对 C 夹具（`src/test/fixtures/<mini-c>/`）返回 `c`。
- 单元数、包名、行数与手工数一致（夹具里放 1 个 `.h` + 2 个 `.c`，含 `struct`、
  `enum`、`typedef`、`static` 函数各一）。

### 阶段 2：依赖方向与 public 判定

#### 动作
1. `#include "…"` → 本树内包级 `depends_on`；`#include <…>` 丢弃；同包不计。
2. public 判定：在**同名 `.h`** 中声明过的类型与原型算 public；只在 `.c` 里定义
   （含 `static`）算私有。
3. `api` 取头文件顶层函数原型；`api_lines` 填行号。

#### 通过条件
- 夹具里 `driver/` 引用 `core/` 时 `depends_on['core']` 出现，系统头不出现；
- `static` 函数不在 `api` 里，头文件原型在 `api` 里且行号可定位到源码行。

### 阶段 3：夹具与用例

#### 动作
1. 新增 C 夹具目录 `src/test/fixtures/<mini-c>/`：`include/common.h`、`widget.h`、`widget.c`、
   `run.c`（分属 `include/`、`src/`、`tools/` 三个子目录）
   （含块注释、无注释文件、`static` 函数、引号/尖括号 include 各一）。
2. `src/test/test_languages.py` 补用例：包归属、include→依赖、public/私有、
   无注释文件摘要为空串、`.h`/`.c` 同包。
3. 分支覆盖不低于单文件地板（`base.json [quality] coverage_min_per_file`）。

#### 通过条件
- `python books/src/python/make.py test` 绿；新增分析器无未覆盖的可达分支。

### 阶段 4：坐标字面量去 Java 化

#### 动作
1. 把按后缀写死的匹配改成按 `sources.suffixes` 取值：`manuscript/cover.py`（引用计数）、
   `audit/balance.py`（密度）、`audit/book_quality.py` 与 `audit/prose_quality.py`
   （`COORD_RE`）、`audit/smart.py`（摘录计数）、`manuscript/terms.py`（术语过滤）。
2. 保留现有 Java 行为作对照：改动后中文 Java 书的门禁结论必须逐条不变。

#### 通过条件
- 设 `languages: ["c"]` 时，`source_refs.py` 认可 `foo.c:12` 并能对过期坐标报红；
- 设 `languages: ["java"]` 时，`make.py check` 的结论与改动前一致（逐门禁对比）。

### 阶段 5：真实 C 树验收

#### 动作
1. 取一棵结构清晰的 C 项目（自带 `Makefile`、头文件与实现分目录），把 `base.json` 的
   `[sources]` 指向它，跑 `digest.py → outline.py → chapters.py`。
2. `book.toml [chapters.packages]` 按包到章的映射填好，跑 `make.py check`。

#### 通过条件
- `digest.py` 产出的 inventory 行数与 `cloc` 同档、包数与该树的目录结构一致；
- `outline.py` 无异常且每个包有章归属；`structure.py`、`source_refs.py` 绿；
- 手稿里至少 20 处 `.c:` 坐标通过核验。

---

## 3. 命令

```bash
books/.venv/bin/python books/src/python/make.py test          # 分析器与用例
books/.venv/bin/python books/src/python/make.py check         # 全部门禁
books/.venv/bin/python books/src/python/make.py cover         # 覆盖率棘轮
books/.venv/bin/python books/src/python/ingest/digest.py      # 真实树：抽 inventory
books/.venv/bin/python books/src/python/ingest/outline.py     # 真实树：包 → 章
```

## 4. 回退

- 分析器与注册表行是新增文件与新增行：删掉即恢复原状。
- 配置只动 `sources.suffixes` 一项：删掉该键后其它语言行为与今天一致。
- 阶段 4 的判据改动以"Java 书结论逐条不变"为通过条件，任一门禁结论变化即回退该处改动。
