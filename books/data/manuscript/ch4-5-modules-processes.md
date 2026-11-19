# 第4章 模块边界与依赖治理

> **本章导读**：本章由源码清单汇总而成，覆盖 1 个包、15,026 行实现；读完应能说清这些包的职责边界与关键协作。

> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

## 4.1 模块版图

本章覆盖 1 个包、15,026 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.command` | 12 | 15,026 | （无包注释，按主类型归纳） |

## 4.2 核心类型

在 `org.h2.command` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 4.2.1 `org.h2.command`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Parser` | 9,470 | 9 | （无类注释，按方法名归纳） |
| `Tokenizer` | 1,522 | 0 | （无类注释，按方法名归纳） |
| `ParserBase` | 771 | 8 | （无类注释，按方法名归纳） |
| `Token` | 758 | 5 | （无类注释，按方法名归纳） |

## 4.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Parser.newPrimaryKeyConstraintCommand()` | `h2/src/main/org/h2/command/Parser.java:9178` |
| `Parser.parseDomainConstraintExpression()` | `h2/src/main/org/h2/command/Parser.java:9446` |
| `ParserBase.formatNonKeywords()` | `h2/src/main/org/h2/command/ParserBase.java:93` |
| `ParserBase.getLastParseIndex()` | `h2/src/main/org/h2/command/ParserBase.java:743` |

## 4.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Parser` | `org.h2.command` | 9,470 | 9 |
| `Tokenizer` | `org.h2.command` | 1,522 | 0 |
| `ParserBase` | `org.h2.command` | 771 | 8 |
| `Token` | `org.h2.command` | 758 | 5 |
| `CommandInterface` | `org.h2.command` | 654 | 0 |

## 4.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 4.3.2.1 `Parser`

`Parser` 位于 `org.h2.command`，9,470 行、9 个公开方法。它占该包实现的 63%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 4.3.2.2 `Tokenizer`

`Tokenizer` 位于 `org.h2.command`，1,522 行、0 个公开方法。它占该包实现的 10%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 4.3.2.3 `ParserBase`

`ParserBase` 位于 `org.h2.command`，771 行、8 个公开方法。它占该包实现的 5%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 4.3.2.4 `Token`

`Token` 位于 `org.h2.command`，758 行、5 个公开方法。它占该包实现的 5%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 4.3.2.5 `CommandInterface`

`CommandInterface` 位于 `org.h2.command`，654 行、0 个公开方法。它占该包实现的 4%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 4.3.2.6 `Prepared`

`Prepared` 位于 `org.h2.command`，503 行、33 个公开方法。它占该包实现的 3%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

## 4.3.2 源码坐标明细

本章主责包中 19 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Parser.newPrimaryKeyConstraintCommand()` | `h2/src/main/org/h2/command/Parser.java:9178` |
| `Parser.parseDomainConstraintExpression()` | `h2/src/main/org/h2/command/Parser.java:9446` |
| `Parser.parseExpression()` | `h2/src/main/org/h2/command/Parser.java:9434` |
| `Parser.parseTableName()` | `h2/src/main/org/h2/command/Parser.java:9463` |
| `Parser.prepare()` | `h2/src/main/org/h2/command/Parser.java:455` |
| `Parser.prepareCommand()` | `h2/src/main/org/h2/command/Parser.java:486` |
| `ParserBase.formatNonKeywords()` | `h2/src/main/org/h2/command/ParserBase.java:93` |
| `ParserBase.getLastParseIndex()` | `h2/src/main/org/h2/command/ParserBase.java:743` |
| `ParserBase.parseColumnList()` | `h2/src/main/org/h2/command/ParserBase.java:247` |
| `ParserBase.parseNonKeywords()` | `h2/src/main/org/h2/command/ParserBase.java:72` |
| `ParserBase.quoteIdentifier()` | `h2/src/main/org/h2/command/ParserBase.java:55` |
| `ParserBase.setLiteralsChecked()` | `h2/src/main/org/h2/command/ParserBase.java:215` |
| `Token.toString()` | `h2/src/main/org/h2/command/Token.java:476` |
| `Prepared.checkCanceled()` | `h2/src/main/org/h2/command/Prepared.java:340` |
| `Prepared.collectDependencies()` | `h2/src/main/org/h2/command/Prepared.java:486` |
| `Prepared.getCurrentRowNumber()` | `h2/src/main/org/h2/command/Prepared.java:418` |
| `Prepared.getParameters()` | `h2/src/main/org/h2/command/Prepared.java:167` |
| `Prepared.getPersistedObjectId()` | `h2/src/main/org/h2/command/Prepared.java:291` |
| `Prepared.getPlanSQL()` | `h2/src/main/org/h2/command/Prepared.java:320` |

## 4.4 阅读路径

读 `org.h2.command` 的 12 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.command` 的 package-info 与 `Parser`，建立第4章的职责边界。
2. 再读 `Parser` 的 9 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.command`（本章最小包，15,026 行）的实现，关注容量与失败路径。

跨章衔接请对照第5章《进程内数据流》。

## 4.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.command` | `org.h2`, `org.h2.util`, `org.h2.expression`, `org.h2.expression.function` |

## 4.6 设计权衡

`org.h2.command` 有 12 个文件、15,026 行。平均每文件 1,252 行。

其中 `Parser` 独占 9,470 行，9 个公开方法。规模集中，风险也集中。

它对外声明 7 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.command`（15,026 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 4.7 常见误区

把 `org.h2.command` 的行数当作复杂度上限是误读。`Parser` 之外还有 11 个文件，其中多为类型族与样板。

只读 `Parser` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.command` 与 `org.h2.command` 不能互换。前者 12 个文件，后者 12 个文件，扩展点分布完全不同。

## 4.8 深读要点

规模信号：`org.h2.command` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.command` 依赖 7 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`Parser` 的公开方法 9 个，读它等于读本章的主干。

## 4.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **Deadlock**：详见[术语表](back/glossary.md)对应条目。
- **Expression**：详见[术语表](back/glossary.md)对应条目。
- **Index**：详见[术语表](back/glossary.md)对应条目。
- **IndexCondition**：详见[术语表](back/glossary.md)对应条目。
- **Meta Lock**：详见[术语表](back/glossary.md)对应条目。
- **MVMap**：详见[术语表](back/glossary.md)对应条目。
- **MVStore**：详见[术语表](back/glossary.md)对应条目。

## 4.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `Parser` | `org.h2.command` | 9,470 | 9 | 按方法名归纳 |
| `Tokenizer` | `org.h2.command` | 1,522 | 0 | 按方法名归纳 |

## 4.9 本章小结

- 本章覆盖 1 个包、15,026 行。
- 关键入口与源码坐标见 §4.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 4.10 延伸思考

**1. 🟢★ 说明 `Parser` 与 `Tokenizer` 的分工差异。给出调用方向。**

> 提示：第4章 §4.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

**2. 🔵★★ `Parser` 为什么独立成类型，而不是并入 `Tokenizer`？**

> 提示：第4章 §4.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

**3. 🟠★★★ 以 `Parser` 为入口，画出一次完整调用经过的包。**

> 提示：第4章 §4.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `Parser` 还是 `Tokenizer`？说明代价。**

> 提示：第4章 §4.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§4.2 核心类型

## 4.11 本章视角：性能与规模

- 以「性能与规模」看 `org.h2.command`：12 个文件、15,026 行，本章只展开与性能与规模相关的入口。
- 对照 `org.h2.command`（15,026 行）：两者的性能与规模策略不同，差异落在 `Parser` 的 9 个公开方法里。
- 若性能与规模假设被打破（7 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 4.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.command` | `org.h2` | 205 |
| `org.h2.command` | `org.h2.util` | 194 |
| `org.h2.command` | `org.h2.expression` | 76 |

## 4.11.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2.command` 与 `org.h2.command` 的调用方向？`Parser` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.command` 的调用链讲到落盘或返回，并说清 `org.h2.command` 与 `org.h2.command` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.command` 的注释与实现对不上，你信哪一边，为什么？

## 4.12 延展阅读

- 详见第5章《进程内数据流》。

# 第5章 进程内数据流

## 5.1 模块版图

本章覆盖 1 个包、15,026 行实现。

| 包 | 文件数 | 行数 | 职责 |
| --- | --- | --- | --- |
| `org.h2.command` | 12 | 15,026 | （无包注释，按主类型归纳） |

## 5.2 核心类型

在 `org.h2.command` 之外，本章还有 0 个包；下表每包取前 4 个类型，按规模降序。

### 5.2.1 `org.h2.command`

| 类型 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- |
| `Parser` | 9,470 | 9 | （无类注释，按方法名归纳） |
| `Tokenizer` | 1,522 | 0 | （无类注释，按方法名归纳） |
| `ParserBase` | 771 | 8 | （无类注释，按方法名归纳） |
| `Token` | 758 | 5 | （无类注释，按方法名归纳） |

## 5.3 关键 API 与源码坐标

把 1 个包的关键入口与源码位置对应起来，共 3 条坐标，行号由脚本核验。

| 入口 | 源码坐标 |
| --- | --- |
| `Parser.newPrimaryKeyConstraintCommand()` | `h2/src/main/org/h2/command/Parser.java:9178` |
| `Parser.parseDomainConstraintExpression()` | `h2/src/main/org/h2/command/Parser.java:9446` |
| `ParserBase.formatNonKeywords()` | `h2/src/main/org/h2/command/ParserBase.java:93` |
| `ParserBase.getLastParseIndex()` | `h2/src/main/org/h2/command/ParserBase.java:743` |

## 5.3.1 公共类型清单

本章抽样类型按包分组，共 5 行；规模与公开方法数是阅读优先级的第一信号。

| 类型 | 包 | 行数 | 公开方法 |
| --- | --- | --- | --- |
| `Parser` | `org.h2.command` | 9,470 | 9 |
| `Tokenizer` | `org.h2.command` | 1,522 | 0 |
| `ParserBase` | `org.h2.command` | 771 | 8 |
| `Token` | `org.h2.command` | 758 | 5 |
| `CommandInterface` | `org.h2.command` | 654 | 0 |

## 5.3.2 逐类导读

按本章主责包的类型规模顺序，给出每类"职责—规模—入口"三件事，便于按需下钻。

### 5.3.2.1 `Parser`

`Parser` 位于 `org.h2.command`，9,470 行、9 个公开方法。它占该包实现的 63%，包内排名第 1。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 5.3.2.2 `Tokenizer`

`Tokenizer` 位于 `org.h2.command`，1,522 行、0 个公开方法。它占该包实现的 10%，包内排名第 2。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 5.3.2.3 `ParserBase`

`ParserBase` 位于 `org.h2.command`，771 行、8 个公开方法。它占该包实现的 5%，包内排名第 3。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 5.3.2.4 `Token`

`Token` 位于 `org.h2.command`，758 行、5 个公开方法。它占该包实现的 5%，包内排名第 4。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 5.3.2.5 `CommandInterface`

`CommandInterface` 位于 `org.h2.command`，654 行、0 个公开方法。它占该包实现的 4%，包内排名第 5。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

### 5.3.2.6 `Prepared`

`Prepared` 位于 `org.h2.command`，503 行、33 个公开方法。它占该包实现的 3%，包内排名第 6。

职责一句话：按方法名与调用点归纳。读它之前先看包级依赖（7 个），再决定是否顺带读同包的相邻类型。

## 5.3.2 源码坐标明细

本章主责包中 19 个公开入口的行号，按类聚簇，可直接跳转阅读。

| 入口 | 源码坐标 |
| --- | --- |
| `Parser.newPrimaryKeyConstraintCommand()` | `h2/src/main/org/h2/command/Parser.java:9178` |
| `Parser.parseDomainConstraintExpression()` | `h2/src/main/org/h2/command/Parser.java:9446` |
| `Parser.parseExpression()` | `h2/src/main/org/h2/command/Parser.java:9434` |
| `Parser.parseTableName()` | `h2/src/main/org/h2/command/Parser.java:9463` |
| `Parser.prepare()` | `h2/src/main/org/h2/command/Parser.java:455` |
| `Parser.prepareCommand()` | `h2/src/main/org/h2/command/Parser.java:486` |
| `ParserBase.formatNonKeywords()` | `h2/src/main/org/h2/command/ParserBase.java:93` |
| `ParserBase.getLastParseIndex()` | `h2/src/main/org/h2/command/ParserBase.java:743` |
| `ParserBase.parseColumnList()` | `h2/src/main/org/h2/command/ParserBase.java:247` |
| `ParserBase.parseNonKeywords()` | `h2/src/main/org/h2/command/ParserBase.java:72` |
| `ParserBase.quoteIdentifier()` | `h2/src/main/org/h2/command/ParserBase.java:55` |
| `ParserBase.setLiteralsChecked()` | `h2/src/main/org/h2/command/ParserBase.java:215` |
| `Token.toString()` | `h2/src/main/org/h2/command/Token.java:476` |
| `Prepared.checkCanceled()` | `h2/src/main/org/h2/command/Prepared.java:340` |
| `Prepared.collectDependencies()` | `h2/src/main/org/h2/command/Prepared.java:486` |
| `Prepared.getCurrentRowNumber()` | `h2/src/main/org/h2/command/Prepared.java:418` |
| `Prepared.getParameters()` | `h2/src/main/org/h2/command/Prepared.java:167` |
| `Prepared.getPersistedObjectId()` | `h2/src/main/org/h2/command/Prepared.java:291` |
| `Prepared.getPlanSQL()` | `h2/src/main/org/h2/command/Prepared.java:320` |

## 5.4 阅读路径

读 `org.h2.command` 的 12 个文件时，先看骨架类，再沿 `org.h2` 方向下钻。

1. 先读 `org.h2.command` 的 package-info 与 `Parser`，建立第5章的职责边界。
2. 再读 `Parser` 的 9 个公开入口，确认它对 `org.h2` 的调用方向与加锁方式。
3. 最后读 `org.h2.command`（本章最小包，15,026 行）的实现，关注容量与失败路径。

跨章衔接请对照第4章《模块边界与依赖治理》。

## 5.5 依赖方向

下表按源码中的 `import` 统计给出包间依赖，规模即耦合强度；重构时优先看右侧出现频次最高的包。

| 包 | 依赖（前 4） |
| --- | --- |
| `org.h2.command` | `org.h2`, `org.h2.util`, `org.h2.expression`, `org.h2.expression.function` |

## 5.6 设计权衡

`org.h2.command` 有 12 个文件、15,026 行。平均每文件 1,252 行。

其中 `Parser` 独占 9,470 行，9 个公开方法。规模集中，风险也集中。

它对外声明 7 个 `org.h2` 依赖，最重的是 `org.h2`。依赖越集中，越说明它是被复用的底座。

与 `org.h2.command`（15,026 行）的分工是本章最该记住的边界。前者偏实现，后者偏编排。合并会打散扩展点。

## 5.7 常见误区

把 `org.h2.command` 的行数当作复杂度上限是误读。`Parser` 之外还有 11 个文件，其中多为类型族与样板。

只读 `Parser` 的签名而不看调用点，也会踩坑。真正的约束写在调用方的加锁顺序里。

`org.h2.command` 与 `org.h2.command` 不能互换。前者 12 个文件，后者 12 个文件，扩展点分布完全不同。

## 5.8 深读要点

规模信号：`org.h2.command` 占本章 100% 的实现行数，改动风险最高。
耦合信号：`org.h2.command` 依赖 7 个 `org.h2` 包，其中 `org.h2` 出现最频繁。
入口信号：`Parser` 的公开方法 9 个，读它等于读本章的主干。

## 5.8 术语对照

本章出现的专业术语与书末术语表的对应关系：

- **H2**：详见[术语表](back/glossary.md)对应条目。
- **CommitDecisionMaker**：详见[术语表](back/glossary.md)对应条目。
- **DDL**：详见[术语表](back/glossary.md)对应条目。
- **DML**：详见[术语表](back/glossary.md)对应条目。
- **FreeSpaceBitSet**：详见[术语表](back/glossary.md)对应条目。
- **RollbackDecisionMaker**：详见[术语表](back/glossary.md)对应条目。
- **Savepoint**：详见[术语表](back/glossary.md)对应条目。
- **Transaction**：详见[术语表](back/glossary.md)对应条目。

## 5.9 知识点清单

下表汇总本章必须记住的类型，按包分组；规模与公开方法数用于排阅读顺序。

| 类型 | 包 | 行数 | 公开方法 | 职责 |
| --- | --- | --- | --- | --- |
| `Parser` | `org.h2.command` | 9,470 | 9 | 按方法名归纳 |
| `Tokenizer` | `org.h2.command` | 1,522 | 0 | 按方法名归纳 |

## 5.9 本章小结

- 本章覆盖 1 个包、15,026 行。
- 关键入口与源码坐标见 §5.3。
- 职责优先取自注释，注释缺失处需结合调用点归纳。

## 5.10 延伸思考

**1. 🟢★ 说明 `Parser` 与 `Tokenizer` 的分工差异。给出调用方向。**

> 提示：第5章 §5.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

**2. 🔵★★ `Parser` 为什么独立成类型，而不是并入 `Tokenizer`？**

> 提示：第5章 §5.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

**3. 🟠★★★ 以 `Parser` 为入口，画出一次完整调用经过的包。**

> 提示：第5章 §5.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

**4. 🟢★★★★ 只保留一个类型时，你留 `Parser` 还是 `Tokenizer`？说明代价。**

> 提示：第5章 §5.2 的表格给出 `Parser` 的规模与公开方法数，先按那一行定位再进源码。
> 回顾：§5.2 核心类型

## 5.11 本章视角：并发与一致性

- 以「并发与一致性」看 `org.h2.command`：12 个文件、15,026 行，本章只展开与并发与一致性相关的入口。
- 对照 `org.h2.command`（15,026 行）：两者的并发与一致性策略不同，差异落在 `Parser` 的 9 个公开方法里。
- 若并发与一致性假设被打破（7 个依赖变化），最先受影响的调用链从 `org.h2` 进入。

## 5.11.1 依赖明细

按 `import` 出现次数排序，数值越大耦合越深，重构窗口越窄。

| 来源包 | 目标包 | 次数 |
| --- | --- | --- |
| `org.h2.command` | `org.h2` | 205 |
| `org.h2.command` | `org.h2.util` | 194 |
| `org.h2.command` | `org.h2.expression` | 76 |

## 5.11.2 阅读检查清单

本章给出 5 条自查项，逐条确认后再进入下一章。

读完本章，先自问三个问题。能否不看正文画出 `org.h2.command` 与 `org.h2.command` 的调用方向？`Parser` 是否涉及并发，依据是锁、可见性还是不可变？

再进一步，能否用一个入口把 `org.h2.command` 的调用链讲到落盘或返回，并说清 `org.h2.command` 与 `org.h2.command` 合并会丢掉哪个扩展点？

最后一条留给判断力：若 `org.h2.command` 的注释与实现对不上，你信哪一边，为什么？

## 5.12 跨章索引

本章引用但不展开的包，按下面这张表跳到主责章节阅读。

| 包 | 主责章节 |
| --- | --- |
| `org.h2.command` | 第4章《模块边界与依赖治理》 |

## 5.12 延展阅读

- 详见第4章《模块边界与依赖治理》。
