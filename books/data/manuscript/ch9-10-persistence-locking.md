# 第11章 持久化

> **本章导读**：本章由源码清单汇总而成，覆盖 3 个包、18,506 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 11.1 模块版图

本章覆盖 2 个包、17,172 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.util` | 48 | 14,460 | Internal utility classes. |
| `org.h2.store` | 17 | 2,712 | Storage abstractions and helper classes. |

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
| `StringUtils.addAsterisk()` | `org/h2/util/StringUtils.java:283` |
| `StringUtils.appendHex()` | `org/h2/util/StringUtils.java:1277` |
| `DateTimeUtils.absoluteDayFromDateValue()` | `org/h2/util/DateTimeUtils.java:873` |
| `DateTimeUtils.absoluteDayFromYear()` | `org/h2/util/DateTimeUtils.java:857` |
| `DateTimeTemplate.format()` | `org/h2/util/DateTimeTemplate.java:178` |
| `DateTimeTemplate.of()` | `org/h2/util/DateTimeTemplate.java:430` |
| `FileLock.getFileLockMethod()` | `org/h2/store/FileLock.java:458` |
| `FileLock.getUniqueId()` | `org/h2/store/FileLock.java:472` |
| `FileStore.autoDelete()` | `org/h2/store/FileStore.java:429` |
| `FileStore.close()` | `org/h2/store/FileStore.java:221` |
| `Data.checkCapacity()` | `org/h2/store/Data.java:171` |
| `Data.copyString()` | `org/h2/store/Data.java:204` |

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

**`StringUtils`**（`org.h2.util`，1,415 行，55 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 10%，包级依赖 8 个。

**`DateTimeUtils`**（`org.h2.util`，1,171 行，42 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

**`DateTimeTemplate`**（`org.h2.util`，859 行，5 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

**`IntervalUtils`**（`org.h2.util`，857 行，12 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

**`Utils`**（`org.h2.util`，832 行，34 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

**`JdbcUtils`**（`org.h2.util`，785 行，17 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

**`FileLock`**（`org.h2.store`，514 行，8 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 19%，包级依赖 8 个。

**`FileStore`**（`org.h2.store`，513 行，22 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 19%，包级依赖 8 个。

**`Data`**（`org.h2.store`，220 行，13 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 8 个。

**`RecoverTester`**（`org.h2.store`，176 行，3 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

**`FileStoreInputStream`**（`org.h2.store`，155 行，5 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 6%，包级依赖 8 个。

**`DataReader`**（`org.h2.store`，133 行，5 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 8 个。

## 11.3.2 源码坐标明细

本章主责包中 45 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `StringUtils.addAsterisk()` | `org/h2/util/StringUtils.java:283` |
| `StringUtils.appendHex()` | `org/h2/util/StringUtils.java:1277` |
| `StringUtils.appendToLength()` | `org/h2/util/StringUtils.java:1360` |
| `StringUtils.appendTwoDigits()` | `org/h2/util/StringUtils.java:1327` |
| `DateTimeUtils.absoluteDayFromDateValue()` | `org/h2/util/DateTimeUtils.java:873` |
| `DateTimeUtils.absoluteDayFromYear()` | `org/h2/util/DateTimeUtils.java:857` |
| `DateTimeUtils.appendDate()` | `org/h2/util/DateTimeUtils.java:981` |
| `DateTimeUtils.appendTime()` | `org/h2/util/DateTimeUtils.java:1003` |
| `DateTimeTemplate.format()` | `org/h2/util/DateTimeTemplate.java:178` |
| `DateTimeTemplate.of()` | `org/h2/util/DateTimeTemplate.java:430` |
| `DateTimeTemplate.parse()` | `org/h2/util/DateTimeTemplate.java:183` |
| `IntervalUtils.appendInterval()` | `org/h2/util/IntervalUtils.java:402` |
| `IntervalUtils.daysFromInterval()` | `org/h2/util/IntervalUtils.java:724` |
| `IntervalUtils.hoursFromInterval()` | `org/h2/util/IntervalUtils.java:753` |
| `IntervalUtils.intervalFromAbsolute()` | `org/h2/util/IntervalUtils.java:540` |
| `Utils.callMethod()` | `org/h2/util/Utils.java:465` |
| `Utils.callStaticMethod()` | `org/h2/util/Utils.java:446` |
| `Utils.cloneByteArray()` | `org/h2/util/Utils.java:218` |
| `Utils.collectGarbage()` | `org/h2/util/Utils.java:289` |
| `JdbcUtils.addClassFactory()` | `org/h2/util/JdbcUtils.java:114` |

## 11.4 阅读路径

读 `org.h2.util` 的 48 个文件时，先看骨架类，再沿 `org.h2.value` 方向下钻。

1. 先读 `org.h2.util` 的 package-info 与 `StringUtils`，建立第11章的职责边界。
2. 再读 `StringUtils` 的 55 个公开入口，确认它对 `org.h2.value` 的调用方向与加锁方式。
3. 最后读 `org.h2.store`（本章最小包，2,712 行）的实现，关注容量与失败路径。

跨章衔接请对照第12章《并发控制》。

## 11.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.util` | `org.h2.value`, `org.h2.engine`, `org.h2.message`, `org.h2.api` |
| `org.h2.store` | `org.h2.engine`, `org.h2.util`, `org.h2.message`, `org.h2.value` |

## 11.6 设计权衡

- `org.h2.util` 用 48 个文件换到 14,460 行实现，平均每文件 301 行，其中 `StringUtils` 独占 1,415 行、55 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.store`（2,712 行）与 `org.h2.util` 的职责差是本章最值得记的一条边界。

## 11.7 常见误区

- 把 `org.h2.util` 的 14,460 行当作复杂度上限：`StringUtils` 之外的 47 个文件多为类型族与样板。
- 只看 `StringUtils` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.util` 与 `org.h2.store` 视为可互换：前者 48 文件、后者 17 文件，扩展点分布完全不同。

## 11.8 深读要点

规模信号：`org.h2.util` 占本章 84% 的实现行数，改动风险最高。
耦合信号：`org.h2.util` 依赖 8 个 `org.h2` 包，其中 `org.h2.value` 出现最频繁。
入口信号：`StringUtils` 的公开方法 55 个，读它等于读本章的主干。

## 11.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Aggregate**：详见[术语表](back/glossary.md)对应条目。
- **ISODEBUG**：详见[术语表](back/glossary.md)对应条目。
- **Maven**：详见[术语表](back/glossary.md)对应条目。
- **MVStoreTool**：详见[术语表](back/glossary.md)对应条目。
- **Query**：详见[术语表](back/glossary.md)对应条目。
- **Select**：详见[术语表](back/glossary.md)对应条目。
- **SmallLRUCache**：详见[术语表](back/glossary.md)对应条目。

## 11.9 知识点清单

1. `org.h2.util` 的 `StringUtils`：1,415 行、55 个公开方法，职责按方法名归纳
2. `org.h2.util` 的 `DateTimeUtils`：1,171 行、42 个公开方法，职责按方法名归纳
3. `org.h2.store` 的 `FileLock`：514 行、8 个公开方法，职责按方法名归纳
4. `org.h2.store` 的 `FileStore`：513 行、22 个公开方法，职责按方法名归纳

## 11.9 本章小结

- 本章覆盖 2 个包、17,172 行。
- 关键入口与源码坐标见 §11.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 11.10 延伸思考

**1. 🟢★ 指出 `org.h2.util` 中 `StringUtils` 与 `DateTimeUtils` 的分工差异，并给出调用方向。**

> 提示：第11章 §11.2 的表格给出 `StringUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

**2. 🔵★★ 围绕 `org.h2.store` 的 `FileLock`，说明它为什么需要独立成类型而不是并入 `FileStore`。**

> 提示：第11章 §11.2 的表格给出 `FileLock` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

**3. 🟠★★★ 以 `org.h2.util` 的 `StringUtils` 为入口，画出一次完整调用经过的包。**

> 提示：第11章 §11.2 的表格给出 `StringUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.store` 的一个类型，你保留 `FileLock` 还是 `FileStore`？说明代价。**

> 提示：第11章 §11.2 的表格给出 `FileLock` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§11.2 核心类型

## 11.11 本章视角：演化与版本

- 以「演化与版本」看 `org.h2.util`：48 个文件、14,460 行，本章只展开与演化与版本相关的入口。
- 对照 `org.h2.store`（2,712 行）：两者的演化与版本策略不同，差异落在 `StringUtils` 的 55 个公开方法里。
- 若演化与版本假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.value` 进入。

## 11.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.util` | `org.h2.value` | 35 |
| `org.h2.util` | `org.h2.engine` | 18 |
| `org.h2.util` | `org.h2.message` | 16 |
| `org.h2.store` | `org.h2.engine` | 16 |
| `org.h2.store` | `org.h2.util` | 14 |
| `org.h2.store` | `org.h2.message` | 11 |

## 11.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.util` 与 `org.h2.store` 之间的调用方向？
- `StringUtils` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.util` 的调用链讲到落盘或返回？
- `org.h2.util` 与 `org.h2.store` 若合并，会丢掉哪个扩展点？
- `org.h2.util` 的注释与实现若不一致，你信哪一边，为什么？

## 11.12 延展阅读

- 详见第12章《并发控制》。

# 第12章 并发控制

## 12.1 模块版图

本章覆盖 1 个包、1,334 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.store.fs` | 7 | 1,334 | A file system abstraction. |

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
| `FileUtils.canWrite()` | `org/h2/store/fs/FileUtils.java:317` |
| `FileUtils.createDirectories()` | `org/h2/store/fs/FileUtils.java:372` |
| `FilePath.canWrite()` | `org/h2/store/fs/FilePath.java:201` |
| `FilePath.createDirectory()` | `org/h2/store/fs/FilePath.java:206` |
| `FilePathWrapper.canWrite()` | `org/h2/store/fs/FilePathWrapper.java:72` |
| `FilePathWrapper.createDirectory()` | `org/h2/store/fs/FilePathWrapper.java:77` |

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

**`FileUtils`**（`org.h2.store.fs`，477 行，29 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 36%，包级依赖 2 个。

**`FilePath`**（`org.h2.store.fs`，353 行，28 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 26%，包级依赖 2 个。

**`FilePathWrapper`**（`org.h2.store.fs`，171 行，22 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 13%，包级依赖 2 个。

**`FakeFileChannel`**（`org.h2.store.fs`，112 行，16 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 8%，包级依赖 2 个。

**`FileBase`**（`org.h2.store.fs`，92 行，10 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 7%，包级依赖 2 个。

**`FileBaseDefault`**（`org.h2.store.fs`，69 行，5 个公开方法）

- 职责：按方法名与调用点归纳
- 规模：占该包 5%，包级依赖 2 个。

## 12.3.2 源码坐标明细

本章主责包中 24 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `FileUtils.canWrite()` | `org/h2/store/fs/FileUtils.java:317` |
| `FileUtils.createDirectories()` | `org/h2/store/fs/FileUtils.java:372` |
| `FileUtils.createDirectory()` | `org/h2/store/fs/FileUtils.java:84` |
| `FileUtils.createFile()` | `org/h2/store/fs/FileUtils.java:96` |
| `FilePath.canWrite()` | `org/h2/store/fs/FilePath.java:201` |
| `FilePath.createDirectory()` | `org/h2/store/fs/FilePath.java:206` |
| `FilePath.createFile()` | `org/h2/store/fs/FilePath.java:132` |
| `FilePath.createTempFile()` | `org/h2/store/fs/FilePath.java:284` |
| `FilePathWrapper.canWrite()` | `org/h2/store/fs/FilePathWrapper.java:72` |
| `FilePathWrapper.createDirectory()` | `org/h2/store/fs/FilePathWrapper.java:77` |
| `FilePathWrapper.createFile()` | `org/h2/store/fs/FilePathWrapper.java:82` |
| `FilePathWrapper.createTempFile()` | `org/h2/store/fs/FilePathWrapper.java:166` |
| `FakeFileChannel.force()` | `org/h2/store/fs/FakeFileChannel.java:109` |
| `FakeFileChannel.lock()` | `org/h2/store/fs/FakeFileChannel.java:34` |
| `FakeFileChannel.map()` | `org/h2/store/fs/FakeFileChannel.java:39` |
| `FakeFileChannel.position()` | `org/h2/store/fs/FakeFileChannel.java:44` |
| `FileBase.force()` | `org/h2/store/fs/FileBase.java:42` |
| `FileBase.lock()` | `org/h2/store/fs/FileBase.java:52` |
| `FileBase.map()` | `org/h2/store/fs/FileBase.java:58` |
| `FileBase.read()` | `org/h2/store/fs/FileBase.java:22` |

## 12.4 阅读路径

读 `org.h2.store.fs` 的 7 个文件时，先看骨架类，再沿 `org.h2.util` 方向下钻。

1. 先读 `org.h2.store.fs` 的 package-info 与 `FileUtils`，建立第12章的职责边界。
2. 再读 `FileUtils` 的 29 个公开入口，确认它对 `org.h2.util` 的调用方向与加锁方式。
3. 最后读 `org.h2.store.fs`（本章最小包，1,334 行）的实现，关注容量与失败路径。

跨章衔接请对照第11章《持久化》。

## 12.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.store.fs` | `org.h2.util`, `org.h2.engine` |

## 12.6 设计权衡

- `org.h2.store.fs` 用 7 个文件换到 1,334 行实现，平均每文件 190 行，其中 `FileUtils` 独占 477 行、29 个公开方法。
- 该包对外声明了 2 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.store.fs`（1,334 行）与 `org.h2.store.fs` 的职责差是本章最值得记的一条边界。

## 12.7 常见误区

- 把 `org.h2.store.fs` 的 1,334 行当作复杂度上限：`FileUtils` 之外的 6 个文件多为类型族与样板。
- 只看 `FileUtils` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.store.fs` 与 `org.h2.store.fs` 视为可互换：前者 7 文件、后者 7 文件，扩展点分布完全不同。

## 12.8 深读要点

规模信号：`org.h2.store.fs` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.store.fs` 依赖 2 个 `org.h2` 包，其中 `org.h2.util` 出现最频繁。
入口信号：`FileUtils` 的公开方法 29 个，读它等于读本章的主干。

## 12.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Bloom 过滤**：详见[术语表](back/glossary.md)对应条目。
- **Single Writer**：详见[术语表](back/glossary.md)对应条目。
- **TransactionMap**：详见[术语表](back/glossary.md)对应条目。
- **Write Amplification**：详见[术语表](back/glossary.md)对应条目。

## 12.9 知识点清单

1. `org.h2.store.fs` 的 `FileUtils`：477 行、29 个公开方法，职责按方法名归纳
2. `org.h2.store.fs` 的 `FilePath`：353 行、28 个公开方法，职责按方法名归纳

## 12.9 本章小结

- 本章覆盖 1 个包、1,334 行。
- 关键入口与源码坐标见 §12.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 12.10 延伸思考

**1. 🟢★ 指出 `org.h2.store.fs` 中 `FileUtils` 与 `FilePath` 的分工差异，并给出调用方向。**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

**2. 🔵★★ 围绕 `org.h2.store.fs` 的 `FileUtils`，说明它为什么需要独立成类型而不是并入 `FilePath`。**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

**3. 🟠★★★ 以 `org.h2.store.fs` 的 `FileUtils` 为入口，画出一次完整调用经过的包。**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.store.fs` 的一个类型，你保留 `FileUtils` 还是 `FilePath`？说明代价。**

> 提示：第12章 §12.2 的表格给出 `FileUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§12.2 核心类型

## 12.11 本章视角：性能与规模

- 以「性能与规模」看 `org.h2.store.fs`：7 个文件、1,334 行，本章只展开与性能与规模相关的入口。
- 对照 `org.h2.store.fs`（1,334 行）：两者的性能与规模策略不同，差异落在 `FileUtils` 的 29 个公开方法里。
- 若性能与规模假设被打破（2 个依赖变化），最先受影响的调用链从 `org.h2.util` 进入。

## 12.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.store.fs` | `org.h2.util` | 1 |
| `org.h2.store.fs` | `org.h2.engine` | 1 |

## 12.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.store.fs` 与 `org.h2.store.fs` 之间的调用方向？
- `FileUtils` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.store.fs` 的调用链讲到落盘或返回？
- `org.h2.store.fs` 与 `org.h2.store.fs` 若合并，会丢掉哪个扩展点？
- `org.h2.store.fs` 的注释与实现若不一致，你信哪一边，为什么？

## 12.12 跨章索引

本章引用但不展开的包，按下面这张表跳到主责章节阅读。

| 包 | 主责章节 |
| --- | --- |
| `org.h2.store.fs` | 第11章《持久化》 |

## 12.12 延展阅读

- 详见第11章《持久化》。
