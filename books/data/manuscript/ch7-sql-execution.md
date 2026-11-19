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

在 `org.h2.command` 之外，本章还有 4 个包；下表每包取前 4 个类型，按规模降序。

### 9.2.1 `org.h2.command`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Parser` | 9,470 | 9 | （无类注释，按方法名归纳） |
| `Tokenizer` | 1,522 | 0 | （无类注释，按方法名归纳） |
| `ParserBase` | 771 | 8 | （无类注释，按方法名归纳） |
| `Token` | 758 | 5 | （无类注释，按方法名归纳） |

### 9.2.2 `org.h2.expression.function`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ToCharFunction` | 1,156 | 8 | （无类注释，按方法名归纳） |
| `DateTimeFunction` | 1,081 | 7 | （无类注释，按方法名归纳） |
| `BitFunction` | 730 | 5 | （无类注释，按方法名归纳） |
| `MathFunction` | 405 | 3 | （无类注释，按方法名归纳） |

### 9.2.3 `org.h2.command.ddl`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `AlterTableAlterColumn` | 734 | 17 | （无类注释，按方法名归纳） |
| `AlterTableAddConstraint` | 520 | 18 | （无类注释，按方法名归纳） |
| `SequenceOptions` | 363 | 18 | （无类注释，按方法名归纳） |
| `CreateTable` | 275 | 17 | （无类注释，按方法名归纳） |

### 9.2.4 `org.h2.expression`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ExpressionColumn` | 553 | 23 | （无类注释，按方法名归纳） |
| `Expression` | 551 | 41 | （无类注释，按方法名归纳） |
| `BinaryOperation` | 455 | 6 | （无类注释，按方法名归纳） |
| `ExpressionVisitor` | 417 | 17 | （无类注释，按方法名归纳） |

### 9.2.5 `org.h2.command.dml`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ScriptCommand` | 858 | 23 | （无类注释，按方法名归纳） |
| `Set` | 652 | 9 | （无类注释，按方法名归纳） |
| `MergeUsing` | 598 | 20 | （无类注释，按方法名归纳） |
| `SetClauseList` | 507 | 3 | （无类注释，按方法名归纳） |

## 9.3 关键 API 与源码坐标

把 5 个包的关键入口与源码位置对应起来，共 15 条坐标，行号由脚本核验。

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

## 9.3.1 公共类型清单

本章抽样类型按包分组，共 25 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Parser` | `org.h2.command` | 9,470 | 9 |
| `Tokenizer` | `org.h2.command` | 1,522 | 0 |
| `ParserBase` | `org.h2.command` | 771 | 8 |
| `Token` | `org.h2.command` | 758 | 5 |
| `CommandInterface` | `org.h2.command` | 654 | 0 |
| `ToCharFunction` | `org.h2.expression.function` | 1,156 | 8 |
| `DateTimeFunction` | `org.h2.expression.function` | 1,081 | 7 |
| `BitFunction` | `org.h2.expression.function` | 730 | 5 |
| `MathFunction` | `org.h2.expression.function` | 405 | 3 |
| `DateTimeFormatFunction` | `org.h2.expression.function` | 339 | 7 |
| `AlterTableAlterColumn` | `org.h2.command.ddl` | 734 | 17 |
| `AlterTableAddConstraint` | `org.h2.command.ddl` | 520 | 18 |
| `SequenceOptions` | `org.h2.command.ddl` | 363 | 18 |
| `CreateTable` | `org.h2.command.ddl` | 275 | 17 |
| `Analyze` | `org.h2.command.ddl` | 258 | 5 |
| `ExpressionColumn` | `org.h2.expression` | 553 | 23 |
| `Expression` | `org.h2.expression` | 551 | 41 |
| `BinaryOperation` | `org.h2.expression` | 455 | 6 |
| `ExpressionVisitor` | `org.h2.expression` | 417 | 17 |
| `IntervalOperation` | `org.h2.expression` | 381 | 4 |

## 9.4 阅读路径

读 `org.h2.command` 的 11 个文件时，先看骨架类，再沿 `org.h2.util.ParserUtil` 方向下钻。

1. 先读 `org.h2.command` 的 package-info 与 `Parser`，建立第9章的职责边界。
2. 再读 `Parser` 的 9 个公开入口，确认它对 `org.h2.util.ParserUtil` 的调用方向与加锁方式。
3. 最后读 `org.h2.command.dml`（本章最小包，5,749 行）的实现，关注容量与失败路径。

跨章衔接请对照第10章《SQL 解析与执行》。

## 9.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.command` | `org.h2.util.ParserUtil`, `org.h2.expression.function`, `org.h2.value`, `org.h2.expression` |
| `org.h2.expression.function` | `org.h2.value`, `org.h2.expression`, `org.h2.engine`, `org.h2.message` |
| `org.h2.command.ddl` | `org.h2.engine`, `org.h2.schema`, `org.h2.table`, `org.h2.command` |
| `org.h2.expression` | `org.h2.value`, `org.h2.table`, `org.h2.engine`, `org.h2.message` |
| `org.h2.command.dml` | `org.h2.engine`, `org.h2.expression`, `org.h2.result`, `org.h2.command` |

## 9.6 设计权衡

- `org.h2.command` 用 11 个文件换到 15,014 行实现，平均每文件 1,364 行，其中 `Parser` 独占 9,470 行、9 个公开方法。
- 该包对外声明了 8 个 `org.h2` 依赖；依赖越集中，越说明它是"被复用"而不是"被调用"。
- `org.h2.expression.function`（9,509 行）与 `org.h2.command` 的职责差是本章最值得记的一条边界。

## 9.7 常见误区

- 把 `org.h2.command` 的 15,014 行当作复杂度上限：`Parser` 之外的 10 个文件多为类型族与样板。
- 只看 `Parser` 的方法签名而不看调用点：约束往往写在调用方的加锁顺序里。
- 把 `org.h2.command` 与 `org.h2.expression.function` 视为可互换：前者 11 文件、后者 50 文件，扩展点分布完全不同。

## 9.8 深读要点

规模信号：`org.h2.command` 占本章 35% 的实现行数，改动风险最高。
耦合信号：`org.h2.command` 依赖 8 个 `org.h2` 包，其中 `org.h2.util.ParserUtil` 出现最频繁。
入口信号：`Parser` 的公开方法 9 个，读它等于读本章的主干。

## 9.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **DDL**：详见[术语表](back/glossary.md)对应条目。
- **DML**：详见[术语表](back/glossary.md)对应条目。
- **Expression**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Parser**：详见[术语表](back/glossary.md)对应条目。
- **Value**：详见[术语表](back/glossary.md)对应条目。

## 9.9 知识点清单

1. `org.h2.command` 的 `Parser`：9,470 行、9 个公开方法，职责按方法名归纳
2. `org.h2.command` 的 `Tokenizer`：1,522 行、0 个公开方法，职责按方法名归纳
3. `org.h2.expression.function` 的 `ToCharFunction`：1,156 行、8 个公开方法，职责按方法名归纳
4. `org.h2.expression.function` 的 `DateTimeFunction`：1,081 行、7 个公开方法，职责按方法名归纳
5. `org.h2.command.ddl` 的 `AlterTableAlterColumn`：734 行、17 个公开方法，职责按方法名归纳
6. `org.h2.command.ddl` 的 `AlterTableAddConstraint`：520 行、18 个公开方法，职责按方法名归纳
7. `org.h2.expression` 的 `ExpressionColumn`：553 行、23 个公开方法，职责按方法名归纳
8. `org.h2.expression` 的 `Expression`：551 行、41 个公开方法，职责按方法名归纳
9. `org.h2.command.dml` 的 `ScriptCommand`：858 行、23 个公开方法，职责按方法名归纳
10. `org.h2.command.dml` 的 `Set`：652 行、9 个公开方法，职责按方法名归纳

## 9.9 本章小结

- 本章覆盖 5 个包、43,366 行。
- 关键入口与源码坐标见 §9.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 9.10 延伸思考

**1. 🟢★ 指出 `org.h2.command` 中 `Parser` 与 `Tokenizer` 的分工差异，并给出调用方向。**

> 提示：第9章 §9.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

**2. 🔵★★ 围绕 `org.h2.expression.function` 的 `ToCharFunction`，说明它为什么需要独立成类型而不是并入 `DateTimeFunction`。**

> 提示：第9章 §9.2 的表格给出 `ToCharFunction` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

**3. 🟠★★★ 以 `org.h2.command.ddl` 的 `AlterTableAlterColumn` 为入口，画出一次完整调用经过的包。**

> 提示：第9章 §9.2 的表格给出 `AlterTableAlterColumn` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

**4. 🟢★★★★ 如果只保留 `org.h2.expression` 的一个类型，你保留 `ExpressionColumn` 还是 `Expression`？说明代价。**

> 提示：第9章 §9.2 的表格给出 `ExpressionColumn` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

## 9.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.command`：11 个文件、15,014 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.expression.function`（9,509 行）：两者的并发与一致性策略不同，差异落在 `Parser` 的 9 个公开方法里。
- 若并发与一致性假设被打破（8 个依赖变化），最先受影响的调用链从 `org.h2.util.ParserUtil` 进入。

## 9.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.command` | `org.h2.util.ParserUtil` | 188 |
| `org.h2.command` | `org.h2.expression.function` | 44 |
| `org.h2.command` | `org.h2.value` | 41 |
| `org.h2.expression.function` | `org.h2.value` | 209 |
| `org.h2.expression.function` | `org.h2.expression` | 103 |
| `org.h2.expression.function` | `org.h2.engine` | 58 |
| `org.h2.command.ddl` | `org.h2.engine` | 151 |
| `org.h2.command.ddl` | `org.h2.schema` | 83 |
| `org.h2.command.ddl` | `org.h2.table` | 68 |
| `org.h2.expression` | `org.h2.value` | 125 |
| `org.h2.expression` | `org.h2.table` | 37 |
| `org.h2.expression` | `org.h2.engine` | 34 |
| `org.h2.command.dml` | `org.h2.engine` | 59 |
| `org.h2.command.dml` | `org.h2.expression` | 42 |
| `org.h2.command.dml` | `org.h2.result` | 40 |

## 9.11.2 阅读检查清单

- 不看正文，能否画出 `org.h2.command` 与 `org.h2.expression.function` 之间的调用方向？
- `Parser` 是否涉及并发？依据是锁、可见性还是不可变？
- 能否用一个入口，把 `org.h2.command` 的调用链讲到落盘或返回？
- `org.h2.command` 与 `org.h2.expression.function` 若合并，会丢掉哪个扩展点？
- `org.h2.command` 的注释与实现若不一致，你信哪一边，为什么？

## 9.12 延展阅读

- 详见第10章《SQL 解析与执行》。
