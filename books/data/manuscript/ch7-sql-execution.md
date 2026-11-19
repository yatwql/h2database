# 第9章 SQL 解析与执行

> **本章导读**：本章由源码清单汇总而成，覆盖 5 个包、43,366 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 9.1 模块版图

本章覆盖 5 个包、43,366 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.command` | 11 | 15,014 | This package contains the parser and the base classes for prepared SQL statements. |
| `org.h2.expression.function` | 50 | 9,509 | Functions. |
| `org.h2.command.ddl` | 63 | 7,262 | Contains DDL (data definition language) and related SQL statements. |
| `org.h2.expression` | 35 | 5,832 | Expressions include mathematical operations, simple values, and others. |
| `org.h2.command.dml` | 24 | 5,749 | Contains DML (data manipulation language) and related SQL statements. |

## 9.2 核心类型

每个包取规模最大的若干类型，列出规模、公开方法数与自述职责。

### 9.2.1 `org.h2.command`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Parser` | 9,470 | 9 | （无类注释，按方法名归纳） |
| `Tokenizer` | 1,522 | 0 | （无类注释，按方法名归纳） |
| `ParserBase` | 771 | 8 | （无类注释，按方法名归纳） |
| `Token` | 758 | 5 | （无类注释，按方法名归纳） |
| `CommandInterface` | 654 | 0 | （无类注释，按方法名归纳） |
| `Prepared` | 503 | 33 | （无类注释，按方法名归纳） |

### 9.2.2 `org.h2.expression.function`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ToCharFunction` | 1,156 | 8 | （无类注释，按方法名归纳） |
| `DateTimeFunction` | 1,081 | 7 | （无类注释，按方法名归纳） |
| `BitFunction` | 730 | 5 | （无类注释，按方法名归纳） |
| `MathFunction` | 405 | 3 | （无类注释，按方法名归纳） |
| `DateTimeFormatFunction` | 339 | 7 | （无类注释，按方法名归纳） |
| `StringFunction1` | 284 | 3 | （无类注释，按方法名归纳） |

### 9.2.3 `org.h2.command.ddl`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `AlterTableAlterColumn` | 734 | 17 | （无类注释，按方法名归纳） |
| `AlterTableAddConstraint` | 520 | 18 | （无类注释，按方法名归纳） |
| `SequenceOptions` | 363 | 18 | （无类注释，按方法名归纳） |
| `CreateTable` | 275 | 17 | （无类注释，按方法名归纳） |
| `Analyze` | 258 | 5 | （无类注释，按方法名归纳） |
| `GrantRevoke` | 230 | 9 | （无类注释，按方法名归纳） |

### 9.2.4 `org.h2.expression`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ExpressionColumn` | 553 | 23 | （无类注释，按方法名归纳） |
| `Expression` | 551 | 41 | （无类注释，按方法名归纳） |
| `BinaryOperation` | 455 | 6 | （无类注释，按方法名归纳） |
| `ExpressionVisitor` | 417 | 17 | （无类注释，按方法名归纳） |
| `IntervalOperation` | 381 | 4 | （无类注释，按方法名归纳） |
| `SimpleCase` | 289 | 12 | （无类注释，按方法名归纳） |

### 9.2.5 `org.h2.command.dml`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ScriptCommand` | 858 | 23 | （无类注释，按方法名归纳） |
| `Set` | 652 | 9 | （无类注释，按方法名归纳） |
| `MergeUsing` | 598 | 20 | （无类注释，按方法名归纳） |
| `SetClauseList` | 507 | 3 | （无类注释，按方法名归纳） |
| `Insert` | 456 | 19 | （无类注释，按方法名归纳） |
| `Merge` | 367 | 11 | （无类注释，按方法名归纳） |

## 9.3 关键 API 与源码坐标

下表把公开入口与当前源码位置对应起来，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Parser.newPrimaryKeyConstraintCommand()` | `org/h2/command/Parser.java:9178` |
| `Parser.parseDomainConstraintExpression()` | `org/h2/command/Parser.java:9446` |
| `ParserBase.formatNonKeywords()` | `org/h2/command/ParserBase.java:93` |
| `ParserBase.getLastParseIndex()` | `org/h2/command/ParserBase.java:743` |
| `ToCharFunction.apply()` | `org/h2/expression/function/ToCharFunction.java:1088` |
| `ToCharFunction.clearNames()` | `org/h2/expression/function/ToCharFunction.java:552` |
| `DateTimeFunction.dateadd()` | `org/h2/expression/function/DateTimeFunction.java:656` |
| `DateTimeFunction.getField()` | `org/h2/expression/function/DateTimeFunction.java:241` |
| `BitFunction.checkArgType()` | `org/h2/expression/function/BitFunction.java:709` |
| `BitFunction.getBitwise()` | `org/h2/expression/function/BitFunction.java:455` |
| `AlterTableAlterColumn.addColumn()` | `org/h2/command/ddl/AlterTableAlterColumn.java:719` |
| `AlterTableAlterColumn.getType()` | `org/h2/command/ddl/AlterTableAlterColumn.java:710` |
| `AlterTableAddConstraint.getConstraintName()` | `org/h2/command/ddl/AlterTableAddConstraint.java:448` |
| `AlterTableAddConstraint.getIndexColumns()` | `org/h2/command/ddl/AlterTableAddConstraint.java:480` |
| `SequenceOptions.getBounds()` | `org/h2/command/ddl/SequenceOptions.java:241` |
| `SequenceOptions.getCacheSize()` | `org/h2/command/ddl/SequenceOptions.java:346` |
| `ExpressionColumn.createIndexConditions()` | `org/h2/expression/ExpressionColumn.java:499` |
| `ExpressionColumn.getAlias()` | `org/h2/expression/ExpressionColumn.java:404` |
| `Expression.addFilterConditions()` | `org/h2/expression/Expression.java:477` |
| `Expression.createIndexConditions()` | `org/h2/expression/Expression.java:354` |

## 9.4 阅读路径

1. 先读包注释与最大类型，建立职责边界。
2. 再读公开入口，确认调用方向与加锁方式。
3. 最后读内部实现与数据结构，关注容量、并发与失败路径。

跨章衔接请对照第10章《SQL 解析与执行》。

## 9.5 本章小结

- 本章覆盖 5 个包、43,366 行。
- 关键入口与源码坐标见 §9.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 9.6 延伸思考

下列题目把"读到的结构"转化为可应用的判断力。

**1. 🟢★ 找一个失败路径（异常或回滚），说明状态如何回退到一致。**

> 提示：回到 §9.1 的表格，按规模排序挑选目标包。
> 回顾：§9.1 模块版图

**2. 🔵★★ 用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。**

> 提示：回到 §9.1 的表格，按规模排序挑选目标包。
> 回顾：§9.1 模块版图

**3. 🟠★★★ 挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。**

> 提示：回到 §9.1 的表格，按规模排序挑选目标包。
> 回顾：§9.1 模块版图

**4. 🟢★★★★ 如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？**

> 提示：回到 §9.1 的表格，按规模排序挑选目标包。
> 回顾：§9.1 模块版图

## 9.7 延展阅读

- 详见第10章《SQL 解析与执行》。
