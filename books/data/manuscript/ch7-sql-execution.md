# 第9章 SQL 解析与执行

> **本章导读**：本章由源码清单汇总而成，覆盖 4 个包、28,396 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 9.1 模块版图

本章覆盖 4 个包、28,396 行实现。下表按规模排序，职责取自 `package-info.java` 首句。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.expression.function` | 51 | 9,520 | （无包注释，按主类型归纳） |
| `org.h2.command.ddl` | 64 | 7,273 | （无包注释，按主类型归纳） |
| `org.h2.expression` | 36 | 5,843 | （无包注释，按主类型归纳） |
| `org.h2.command.dml` | 25 | 5,760 | （无包注释，按主类型归纳） |

## 9.2 核心类型

在 `org.h2.expression.function` 之外，本章还有 3 个包；下表每包取前 4 个类型，按规模降序。

### 9.2.1 `org.h2.expression.function`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ToCharFunction` | 1,156 | 8 | （无类注释，按方法名归纳） |
| `DateTimeFunction` | 1,081 | 7 | （无类注释，按方法名归纳） |
| `BitFunction` | 730 | 5 | （无类注释，按方法名归纳） |
| `MathFunction` | 405 | 3 | （无类注释，按方法名归纳） |

### 9.2.2 `org.h2.command.ddl`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `AlterTableAlterColumn` | 734 | 17 | （无类注释，按方法名归纳） |
| `AlterTableAddConstraint` | 520 | 18 | （无类注释，按方法名归纳） |
| `SequenceOptions` | 363 | 18 | （无类注释，按方法名归纳） |
| `CreateTable` | 275 | 17 | （无类注释，按方法名归纳） |

### 9.2.3 `org.h2.expression`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ExpressionColumn` | 553 | 23 | （无类注释，按方法名归纳） |
| `Expression` | 551 | 41 | （无类注释，按方法名归纳） |
| `BinaryOperation` | 455 | 6 | （无类注释，按方法名归纳） |
| `ExpressionVisitor` | 417 | 17 | （无类注释，按方法名归纳） |

### 9.2.4 `org.h2.command.dml`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `ScriptCommand` | 858 | 23 | （无类注释，按方法名归纳） |
| `Set` | 652 | 9 | （无类注释，按方法名归纳） |
| `MergeUsing` | 598 | 20 | （无类注释，按方法名归纳） |
| `SetClauseList` | 507 | 3 | （无类注释，按方法名归纳） |

## 9.3 关键 API 与源码坐标

把 4 个包的关键入口与源码位置对应起来，共 12 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `ToCharFunction.apply()` | `h2/src/main/org/h2/expression/function/ToCharFunction.java:1088` |
| `ToCharFunction.clearNames()` | `h2/src/main/org/h2/expression/function/ToCharFunction.java:552` |
| `DateTimeFunction.dateadd()` | `h2/src/main/org/h2/expression/function/DateTimeFunction.java:656` |
| `DateTimeFunction.getField()` | `h2/src/main/org/h2/expression/function/DateTimeFunction.java:241` |
| `BitFunction.checkArgType()` | `h2/src/main/org/h2/expression/function/BitFunction.java:709` |
| `BitFunction.getBitwise()` | `h2/src/main/org/h2/expression/function/BitFunction.java:455` |
| `AlterTableAlterColumn.addColumn()` | `h2/src/main/org/h2/command/ddl/AlterTableAlterColumn.java:719` |
| `AlterTableAlterColumn.getType()` | `h2/src/main/org/h2/command/ddl/AlterTableAlterColumn.java:710` |
| `AlterTableAddConstraint.getConstraintName()` | `h2/src/main/org/h2/command/ddl/AlterTableAddConstraint.java:448` |
| `AlterTableAddConstraint.getIndexColumns()` | `h2/src/main/org/h2/command/ddl/AlterTableAddConstraint.java:480` |
| `SequenceOptions.getBounds()` | `h2/src/main/org/h2/command/ddl/SequenceOptions.java:241` |
| `SequenceOptions.getCacheSize()` | `h2/src/main/org/h2/command/ddl/SequenceOptions.java:346` |
| `ExpressionColumn.createIndexConditions()` | `h2/src/main/org/h2/expression/ExpressionColumn.java:499` |
| `ExpressionColumn.getAlias()` | `h2/src/main/org/h2/expression/ExpressionColumn.java:404` |
| `Expression.addFilterConditions()` | `h2/src/main/org/h2/expression/Expression.java:477` |
| `Expression.createIndexConditions()` | `h2/src/main/org/h2/expression/Expression.java:354` |
| `BinaryOperation.getOperationType()` | `h2/src/main/org/h2/expression/BinaryOperation.java:450` |
| `BinaryOperation.getUnenclosedSQL()` | `h2/src/main/org/h2/expression/BinaryOperation.java:74` |
| `ScriptCommand.close()` | `h2/src/main/org/h2/command/dml/ScriptCommand.java:677` |
| `ScriptCommand.collectDependencies()` | `h2/src/main/org/h2/command/dml/ScriptCommand.java:119` |

## 9.3.1 公共类型清单

本章抽样类型按包分组，共 20 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
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
| `ScriptCommand` | `org.h2.command.dml` | 858 | 23 |
| `Set` | `org.h2.command.dml` | 652 | 9 |
| `MergeUsing` | `org.h2.command.dml` | 598 | 20 |
| `SetClauseList` | `org.h2.command.dml` | 507 | 3 |
| `Insert` | `org.h2.command.dml` | 456 | 19 |

## 9.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 9.3.2.1 `ToCharFunction`

`ToCharFunction` 位于 `org.h2.expression.function`，1,156 行、8 个公开方法。它占该包实现的 12%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.2 `DateTimeFunction`

`DateTimeFunction` 位于 `org.h2.expression.function`，1,081 行、7 个公开方法。它占该包实现的 11%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.3 `BitFunction`

`BitFunction` 位于 `org.h2.expression.function`，730 行、5 个公开方法。它占该包实现的 8%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.4 `MathFunction`

`MathFunction` 位于 `org.h2.expression.function`，405 行、3 个公开方法。它占该包实现的 4%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.5 `AlterTableAlterColumn`

`AlterTableAlterColumn` 位于 `org.h2.command.ddl`，734 行、17 个公开方法。它占该包实现的 10%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.6 `AlterTableAddConstraint`

`AlterTableAddConstraint` 位于 `org.h2.command.ddl`，520 行、18 个公开方法。它占该包实现的 7%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.7 `SequenceOptions`

`SequenceOptions` 位于 `org.h2.command.ddl`，363 行、18 个公开方法。它占该包实现的 5%，包内排名第 7。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.8 `CreateTable`

`CreateTable` 位于 `org.h2.command.ddl`，275 行、17 个公开方法。它占该包实现的 4%，包内排名第 8。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（3 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.9 `ExpressionColumn`

`ExpressionColumn` 位于 `org.h2.expression`，553 行、23 个公开方法。它占该包实现的 9%，包内排名第 9。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.10 `Expression`

`Expression` 位于 `org.h2.expression`，551 行、41 个公开方法。它占该包实现的 9%，包内排名第 10。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.11 `BinaryOperation`

`BinaryOperation` 位于 `org.h2.expression`，455 行、6 个公开方法。它占该包实现的 8%，包内排名第 11。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.12 `ExpressionVisitor`

`ExpressionVisitor` 位于 `org.h2.expression`，417 行、17 个公开方法。它占该包实现的 7%，包内排名第 12。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（4 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.13 `ScriptCommand`

`ScriptCommand` 位于 `org.h2.command.dml`，858 行、23 个公开方法。它占该包实现的 15%，包内排名第 13。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.14 `Set`

`Set` 位于 `org.h2.command.dml`，652 行、9 个公开方法。它占该包实现的 11%，包内排名第 14。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.15 `MergeUsing`

`MergeUsing` 位于 `org.h2.command.dml`，598 行、20 个公开方法。它占该包实现的 10%，包内排名第 15。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

### 9.3.2.16 `SetClauseList`

`SetClauseList` 位于 `org.h2.command.dml`，507 行、3 个公开方法。它占该包实现的 9%，包内排名第 16。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（8 个），再决定是否顺带读同包的相邻类型。

## 9.3.2 源码坐标明细

本章主责包中 131 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `ToCharFunction.apply()` | `h2/src/main/org/h2/expression/function/ToCharFunction.java:1088` |
| `ToCharFunction.clearNames()` | `h2/src/main/org/h2/expression/function/ToCharFunction.java:552` |
| `ToCharFunction.getDateNames()` | `h2/src/main/org/h2/expression/function/ToCharFunction.java:527` |
| `ToCharFunction.getName()` | `h2/src/main/org/h2/expression/function/ToCharFunction.java:1151` |
| `ToCharFunction.getValue()` | `h2/src/main/org/h2/expression/function/ToCharFunction.java:1113` |
| `ToCharFunction.optimize()` | `h2/src/main/org/h2/expression/function/ToCharFunction.java:1141` |
| `DateTimeFunction.dateadd()` | `h2/src/main/org/h2/expression/function/DateTimeFunction.java:656` |
| `DateTimeFunction.getField()` | `h2/src/main/org/h2/expression/function/DateTimeFunction.java:241` |
| `DateTimeFunction.getFieldName()` | `h2/src/main/org/h2/expression/function/DateTimeFunction.java:337` |
| `DateTimeFunction.getName()` | `h2/src/main/org/h2/expression/function/DateTimeFunction.java:1076` |
| `DateTimeFunction.getUnenclosedSQL()` | `h2/src/main/org/h2/expression/function/DateTimeFunction.java:1050` |
| `DateTimeFunction.getValue()` | `h2/src/main/org/h2/expression/function/DateTimeFunction.java:353` |
| `BitFunction.checkArgType()` | `h2/src/main/org/h2/expression/function/BitFunction.java:709` |
| `BitFunction.getBitwise()` | `h2/src/main/org/h2/expression/function/BitFunction.java:455` |
| `BitFunction.getName()` | `h2/src/main/org/h2/expression/function/BitFunction.java:725` |
| `BitFunction.getValue()` | `h2/src/main/org/h2/expression/function/BitFunction.java:123` |
| `BitFunction.optimize()` | `h2/src/main/org/h2/expression/function/BitFunction.java:578` |
| `MathFunction.getName()` | `h2/src/main/org/h2/expression/function/MathFunction.java:400` |
| `MathFunction.getValue()` | `h2/src/main/org/h2/expression/function/MathFunction.java:87` |
| `MathFunction.optimize()` | `h2/src/main/org/h2/expression/function/MathFunction.java:216` |

## 9.4 阅读路径

读 `org.h2.expression.function` 的 51 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.expression.function` 的 package-info 与 `ToCharFunction`，建立第9章的职责边界。
2. 再读 `ToCharFunction` 的 8 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.command.dml`（本章最小包，5,760 行）的实现，关注容量与失败路径。

跨章衔接请对照第10章《SQL 解析与执行》。

## 9.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.expression.function` | `org.h2`, `org.h2.util`, `org.h2.engine`, `org.h2.mvstore` |
| `org.h2.command.ddl` | `org.h2`, `org.h2.constraint`, `org.h2.command` |
| `org.h2.expression` | `org.h2`, `org.h2.util`, `org.h2.command`, `org.h2.mvstore` |
| `org.h2.command.dml` | `org.h2`, `org.h2.table`, `org.h2.command`, `org.h2.mvstore` |

## 9.6 设计权衡

`org.h2.expression.function` 有 51 个文件、9,520 行。平均每文件 186 行。

其中 `ToCharFunction` 独占 1,156 行，8 个公开方法。规模集中，风险也集中。

它对外声明 7 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.command.ddl`（7,273 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 9.7 常见误区

把 `org.h2.expression.function` 的行数当作复杂度上限是误读。`ToCharFunction` 之外还有 50 个文件，其中多为类型族与样板。

只读 `ToCharFunction` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.expression.function` 与 `org.h2.command.ddl` 不能互换。前者 51 个文件，后者 64 个文件，扩展点分布完全不同。

## 9.8 深读要点

规模信号：`org.h2.expression.function` 占本章 34% 的实现行数，改动风险最高。
耦合信号：`org.h2.expression.function` 依赖 7 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`ToCharFunction` 的公开方法 8 个，读它等于读本章的主干。

## 9.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **DDL**：详见[术语表](back/glossary.md)对应条目。
- **DML**：详见[术语表](back/glossary.md)对应条目。
- **Expression**：详见[术语表](back/glossary.md)对应条目。
- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Append-Only**：详见[术语表](back/glossary.md)对应条目。
- **BackgroundWriter**：详见[术语表](back/glossary.md)对应条目。
- **Block**：详见[术语表](back/glossary.md)对应条目。
- **Chunk**：详见[术语表](back/glossary.md)对应条目。

## 9.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `ToCharFunction` | `org.h2.expression.function` | 1,156 | 8 | 按方法名归纳 |
| `DateTimeFunction` | `org.h2.expression.function` | 1,081 | 7 | 按方法名归纳 |
| `AlterTableAlterColumn` | `org.h2.command.ddl` | 734 | 17 | 按方法名归纳 |
| `AlterTableAddConstraint` | `org.h2.command.ddl` | 520 | 18 | 按方法名归纳 |
| `ExpressionColumn` | `org.h2.expression` | 553 | 23 | 按方法名归纳 |
| `Expression` | `org.h2.expression` | 551 | 41 | 按方法名归纳 |
| `ScriptCommand` | `org.h2.command.dml` | 858 | 23 | 按方法名归纳 |
| `Set` | `org.h2.command.dml` | 652 | 9 | 按方法名归纳 |

## 9.9 本章小结

- 本章覆盖 4 个包、28,396 行。
- 关键入口与源码坐标见 §9.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 9.10 延伸思考

**1. 🟢★ 说明 `ToCharFunction` 与 `DateTimeFunction` 的分工差异。给出调用方向。**

> 提示：第9章 §9.2 的表格给出 `ToCharFunction` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

**2. 🔵★★ `AlterTableAlterColumn` 为什么独立成类型，而不是并入 `AlterTableAddConstraint`？**

> 提示：第9章 §9.2 的表格给出 `AlterTableAlterColumn` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

**3. 🟠★★★ 以 `ExpressionColumn` 为入口，画出一次完整调用经过的包。**

> 提示：第9章 §9.2 的表格给出 `ExpressionColumn` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `ScriptCommand` 还是 `Set`？说明代价。**

> 提示：第9章 §9.2 的表格给出 `ScriptCommand` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§9.2 核心类型

## 9.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.expression.function`：51 个文件、9,520 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.command.ddl`（7,273 行）：两者的并发与一致性策略不同，差异落在 `ToCharFunction` 的 8 个公开方法里。
- 若并发与一致性假设被打破（7 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 9.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.expression.function` | `org.h2` | 484 |
| `org.h2.expression.function` | `org.h2.util` | 11 |
| `org.h2.expression.function` | `org.h2.engine` | 5 |
| `org.h2.command.ddl` | `org.h2` | 551 |
| `org.h2.command.ddl` | `org.h2.constraint` | 4 |
| `org.h2.command.ddl` | `org.h2.command` | 4 |
| `org.h2.expression` | `org.h2` | 254 |
| `org.h2.expression` | `org.h2.util` | 13 |
| `org.h2.expression` | `org.h2.command` | 7 |
| `org.h2.command.dml` | `org.h2` | 310 |
| `org.h2.command.dml` | `org.h2.table` | 7 |
| `org.h2.command.dml` | `org.h2.command` | 6 |

## 9.11.2 阅读检查清单

读完本章，先自问三个问题。能否不看正文画出 `org.h2.expression.function` 与 `org.h2.command.ddl` 的调用方向？`ToCharFunction` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.expression.function` 的调用链讲到落盘或返回，并说清 `org.h2.expression.function` 与 `org.h2.command.ddl` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.expression.function` 的注释与实现对不上，你信哪一边，为什么？

## 9.12 延展阅读

- 详见第10章《SQL 解析与执行》。
