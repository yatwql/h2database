# 第3章 包结构与模块职责

> **本章导读**：本章由源码清单汇总而成，覆盖 2 个包、7,363 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 3.1 模块版图

本章覆盖 2 个包、7,363 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.api` | 12 | 4,150 | Contains interfaces for user-defined extensions, such as triggers and user-defined aggregate functions. |
| `org.h2.schema` | 11 | 3,213 | Schema implementation and objects that are stored in a schema (for example, sequences and constants). |

## 3.2 核心类型

在 `org.h2.api` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 3.2.1 `org.h2.api`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ErrorCode` | 2,367 | 2 | （无类注释，按方法名归纳） |
| `Interval` | 636 | 33 | （无类注释，按方法名归纳） |
| `IntervalQualifier` | 353 | 13 | （无类注释，按方法名归纳） |
| `H2Type` | 322 | 6 | （无类注释，按方法名归纳） |

### 3.2.2 `org.h2.schema`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Schema` | 848 | 51 | （无类注释，按方法名归纳） |
| `Sequence` | 586 | 25 | （无类注释，按方法名归纳） |
| `FunctionAlias` | 562 | 22 | （无类注释，按方法名归纳） |
| `TriggerObject` | 543 | 28 | （无类注释，按方法名归纳） |

## 3.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `ErrorCode.getState()` | `org/h2/api/ErrorCode.java:2317` |
| `ErrorCode.isCommon()` | `org/h2/api/ErrorCode.java:2287` |
| `Interval.equals()` | `org/h2/api/Interval.java:617` |
| `Interval.getDays()` | `org/h2/api/Interval.java:543` |
| `IntervalQualifier.getTypeName()` | `org/h2/api/IntervalQualifier.java:253` |
| `IntervalQualifier.hasDays()` | `org/h2/api/IntervalQualifier.java:165` |
| `Schema.add()` | `org/h2/schema/Schema.java:267` |
| `Schema.canDrop()` | `org/h2/schema/Schema.java:92` |
| `Sequence.close()` | `org/h2/schema/Sequence.java:553` |
| `Sequence.flush()` | `org/h2/schema/Sequence.java:510` |
| `FunctionAlias.compareTo()` | `org/h2/schema/FunctionAlias.java:546` |
| `FunctionAlias.findJavaMethod()` | `org/h2/schema/FunctionAlias.java:243` |

## 3.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `ErrorCode` | `org.h2.api` | 2,367 | 2 |
| `Interval` | `org.h2.api` | 636 | 33 |
| `IntervalQualifier` | `org.h2.api` | 353 | 13 |
| `H2Type` | `org.h2.api` | 322 | 6 |
| `DatabaseEventListener` | `org.h2.api` | 113 | 0 |
| `Schema` | `org.h2.schema` | 848 | 51 |
| `Sequence` | `org.h2.schema` | 586 | 25 |
| `FunctionAlias` | `org.h2.schema` | 562 | 22 |
| `TriggerObject` | `org.h2.schema` | 543 | 28 |
| `Domain` | `org.h2.schema` | 241 | 22 |

## 3.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

**`ErrorCode`**（`org.h2.api`，2,367 行，2 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 57%，包级依赖 7 个。

**`Interval`**（`org.h2.api`，636 行，33 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 15%，包级依赖 7 个。

**`IntervalQualifier`**（`org.h2.api`，353 行，13 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 7 个。

**`H2Type`**（`org.h2.api`，322 行，6 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 7 个。

**`DatabaseEventListener`**（`org.h2.api`，113 行，0 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 3%，包级依赖 7 个。

**`Trigger`**（`org.h2.api`，105 行，0 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 3%，包级依赖 7 个。

**`Schema`**（`org.h2.schema`，848 行，51 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 26%，包级依赖 8 个。

**`Sequence`**（`org.h2.schema`，586 行，25 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 18%，包级依赖 8 个。

**`FunctionAlias`**（`org.h2.schema`，562 行，22 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 17%，包级依赖 8 个。

**`TriggerObject`**（`org.h2.schema`，543 行，28 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 17%，包级依赖 8 个。

**`Domain`**（`org.h2.schema`，241 行，22 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

**`UserAggregate`**（`org.h2.schema`，120 行，9 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 4%，包级依赖 8 个。

## 3.3.2 源码坐标明细

本章主责包中 38 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `ErrorCode.getState()` | `org/h2/api/ErrorCode.java:2317` |
| `ErrorCode.isCommon()` | `org/h2/api/ErrorCode.java:2287` |
| `Interval.equals()` | `org/h2/api/Interval.java:617` |
| `Interval.getDays()` | `org/h2/api/Interval.java:543` |
| `Interval.getHours()` | `org/h2/api/Interval.java:552` |
| `Interval.getLeading()` | `org/h2/api/Interval.java:506` |
| `IntervalQualifier.getTypeName()` | `org/h2/api/IntervalQualifier.java:253` |
| `IntervalQualifier.hasDays()` | `org/h2/api/IntervalQualifier.java:165` |
| `IntervalQualifier.hasHours()` | `org/h2/api/IntervalQualifier.java:182` |
| `IntervalQualifier.hasMinutes()` | `org/h2/api/IntervalQualifier.java:201` |
| `H2Type.array()` | `org/h2/api/H2Type.java:258` |
| `H2Type.getName()` | `org/h2/api/H2Type.java:296` |
| `H2Type.getVendor()` | `org/h2/api/H2Type.java:301` |
| `H2Type.getVendorTypeNumber()` | `org/h2/api/H2Type.java:312` |
| `Schema.add()` | `org/h2/schema/Schema.java:267` |
| `Schema.canDrop()` | `org/h2/schema/Schema.java:92` |
| `Schema.createSynonym()` | `org/h2/schema/Schema.java:814` |
| `Schema.createTable()` | `org/h2/schema/Schema.java:786` |
| `Sequence.close()` | `org/h2/schema/Sequence.java:553` |
| `Sequence.flush()` | `org/h2/schema/Sequence.java:510` |

## 3.4 阅读路径

读 `org.h2.api` 的 12 个文件时，先看骨架类，再沿 `org.h2.security.auth` 方向下钻。

1. 先读 `org.h2.api` 的 package-info 与 `ErrorCode`，建立第3章的职责边界。
2. 再读 `ErrorCode` 的 2 个公开入口，确认它对 `org.h2.security.auth` 的调用方向与加锁方式。
3. 最后读 `org.h2.schema`（本章最小包，3,213 行）的实现，关注容量与失败路径。

跨章衔接请对照第4章《包结构与模块职责》。

## 3.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.api` | `org.h2.security.auth`, `org.h2.value`, `org.h2.util.DateTimeUtils`, `org.h2.message` |
| `org.h2.schema` | `org.h2.engine`, `org.h2.value`, `org.h2.message`, `org.h2.table` |

## 3.6 设计权衡

- `org.h2.api` 用 12 个文件换到 4,150 行实现，平均每文件 345 行，其中 `ErrorCode` 独占 2,367 行、2 个公开方法。
- 该包对外声明了 7 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.schema`（3,213 行）与 `org.h2.api` 的职责差是本章最值得记的一条边界。

## 3.7 常见误区

- 把 `org.h2.api` 的 4,150 行当作复杂度上限：`ErrorCode` 之外的 11 个文件多为类型族与样板。
- 只看 `ErrorCode` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.api` 与 `org.h2.schema` 视为可互换：前者 12 文件、后者 11 文件，扩展点分布完全不同。

## 3.8 深读要点

规模信号：`org.h2.api` 占本章 56% 的实现行数，改动风险最高。
耦合信号：`org.h2.api` 依赖 7 个 `org.h2` 包，其中 `org.h2.security.auth` 出现最频繁。
入口信号：`ErrorCode` 的公开方法 2 个，读它等于读本章的主干。

## 3.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Aggregate**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Schema**：详见[术语表](back/glossary.md)对应条目。
- **Column**：详见[术语表](back/glossary.md)对应条目。
- **Database**：详见[术语表](back/glossary.md)对应条目。
- **DbSettings**：详见[术语表](back/glossary.md)对应条目。
- **Driver**：详见[术语表](back/glossary.md)对应条目。
- **Engine**：详见[术语表](back/glossary.md)对应条目。

## 3.9 知识点清单

1. `org.h2.api` 的 `ErrorCode`：2,367 行、2 个公开方法，职责按方法名归纳
2. `org.h2.api` 的 `Interval`：636 行、33 个公开方法，职责按方法名归纳
3. `org.h2.schema` 的 `Schema`：848 行、51 个公开方法，职责按方法名归纳
4. `org.h2.schema` 的 `Sequence`：586 行、25 个公开方法，职责按方法名归纳

## 3.9 本章小结

- 本章覆盖 2 个包、7,363 行。
- 关键入口与源码坐标见 §3.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 3.10 延伸思考

**1. 🟢★ 指出 `org.h2.api` 中 `ErrorCode` 与 `Interval` 的分工差异，并给出调用方向。**

> 提示：第3章 §3.2 的表格给出 `ErrorCode` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§3.2 核心类型

**2. 🔵★★ 围绕 `org.h2.schema` 的 `Schema`，说明它为什么需要独立成类型而不是并入 `Sequence`。**

> 提示：第3章 §3.2 的表格给出 `Schema` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§3.2 核心类型

**3. 🟠★★★ 以 `org.h2.api` 的 `ErrorCode` 为入口，画出一次完整调用经过的包。**

> 提示：第3章 §3.2 的表格给出 `ErrorCode` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§3.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.schema` 的一个类型，你保留 `Schema` 还是 `Sequence`？说明代价。**

> 提示：第3章 §3.2 的表格给出 `Schema` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§3.2 核心类型

## 3.11 本章视角：演化与版本

- 以「演化与版本」看 `org.h2.api`：12 个文件、4,150 行，本章只展开与演化与版本相关的入口。
- 对照 `org.h2.schema`（3,213 行）：两者的演化与版本策略不同，差异落在 `ErrorCode` 的 2 个公开方法里。
- 若演化与版本假设被打破（7 个依赖变化），最先受影响的调用链从 `org.h2.security.auth` 进入。

## 3.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.api` | `org.h2.security.auth` | 5 |
| `org.h2.api` | `org.h2.value` | 3 |
| `org.h2.api` | `org.h2.util.DateTimeUtils` | 2 |
| `org.h2.schema` | `org.h2.engine` | 29 |
| `org.h2.schema` | `org.h2.value` | 16 |
| `org.h2.schema` | `org.h2.message` | 13 |

## 3.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.api` 与 `org.h2.schema` 之间的调用方向？
- `ErrorCode` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.api` 的调用链讲到落盘或返回？
- `org.h2.api` 与 `org.h2.schema` 若合并，会丢掉哪个扩展点？
- `org.h2.api` 的注释与实现若不一致，你信哪一边，为什么？

## 3.12 延展阅读

- 详见第4章《包结构与模块职责》。
