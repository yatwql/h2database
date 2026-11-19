# 第6章 数据结构：值、行与页

> **本章导读**：本章由源码清单汇总而成，覆盖 2 个包、19,178 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 6.1 模块版图

本章覆盖 2 个包、19,178 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.value` | 55 | 15,501 | Data type and value implementations. |
| `org.h2.result` | 21 | 3,677 | Implementation of row and internal result sets. |

## 6.2 核心类型

在 `org.h2.value` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 6.2.1 `org.h2.value`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Value` | 2,873 | 67 | （无类注释，按方法名归纳） |
| `TypeInfo` | 1,539 | 23 | （无类注释，按方法名归纳） |
| `Transfer` | 1,368 | 31 | （无类注释，按方法名归纳） |
| `DataType` | 828 | 25 | （无类注释，按方法名归纳） |

### 6.2.2 `org.h2.result`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `LocalResult` | 710 | 42 | （无类注释，按方法名归纳） |
| `UpdatableRow` | 341 | 5 | （无类注释，按方法名归纳） |
| `SortOrder` | 334 | 15 | （无类注释，按方法名归纳） |
| `SimpleResult` | 303 | 31 | （无类注释，按方法名归纳） |

## 6.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Value.add()` | `org/h2/value/Value.java:929` |
| `Value.castTo()` | `org/h2/value/Value.java:1105` |
| `TypeInfo.areSameTypes()` | `org/h2/value/TypeInfo.java:738` |
| `TypeInfo.checkComparable()` | `org/h2/value/TypeInfo.java:764` |
| `Transfer.close()` | `org/h2/value/Transfer.java:478` |
| `Transfer.flush()` | `org/h2/value/Transfer.java:216` |
| `LocalResult.addRow()` | `org/h2/result/LocalResult.java:420` |
| `LocalResult.addRowForTable()` | `org/h2/result/LocalResult.java:404` |
| `UpdatableRow.deleteRow()` | `org/h2/result/UpdatableRow.java:257` |
| `UpdatableRow.insertRow()` | `org/h2/result/UpdatableRow.java:309` |
| `SortOrder.addNullOrdering()` | `org/h2/result/SortOrder.java:312` |
| `SortOrder.compare()` | `org/h2/result/SortOrder.java:162` |

## 6.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Value` | `org.h2.value` | 2,873 | 67 |
| `TypeInfo` | `org.h2.value` | 1,539 | 23 |
| `Transfer` | `org.h2.value` | 1,368 | 31 |
| `DataType` | `org.h2.value` | 828 | 25 |
| `ValueToObjectConverter` | `org.h2.value` | 642 | 6 |
| `LocalResult` | `org.h2.result` | 710 | 42 |
| `UpdatableRow` | `org.h2.result` | 341 | 5 |
| `SortOrder` | `org.h2.result` | 334 | 15 |
| `SimpleResult` | `org.h2.result` | 303 | 31 |
| `ResultRemote` | `org.h2.result` | 287 | 17 |

## 6.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

**`Value`**（`org.h2.value`，2,873 行，67 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 19%，包级依赖 8 个。

**`TypeInfo`**（`org.h2.value`，1,539 行，23 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 10%，包级依赖 8 个。

**`Transfer`**（`org.h2.value`，1,368 行，31 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

**`DataType`**（`org.h2.value`，828 行，25 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

**`ValueToObjectConverter`**（`org.h2.value`，642 行，6 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 4%，包级依赖 8 个。

**`ValueToObjectConverter2`**（`org.h2.value`，433 行，2 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 3%，包级依赖 8 个。

**`LocalResult`**（`org.h2.result`，710 行，42 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 19%，包级依赖 8 个。

**`UpdatableRow`**（`org.h2.result`，341 行，5 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

**`SortOrder`**（`org.h2.result`，334 行，15 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 9%，包级依赖 8 个。

**`SimpleResult`**（`org.h2.result`，303 行，31 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

**`ResultRemote`**（`org.h2.result`，287 行，17 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

**`RowFactory`**（`org.h2.result`，201 行，17 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

## 6.3.2 源码坐标明细

本章主责包中 46 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Value.add()` | `org/h2/value/Value.java:929` |
| `Value.castTo()` | `org/h2/value/Value.java:1105` |
| `Value.charLength()` | `org/h2/value/Value.java:2832` |
| `Value.clearCache()` | `org/h2/value/Value.java:773` |
| `TypeInfo.areSameTypes()` | `org/h2/value/TypeInfo.java:738` |
| `TypeInfo.checkComparable()` | `org/h2/value/TypeInfo.java:764` |
| `TypeInfo.equals()` | `org/h2/value/TypeInfo.java:1397` |
| `TypeInfo.getDecimalPrecision()` | `org/h2/value/TypeInfo.java:1490` |
| `Transfer.close()` | `org/h2/value/Transfer.java:478` |
| `Transfer.flush()` | `org/h2/value/Transfer.java:216` |
| `Transfer.getSocket()` | `org/h2/value/Transfer.java:1289` |
| `Transfer.getVersion()` | `org/h2/value/Transfer.java:1330` |
| `DataType.addPrecision()` | `org/h2/value/DataType.java:791` |
| `DataType.areStableComparable()` | `org/h2/value/DataType.java:592` |
| `DataType.convertSQLTypeToValueType()` | `org/h2/value/DataType.java:366` |
| `DataType.convertTypeToSQLType()` | `org/h2/value/DataType.java:343` |
| `ValueToObjectConverter.getDefaultClass()` | `org/h2/value/ValueToObjectConverter.java:403` |
| `ValueToObjectConverter.objectToValue()` | `org/h2/value/ValueToObjectConverter.java:85` |
| `ValueToObjectConverter.readValue()` | `org/h2/value/ValueToObjectConverter.java:624` |
| `ValueToObjectConverter.valueToDefaultArray()` | `org/h2/value/ValueToObjectConverter.java:603` |

## 6.4 阅读路径

读 `org.h2.value` 的 55 个文件时，先看骨架类，再沿 `org.h2.util` 方向下钻。

1. 先读 `org.h2.value` 的 package-info 与 `Value`，建立第6章的职责边界。
2. 再读 `Value` 的 67 个公开入口，确认它对 `org.h2.util` 的调用方向与加锁方式。
3. 最后读 `org.h2.result`（本章最小包，3,677 行）的实现，关注容量与失败路径。

跨章衔接请对照第7章《数据结构：值、行与页》。

## 6.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.value` | `org.h2.util`, `org.h2.engine`, `org.h2.message`, `org.h2.api` |
| `org.h2.result` | `org.h2.value`, `org.h2.engine`, `org.h2.util`, `org.h2.expression` |

## 6.6 设计权衡

- `org.h2.value` 用 55 个文件换到 15,501 行实现，平均每文件 281 行，其中 `Value` 独占 2,873 行、67 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.result`（3,677 行）与 `org.h2.value` 的职责差是本章最值得记的一条边界。

## 6.7 常见误区

- 把 `org.h2.value` 的 15,501 行当作复杂度上限：`Value` 之外的 54 个文件多为类型族与样板。
- 只看 `Value` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.value` 与 `org.h2.result` 视为可互换：前者 55 文件、后者 21 文件，扩展点分布完全不同。

## 6.8 深读要点

规模信号：`org.h2.value` 占本章 81% 的实现行数，改动风险最高。
耦合信号：`org.h2.value` 依赖 8 个 `org.h2` 包，其中 `org.h2.util` 出现最频繁。
入口信号：`Value` 的公开方法 67 个，读它等于读本章的主干。

## 6.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Value**：详见[术语表](back/glossary.md)对应条目。
- **Append-Only**：详见[术语表](back/glossary.md)对应条目。
- **B-Tree**：详见[术语表](back/glossary.md)对应条目。
- **Chunk**：详见[术语表](back/glossary.md)对应条目。
- **COW / Copy-on-Write**：详见[术语表](back/glossary.md)对应条目。
- **Compact**：详见[术语表](back/glossary.md)对应条目。
- **Free Space**：详见[术语表](back/glossary.md)对应条目。

## 6.9 知识点清单

1. `org.h2.value` 的 `Value`：2,873 行、67 个公开方法，职责按方法名归纳
2. `org.h2.value` 的 `TypeInfo`：1,539 行、23 个公开方法，职责按方法名归纳
3. `org.h2.result` 的 `LocalResult`：710 行、42 个公开方法，职责按方法名归纳
4. `org.h2.result` 的 `UpdatableRow`：341 行、5 个公开方法，职责按方法名归纳

## 6.9 本章小结

- 本章覆盖 2 个包、19,178 行。
- 关键入口与源码坐标见 §6.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 6.10 延伸思考

**1. 🟢★ 指出 `org.h2.value` 中 `Value` 与 `TypeInfo` 的分工差异，并给出调用方向。**

> 提示：第6章 §6.2 的表格给出 `Value` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

**2. 🔵★★ 围绕 `org.h2.result` 的 `LocalResult`，说明它为什么需要独立成类型而不是并入 `UpdatableRow`。**

> 提示：第6章 §6.2 的表格给出 `LocalResult` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

**3. 🟠★★★ 以 `org.h2.value` 的 `Value` 为入口，画出一次完整调用经过的包。**

> 提示：第6章 §6.2 的表格给出 `Value` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.result` 的一个类型，你保留 `LocalResult` 还是 `UpdatableRow`？说明代价。**

> 提示：第6章 §6.2 的表格给出 `LocalResult` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§6.2 核心类型

## 6.11 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2.value`：55 个文件、15,501 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2.result`（3,677 行）：两者的扩展与兼容策略不同，差异落在 `Value` 的 67 个公开方法里。
- 若扩展与兼容假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.util` 进入。

## 6.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.value` | `org.h2.util` | 63 |
| `org.h2.value` | `org.h2.engine` | 59 |
| `org.h2.value` | `org.h2.message` | 40 |
| `org.h2.result` | `org.h2.value` | 45 |
| `org.h2.result` | `org.h2.engine` | 21 |
| `org.h2.result` | `org.h2.util` | 8 |

## 6.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.value` 与 `org.h2.result` 之间的调用方向？
- `Value` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.value` 的调用链讲到落盘或返回？
- `org.h2.value` 与 `org.h2.result` 若合并，会丢掉哪个扩展点？
- `org.h2.value` 的注释与实现若不一致，你信哪一边，为什么？

## 6.12 延展阅读

- 详见第7章《数据结构：值、行与页》。
