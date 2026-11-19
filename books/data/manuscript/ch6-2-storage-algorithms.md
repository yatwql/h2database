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

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

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

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

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

## 7.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第8章《存储与压缩算法》。

## 7.5 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **MVStore**：详见[术语表](back/glossary.md)对应条目。

## 7.6 本章小结

- 本章覆盖 3 个包、18,551 行。
- 关键入口与源码坐标见 §7.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 7.7 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：回到 §7.1 的表格，按规模排序挑选目标包。
> 回顾：§7.1 模块版图

**2. 🔵★★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：回到 §7.1 的表格，按规模排序挑选目标包。
> 回顾：§7.1 模块版图

**3. 🟠★★★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §7.1 的表格，按规模排序挑选目标包。
> 回顾：§7.1 模块版图

**4. 🟢★★★★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：回到 §7.1 的表格，按规模排序挑选目标包。
> 回顾：§7.1 模块版图

## 7.8 延展阅读

- 详见第8章《存储与压缩算法》。
