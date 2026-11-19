# 第4章 模块边界与依赖治理

> **本章导读**：本章由源码清单汇总而成，覆盖 4 个包、44,070 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 4.1 模块版图

本章覆盖 2 个包、29,519 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.command` | 11 | 15,014 | This package contains the parser and the base classes for prepared SQL statements. |
| `org.h2.mvstore` | 20 | 14,505 | A persistent storage for tree maps. |

## 4.2 核心类型

在 `org.h2.command` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 4.2.1 `org.h2.command`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Parser` | 9,470 | 9 | （无类注释，按方法名归纳） |
| `Tokenizer` | 1,522 | 0 | （无类注释，按方法名归纳） |
| `ParserBase` | 771 | 8 | （无类注释，按方法名归纳） |
| `Token` | 758 | 5 | （无类注释，按方法名归纳） |

### 4.2.2 `org.h2.mvstore`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileStore` | 2,386 | 64 | （无类注释，按方法名归纳） |
| `MVStore` | 2,215 | 85 | （无类注释，按方法名归纳） |
| `MVMap` | 2,181 | 102 | （无类注释，按方法名归纳） |
| `Page` | 1,779 | 77 | （无类注释，按方法名归纳） |

## 4.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Parser.newPrimaryKeyConstraintCommand()` | `org/h2/command/Parser.java:9178` |
| `Parser.parseDomainConstraintExpression()` | `org/h2/command/Parser.java:9446` |
| `ParserBase.formatNonKeywords()` | `org/h2/command/ParserBase.java:93` |
| `ParserBase.getLastParseIndex()` | `org/h2/command/ParserBase.java:743` |
| `FileStore.accountForRemovedPage()` | `org/h2/mvstore/FileStore.java:2178` |
| `FileStore.backup()` | `org/h2/mvstore/FileStore.java:1432` |
| `MVStore.adoptFileStore()` | `org/h2/mvstore/MVStore.java:2183` |
| `MVStore.autoCommitBufferSize()` | `org/h2/mvstore/MVStore.java:2003` |
| `MVMap.append()` | `org/h2/mvstore/MVMap.java:1364` |
| `MVMap.ceilingKey()` | `org/h2/mvstore/MVMap.java:325` |

## 4.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Parser` | `org.h2.command` | 9,470 | 9 |
| `Tokenizer` | `org.h2.command` | 1,522 | 0 |
| `ParserBase` | `org.h2.command` | 771 | 8 |
| `Token` | `org.h2.command` | 758 | 5 |
| `CommandInterface` | `org.h2.command` | 654 | 0 |
| `FileStore` | `org.h2.mvstore` | 2,386 | 64 |
| `MVStore` | `org.h2.mvstore` | 2,215 | 85 |
| `MVMap` | `org.h2.mvstore` | 2,181 | 102 |
| `Page` | `org.h2.mvstore` | 1,779 | 77 |
| `DataUtils` | `org.h2.mvstore` | 1,185 | 45 |

## 4.4 阅读路径

读 `org.h2.command` 的 11 个文件时，先看骨架类，再沿 `org.h2.util.ParserUtil` 方向下钻。

1. 先读 `org.h2.command` 的 package-info 与 `Parser`，建立第4章的职责边界。
2. 再读 `Parser` 的 9 个公开入口，确认它对 `org.h2.util.ParserUtil` 的调用方向与加锁方式。
3. 最后读 `org.h2.mvstore`（本章最小包，14,505 行）的实现，关注容量与失败路径。

跨章衔接请对照第5章《进程内数据流》。

## 4.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.command` | `org.h2.util.ParserUtil`, `org.h2.expression.function`, `org.h2.value`, `org.h2.expression` |
| `org.h2.mvstore` | `org.h2.util`, `org.h2.compress`, `org.h2.store.fs`, `org.h2.store.fs.encrypt` |

## 4.6 设计权衡

- `org.h2.command` 用 11 个文件换到 15,014 行实现，平均每文件 1,364 行，其中 `Parser` 独占 9,470 行、9 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.mvstore`（14,505 行）与 `org.h2.command` 的职责差是本章最值得记的一条边界。

## 4.7 常见误区

- 把 `org.h2.command` 的 15,014 行当作复杂度上限：`Parser` 之外的 10 个文件多为类型族与样板。
- 只看 `Parser` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.command` 与 `org.h2.mvstore` 视为可互换：前者 11 文件、后者 20 文件，扩展点分布完全不同。

## 4.8 深读要点

规模信号：`org.h2.command` 占本章 51% 的实现行数，改动风险最高。
耦合信号：`org.h2.command` 依赖 8 个 `org.h2` 包，其中 `org.h2.util.ParserUtil` 出现最频繁。
入口信号：`Parser` 的公开方法 9 个，读它等于读本章的主干。

## 4.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **MVStore**：详见[术语表](back/glossary.md)对应条目。
- **Parser**：详见[术语表](back/glossary.md)对应条目。

## 4.9 知识点清单

1. `org.h2.command` 的 `Parser`：9,470 行、9 个公开方法，职责按方法名归纳
2. `org.h2.command` 的 `Tokenizer`：1,522 行、0 个公开方法，职责按方法名归纳
3. `org.h2.mvstore` 的 `FileStore`：2,386 行、64 个公开方法，职责按方法名归纳
4. `org.h2.mvstore` 的 `MVStore`：2,215 行、85 个公开方法，职责按方法名归纳

## 4.9 本章小结

- 本章覆盖 2 个包、29,519 行。
- 关键入口与源码坐标见 §4.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 4.10 延伸思考

**1. 🟢★ 指出 `org.h2.command` 中 `Parser` 与 `Tokenizer` 的分工差异，并给出调用方向。**

> 提示：第4章 §4.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

**2. 🔵★★ 围绕 `org.h2.mvstore` 的 `FileStore`，说明它为什么需要独立成类型而不是并入 `MVStore`。**

> 提示：第4章 §4.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

**3. 🟠★★★ 以 `org.h2.command` 的 `Parser` 为入口，画出一次完整调用经过的包。**

> 提示：第4章 §4.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.mvstore` 的一个类型，你保留 `FileStore` 还是 `MVStore`？说明代价。**

> 提示：第4章 §4.2 的表格给出 `FileStore` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

## 4.11 本章视角：性能与规模

- 以「性能与规模」看 `org.h2.command`：11 个文件、15,014 行，本章只展开与性能与规模相关的入口。
- 对照 `org.h2.mvstore`（14,505 行）：两者的性能与规模策略不同，差异落在 `Parser` 的 9 个公开方法里。
- 若性能与规模假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.util.ParserUtil` 进入。

## 4.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.command` | `org.h2.util.ParserUtil` | 188 |
| `org.h2.command` | `org.h2.expression.function` | 44 |
| `org.h2.command` | `org.h2.value` | 41 |
| `org.h2.mvstore` | `org.h2.util` | 10 |
| `org.h2.mvstore` | `org.h2.compress` | 7 |
| `org.h2.mvstore` | `org.h2.store.fs` | 5 |

## 4.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.command` 与 `org.h2.mvstore` 之间的调用方向？
- `Parser` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.command` 的调用链讲到落盘或返回？
- `org.h2.command` 与 `org.h2.mvstore` 若合并，会丢掉哪个扩展点？
- `org.h2.command` 的注释与实现若不一致，你信哪一边，为什么？

## 4.12 延展阅读

- 详见第5章《进程内数据流》。

# 第5章 进程内数据流

## 5.1 模块版图

本章覆盖 2 个包、14,551 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.engine` | 28 | 11,839 | Contains high level classes of the database and classes that don't fit in another sub-package. |
| `org.h2.store` | 17 | 2,712 | Storage abstractions and helper classes. |

## 5.2 核心类型

在 `org.h2.engine` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 5.2.1 `org.h2.engine`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Database` | 2,566 | 152 | （无类注释，按方法名归纳） |
| `SessionLocal` | 2,156 | 135 | （无类注释，按方法名归纳） |
| `SessionRemote` | 1,068 | 53 | （无类注释，按方法名归纳） |
| `Mode` | 776 | 5 | （无类注释，按方法名归纳） |

### 5.2.2 `org.h2.store`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `FileLock` | 514 | 8 | （无类注释，按方法名归纳） |
| `FileStore` | 513 | 22 | （无类注释，按方法名归纳） |
| `Data` | 220 | 13 | （无类注释，按方法名归纳） |
| `RecoverTester` | 176 | 3 | （无类注释，按方法名归纳） |

## 5.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Database.addDatabaseObject()` | `org/h2/engine/Database.java:948` |
| `Database.addSchemaObject()` | `org/h2/engine/Database.java:923` |
| `SessionLocal.addLocalTempTable()` | `org/h2/engine/SessionLocal.java:397` |
| `SessionLocal.addLocalTempTableConstraint()` | `org/h2/engine/SessionLocal.java:510` |
| `SessionRemote.addTemporaryLob()` | `org/h2/engine/SessionRemote.java:819` |
| `SessionRemote.autoCommitIfCluster()` | `org/h2/engine/SessionRemote.java:296` |
| `FileLock.getFileLockMethod()` | `org/h2/store/FileLock.java:458` |
| `FileLock.getUniqueId()` | `org/h2/store/FileLock.java:472` |
| `FileStore.autoDelete()` | `org/h2/store/FileStore.java:429` |
| `FileStore.close()` | `org/h2/store/FileStore.java:221` |
| `Data.checkCapacity()` | `org/h2/store/Data.java:171` |
| `Data.copyString()` | `org/h2/store/Data.java:204` |

## 5.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Database` | `org.h2.engine` | 2,566 | 152 |
| `SessionLocal` | `org.h2.engine` | 2,156 | 135 |
| `SessionRemote` | `org.h2.engine` | 1,068 | 53 |
| `Mode` | `org.h2.engine` | 776 | 5 |
| `ConnectionInfo` | `org.h2.engine` | 766 | 25 |
| `FileLock` | `org.h2.store` | 514 | 8 |
| `FileStore` | `org.h2.store` | 513 | 22 |
| `Data` | `org.h2.store` | 220 | 13 |
| `RecoverTester` | `org.h2.store` | 176 | 3 |
| `FileStoreInputStream` | `org.h2.store` | 155 | 5 |

## 5.4 阅读路径

读 `org.h2.engine` 的 28 个文件时，先看骨架类，再沿 `org.h2.util` 方向下钻。

1. 先读 `org.h2.engine` 的 package-info 与 `Database`，建立第5章的职责边界。
2. 再读 `Database` 的 152 个公开入口，确认它对 `org.h2.util` 的调用方向与加锁方式。
3. 最后读 `org.h2.store`（本章最小包，2,712 行）的实现，关注容量与失败路径。

跨章衔接请对照第4章《模块边界与依赖治理》。

## 5.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.engine` | `org.h2.util`, `org.h2.message`, `org.h2.value`, `org.h2.api` |
| `org.h2.store` | `org.h2.engine`, `org.h2.util`, `org.h2.message`, `org.h2.value` |

## 5.6 设计权衡

- `org.h2.engine` 用 28 个文件换到 11,839 行实现，平均每文件 422 行，其中 `Database` 独占 2,566 行、152 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.store`（2,712 行）与 `org.h2.engine` 的职责差是本章最值得记的一条边界。

## 5.7 常见误区

- 把 `org.h2.engine` 的 11,839 行当作复杂度上限：`Database` 之外的 27 个文件多为类型族与样板。
- 只看 `Database` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.engine` 与 `org.h2.store` 视为可互换：前者 28 文件、后者 17 文件，扩展点分布完全不同。

## 5.8 深读要点

规模信号：`org.h2.engine` 占本章 81% 的实现行数，改动风险最高。
耦合信号：`org.h2.engine` 依赖 8 个 `org.h2` 包，其中 `org.h2.util` 出现最频繁。
入口信号：`Database` 的公开方法 152 个，读它等于读本章的主干。

## 5.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Database**：详见[术语表](back/glossary.md)对应条目。
- **Engine**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。

## 5.9 知识点清单

1. `org.h2.engine` 的 `Database`：2,566 行、152 个公开方法，职责按方法名归纳
2. `org.h2.engine` 的 `SessionLocal`：2,156 行、135 个公开方法，职责按方法名归纳
3. `org.h2.store` 的 `FileLock`：514 行、8 个公开方法，职责按方法名归纳
4. `org.h2.store` 的 `FileStore`：513 行、22 个公开方法，职责按方法名归纳

## 5.9 本章小结

- 本章覆盖 2 个包、14,551 行。
- 关键入口与源码坐标见 §5.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 5.10 延伸思考

**1. 🟢★ 指出 `org.h2.engine` 中 `Database` 与 `SessionLocal` 的分工差异，并给出调用方向。**

> 提示：第5章 §5.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

**2. 🔵★★ 围绕 `org.h2.store` 的 `FileLock`，说明它为什么需要独立成类型而不是并入 `FileStore`。**

> 提示：第5章 §5.2 的表格给出 `FileLock` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

**3. 🟠★★★ 以 `org.h2.engine` 的 `Database` 为入口，画出一次完整调用经过的包。**

> 提示：第5章 §5.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.store` 的一个类型，你保留 `FileLock` 还是 `FileStore`？说明代价。**

> 提示：第5章 §5.2 的表格给出 `FileLock` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

## 5.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.engine`：28 个文件、11,839 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.store`（2,712 行）：两者的并发与一致性策略不同，差异落在 `Database` 的 152 个公开方法里。
- 若并发与一致性假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.util` 进入。

## 5.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.engine` | `org.h2.util` | 55 |
| `org.h2.engine` | `org.h2.message` | 33 |
| `org.h2.engine` | `org.h2.value` | 26 |
| `org.h2.store` | `org.h2.engine` | 16 |
| `org.h2.store` | `org.h2.util` | 14 |
| `org.h2.store` | `org.h2.message` | 11 |

## 5.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.engine` 与 `org.h2.store` 之间的调用方向？
- `Database` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.engine` 的调用链讲到落盘或返回？
- `org.h2.engine` 与 `org.h2.store` 若合并，会丢掉哪个扩展点？
- `org.h2.engine` 的注释与实现若不一致，你信哪一边，为什么？

## 5.12 延展阅读

- 详见第4章《模块边界与依赖治理》。
