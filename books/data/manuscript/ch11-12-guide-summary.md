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

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

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

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

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

## 13.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第14章《全书总结》。

## 13.5 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。

## 13.6 本章小结

- 本章覆盖 2 个包、25,328 行。
- 关键入口与源码坐标见 §13.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 13.7 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 列举本章中两处用空间换时间的设计，并说明其收益与上限。**

> 提示：回到 §13.1 的表格，按规模排序挑选目标包。
> 回顾：§13.1 模块版图

**2. 🔵★★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §13.1 的表格，按规模排序挑选目标包。
> 回顾：§13.1 模块版图

**3. 🟠★★★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：回到 §13.1 的表格，按规模排序挑选目标包。
> 回顾：§13.1 模块版图

**4. 🟢★★★★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：回到 §13.1 的表格，按规模排序挑选目标包。
> 回顾：§13.1 模块版图

## 13.8 延展阅读

- 详见第14章《全书总结》。

# 第14章 全书总结

## 14.1 模块版图

本章覆盖 1 个包、4,150 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.api` | 12 | 4,150 | Contains interfaces for user-defined extensions, such as triggers and user-defined aggregate functions. |

## 14.2 核心类型

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 14.2.1 `org.h2.api`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ErrorCode` | 2,367 | 2 | （无类注释，按方法名归纳） |
| `Interval` | 636 | 33 | （无类注释，按方法名归纳） |
| `IntervalQualifier` | 353 | 13 | （无类注释，按方法名归纳） |
| `H2Type` | 322 | 6 | （无类注释，按方法名归纳） |

## 14.3 关键 API 与源码坐标

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `ErrorCode.getState()` | `org/h2/api/ErrorCode.java:2317` |
| `ErrorCode.isCommon()` | `org/h2/api/ErrorCode.java:2287` |
| `Interval.equals()` | `org/h2/api/Interval.java:617` |
| `Interval.getDays()` | `org/h2/api/Interval.java:543` |
| `IntervalQualifier.getTypeName()` | `org/h2/api/IntervalQualifier.java:253` |
| `IntervalQualifier.hasDays()` | `org/h2/api/IntervalQualifier.java:165` |

## 14.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第13章《二次开发指南》。

## 14.5 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **Aggregate**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。

## 14.6 本章小结

- 本章覆盖 1 个包、4,150 行。
- 关键入口与源码坐标见 §14.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 14.7 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §14.1 的表格，按规模排序挑选目标包。
> 回顾：§14.1 模块版图

**2. 🔵★★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：回到 §14.1 的表格，按规模排序挑选目标包。
> 回顾：§14.1 模块版图

**3. 🟠★★★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：回到 §14.1 的表格，按规模排序挑选目标包。
> 回顾：§14.1 模块版图

**4. 🟢★★★★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：回到 §14.1 的表格，按规模排序挑选目标包。
> 回顾：§14.1 模块版图

## 14.8 延展阅读

- 详见第13章《二次开发指南》。
