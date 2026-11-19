# 第7章 存储与压缩算法

> **本章导读**：本章由源码清单汇总而成，覆盖 3 个包、18,551 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 7.1 模块版图

本章覆盖 3 个包、18,551 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.mvstore` | 20 | 14,505 | A persistent storage for tree maps. |
| `org.h2.store` | 17 | 2,712 | Storage abstractions and helper classes. |
| `org.h2.store.fs` | 7 | 1,334 | A file system abstraction. |

## 7.2 核心类型

在 `org.h2.mvstore` 之外，本章还有 2 个包；下表每包取前 4 个类型，按规模降序。

### 7.2.1 `org.h2.mvstore`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileStore` | 2,386 | 64 | （无类注释，按方法名归纳） |
| `MVStore` | 2,215 | 85 | （无类注释，按方法名归纳） |
| `MVMap` | 2,181 | 102 | （无类注释，按方法名归纳） |
| `Page` | 1,779 | 77 | （无类注释，按方法名归纳） |

### 7.2.2 `org.h2.store`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileLock` | 514 | 8 | （无类注释，按方法名归纳） |
| `FileStore` | 513 | 22 | （无类注释，按方法名归纳） |
| `Data` | 220 | 13 | （无类注释，按方法名归纳） |
| `RecoverTester` | 176 | 3 | （无类注释，按方法名归纳） |

### 7.2.3 `org.h2.store.fs`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileUtils` | 477 | 29 | （无类注释，按方法名归纳） |
| `FilePath` | 353 | 28 | （无类注释，按方法名归纳） |
| `FilePathWrapper` | 171 | 22 | （无类注释，按方法名归纳） |
| `FakeFileChannel` | 112 | 16 | （无类注释，按方法名归纳） |

## 7.3 关键 API 与源码坐标

把 3 个包的关键入口与源码位置对应起来，共 9 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `FileStore.accountForRemovedPage()` | `org/h2/mvstore/FileStore.java:2178` |
| `FileStore.backup()` | `org/h2/mvstore/FileStore.java:1432` |
| `MVStore.adoptFileStore()` | `org/h2/mvstore/MVStore.java:2183` |
| `MVStore.autoCommitBufferSize()` | `org/h2/mvstore/MVStore.java:2003` |
| `MVMap.append()` | `org/h2/mvstore/MVMap.java:1364` |
| `MVMap.ceilingKey()` | `org/h2/mvstore/MVMap.java:325` |
| `FileLock.getFileLockMethod()` | `org/h2/store/FileLock.java:458` |
| `FileLock.getUniqueId()` | `org/h2/store/FileLock.java:472` |
| `FileStore.autoDelete()` | `org/h2/store/FileStore.java:429` |
| `FileStore.close()` | `org/h2/store/FileStore.java:221` |
| `Data.checkCapacity()` | `org/h2/store/Data.java:171` |
| `Data.copyString()` | `org/h2/store/Data.java:204` |
| `FileUtils.canWrite()` | `org/h2/store/fs/FileUtils.java:317` |
| `FileUtils.createDirectories()` | `org/h2/store/fs/FileUtils.java:372` |
| `FilePath.canWrite()` | `org/h2/store/fs/FilePath.java:201` |
| `FilePath.createDirectory()` | `org/h2/store/fs/FilePath.java:206` |
| `FilePathWrapper.canWrite()` | `org/h2/store/fs/FilePathWrapper.java:72` |
| `FilePathWrapper.createDirectory()` | `org/h2/store/fs/FilePathWrapper.java:77` |

## 7.3.1 公共类型清单

本章抽样类型按包分组，共 15 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `FileStore` | `org.h2.mvstore` | 2,386 | 64 |
| `MVStore` | `org.h2.mvstore` | 2,215 | 85 |
| `MVMap` | `org.h2.mvstore` | 2,181 | 102 |
| `Page` | `org.h2.mvstore` | 1,779 | 77 |
| `DataUtils` | `org.h2.mvstore` | 1,185 | 45 |
| `FileLock` | `org.h2.store` | 514 | 8 |
| `FileStore` | `org.h2.store` | 513 | 22 |
| `Data` | `org.h2.store` | 220 | 13 |
| `RecoverTester` | `org.h2.store` | 176 | 3 |
| `FileStoreInputStream` | `org.h2.store` | 155 | 5 |
| `FileUtils` | `org.h2.store.fs` | 477 | 29 |
| `FilePath` | `org.h2.store.fs` | 353 | 28 |
| `FilePathWrapper` | `org.h2.store.fs` | 171 | 22 |
| `FakeFileChannel` | `org.h2.store.fs` | 112 | 16 |
| `FileBase` | `org.h2.store.fs` | 92 | 10 |

## 7.4 阅读路径

读 `org.h2.mvstore` 的 20 个文件时，先看骨架类，再沿 `org.h2.util` 方向下钻。

1. 先读 `org.h2.mvstore` 的 package-info 与 `FileStore`，建立第7章的职责边界。
2. 再读 `FileStore` 的 64 个公开入口，确认它对 `org.h2.util` 的调用方向与加锁方式。
3. 最后读 `org.h2.store.fs`（本章最小包，1,334 行）的实现，关注容量与失败路径。

跨章衔接请对照第8章《存储与压缩算法》。

## 7.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.mvstore` | `org.h2.util`, `org.h2.compress`, `org.h2.store.fs`, `org.h2.store.fs.encrypt` |
| `org.h2.store` | `org.h2.engine`, `org.h2.util`, `org.h2.message`, `org.h2.value` |
| `org.h2.store.fs` | `org.h2.util`, `org.h2.engine` |

## 7.6 设计权衡

- `org.h2.mvstore` 用 20 个文件换到 14,505 行实现，平均每文件 725 行，其中 `FileStore` 独占 2,386 行、64 个公开方法。
- 该包对外声明了 7 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.store`（2,712 行）与 `org.h2.mvstore` 的职责差是本章最值得记的一条边界。

## 7.7 常见误区

- 把 `org.h2.mvstore` 的 14,505 行当作复杂度上限：`FileStore` 之外的 19 个文件多为类型族与样板。
- 只看 `FileStore` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.mvstore` 与 `org.h2.store` 视为可互换：前者 20 文件、后者 17 文件，扩展点分布完全不同。

## 7.8 深读要点

规模信号：`org.h2.mvstore` 占本章 78% 的实现行数，改动风险最高。
耦合信号：`org.h2.mvstore` 依赖 7 个 `org.h2` 包，其中 `org.h2.util` 出现最频繁。
入口信号：`FileStore` 的公开方法 64 个，读它等于读本章的主干。

## 7.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **MVStore**：详见[术语表](back/glossary.md)对应条目。

## 7.9 知识点清单

1. `org.h2.mvstore` 的 `FileStore`：2,386 行、64 个公开方法，职责按方法名归纳
2. `org.h2.mvstore` 的 `MVStore`：2,215 行、85 个公开方法，职责按方法名归纳
3. `org.h2.store` 的 `FileLock`：514 行、8 个公开方法，职责按方法名归纳
4. `org.h2.store` 的 `FileStore`：513 行、22 个公开方法，职责按方法名归纳
5. `org.h2.store.fs` 的 `FileUtils`：477 行、29 个公开方法，职责按方法名归纳
6. `org.h2.store.fs` 的 `FilePath`：353 行、28 个公开方法，职责按方法名归纳

## 7.9 本章小结

- 本章覆盖 3 个包、18,551 行。
- 关键入口与源码坐标见 §7.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 7.10 延伸思考

**1. 🟢★ 指出 `org.h2.mvstore` 中 `FileStore` 与 `MVStore` 的分工差异，并给出调用方向。**

> 提示：第7章 §7.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

**2. 🔵★★ 围绕 `org.h2.store` 的 `FileLock`，说明它为什么需要独立成类型而不是并入 `FileStore`。**

> 提示：第7章 §7.2 的表格给出 `FileLock` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

**3. 🟠★★★ 以 `org.h2.store.fs` 的 `FileUtils` 为入口，画出一次完整调用经过的包。**

> 提示：第7章 §7.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.mvstore` 的一个类型，你保留 `FileStore` 还是 `MVStore`？说明代价。**

> 提示：第7章 §7.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§7.2 核心类型

## 7.11 本章视角：演化与版本

- 以「演化与版本」看 `org.h2.mvstore`：20 个文件、14,505 行，本章只展开与演化与版本相关的入口。
- 对照 `org.h2.store`（2,712 行）：两者的演化与版本策略不同，差异落在 `FileStore` 的 64 个公开方法里。
- 若演化与版本假设被打破（7 个依赖变化），最先受影响的调用链从 `org.h2.util` 进入。

## 7.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.mvstore` | `org.h2.util` | 10 |
| `org.h2.mvstore` | `org.h2.compress` | 7 |
| `org.h2.mvstore` | `org.h2.store.fs` | 5 |
| `org.h2.store` | `org.h2.engine` | 16 |
| `org.h2.store` | `org.h2.util` | 14 |
| `org.h2.store` | `org.h2.message` | 11 |
| `org.h2.store.fs` | `org.h2.util` | 1 |
| `org.h2.store.fs` | `org.h2.engine` | 1 |

## 7.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.mvstore` 与 `org.h2.store` 之间的调用方向？
- `FileStore` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.mvstore` 的调用链讲到落盘或返回？
- `org.h2.mvstore` 与 `org.h2.store` 若合并，会丢掉哪个扩展点？
- `org.h2.mvstore` 的注释与实现若不一致，你信哪一边，为什么？

## 7.12 延展阅读

- 详见第8章《存储与压缩算法》。
