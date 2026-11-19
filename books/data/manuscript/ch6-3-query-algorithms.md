# 第8章 索引与表达式求值

> **本章导读**：本章由源码清单汇总而成，覆盖 1 个包、4,093 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 8.1 模块版图

本章覆盖 1 个包、4,093 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.index` | 23 | 4,093 | Various table index implementations, as well as cursors to navigate in an index. |

## 8.2 核心类型

在 `org.h2.index` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 8.2.1 `org.h2.index`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Index` | 834 | 37 | （无类注释，按方法名归纳） |
| `IndexCondition` | 675 | 24 | （无类注释，按方法名归纳） |
| `IndexCursor` | 494 | 13 | （无类注释，按方法名归纳） |
| `LinkedIndex` | 298 | 13 | （无类注释，按方法名归纳） |

## 8.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Index.add()` | `org/h2/index/Index.java:210` |
| `Index.areRowsEquivalent()` | `org/h2/index/Index.java:379` |
| `IndexCondition.cloneWithIndexColumns()` | `org/h2/index/IndexCondition.java:559` |
| `IndexCondition.get()` | `org/h2/index/IndexCondition.java:122` |
| `IndexCursor.canUseIndexForIn()` | `org/h2/index/IndexCursor.java:318` |
| `IndexCursor.find()` | `org/h2/index/IndexCursor.java:289` |

## 8.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Index` | `org.h2.index` | 834 | 37 |
| `IndexCondition` | `org.h2.index` | 675 | 24 |
| `IndexCursor` | `org.h2.index` | 494 | 13 |
| `LinkedIndex` | `org.h2.index` | 298 | 13 |
| `RegularQueryExpressionIndex` | `org.h2.index` | 223 | 4 |

## 8.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

**`Index`**（`org.h2.index`，834 行，37 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 20%，包级依赖 8 个。

**`IndexCondition`**（`org.h2.index`，675 行，24 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 16%，包级依赖 8 个。

**`IndexCursor`**（`org.h2.index`，494 行，13 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 12%，包级依赖 8 个。

**`LinkedIndex`**（`org.h2.index`，298 行，13 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 7%，包级依赖 8 个。

**`RegularQueryExpressionIndex`**（`org.h2.index`，223 行，4 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

**`IndexType`**（`org.h2.index`，222 行，16 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

## 8.3.2 源码坐标明细

本章主责包中 24 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Index.add()` | `org/h2/index/Index.java:210` |
| `Index.areRowsEquivalent()` | `org/h2/index/Index.java:379` |
| `Index.canFindNext()` | `org/h2/index/Index.java:302` |
| `Index.canGetFirstOrLast()` | `org/h2/index/Index.java:293` |
| `IndexCondition.cloneWithIndexColumns()` | `org/h2/index/IndexCondition.java:559` |
| `IndexCondition.get()` | `org/h2/index/IndexCondition.java:122` |
| `IndexCondition.getColumn()` | `org/h2/index/IndexCondition.java:472` |
| `IndexCondition.getColumns()` | `org/h2/index/IndexCondition.java:485` |
| `IndexCursor.canUseIndexForIn()` | `org/h2/index/IndexCursor.java:318` |
| `IndexCursor.find()` | `org/h2/index/IndexCursor.java:289` |
| `IndexCursor.get()` | `org/h2/index/IndexCursor.java:411` |
| `IndexCursor.getEnd()` | `org/h2/index/IndexCursor.java:406` |
| `LinkedIndex.add()` | `org/h2/index/LinkedIndex.java:61` |
| `LinkedIndex.checkRename()` | `org/h2/index/LinkedIndex.java:199` |
| `LinkedIndex.close()` | `org/h2/index/LinkedIndex.java:52` |
| `LinkedIndex.find()` | `org/h2/index/LinkedIndex.java:90` |
| `RegularQueryExpressionIndex.find()` | `org/h2/index/RegularQueryExpressionIndex.java:161` |
| `RegularQueryExpressionIndex.findByGeometry()` | `org/h2/index/RegularQueryExpressionIndex.java:166` |
| `RegularQueryExpressionIndex.getCost()` | `org/h2/index/RegularQueryExpressionIndex.java:155` |
| `RegularQueryExpressionIndex.isExpired()` | `org/h2/index/RegularQueryExpressionIndex.java:149` |

## 8.4 阅读路径

读 `org.h2.index` 的 23 个文件时，先看骨架类，再沿 `org.h2.result` 方向下钻。

1. 先读 `org.h2.index` 的 package-info 与 `Index`，建立第8章的职责边界。
2. 再读 `Index` 的 37 个公开入口，确认它对 `org.h2.result` 的调用方向与加锁方式。
3. 最后读 `org.h2.index`（本章最小包，4,093 行）的实现，关注容量与失败路径。

跨章衔接请对照第9章《索引与表达式求值》。

## 8.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.index` | `org.h2.result`, `org.h2.table`, `org.h2.value`, `org.h2.engine` |

## 8.6 设计权衡

- `org.h2.index` 用 23 个文件换到 4,093 行实现，平均每文件 177 行，其中 `Index` 独占 834 行、37 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.index`（4,093 行）与 `org.h2.index` 的职责差是本章最值得记的一条边界。

## 8.7 常见误区

- 把 `org.h2.index` 的 4,093 行当作复杂度上限：`Index` 之外的 22 个文件多为类型族与样板。
- 只看 `Index` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.index` 与 `org.h2.index` 视为可互换：前者 23 文件、后者 23 文件，扩展点分布完全不同。

## 8.8 深读要点

规模信号：`org.h2.index` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.index` 依赖 8 个 `org.h2` 包，其中 `org.h2.result` 出现最频繁。
入口信号：`Index` 的公开方法 37 个，读它等于读本章的主干。

## 8.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Index**：详见[术语表](back/glossary.md)对应条目。
- **Table**：详见[术语表](back/glossary.md)对应条目。
- **CBO / Cost-Based Optimization**：详见[术语表](back/glossary.md)对应条目。
- **Genetic Algorithm**：详见[术语表](back/glossary.md)对应条目。
- **Hybrid Strategy**：详见[术语表](back/glossary.md)对应条目。
- **IndexCondition**：详见[术语表](back/glossary.md)对应条目。
- **Optimizer**：详见[术语表](back/glossary.md)对应条目。

## 8.9 知识点清单

1. `org.h2.index` 的 `Index`：834 行、37 个公开方法，职责按方法名归纳
2. `org.h2.index` 的 `IndexCondition`：675 行、24 个公开方法，职责按方法名归纳

## 8.9 本章小结

- 本章覆盖 1 个包、4,093 行。
- 关键入口与源码坐标见 §8.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 8.10 延伸思考

**1. 🟢★ 指出 `org.h2.index` 中 `Index` 与 `IndexCondition` 的分工差异，并给出调用方向。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**2. 🔵★★ 围绕 `org.h2.index` 的 `Index`，说明它为什么需要独立成类型而不是并入 `IndexCondition`。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**3. 🟠★★★ 以 `org.h2.index` 的 `Index` 为入口，画出一次完整调用经过的包。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.index` 的一个类型，你保留 `Index` 还是 `IndexCondition`？说明代价。**

> 提示：第8章 §8.2 的表格给出 `Index` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§8.2 核心类型

## 8.11 本章视角：性能与规模

- 以「性能与规模」看 `org.h2.index`：23 个文件、4,093 行，本章只展开与性能与规模相关的入口。
- 对照 `org.h2.index`（4,093 行）：两者的性能与规模策略不同，差异落在 `Index` 的 37 个公开方法里。
- 若性能与规模假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.result` 进入。

## 8.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.index` | `org.h2.result` | 51 |
| `org.h2.index` | `org.h2.table` | 41 |
| `org.h2.index` | `org.h2.value` | 27 |

## 8.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.index` 与 `org.h2.index` 之间的调用方向？
- `Index` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.index` 的调用链讲到落盘或返回？
- `org.h2.index` 与 `org.h2.index` 若合并，会丢掉哪个扩展点？
- `org.h2.index` 的注释与实现若不一致，你信哪一边，为什么？

## 8.12 延展阅读

- 详见第9章《索引与表达式求值》。
