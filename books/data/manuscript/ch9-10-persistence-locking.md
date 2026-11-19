# 第11章 持久化

> **本章导读**：本章《持久化》由源码清单汇总而成，覆盖 3 个包、18,539 行实现。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 11.1 模块版图

本章覆盖 2 个包、17,194 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.util` | 49 | 14,471 | （无包注释，按主类型归纳） |
| `org.h2.store` | 18 | 2,723 | （无包注释，按主类型归纳） |

## 11.2 核心类型

在 `org.h2.util` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 11.2.1 `org.h2.util`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `StringUtils` | 1,415 | 55 | （无类注释，按方法名归纳） |
| `DateTimeUtils` | 1,171 | 42 | （无类注释，按方法名归纳） |
| `DateTimeTemplate` | 859 | 5 | （无类注释，按方法名归纳） |
| `IntervalUtils` | 857 | 12 | （无类注释，按方法名归纳） |

### 11.2.2 `org.h2.store`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileLock` | 514 | 8 | （无类注释，按方法名归纳） |
| `FileStore` | 513 | 22 | （无类注释，按方法名归纳） |
| `Data` | 220 | 13 | （无类注释，按方法名归纳） |
| `RecoverTester` | 176 | 3 | （无类注释，按方法名归纳） |

## 11.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `StringUtils.addAsterisk()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/StringUtils.java:283` |
| `StringUtils.appendHex()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/StringUtils.java:1277` |
| `DateTimeUtils.absoluteDayFromDateValue()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeUtils.java:873` |
| `DateTimeUtils.absoluteDayFromYear()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeUtils.java:857` |
| `DateTimeTemplate.format()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeTemplate.java:178` |
| `DateTimeTemplate.of()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeTemplate.java:430` |
| `FileLock.getFileLockMethod()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/FileLock.java:458` |
| `FileLock.getUniqueId()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/FileLock.java:472` |
| `FileStore.autoDelete()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/FileStore.java:429` |
| `FileStore.close()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/FileStore.java:221` |
| `Data.checkCapacity()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/Data.java:171` |
| `Data.copyString()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/Data.java:204` |

## 11.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `StringUtils` | `org.h2.util` | 1,415 | 55 |
| `DateTimeUtils` | `org.h2.util` | 1,171 | 42 |
| `DateTimeTemplate` | `org.h2.util` | 859 | 5 |
| `IntervalUtils` | `org.h2.util` | 857 | 12 |
| `Utils` | `org.h2.util` | 832 | 34 |
| `FileLock` | `org.h2.store` | 514 | 8 |
| `FileStore` | `org.h2.store` | 513 | 22 |
| `Data` | `org.h2.store` | 220 | 13 |
| `RecoverTester` | `org.h2.store` | 176 | 3 |
| `FileStoreInputStream` | `org.h2.store` | 155 | 5 |

## 11.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 11.3.2.1 `StringUtils`

`StringUtils` 位于 `org.h2.util`，1,415 行、55 个公开方法。它占该包实现的 10%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 11.3.2.2 `DateTimeUtils`

`DateTimeUtils` 位于 `org.h2.util`，1,171 行、42 个公开方法。它占该包实现的 8%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 11.3.2.3 `DateTimeTemplate`

`DateTimeTemplate` 位于 `org.h2.util`，859 行、5 个公开方法。它占该包实现的 6%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 11.3.2.4 `IntervalUtils`

`IntervalUtils` 位于 `org.h2.util`，857 行、12 个公开方法。它占该包实现的 6%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 11.3.2.5 `Utils`

`Utils` 位于 `org.h2.util`，832 行、34 个公开方法。它占该包实现的 6%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 11.3.2.6 `JdbcUtils`

`JdbcUtils` 位于 `org.h2.util`，785 行、17 个公开方法。它占该包实现的 5%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（5 个），再决定是否顺带读同包的相邻类型。

### 11.3.2.7 `FileLock`

`FileLock` 位于 `org.h2.store`，514 行、8 个公开方法。它占该包实现的 19%，包内排名第 7。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 11.3.2.8 `FileStore`

`FileStore` 位于 `org.h2.store`，513 行、22 个公开方法。它占该包实现的 19%，包内排名第 8。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 11.3.2.9 `Data`

`Data` 位于 `org.h2.store`，220 行、13 个公开方法。它占该包实现的 8%，包内排名第 9。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 11.3.2.10 `RecoverTester`

`RecoverTester` 位于 `org.h2.store`，176 行、3 个公开方法。它占该包实现的 6%，包内排名第 10。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 11.3.2.11 `FileStoreInputStream`

`FileStoreInputStream` 位于 `org.h2.store`，155 行、5 个公开方法。它占该包实现的 6%，包内排名第 11。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 11.3.2.12 `DataReader`

`DataReader` 位于 `org.h2.store`，133 行、5 个公开方法。它占该包实现的 5%，包内排名第 12。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

## 11.3.2 源码坐标明细

本章主责包中 62 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `StringUtils.addAsterisk()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/StringUtils.java:283` |
| `StringUtils.appendHex()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/StringUtils.java:1277` |
| `StringUtils.appendToLength()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/StringUtils.java:1360` |
| `StringUtils.appendTwoDigits()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/StringUtils.java:1327` |
| `StringUtils.appendZeroPadded()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/StringUtils.java:1342` |
| `StringUtils.arrayCombine()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/StringUtils.java:525` |
| `DateTimeUtils.absoluteDayFromDateValue()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeUtils.java:873` |
| `DateTimeUtils.absoluteDayFromYear()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeUtils.java:857` |
| `DateTimeUtils.appendDate()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeUtils.java:981` |
| `DateTimeUtils.appendTime()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeUtils.java:1003` |
| `DateTimeUtils.appendTimeZone()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeUtils.java:1063` |
| `DateTimeUtils.convertScale()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeUtils.java:1123` |
| `DateTimeTemplate.format()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeTemplate.java:178` |
| `DateTimeTemplate.of()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeTemplate.java:430` |
| `DateTimeTemplate.parse()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/DateTimeTemplate.java:183` |
| `IntervalUtils.appendInterval()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/IntervalUtils.java:402` |
| `IntervalUtils.daysFromInterval()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/IntervalUtils.java:724` |
| `IntervalUtils.hoursFromInterval()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/IntervalUtils.java:753` |
| `IntervalUtils.intervalFromAbsolute()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/IntervalUtils.java:540` |
| `IntervalUtils.intervalToAbsolute()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/util/IntervalUtils.java:472` |

## 11.4 阅读路径

读 `org.h2.util` 的 49 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.util` 的 package-info 与 `StringUtils`，建立第11章的职责边界。
2. 再读 `StringUtils` 的 55 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.store`（本章最小包，2,723 行）的实现，关注容量与失败路径。

跨章衔接请对照第12章《并发控制》。

## 11.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.util` | `org.h2`, `org.h2.util.DateTimeTemplate`, `org.h2.store`, `org.h2.mvstore` |
| `org.h2.store` | `org.h2`, `org.h2.util`, `org.h2.store.fs` |

## 11.6 设计权衡

`org.h2.util` 有 49 个文件、14,471 行。平均每文件 295 行。

其中 `StringUtils` 独占 1,415 行，55 个公开方法。规模集中，风险也集中。

它对外声明 5 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.store`（2,723 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 11.7 常见误区

把 `org.h2.util` 的行数当作复杂度上限是误读。`StringUtils` 之外还有 48 个文件，其中多为类型族与样板。

只读 `StringUtils` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.util` 与 `org.h2.store` 不能互换。前者 49 个文件，后者 18 个文件，扩展点分布完全不同。

## 11.8 深读要点

规模信号：`org.h2.util` 占本章 84% 的实现行数，改动风险最高。
耦合信号：`org.h2.util` 依赖 5 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`StringUtils` 的公开方法 55 个，读它等于读本章的主干。

## 11.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **JdbcResultSet**：详见[术语表](back/glossary.md)对应条目。
- **SimpleResultSet**：详见[术语表](back/glossary.md)对应条目。
- **JdbcDatabaseMetaData**：详见[术语表](back/glossary.md)对应条目。

## 11.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `StringUtils` | `org.h2.util` | 1,415 | 55 | 按方法名归纳 |
| `DateTimeUtils` | `org.h2.util` | 1,171 | 42 | 按方法名归纳 |
| `FileLock` | `org.h2.store` | 514 | 8 | 按方法名归纳 |
| `FileStore` | `org.h2.store` | 513 | 22 | 按方法名归纳 |

## 11.9 本章小结

本章覆盖 2 个包、共 17,194 行，主要包为 org.h2.util。
- 关键入口与源码坐标见 §11.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 11.10 延伸思考

**1. 🟢★ 说明 `StringUtils` 与 `DateTimeUtils` 的分工差异。给出调用方向。**

> 提示：第11章 §11.2 的表格给出 `StringUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

**2. 🔵★★ `FileLock` 为什么独立成类型，而不是并入 `FileStore`？**

> 提示：第11章 §11.2 的表格给出 `FileLock` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

**3. 🟠★★★ 以 `StringUtils` 为入口，画出一次完整调用经过的包。**

> 提示：第11章 §11.2 的表格给出 `StringUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `FileLock` 还是 `FileStore`？说明代价。**

> 提示：第11章 §11.2 的表格给出 `FileLock` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

## 11.11 本章视角：演化与版本

- 以「演化与版本」看 `org.h2.util`：49 个文件、14,471 行，本章只展开与演化与版本相关的入口。
- 对照 `org.h2.store`（2,723 行）：两者的演化与版本策略不同，差异落在 `StringUtils` 的 55 个公开方法里。
- 若演化与版本假设被打破（5 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 11.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.util` | `org.h2` | 89 |
| `org.h2.util` | `org.h2.util.DateTimeTemplate` | 16 |
| `org.h2.util` | `org.h2.store` | 5 |
| `org.h2.store` | `org.h2` | 59 |
| `org.h2.store` | `org.h2.util` | 1 |
| `org.h2.store` | `org.h2.store.fs` | 1 |

## 11.11.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2.util` 与 `org.h2.store` 的调用方向？`StringUtils` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.util` 的调用链讲到落盘或返回，并说清 `org.h2.util` 与 `org.h2.store` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.util` 的注释与实现对不上，你信哪一边，为什么？

## 11.12 延展阅读

- 详见第12章《并发控制》。

# 第12章 并发控制

## 12.1 模块版图

本章覆盖 1 个包、1,345 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.store.fs` | 8 | 1,345 | （无包注释，按主类型归纳） |

## 12.2 核心类型

在 `org.h2.store.fs` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 12.2.1 `org.h2.store.fs`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileUtils` | 477 | 29 | （无类注释，按方法名归纳） |
| `FilePath` | 353 | 28 | （无类注释，按方法名归纳） |
| `FilePathWrapper` | 171 | 22 | （无类注释，按方法名归纳） |
| `FakeFileChannel` | 112 | 16 | （无类注释，按方法名归纳） |

## 12.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `FileUtils.canWrite()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FileUtils.java:317` |
| `FileUtils.createDirectories()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FileUtils.java:372` |
| `FilePath.canWrite()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePath.java:201` |
| `FilePath.createDirectory()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePath.java:206` |
| `FilePathWrapper.canWrite()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePathWrapper.java:72` |
| `FilePathWrapper.createDirectory()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePathWrapper.java:77` |

## 12.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `FileUtils` | `org.h2.store.fs` | 477 | 29 |
| `FilePath` | `org.h2.store.fs` | 353 | 28 |
| `FilePathWrapper` | `org.h2.store.fs` | 171 | 22 |
| `FakeFileChannel` | `org.h2.store.fs` | 112 | 16 |
| `FileBase` | `org.h2.store.fs` | 92 | 10 |

## 12.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 12.3.2.1 `FileUtils`

`FileUtils` 位于 `org.h2.store.fs`，477 行、29 个公开方法。它占该包实现的 35%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（1 个），再决定是否顺带读同包的相邻类型。

### 12.3.2.2 `FilePath`

`FilePath` 位于 `org.h2.store.fs`，353 行、28 个公开方法。它占该包实现的 26%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（1 个），再决定是否顺带读同包的相邻类型。

### 12.3.2.3 `FilePathWrapper`

`FilePathWrapper` 位于 `org.h2.store.fs`，171 行、22 个公开方法。它占该包实现的 13%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（1 个），再决定是否顺带读同包的相邻类型。

### 12.3.2.4 `FakeFileChannel`

`FakeFileChannel` 位于 `org.h2.store.fs`，112 行、16 个公开方法。它占该包实现的 8%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（1 个），再决定是否顺带读同包的相邻类型。

### 12.3.2.5 `FileBase`

`FileBase` 位于 `org.h2.store.fs`，92 行、10 个公开方法。它占该包实现的 7%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（1 个），再决定是否顺带读同包的相邻类型。

### 12.3.2.6 `FileBaseDefault`

`FileBaseDefault` 位于 `org.h2.store.fs`，69 行、5 个公开方法。它占该包实现的 5%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（1 个），再决定是否顺带读同包的相邻类型。

## 12.3.2 源码坐标明细

本章主责包中 34 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `FileUtils.canWrite()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FileUtils.java:317` |
| `FileUtils.createDirectories()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FileUtils.java:372` |
| `FileUtils.createDirectory()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FileUtils.java:84` |
| `FileUtils.createFile()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FileUtils.java:96` |
| `FileUtils.createTempFile()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FileUtils.java:412` |
| `FileUtils.delete()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FileUtils.java:108` |
| `FilePath.canWrite()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePath.java:201` |
| `FilePath.createDirectory()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePath.java:206` |
| `FilePath.createFile()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePath.java:132` |
| `FilePath.createTempFile()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePath.java:284` |
| `FilePath.delete()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePath.java:145` |
| `FilePath.exists()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePath.java:139` |
| `FilePathWrapper.canWrite()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePathWrapper.java:72` |
| `FilePathWrapper.createDirectory()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePathWrapper.java:77` |
| `FilePathWrapper.createFile()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePathWrapper.java:82` |
| `FilePathWrapper.createTempFile()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePathWrapper.java:166` |
| `FilePathWrapper.delete()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePathWrapper.java:87` |
| `FilePathWrapper.exists()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FilePathWrapper.java:92` |
| `FakeFileChannel.force()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FakeFileChannel.java:109` |
| `FakeFileChannel.lock()` | `../lzcapp/document/codebase/h2db/h2/src/main/org/h2/store/fs/FakeFileChannel.java:34` |

## 12.4 阅读路径

读 `org.h2.store.fs` 的 8 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.store.fs` 的 package-info 与 `FileUtils`，建立第12章的职责边界。
2. 再读 `FileUtils` 的 29 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.store.fs`（本章最小包，1,345 行）的实现，关注容量与失败路径。

跨章衔接请对照第11章《持久化》。

## 12.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.store.fs` | `org.h2` |

## 12.6 设计权衡

`org.h2.store.fs` 有 8 个文件、1,345 行。平均每文件 168 行。

其中 `FileUtils` 独占 477 行，29 个公开方法。规模集中，风险也集中。

它对外声明 1 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.store.fs`（1,345 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 12.7 常见误区

把 `org.h2.store.fs` 的行数当作复杂度上限是误读。`FileUtils` 之外还有 7 个文件，其中多为类型族与样板。

只读 `FileUtils` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.store.fs` 与 `org.h2.store.fs` 不能互换。前者 8 个文件，后者 8 个文件，扩展点分布完全不同。

## 12.8 深读要点

规模信号：`org.h2.store.fs` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.store.fs` 依赖 1 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`FileUtils` 的公开方法 29 个，读它等于读本章的主干。

## 12.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。

## 12.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `FileUtils` | `org.h2.store.fs` | 477 | 29 | 按方法名归纳 |
| `FilePath` | `org.h2.store.fs` | 353 | 28 | 按方法名归纳 |

## 12.9 本章小结

本章覆盖 1 个包、共 1,345 行代码，主要包为 org.h2.store.fs。
- 关键入口与源码坐标见 §12.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 12.10 延伸思考

**1. 🟢★ 说明 `FileUtils` 与 `FilePath` 的分工差异。给出调用方向。**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

**2. 🔵★★ `FileUtils` 为什么独立成类型，而不是并入 `FilePath`？**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

**3. 🟠★★★ 以 `FileUtils` 为入口，画出一次完整调用经过的包。**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `FileUtils` 还是 `FilePath`？说明代价。**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

## 12.11 本章视角：性能与规模

- 以「性能与规模」看 `org.h2.store.fs`：8 个文件、1,345 行，本章只展开与性能与规模相关的入口。
- 对照 `org.h2.store.fs`（1,345 行）：两者的性能与规模策略不同，差异落在 `FileUtils` 的 29 个公开方法里。
- 若性能与规模假设被打破（1 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 12.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.store.fs` | `org.h2` | 2 |

## 12.11.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2.store.fs` 与 `org.h2.store.fs` 的调用方向？`FileUtils` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.store.fs` 的调用链讲到落盘或返回，并说清 `org.h2.store.fs` 与 `org.h2.store.fs` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.store.fs` 的注释与实现对不上，你信哪一边，为什么？

## 12.12 跨章索引

本章引用但不展开的包，按下面这张表跳到主责章节阅读。

| 包 | 主责章节 |
| --- | --- |
| `org.h2.store.fs` | 第11章《持久化》 |

## 12.12 延展阅读

- 详见第11章《持久化》。
