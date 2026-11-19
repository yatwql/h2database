# 第1章 H2 总体架构

> **本章导读**：本章由源码清单汇总而成，覆盖 2 个包、12,067 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 1.1 模块版图

本章覆盖 1 个包、11,851 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.engine` | 29 | 11,851 | （无包注释，按主类型归纳） |

## 1.2 核心类型

在 `org.h2.engine` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 1.2.1 `org.h2.engine`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Database` | 2,566 | 152 | （无类注释，按方法名归纳） |
| `SessionLocal` | 2,156 | 135 | （无类注释，按方法名归纳） |
| `SessionRemote` | 1,068 | 53 | （无类注释，按方法名归纳） |
| `Mode` | 776 | 5 | （无类注释，按方法名归纳） |

## 1.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Database.addDatabaseObject()` | `h2/src/main/org/h2/engine/Database.java:948` |
| `Database.addSchemaObject()` | `h2/src/main/org/h2/engine/Database.java:923` |
| `SessionLocal.addLocalTempTable()` | `h2/src/main/org/h2/engine/SessionLocal.java:397` |
| `SessionLocal.addLocalTempTableConstraint()` | `h2/src/main/org/h2/engine/SessionLocal.java:510` |
| `SessionRemote.addTemporaryLob()` | `h2/src/main/org/h2/engine/SessionRemote.java:819` |
| `SessionRemote.autoCommitIfCluster()` | `h2/src/main/org/h2/engine/SessionRemote.java:296` |

## 1.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Database` | `org.h2.engine` | 2,566 | 152 |
| `SessionLocal` | `org.h2.engine` | 2,156 | 135 |
| `SessionRemote` | `org.h2.engine` | 1,068 | 53 |
| `Mode` | `org.h2.engine` | 776 | 5 |
| `ConnectionInfo` | `org.h2.engine` | 766 | 25 |

## 1.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 1.3.2.1 `Database`

`Database` 位于 `org.h2.engine`，2,566 行、152 个公开方法。它占该包实现的 22%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 1.3.2.2 `SessionLocal`

`SessionLocal` 位于 `org.h2.engine`，2,156 行、135 个公开方法。它占该包实现的 18%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 1.3.2.3 `SessionRemote`

`SessionRemote` 位于 `org.h2.engine`，1,068 行、53 个公开方法。它占该包实现的 9%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 1.3.2.4 `Mode`

`Mode` 位于 `org.h2.engine`，776 行、5 个公开方法。它占该包实现的 7%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 1.3.2.5 `ConnectionInfo`

`ConnectionInfo` 位于 `org.h2.engine`，766 行、25 个公开方法。它占该包实现的 6%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 1.3.2.6 `Constants`

`Constants` 位于 `org.h2.engine`，520 行、0 个公开方法。它占该包实现的 4%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

## 1.3.2 源码坐标明细

本章主责包中 29 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Database.addDatabaseObject()` | `h2/src/main/org/h2/engine/Database.java:948` |
| `Database.addSchemaObject()` | `h2/src/main/org/h2/engine/Database.java:923` |
| `Database.allocateObjectId()` | `h2/src/main/org/h2/engine/Database.java:1369` |
| `Database.checkPowerOff()` | `h2/src/main/org/h2/engine/Database.java:475` |
| `Database.checkWritingAllowed()` | `h2/src/main/org/h2/engine/Database.java:1824` |
| `Database.checkpoint()` | `h2/src/main/org/h2/engine/Database.java:2320` |
| `SessionLocal.addLocalTempTable()` | `h2/src/main/org/h2/engine/SessionLocal.java:397` |
| `SessionLocal.addLocalTempTableConstraint()` | `h2/src/main/org/h2/engine/SessionLocal.java:510` |
| `SessionLocal.addLocalTempTableIndex()` | `h2/src/main/org/h2/engine/SessionLocal.java:454` |
| `SessionLocal.addProcedure()` | `h2/src/main/org/h2/engine/SessionLocal.java:1424` |
| `SessionLocal.addSavepoint()` | `h2/src/main/org/h2/engine/SessionLocal.java:1140` |
| `SessionLocal.addTemporaryLob()` | `h2/src/main/org/h2/engine/SessionLocal.java:1768` |
| `SessionRemote.addTemporaryLob()` | `h2/src/main/org/h2/engine/SessionRemote.java:819` |
| `SessionRemote.autoCommitIfCluster()` | `h2/src/main/org/h2/engine/SessionRemote.java:296` |
| `SessionRemote.cancel()` | `h2/src/main/org/h2/engine/SessionRemote.java:197` |
| `SessionRemote.cancelStatement()` | `h2/src/main/org/h2/engine/SessionRemote.java:208` |
| `SessionRemote.checkClosed()` | `h2/src/main/org/h2/engine/SessionRemote.java:558` |
| `SessionRemote.checkPowerOff()` | `h2/src/main/org/h2/engine/SessionRemote.java:704` |
| `Mode.getEnum()` | `h2/src/main/org/h2/engine/Mode.java:766` |
| `Mode.getInstance()` | `h2/src/main/org/h2/engine/Mode.java:754` |

## 1.4 阅读路径

读 `org.h2.engine` 的 29 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.engine` 的 package-info 与 `Database`，建立第1章的职责边界。
2. 再读 `Database` 的 152 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.engine`（本章最小包，11,851 行）的实现，关注容量与失败路径。

跨章衔接请对照第2章《分层模块划分》。

## 1.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.engine` | `org.h2`, `org.h2.command`, `org.h2.mvstore`, `org.h2.jdbc` |

## 1.6 设计权衡

`org.h2.engine` 有 29 个文件、11,851 行。平均每文件 408 行。

其中 `Database` 独占 2,566 行，152 个公开方法。规模集中，风险也集中。

它对外声明 8 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.engine`（11,851 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 1.7 常见误区

把 `org.h2.engine` 的行数当作复杂度上限是误读。`Database` 之外还有 28 个文件，其中多为类型族与样板。

只读 `Database` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.engine` 与 `org.h2.engine` 不能互换。前者 29 个文件，后者 29 个文件，扩展点分布完全不同。

## 1.8 深读要点

规模信号：`org.h2.engine` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.engine` 依赖 8 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`Database` 的公开方法 152 个，读它等于读本章的主干。

## 1.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Engine**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **CAS (Compare-And-Swap)**：详见[术语表](back/glossary.md)对应条目。
- **CTE**：详见[术语表](back/glossary.md)对应条目。
- **JSON**：详见[术语表](back/glossary.md)对应条目。
- **LSM-Tree / Log-Structured Merge-Tree**：详见[术语表](back/glossary.md)对应条目。
- **PageStore**：详见[术语表](back/glossary.md)对应条目。

## 1.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `Database` | `org.h2.engine` | 2,566 | 152 | 按方法名归纳 |
| `SessionLocal` | `org.h2.engine` | 2,156 | 135 | 按方法名归纳 |

## 1.9 本章小结

- 本章覆盖 1 个包、11,851 行。
- 关键入口与源码坐标见 §1.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 1.10 延伸思考

**1. 🟢★ 说明 `Database` 与 `SessionLocal` 的分工差异。给出调用方向。**

> 提示：第1章 §1.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

**2. 🔵★★ `Database` 为什么独立成类型，而不是并入 `SessionLocal`？**

> 提示：第1章 §1.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

**3. 🟠★★★ 以 `Database` 为入口，画出一次完整调用经过的包。**

> 提示：第1章 §1.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `Database` 还是 `SessionLocal`？说明代价。**

> 提示：第1章 §1.2 的表格给出 `Database` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§1.2 核心类型

## 1.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.engine`：29 个文件、11,851 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.engine`（11,851 行）：两者的并发与一致性策略不同，差异落在 `Database` 的 152 个公开方法里。
- 若并发与一致性假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 1.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.engine` | `org.h2` | 213 |
| `org.h2.engine` | `org.h2.command` | 7 |
| `org.h2.engine` | `org.h2.mvstore` | 7 |

## 1.11.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2.engine` 与 `org.h2.engine` 的调用方向？`Database` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.engine` 的调用链讲到落盘或返回，并说清 `org.h2.engine` 与 `org.h2.engine` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.engine` 的注释与实现对不上，你信哪一边，为什么？

## 1.12 延展阅读

- 详见第2章《分层模块划分》。

# 第2章 分层模块划分

## 2.1 模块版图

本章覆盖 1 个包、216 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2` | 2 | 216 | （无包注释，按主类型归纳） |

## 2.2 核心类型

在 `org.h2` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 2.2.1 `org.h2`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Driver` | 205 | 11 | （无类注释，按方法名归纳） |

## 2.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Driver.acceptsURL()` | `h2/src/main/org/h2/Driver.java:76` |
| `Driver.connect()` | `h2/src/main/org/h2/Driver.java:55` |

## 2.3.1 公共类型清单

本章抽样类型按包分组，共 1 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Driver` | `org.h2` | 205 | 11 |

## 2.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 2.3.2.1 `Driver`

`Driver` 位于 `org.h2`，205 行、11 个公开方法。它占该包实现的 95%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（0 个），再决定是否顺带读同包的相邻类型。

## 2.3.2 源码坐标明细

本章主责包中 6 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Driver.acceptsURL()` | `h2/src/main/org/h2/Driver.java:76` |
| `Driver.connect()` | `h2/src/main/org/h2/Driver.java:55` |
| `Driver.getMajorVersion()` | `h2/src/main/org/h2/Driver.java:95` |
| `Driver.getMinorVersion()` | `h2/src/main/org/h2/Driver.java:106` |
| `Driver.getParentLogger()` | `h2/src/main/org/h2/Driver.java:138` |
| `Driver.getPropertyInfo()` | `h2/src/main/org/h2/Driver.java:119` |

## 2.4 阅读路径

读 `org.h2` 的 2 个文件时，先看骨架类，再沿 `—` 方向下钻。

1. 先读 `org.h2` 的 package-info 与 `Driver`，建立第2章的职责边界。
2. 再读 `Driver` 的 11 个公开入口，确认它对 `—` 的调用方向与加锁方式。
3. 最后读 `org.h2`（本章最小包，216 行）的实现，关注容量与失败路径。

跨章衔接请对照第1章《H2 总体架构》。

## 2.5 设计权衡

`org.h2` 有 2 个文件、216 行。平均每文件 108 行。

其中 `Driver` 独占 205 行，11 个公开方法。规模集中，风险也集中。

它对外声明 0 个 `org.h2` 依赖，最重的是 `—`。依赖越集中，越说明它是被复用的底座。

与 `org.h2`（216 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 2.6 常见误区

把 `org.h2` 的行数当作复杂度上限是误读。`Driver` 之外还有 1 个文件，其中多为类型族与样板。

只读 `Driver` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2` 与 `org.h2` 不能互换。前者 2 个文件，后者 2 个文件，扩展点分布完全不同。

## 2.7 深读要点

规模信号：`org.h2` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2` 依赖 0 个 `org.h2` 包，其中 `—` 出现最频繁。
入口信号：`Driver` 的公开方法 11 个，读它等于读本章的主干。

## 2.7 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **ConnectionInfo**：详见[术语表](back/glossary.md)对应条目。
- **Database**：详见[术语表](back/glossary.md)对应条目。
- **Driver**：详见[术语表](back/glossary.md)对应条目。
- **Engine**：详见[术语表](back/glossary.md)对应条目。
- **Expression**：详见[术语表](back/glossary.md)对应条目。
- **FilePathDisk**：详见[术语表](back/glossary.md)对应条目。
- **FilePathEncrypt**：详见[术语表](back/glossary.md)对应条目。

## 2.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `Driver` | `org.h2` | 205 | 11 | 按方法名归纳 |

## 2.8 本章小结

- 本章覆盖 1 个包、216 行。
- 关键入口与源码坐标见 §2.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 2.9 延伸思考

**1. 🟢★ 说明 `Driver` 与 `相邻工具类型` 的分工差异。给出调用方向。**

> 提示：第2章 §2.2 的表格给出 `Driver` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

**2. 🔵★★ `Driver` 为什么独立成类型，而不是并入 `相邻工具类型`？**

> 提示：第2章 §2.2 的表格给出 `Driver` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

**3. 🟠★★★ 以 `Driver` 为入口，画出一次完整调用经过的包。**

> 提示：第2章 §2.2 的表格给出 `Driver` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `Driver` 还是 `相邻工具类型`？说明代价。**

> 提示：第2章 §2.2 的表格给出 `Driver` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§2.2 核心类型

## 2.10 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2`：2 个文件、216 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2`（216 行）：两者的扩展与兼容策略不同，差异落在 `Driver` 的 11 个公开方法里。
- 若扩展与兼容假设被打破（0 个依赖变化），最先受影响的调用链从 `—` 进入。

## 2.10.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2` 与 `org.h2` 的调用方向？`Driver` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2` 的调用链讲到落盘或返回，并说清 `org.h2` 与 `org.h2` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2` 的注释与实现对不上，你信哪一边，为什么？

## 2.11 跨章索引

本章引用但不展开的包，按下面这张表跳到主责章节阅读。

| 包 | 主责章节 |
| --- | --- |
| `org.h2` | 第1章《H2 总体架构》 |

## 2.11 延展阅读

- 详见第1章《H2 总体架构》。
