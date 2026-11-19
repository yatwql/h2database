# 第13章 二次开发指南

> **本章导读**：本章由源码清单汇总而成，覆盖 3 个包、29,478 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 13.1 模块版图

本章覆盖 2 个包、25,328 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.util` | 48 | 14,460 | Internal utility classes. |
| `org.h2.tools` | 23 | 10,868 | Various tools. |

## 13.2 核心类型

在 `org.h2.util` 之外，本章还有 1 个包；下表每包取前 4 个类型，按规模降序。

### 13.2.1 `org.h2.util`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `StringUtils` | 1,415 | 55 | （无类注释，按方法名归纳） |
| `DateTimeUtils` | 1,171 | 42 | （无类注释，按方法名归纳） |
| `DateTimeTemplate` | 859 | 5 | （无类注释，按方法名归纳） |
| `IntervalUtils` | 857 | 12 | （无类注释，按方法名归纳） |

### 13.2.2 `org.h2.tools`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `SimpleResultSet` | 2,480 | 228 | （无类注释，按方法名归纳） |
| `Csv` | 986 | 33 | （无类注释，按方法名归纳） |
| `Recover` | 922 | 18 | （无类注释，按方法名归纳） |
| `Server` | 823 | 19 | （无类注释，按方法名归纳） |

## 13.3 关键 API 与源码坐标

把 2 个包的关键入口与源码位置对应起来，共 6 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `StringUtils.addAsterisk()` | `org/h2/util/StringUtils.java:283` |
| `StringUtils.appendHex()` | `org/h2/util/StringUtils.java:1277` |
| `DateTimeUtils.absoluteDayFromDateValue()` | `org/h2/util/DateTimeUtils.java:873` |
| `DateTimeUtils.absoluteDayFromYear()` | `org/h2/util/DateTimeUtils.java:857` |
| `DateTimeTemplate.format()` | `org/h2/util/DateTimeTemplate.java:178` |
| `DateTimeTemplate.of()` | `org/h2/util/DateTimeTemplate.java:430` |
| `SimpleResultSet.absolute()` | `org/h2/tools/SimpleResultSet.java:2229` |
| `SimpleResultSet.addColumn()` | `org/h2/tools/SimpleResultSet.java:100` |
| `Csv.close()` | `org/h2/tools/Csv.java:639` |
| `Csv.getBinaryColumns()` | `org/h2/tools/Csv.java:909` |
| `Recover.checkPowerOff()` | `org/h2/tools/Recover.java:857` |
| `Recover.checkWritingAllowed()` | `org/h2/tools/Recover.java:865` |

## 13.3.1 公共类型清单

本章抽样类型按包分组，共 10 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `StringUtils` | `org.h2.util` | 1,415 | 55 |
| `DateTimeUtils` | `org.h2.util` | 1,171 | 42 |
| `DateTimeTemplate` | `org.h2.util` | 859 | 5 |
| `IntervalUtils` | `org.h2.util` | 857 | 12 |
| `Utils` | `org.h2.util` | 832 | 34 |
| `SimpleResultSet` | `org.h2.tools` | 2,480 | 228 |
| `Csv` | `org.h2.tools` | 986 | 33 |
| `Recover` | `org.h2.tools` | 922 | 18 |
| `Server` | `org.h2.tools` | 823 | 19 |
| `DirectRecover` | `org.h2.tools` | 767 | 11 |

## 13.4 阅读路径

读 `org.h2.util` 的 48 个文件时，先看骨架类，再沿 `org.h2.value` 方向下钻。

1. 先读 `org.h2.util` 的 package-info 与 `StringUtils`，建立第13章的职责边界。
2. 再读 `StringUtils` 的 55 个公开入口，确认它对 `org.h2.value` 的调用方向与加锁方式。
3. 最后读 `org.h2.tools`（本章最小包，10,868 行）的实现，关注容量与失败路径。

跨章衔接请对照第14章《全书总结》。

## 13.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.util` | `org.h2.value`, `org.h2.engine`, `org.h2.message`, `org.h2.api` |
| `org.h2.tools` | `org.h2.util`, `org.h2.engine`, `org.h2.value`, `org.h2.message` |

## 13.6 设计权衡

- `org.h2.util` 用 48 个文件换到 14,460 行实现，平均每文件 301 行，其中 `StringUtils` 独占 1,415 行、55 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.tools`（10,868 行）与 `org.h2.util` 的职责差是本章最值得记的一条边界。

## 13.7 常见误区

- 把 `org.h2.util` 的 14,460 行当作复杂度上限：`StringUtils` 之外的 47 个文件多为类型族与样板。
- 只看 `StringUtils` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.util` 与 `org.h2.tools` 视为可互换：前者 48 文件、后者 23 文件，扩展点分布完全不同。

## 13.8 深读要点

规模信号：`org.h2.util` 占本章 57% 的实现行数，改动风险最高。
耦合信号：`org.h2.util` 依赖 8 个 `org.h2` 包，其中 `org.h2.value` 出现最频繁。
入口信号：`StringUtils` 的公开方法 55 个，读它等于读本章的主干。

## 13.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。

## 13.9 知识点清单

1. `org.h2.util` 的 `StringUtils`：1,415 行、55 个公开方法，职责按方法名归纳
2. `org.h2.util` 的 `DateTimeUtils`：1,171 行、42 个公开方法，职责按方法名归纳
3. `org.h2.tools` 的 `SimpleResultSet`：2,480 行、228 个公开方法，职责按方法名归纳
4. `org.h2.tools` 的 `Csv`：986 行、33 个公开方法，职责按方法名归纳

## 13.9 本章小结

- 本章覆盖 2 个包、25,328 行。
- 关键入口与源码坐标见 §13.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 13.10 延伸思考

**1. 🟢★ 指出 `org.h2.util` 中 `StringUtils` 与 `DateTimeUtils` 的分工差异，并给出调用方向。**

> 提示：第13章 §13.2 的表格给出 `StringUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**2. 🔵★★ 围绕 `org.h2.tools` 的 `SimpleResultSet`，说明它为什么需要独立成类型而不是并入 `Csv`。**

> 提示：第13章 §13.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**3. 🟠★★★ 以 `org.h2.util` 的 `StringUtils` 为入口，画出一次完整调用经过的包。**

> 提示：第13章 §13.2 的表格给出 `StringUtils` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.tools` 的一个类型，你保留 `SimpleResultSet` 还是 `Csv`？说明代价。**

> 提示：第13章 §13.2 的表格给出 `SimpleResultSet` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§13.2 核心类型

## 13.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.util`：48 个文件、14,460 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.tools`（10,868 行）：两者的并发与一致性策略不同，差异落在 `StringUtils` 的 55 个公开方法里。
- 若并发与一致性假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.value` 进入。

## 13.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.util` | `org.h2.value` | 35 |
| `org.h2.util` | `org.h2.engine` | 18 |
| `org.h2.util` | `org.h2.message` | 16 |
| `org.h2.tools` | `org.h2.util` | 53 |
| `org.h2.tools` | `org.h2.engine` | 14 |
| `org.h2.tools` | `org.h2.value` | 14 |

## 13.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.util` 与 `org.h2.tools` 之间的调用方向？
- `StringUtils` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.util` 的调用链讲到落盘或返回？
- `org.h2.util` 与 `org.h2.tools` 若合并，会丢掉哪个扩展点？
- `org.h2.util` 的注释与实现若不一致，你信哪一边，为什么？

## 13.12 延展阅读

- 详见第14章《全书总结》。

# 第14章 全书总结

## 14.1 模块版图

本章覆盖 1 个包、4,150 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.api` | 12 | 4,150 | Contains interfaces for user-defined extensions, such as triggers and user-defined aggregate functions. |

## 14.2 核心类型

在 `org.h2.api` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 14.2.1 `org.h2.api`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ErrorCode` | 2,367 | 2 | （无类注释，按方法名归纳） |
| `Interval` | 636 | 33 | （无类注释，按方法名归纳） |
| `IntervalQualifier` | 353 | 13 | （无类注释，按方法名归纳） |
| `H2Type` | 322 | 6 | （无类注释，按方法名归纳） |

## 14.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `ErrorCode.getState()` | `org/h2/api/ErrorCode.java:2317` |
| `ErrorCode.isCommon()` | `org/h2/api/ErrorCode.java:2287` |
| `Interval.equals()` | `org/h2/api/Interval.java:617` |
| `Interval.getDays()` | `org/h2/api/Interval.java:543` |
| `IntervalQualifier.getTypeName()` | `org/h2/api/IntervalQualifier.java:253` |
| `IntervalQualifier.hasDays()` | `org/h2/api/IntervalQualifier.java:165` |

## 14.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `ErrorCode` | `org.h2.api` | 2,367 | 2 |
| `Interval` | `org.h2.api` | 636 | 33 |
| `IntervalQualifier` | `org.h2.api` | 353 | 13 |
| `H2Type` | `org.h2.api` | 322 | 6 |
| `DatabaseEventListener` | `org.h2.api` | 113 | 0 |

## 14.4 阅读路径

读 `org.h2.api` 的 12 个文件时，先看骨架类，再沿 `org.h2.security.auth` 方向下钻。

1. 先读 `org.h2.api` 的 package-info 与 `ErrorCode`，建立第14章的职责边界。
2. 再读 `ErrorCode` 的 2 个公开入口，确认它对 `org.h2.security.auth` 的调用方向与加锁方式。
3. 最后读 `org.h2.api`（本章最小包，4,150 行）的实现，关注容量与失败路径。

跨章衔接请对照第13章《二次开发指南》。

## 14.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.api` | `org.h2.security.auth`, `org.h2.value`, `org.h2.util.DateTimeUtils`, `org.h2.message` |

## 14.6 设计权衡

- `org.h2.api` 用 12 个文件换到 4,150 行实现，平均每文件 345 行，其中 `ErrorCode` 独占 2,367 行、2 个公开方法。
- 该包对外声明了 7 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.api`（4,150 行）与 `org.h2.api` 的职责差是本章最值得记的一条边界。

## 14.7 常见误区

- 把 `org.h2.api` 的 4,150 行当作复杂度上限：`ErrorCode` 之外的 11 个文件多为类型族与样板。
- 只看 `ErrorCode` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.api` 与 `org.h2.api` 视为可互换：前者 12 文件、后者 12 文件，扩展点分布完全不同。

## 14.8 深读要点

规模信号：`org.h2.api` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.api` 依赖 7 个 `org.h2` 包，其中 `org.h2.security.auth` 出现最频繁。
入口信号：`ErrorCode` 的公开方法 2 个，读它等于读本章的主干。

## 14.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Aggregate**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。

## 14.9 知识点清单

1. `org.h2.api` 的 `ErrorCode`：2,367 行、2 个公开方法，职责按方法名归纳
2. `org.h2.api` 的 `Interval`：636 行、33 个公开方法，职责按方法名归纳

## 14.9 本章小结

- 本章覆盖 1 个包、4,150 行。
- 关键入口与源码坐标见 §14.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 14.10 延伸思考

**1. 🟢★ 指出 `org.h2.api` 中 `ErrorCode` 与 `Interval` 的分工差异，并给出调用方向。**

> 提示：第14章 §14.2 的表格给出 `ErrorCode` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**2. 🔵★★ 围绕 `org.h2.api` 的 `ErrorCode`，说明它为什么需要独立成类型而不是并入 `Interval`。**

> 提示：第14章 §14.2 的表格给出 `ErrorCode` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**3. 🟠★★★ 以 `org.h2.api` 的 `ErrorCode` 为入口，画出一次完整调用经过的包。**

> 提示：第14章 §14.2 的表格给出 `ErrorCode` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.api` 的一个类型，你保留 `ErrorCode` 还是 `Interval`？说明代价。**

> 提示：第14章 §14.2 的表格给出 `ErrorCode` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§14.2 核心类型

## 14.11 本章视角：扩展与兼容

- 以「扩展与兼容」看 `org.h2.api`：12 个文件、4,150 行，本章只展开与扩展与兼容相关的入口。
- 对照 `org.h2.api`（4,150 行）：两者的扩展与兼容策略不同，差异落在 `ErrorCode` 的 2 个公开方法里。
- 若扩展与兼容假设被打破（7 个依赖变化），最先受影响的调用链从 `org.h2.security.auth` 进入。

## 14.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.api` | `org.h2.security.auth` | 5 |
| `org.h2.api` | `org.h2.value` | 3 |
| `org.h2.api` | `org.h2.util.DateTimeUtils` | 2 |

## 14.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.api` 与 `org.h2.api` 之间的调用方向？
- `ErrorCode` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.api` 的调用链讲到落盘或返回？
- `org.h2.api` 与 `org.h2.api` 若合并，会丢掉哪个扩展点？
- `org.h2.api` 的注释与实现若不一致，你信哪一边，为什么？

## 14.12 延展阅读

- 详见第13章《二次开发指南》。
