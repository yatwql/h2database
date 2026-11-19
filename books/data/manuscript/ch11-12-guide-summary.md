# 第13章 二次开发指南

> **本章导读**：本章由源码清单汇总而成，覆盖 2 个包、28,213 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 13.1 模块版图

本章覆盖 1 个包、17,330 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.jdbc` | 28 | 17,330 | （无包注释，按主类型归纳） |

## 13.2 核心类型

在 `org.h2.jdbc` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 13.2.1 `org.h2.jdbc`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `JdbcResultSet` | 4,291 | 199 | （无类注释，按方法名归纳） |
| `JdbcDatabaseMetaData` | 2,756 | 177 | （无类注释，按方法名归纳） |
| `JdbcConnection` | 1,930 | 62 | （无类注释，按方法名归纳） |
| `JdbcCallableStatement` | 1,863 | 117 | （无类注释，按方法名归纳） |

## 13.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `JdbcResultSet.absolute()` | `h2/src/main/org/h2/jdbc/JdbcResultSet.java:3173` |
| `JdbcResultSet.afterLast()` | `h2/src/main/org/h2/jdbc/JdbcResultSet.java:3105` |
| `JdbcDatabaseMetaData.allProceduresAreCallable()` | `h2/src/main/org/h2/jdbc/JdbcDatabaseMetaData.java:305` |
| `JdbcDatabaseMetaData.allTablesAreSelectable()` | `h2/src/main/org/h2/jdbc/JdbcDatabaseMetaData.java:316` |
| `JdbcConnection.abort()` | `h2/src/main/org/h2/jdbc/JdbcConnection.java:1832` |
| `JdbcConnection.clearWarnings()` | `h2/src/main/org/h2/jdbc/JdbcConnection.java:655` |

## 13.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `JdbcResultSet` | `org.h2.jdbc` | 4,291 | 199 |
| `JdbcDatabaseMetaData` | `org.h2.jdbc` | 2,756 | 177 |
| `JdbcConnection` | `org.h2.jdbc` | 1,930 | 62 |
| `JdbcCallableStatement` | `org.h2.jdbc` | 1,863 | 117 |
| `JdbcPreparedStatement` | `org.h2.jdbc` | 1,629 | 65 |

## 13.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 13.3.2.1 `JdbcResultSet`

`JdbcResultSet` 位于 `org.h2.jdbc`，4,291 行、199 个公开方法。它占该包实现的 25%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（2 个），再决定是否顺带读同包的相邻类型。

### 13.3.2.2 `JdbcDatabaseMetaData`

`JdbcDatabaseMetaData` 位于 `org.h2.jdbc`，2,756 行、177 个公开方法。它占该包实现的 16%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（2 个），再决定是否顺带读同包的相邻类型。

### 13.3.2.3 `JdbcConnection`

`JdbcConnection` 位于 `org.h2.jdbc`，1,930 行、62 个公开方法。它占该包实现的 11%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（2 个），再决定是否顺带读同包的相邻类型。

### 13.3.2.4 `JdbcCallableStatement`

`JdbcCallableStatement` 位于 `org.h2.jdbc`，1,863 行、117 个公开方法。它占该包实现的 11%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（2 个），再决定是否顺带读同包的相邻类型。

### 13.3.2.5 `JdbcPreparedStatement`

`JdbcPreparedStatement` 位于 `org.h2.jdbc`，1,629 行、65 个公开方法。它占该包实现的 9%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（2 个），再决定是否顺带读同包的相邻类型。

### 13.3.2.6 `JdbcStatement`

`JdbcStatement` 位于 `org.h2.jdbc`，1,502 行、56 个公开方法。它占该包实现的 9%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（2 个），再决定是否顺带读同包的相邻类型。

## 13.3.2 源码坐标明细

本章主责包中 36 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `JdbcResultSet.absolute()` | `h2/src/main/org/h2/jdbc/JdbcResultSet.java:3173` |
| `JdbcResultSet.afterLast()` | `h2/src/main/org/h2/jdbc/JdbcResultSet.java:3105` |
| `JdbcResultSet.beforeFirst()` | `h2/src/main/org/h2/jdbc/JdbcResultSet.java:3086` |
| `JdbcResultSet.cancelRowUpdates()` | `h2/src/main/org/h2/jdbc/JdbcResultSet.java:3432` |
| `JdbcResultSet.clearWarnings()` | `h2/src/main/org/h2/jdbc/JdbcResultSet.java:260` |
| `JdbcResultSet.close()` | `h2/src/main/org/h2/jdbc/JdbcResultSet.java:188` |
| `JdbcDatabaseMetaData.allProceduresAreCallable()` | `h2/src/main/org/h2/jdbc/JdbcDatabaseMetaData.java:305` |
| `JdbcDatabaseMetaData.allTablesAreSelectable()` | `h2/src/main/org/h2/jdbc/JdbcDatabaseMetaData.java:316` |
| `JdbcDatabaseMetaData.autoCommitFailureClosesAllResultSets()` | `h2/src/main/org/h2/jdbc/JdbcDatabaseMetaData.java:2598` |
| `JdbcDatabaseMetaData.dataDefinitionCausesTransactionCommit()` | `h2/src/main/org/h2/jdbc/JdbcDatabaseMetaData.java:1814` |
| `JdbcDatabaseMetaData.dataDefinitionIgnoredInTransactions()` | `h2/src/main/org/h2/jdbc/JdbcDatabaseMetaData.java:1825` |
| `JdbcDatabaseMetaData.deletesAreDetected()` | `h2/src/main/org/h2/jdbc/JdbcDatabaseMetaData.java:1950` |
| `JdbcConnection.abort()` | `h2/src/main/org/h2/jdbc/JdbcConnection.java:1832` |
| `JdbcConnection.clearWarnings()` | `h2/src/main/org/h2/jdbc/JdbcConnection.java:655` |
| `JdbcConnection.close()` | `h2/src/main/org/h2/jdbc/JdbcConnection.java:355` |
| `JdbcConnection.commit()` | `h2/src/main/org/h2/jdbc/JdbcConnection.java:480` |
| `JdbcConnection.createArrayOf()` | `h2/src/main/org/h2/jdbc/JdbcConnection.java:1521` |
| `JdbcConnection.createBlob()` | `h2/src/main/org/h2/jdbc/JdbcConnection.java:1468` |
| `JdbcCallableStatement.executeLargeUpdate()` | `h2/src/main/org/h2/jdbc/JdbcCallableStatement.java:119` |
| `JdbcCallableStatement.executeUpdate()` | `h2/src/main/org/h2/jdbc/JdbcCallableStatement.java:89` |

## 13.4 阅读路径

读 `org.h2.jdbc` 的 28 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.jdbc` 的 package-info 与 `JdbcResultSet`，建立第13章的职责边界。
2. 再读 `JdbcResultSet` 的 199 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.jdbc`（本章最小包，17,330 行）的实现，关注容量与失败路径。

跨章衔接请对照第14章《全书总结》。

## 13.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.jdbc` | `org.h2`, `org.h2.engine` |

## 13.6 设计权衡

`org.h2.jdbc` 有 28 个文件、17,330 行。平均每文件 618 行。

其中 `JdbcResultSet` 独占 4,291 行，199 个公开方法。规模集中，风险也集中。

它对外声明 2 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.jdbc`（17,330 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 13.7 常见误区

把 `org.h2.jdbc` 的行数当作复杂度上限是误读。`JdbcResultSet` 之外还有 27 个文件，其中多为类型族与样板。

只读 `JdbcResultSet` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.jdbc` 与 `org.h2.jdbc` 不能互换。前者 28 个文件，后者 28 个文件，扩展点分布完全不同。

## 13.8 深读要点

规模信号：`org.h2.jdbc` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.jdbc` 依赖 2 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`JdbcResultSet` 的公开方法 199 个，读它等于读本章的主干。

## 13.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **JDBC**：详见[术语表](back/glossary.md)对应条目。

## 13.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `JdbcResultSet` | `org.h2.jdbc` | 4,291 | 199 | 按方法名归纳 |
| `JdbcDatabaseMetaData` | `org.h2.jdbc` | 2,756 | 177 | 按方法名归纳 |

## 13.9 本章小结

- 本章覆盖 1 个包、17,330 行。
- 关键入口与源码坐标见 §13.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 13.10 延伸思考

**1. 🟢★ 说明 `JdbcResultSet` 与 `JdbcDatabaseMetaData` 的分工差异。给出调用方向。**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**2. 🔵★★ `JdbcResultSet` 为什么独立成类型，而不是并入 `JdbcDatabaseMetaData`？**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**3. 🟠★★★ 以 `JdbcResultSet` 为入口，画出一次完整调用经过的包。**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `JdbcResultSet` 还是 `JdbcDatabaseMetaData`？说明代价。**

> 提示：第13章 §13.2 的表格给出 `JdbcResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

## 13.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.jdbc`：28 个文件、17,330 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.jdbc`（17,330 行）：两者的并发与一致性策略不同，差异落在 `JdbcResultSet` 的 199 个公开方法里。
- 若并发与一致性假设被打破（2 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 13.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.jdbc` | `org.h2` | 169 |
| `org.h2.jdbc` | `org.h2.engine` | 1 |

## 13.11.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2.jdbc` 与 `org.h2.jdbc` 的调用方向？`JdbcResultSet` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.jdbc` 的调用链讲到落盘或返回，并说清 `org.h2.jdbc` 与 `org.h2.jdbc` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.jdbc` 的注释与实现对不上，你信哪一边，为什么？

## 13.12 延展阅读

- 详见第14章《全书总结》。

# 第14章 全书总结

## 14.1 模块版图

本章覆盖 1 个包、10,883 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.tools` | 24 | 10,883 | （无包注释，按主类型归纳） |

## 14.2 核心类型

在 `org.h2.tools` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 14.2.1 `org.h2.tools`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `SimpleResultSet` | 2,480 | 228 | （无类注释，按方法名归纳） |
| `Csv` | 986 | 33 | （无类注释，按方法名归纳） |
| `Recover` | 922 | 18 | （无类注释，按方法名归纳） |
| `Server` | 823 | 19 | （无类注释，按方法名归纳） |

## 14.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `SimpleResultSet.absolute()` | `h2/src/main/org/h2/tools/SimpleResultSet.java:2229` |
| `SimpleResultSet.addColumn()` | `h2/src/main/org/h2/tools/SimpleResultSet.java:100` |
| `Csv.close()` | `h2/src/main/org/h2/tools/Csv.java:639` |
| `Csv.getBinaryColumns()` | `h2/src/main/org/h2/tools/Csv.java:909` |
| `Recover.checkPowerOff()` | `h2/src/main/org/h2/tools/Recover.java:857` |
| `Recover.checkWritingAllowed()` | `h2/src/main/org/h2/tools/Recover.java:865` |

## 14.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `SimpleResultSet` | `org.h2.tools` | 2,480 | 228 |
| `Csv` | `org.h2.tools` | 986 | 33 |
| `Recover` | `org.h2.tools` | 922 | 18 |
| `Server` | `org.h2.tools` | 823 | 19 |
| `DirectRecover` | `org.h2.tools` | 767 | 11 |

## 14.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 14.3.2.1 `SimpleResultSet`

`SimpleResultSet` 位于 `org.h2.tools`，2,480 行、228 个公开方法。它占该包实现的 23%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 14.3.2.2 `Csv`

`Csv` 位于 `org.h2.tools`，986 行、33 个公开方法。它占该包实现的 9%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 14.3.2.3 `Recover`

`Recover` 位于 `org.h2.tools`，922 行、18 个公开方法。它占该包实现的 8%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 14.3.2.4 `Server`

`Server` 位于 `org.h2.tools`，823 行、19 个公开方法。它占该包实现的 8%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 14.3.2.5 `DirectRecover`

`DirectRecover` 位于 `org.h2.tools`，767 行、11 个公开方法。它占该包实现的 7%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 14.3.2.6 `Shell`

`Shell` 位于 `org.h2.tools`，639 行、7 个公开方法。它占该包实现的 6%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

## 14.3.2 源码坐标明细

本章主责包中 36 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `SimpleResultSet.absolute()` | `h2/src/main/org/h2/tools/SimpleResultSet.java:2229` |
| `SimpleResultSet.addColumn()` | `h2/src/main/org/h2/tools/SimpleResultSet.java:100` |
| `SimpleResultSet.addRow()` | `h2/src/main/org/h2/tools/SimpleResultSet.java:133` |
| `SimpleResultSet.afterLast()` | `h2/src/main/org/h2/tools/SimpleResultSet.java:2069` |
| `SimpleResultSet.beforeFirst()` | `h2/src/main/org/h2/tools/SimpleResultSet.java:242` |
| `SimpleResultSet.cancelRowUpdates()` | `h2/src/main/org/h2/tools/SimpleResultSet.java:2077` |
| `Csv.close()` | `h2/src/main/org/h2/tools/Csv.java:639` |
| `Csv.getBinaryColumns()` | `h2/src/main/org/h2/tools/Csv.java:909` |
| `Csv.getCaseSensitiveColumnNames()` | `h2/src/main/org/h2/tools/Csv.java:687` |
| `Csv.getEscapeCharacter()` | `h2/src/main/org/h2/tools/Csv.java:782` |
| `Csv.getFieldDelimiter()` | `h2/src/main/org/h2/tools/Csv.java:743` |
| `Csv.getFieldSeparatorRead()` | `h2/src/main/org/h2/tools/Csv.java:705` |
| `Recover.checkPowerOff()` | `h2/src/main/org/h2/tools/Recover.java:857` |
| `Recover.checkWritingAllowed()` | `h2/src/main/org/h2/tools/Recover.java:865` |
| `Recover.execute()` | `h2/src/main/org/h2/tools/Recover.java:239` |
| `Recover.getCompareMode()` | `h2/src/main/org/h2/tools/Recover.java:918` |
| `Recover.getDatabasePath()` | `h2/src/main/org/h2/tools/Recover.java:841` |
| `Recover.getLobFileListCache()` | `h2/src/main/org/h2/tools/Recover.java:889` |
| `Server.createPgServer()` | `h2/src/main/org/h2/tools/Server.java:539` |
| `Server.createTcpServer()` | `h2/src/main/org/h2/tools/Server.java:511` |

## 14.4 阅读路径

读 `org.h2.tools` 的 24 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.tools` 的 package-info 与 `SimpleResultSet`，建立第14章的职责边界。
2. 再读 `SimpleResultSet` 的 228 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.tools`（本章最小包，10,883 行）的实现，关注容量与失败路径。

跨章衔接请对照第13章《二次开发指南》。

## 14.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.tools` | `org.h2`, `org.h2.store`, `org.h2.mvstore`, `org.h2.server` |

## 14.6 设计权衡

`org.h2.tools` 有 24 个文件、10,883 行。平均每文件 453 行。

其中 `SimpleResultSet` 独占 2,480 行，228 个公开方法。规模集中，风险也集中。

它对外声明 8 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.tools`（10,883 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 14.7 常见误区

把 `org.h2.tools` 的行数当作复杂度上限是误读。`SimpleResultSet` 之外还有 23 个文件，其中多为类型族与样板。

只读 `SimpleResultSet` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.tools` 与 `org.h2.tools` 不能互换。前者 24 个文件，后者 24 个文件，扩展点分布完全不同。

## 14.8 深读要点

规模信号：`org.h2.tools` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.tools` 依赖 8 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`SimpleResultSet` 的公开方法 228 个，读它等于读本章的主干。

## 14.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。

## 14.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `SimpleResultSet` | `org.h2.tools` | 2,480 | 228 | 按方法名归纳 |
| `Csv` | `org.h2.tools` | 986 | 33 | 按方法名归纳 |

## 14.9 本章小结

- 本章覆盖 1 个包、10,883 行。
- 关键入口与源码坐标见 §14.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 14.10 延伸思考

**1. 🟢★ 说明 `SimpleResultSet` 与 `Csv` 的分工差异。给出调用方向。**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**2. 🔵★★ `SimpleResultSet` 为什么独立成类型，而不是并入 `Csv`？**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**3. 🟠★★★ 以 `SimpleResultSet` 为入口，画出一次完整调用经过的包。**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `SimpleResultSet` 还是 `Csv`？说明代价。**

> 提示：第14章 §14.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

## 14.11 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2.tools`：24 个文件、10,883 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2.tools`（10,883 行）：两者的扩展与兼容策略不同，差异落在 `SimpleResultSet` 的 228 个公开方法里。
- 若扩展与兼容假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 14.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.tools` | `org.h2` | 130 |
| `org.h2.tools` | `org.h2.store` | 10 |
| `org.h2.tools` | `org.h2.mvstore` | 7 |

## 14.11.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2.tools` 与 `org.h2.tools` 的调用方向？`SimpleResultSet` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.tools` 的调用链讲到落盘或返回，并说清 `org.h2.tools` 与 `org.h2.tools` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.tools` 的注释与实现对不上，你信哪一边，为什么？

## 14.12 跨章索引

本章引用但不展开的包，按下面这张表跳到主责章节阅读。

| 包 | 主责章节 |
| --- | --- |
| `org.h2.tools` | 第13章《二次开发指南》 |

## 14.12 延展阅读

- 详见第13章《二次开发指南》。
