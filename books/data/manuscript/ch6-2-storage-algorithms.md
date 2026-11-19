# 第7章 存储与压缩算法

> **本章导读**：本章由源码清单汇总而成，覆盖 1 个包、14,516 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 7.1 模块版图

本章覆盖 1 个包、14,516 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.mvstore` | 21 | 14,516 | （无包注释，按主类型归纳） |

## 7.2 核心类型

在 `org.h2.mvstore` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 7.2.1 `org.h2.mvstore`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileStore` | 2,386 | 64 | （无类注释，按方法名归纳） |
| `MVStore` | 2,215 | 85 | （无类注释，按方法名归纳） |
| `MVMap` | 2,181 | 102 | （无类注释，按方法名归纳） |
| `Page` | 1,779 | 77 | （无类注释，按方法名归纳） |

## 7.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `FileStore.accountForRemovedPage()` | `h2/src/main/org/h2/mvstore/FileStore.java:2178` |
| `FileStore.backup()` | `h2/src/main/org/h2/mvstore/FileStore.java:1432` |
| `MVStore.adoptFileStore()` | `h2/src/main/org/h2/mvstore/MVStore.java:2183` |
| `MVStore.autoCommitBufferSize()` | `h2/src/main/org/h2/mvstore/MVStore.java:2003` |
| `MVMap.append()` | `h2/src/main/org/h2/mvstore/MVMap.java:1364` |
| `MVMap.ceilingKey()` | `h2/src/main/org/h2/mvstore/MVMap.java:325` |

## 7.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `FileStore` | `org.h2.mvstore` | 2,386 | 64 |
| `MVStore` | `org.h2.mvstore` | 2,215 | 85 |
| `MVMap` | `org.h2.mvstore` | 2,181 | 102 |
| `Page` | `org.h2.mvstore` | 1,779 | 77 |
| `DataUtils` | `org.h2.mvstore` | 1,185 | 45 |

## 7.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 7.3.2.1 `FileStore`

`FileStore` 位于 `org.h2.mvstore`，2,386 行、64 个公开方法。它占该包实现的 16%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 7.3.2.2 `MVStore`

`MVStore` 位于 `org.h2.mvstore`，2,215 行、85 个公开方法。它占该包实现的 15%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 7.3.2.3 `MVMap`

`MVMap` 位于 `org.h2.mvstore`，2,181 行、102 个公开方法。它占该包实现的 15%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 7.3.2.4 `Page`

`Page` 位于 `org.h2.mvstore`，1,779 行、77 个公开方法。它占该包实现的 12%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 7.3.2.5 `DataUtils`

`DataUtils` 位于 `org.h2.mvstore`，1,185 行、45 个公开方法。它占该包实现的 8%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 7.3.2.6 `RandomAccessStore`

`RandomAccessStore` 位于 `org.h2.mvstore`，851 行、10 个公开方法。它占该包实现的 6%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

## 7.3.2 源码坐标明细

本章主责包中 36 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `FileStore.accountForRemovedPage()` | `h2/src/main/org/h2/mvstore/FileStore.java:2178` |
| `FileStore.backup()` | `h2/src/main/org/h2/mvstore/FileStore.java:1432` |
| `FileStore.bind()` | `h2/src/main/org/h2/mvstore/FileStore.java:281` |
| `FileStore.clear()` | `h2/src/main/org/h2/mvstore/FileStore.java:1397` |
| `FileStore.close()` | `h2/src/main/org/h2/mvstore/FileStore.java:314` |
| `FileStore.compact()` | `h2/src/main/org/h2/mvstore/FileStore.java:937` |
| `MVStore.adoptFileStore()` | `h2/src/main/org/h2/mvstore/MVStore.java:2183` |
| `MVStore.autoCommitBufferSize()` | `h2/src/main/org/h2/mvstore/MVStore.java:2003` |
| `MVStore.autoCommitDisabled()` | `h2/src/main/org/h2/mvstore/MVStore.java:1981` |
| `MVStore.autoCompactFillRate()` | `h2/src/main/org/h2/mvstore/MVStore.java:2021` |
| `MVStore.backgroundExceptionHandler()` | `h2/src/main/org/h2/mvstore/MVStore.java:2161` |
| `MVStore.cacheConcurrency()` | `h2/src/main/org/h2/mvstore/MVStore.java:2105` |
| `MVMap.append()` | `h2/src/main/org/h2/mvstore/MVMap.java:1364` |
| `MVMap.ceilingKey()` | `h2/src/main/org/h2/mvstore/MVMap.java:325` |
| `MVMap.clear()` | `h2/src/main/org/h2/mvstore/MVMap.java:441` |
| `MVMap.contains()` | `h2/src/main/org/h2/mvstore/MVMap.java:763` |
| `MVMap.containsKey()` | `h2/src/main/org/h2/mvstore/MVMap.java:433` |
| `MVMap.create()` | `h2/src/main/org/h2/mvstore/MVMap.java:1518` |
| `Page.copy()` | `h2/src/main/org/h2/mvstore/Page.java:382` |
| `Page.createEmptyLeaf()` | `h2/src/main/org/h2/mvstore/Page.java:156` |

## 7.4 阅读路径

读 `org.h2.mvstore` 的 21 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.mvstore` 的 package-info 与 `FileStore`，建立第7章的职责边界。
2. 再读 `FileStore` 的 64 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.mvstore`（本章最小包，14,516 行）的实现，关注容量与失败路径。

跨章衔接请对照第8章《存储与压缩算法》。

## 7.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.mvstore` | `org.h2`, `org.h2.store`, `org.h2.store.fs`, `org.h2.engine` |

## 7.6 设计权衡

`org.h2.mvstore` 有 21 个文件、14,516 行。平均每文件 691 行。

其中 `FileStore` 独占 2,386 行，64 个公开方法。规模集中，风险也集中。

它对外声明 4 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.mvstore`（14,516 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 7.7 常见误区

把 `org.h2.mvstore` 的行数当作复杂度上限是误读。`FileStore` 之外还有 20 个文件，其中多为类型族与样板。

只读 `FileStore` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.mvstore` 与 `org.h2.mvstore` 不能互换。前者 21 个文件，后者 21 个文件，扩展点分布完全不同。

## 7.8 深读要点

规模信号：`org.h2.mvstore` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.mvstore` 依赖 4 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`FileStore` 的公开方法 64 个，读它等于读本章的主干。

## 7.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **MVStore**：详见[术语表](back/glossary.md)对应条目。
- **Append-Only**：详见[术语表](back/glossary.md)对应条目。
- **BackgroundWriter**：详见[术语表](back/glossary.md)对应条目。
- **Block**：详见[术语表](back/glossary.md)对应条目。
- **Chunk**：详见[术语表](back/glossary.md)对应条目。
- **Checkpoint**：详见[术语表](back/glossary.md)对应条目。
- **Counted B-Tree**：详见[术语表](back/glossary.md)对应条目。

## 7.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `FileStore` | `org.h2.mvstore` | 2,386 | 64 | 按方法名归纳 |
| `MVStore` | `org.h2.mvstore` | 2,215 | 85 | 按方法名归纳 |

## 7.9 本章小结

- 本章覆盖 1 个包、14,516 行。
- 关键入口与源码坐标见 §7.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 7.10 延伸思考

**1. 🟢★ 说明 `FileStore` 与 `MVStore` 的分工差异。给出调用方向。**

> 提示：第7章 §7.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

**2. 🔵★★ `FileStore` 为什么独立成类型，而不是并入 `MVStore`？**

> 提示：第7章 §7.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

**3. 🟠★★★ 以 `FileStore` 为入口，画出一次完整调用经过的包。**

> 提示：第7章 §7.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `FileStore` 还是 `MVStore`？说明代价。**

> 提示：第7章 §7.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

## 7.11 本章视角：演化与版本

- 以「演化与版本」看 `org.h2.mvstore`：21 个文件、14,516 行，本章只展开与演化与版本相关的入口。
- 对照 `org.h2.mvstore`（14,516 行）：两者的演化与版本策略不同，差异落在 `FileStore` 的 64 个公开方法里。
- 若演化与版本假设被打破（4 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 7.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.mvstore` | `org.h2` | 22 |
| `org.h2.mvstore` | `org.h2.store` | 5 |
| `org.h2.mvstore` | `org.h2.store.fs` | 4 |

## 7.11.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2.mvstore` 与 `org.h2.mvstore` 的调用方向？`FileStore` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.mvstore` 的调用链讲到落盘或返回，并说清 `org.h2.mvstore` 与 `org.h2.mvstore` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.mvstore` 的注释与实现对不上，你信哪一边，为什么？

## 7.12 延展阅读

- 详见第8章《存储与压缩算法》。
