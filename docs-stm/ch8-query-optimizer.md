# 第8章 查询优化器深度解读

> **本章导读**: 本章深入分析 H2 查询优化器的实现，涵盖基于代价的优化框架、连接顺序选择、索引条件评估、表达式预处理和子查询优化等核心主题。
> **前置知识**: 第7章《SQL 执行全流程》§7.1（SELECT 执行流程）；第6章§6.8（Optimizer 算法基础）；第4章§4.1（Command 层）
> **章节要点**:
> - 理解查询优化的基本框架和代价估算模型
> - 掌握连接顺序选择的算法和策略
> - 熟悉索引条件下推和表达式优化的实现
> - 了解子查询和视图的优化处理
> **术语参考**: 本章涉及的专业术语详见书末[术语表](back/glossary.md)。

> 查询优化器是 SQL 执行的核心组件，其涉及的基础算法（B-Tree 索引、代价估算等）详见第6章《H2 数据库核心算法分析》。本章共 100 张插图，信息量较大，建议分段阅读。

本章结构：8.1 概述 Optimizer 框架，8.2 分析连接顺序优化，8.3 推导演绎代价模型，8.4 说明索引选择策略，8.5 讲解 TableFilter 代价估算，8.6 展示优化实现原语，8.7 展示完整优化流程图，8.8 总结全章要点。

---

## 8.1 Optimizer 类架构

### 8.1.1 类定义

源码位置：`org/h2/command/query/Optimizer.java`

```java
class Optimizer {
    private static final int MAX_BRUTE_FORCE_FILTERS = 7;
    private static final int MAX_BRUTE_FORCE = 2000;
    private static final int MAX_GENETIC = 500;

    private final TableFilter[] filters;
    private final Expression condition;
    private final SessionLocal session;
    private Plan bestPlan;
    private TableFilter topFilter;
    private double cost;
}
```

如图 7-61 所示，核心常量：
- `MAX_BRUTE_FORCE_FILTERS = 7` — 暴力枚举的最大表数
- `MAX_BRUTE_FORCE = 2000` — 混合策略的枚举上限
- `MAX_GENETIC = 500` — 遗传算法最大迭代次数

Optimizer 类的核心字段及其在优化过程中的作用：

```text
如图 8-1 所示，Optimizer 核心字段与用途
                        │
  ┌────────────────────┬────────────────────────────────────────────┐
  │ 字段                │ 用途                                       │
  ├────────────────────┼────────────────────────────────────────────┤
  │ filters            │ 输入: 参与连接的所有 TableFilter           │
  │                    │ 来源: Select.preparePlan() 传入             │
  │                    │ 长度: 即连接的表数量                        │
  ├────────────────────┼────────────────────────────────────────────┤
  │ condition          │ 输入: 完整的 WHERE 条件表达式              │
  │                    │ 用于: Plan.calculateCost() 中的条件可求值检查│
  ├────────────────────┼────────────────────────────────────────────┤
  │ session            │ 输入: 会话上下文                           │
  │                    │ 用于: 索引选择的会话级统计信息              │
  ├────────────────────┼────────────────────────────────────────────┤
  │ bestPlan           │ 输出: 当前找到的最优 Plan                 │
  │                    │ 初始: null (首次 testPlan 后更新)          │
  ├────────────────────┼────────────────────────────────────────────┤
  │ topFilter          │ 输出: 最优计划的头节点 TableFilter         │
  │                    │ 最终: Select.topTableFilter = this         │
  ├────────────────────┼────────────────────────────────────────────┤
  │ cost               │ 输出: 最优计划的代价                       │
  │                    │ 初始: -1 (表示尚未找到可行计划)            │
  │                    │ 用于: canStop() 的提前终止判断             │
  └────────────────────┴────────────────────────────────────────────┘
```
**图 8-1: 罗列 Optimizer 五个核心字段及其用途**
```text
如图 8-2 所示，Optimizer 字段的运行时关系
                        │
  Select.preparePlan()
    │
    ├── new Optimizer(filters, condition, session)
    │     │
    │     ├── this.filters = filters        ← TableFilter[]
    │     │     (长度 n = 连接的表数量)     ← 关键输入
    │     │
    │     ├── this.condition = condition    ← Expression (WHERE 条件)
    │     │
    │     └── this.session = session        ← SessionLocal (统计信息)
    │
    ├── optimizer.optimize()
    │     │
    │     ├── calculateBestPlan()
    │     │     │
    │     │     ├── 策略选择（根据 filters.length)
    │     │     ├── 生成最佳排列
    │     │     └── cost = 最终的最优代价 (或 -1 如无可行计划)
    │     │
    │     ├── bestPlan = 当前最优 Plan 对象
    │     │     (比较每个 testPlan 返回的 Plan)
    │     │
    │     └── topFilter = bestPlan.filters[0]
    │
    └── 输出: topFilter (已链接所有其他 TableFilter)
          └── 每个 TableFilter 已通过 setPlanItem() 设置索引
```
**图 8-2: 追踪 Optimizer 字段在运行时的赋值流转**

### 8.1.2 构造与入口

```java
Optimizer(TableFilter[] filters, Expression condition, SessionLocal session)
```

如图 8-1 所示，在 `Select.preparePlan()` 中创建并调用：

```java
// Select.java:1359
Optimizer optimizer = new Optimizer(topArray, condition, session);
optimizer.optimize(parse, isSelectCommand);
topTableFilter = optimizer.getTopFilter();
```

Optimizer 对象从创建到产出最优计划的完整生命周期：

```text
Optimizer 对象生命周期
                        │
  创建: new Optimizer(filters, condition, session)
    │
    ├── 初始化: 接收 TableFilter 数组和 WHERE 条件
    ├── 状态: bestPlan=null, cost=-1, topFilter=null
    │
    ▼
  优化: optimizer.optimize(parse, isSelectCommand)
    │
    ├── parse=true? (视图解析阶段)
    │     └── YES → calculateFakePlan()
    │                  └── 创建简单的 fake plan (不执行真实代价计算)
    │
    ├── parse=false? (真实查询优化)
    │     └── YES → calculateBestPlan(isSelectCommand)
    │                  └── 选择策略 → 生成候选 Plan → 选最优
    │
    └── 后处理:
          ├── bestPlan.removeUnusableIndexConditions()
          ├── 设置 topFilter 链
          └── 设置每个 TableFilter 的 PlanItem
    │
    ▼
  结果获取: optimizer.getTopFilter()
    │
    └── 返回: topFilter (已设置 PlanItem 和 join 链)
          └── Select.topTableFilter = topFilter
```
**图 8-3: 追踪 Optimizer 从构造到产出计划的生命周期**

如图 8-3 所示，Optimizer 对象的生命周期包括三个阶段：创建（接收输入参数）、优化（选择策略并生成最优计划）、结果获取（返回配置完成的 TableFilter 链）。`parse` 参数区分了两种模式：视图解析阶段仅生成占位计划，真实查询优化阶段才执行代价计算和策略选择。

```text
构造方法与 Select.preparePlan() 的交互
                        │
  Select.preparePlan()
    │
    ├── 1. 创建 Optimizer
    │     new Optimizer(filters, condition, session)
    │     │
    │     └── filters 来源:
    │           ├── FROM user u               → TableFilter(u)
    │           ├── JOIN orders o             → TableFilter(o)
    │           └── JOIN order_items i        → TableFilter(i)
    │
    ├── 2. 调用 optimize(true)  ← 初次优化
    │     │
    │     └── 内部: calculateBestPlan(true)
    │           ├── 评估每个候选排列
    │           └── 找到最优 Plan
    │
    ├── 3. 获取结果
    │     topTableFilter = optimizer.getTopFilter()
    │
    └── 4. 设置链接
          topFilter.addJoin(optimizer.getTopFilter())
          (将优化后的计划挂载到 Select 的 topFilter 下)
```
**图 8-4: 拆解 Optimizer 与 preparePlan 的交互**

### 8.1.3 `optimize()` 主方法

如图 8-4 所示，源码位置：`Optimizer.java:237`

```java
void optimize(boolean parse, boolean isSelectCommand) {
    if (parse) {
        calculateFakePlan();          // 视图解析阶段，无需真实代价计算
    } else {
        calculateBestPlan(isSelectCommand); // 选择最优计划
        bestPlan.removeUnusableIndexConditions(); // 清理无用索引条件
    }
    // 将最优计划的 TableFilter 链连接起来
    TableFilter[] f2 = bestPlan.getFilters();
    topFilter = f2[0];
    for (int i = 0; i < f2.length - 1; i++) {
        f2[i].addJoin(f2[i + 1], false, null);
    }
    // 为每个 TableFilter 设置 PlanItem（索引 + 代价）
    for (TableFilter f : f2) {
        PlanItem item = bestPlan.getItem(f);
        f.setPlanItem(item);
    }
}
```

`optimize()` 方法包含两个主要阶段——计划生成和结果组装：

```text
optimize() 两阶段流程
                        │
  ┌──────────────────────────────────────────────────────────────┐
  │  阶段 1: 计划生成                                              │
  │                                                               │
  │  parse?                                                       │
  │    │                                                          │
  │    ├── YES: calculateFakePlan()                               │
  │    │     └── 生成占位计划 (视图解析时使用)                     │
  │    │         bestPlan = new Plan(...)                         │
  │    │                                                          │
  │    └── NO: calculateBestPlan()                                │
  │          └── 选择连接顺序 + 索引 + 计算代价                    │
  │              bestPlan = 代价最低的 Plan                        │
  │                                                               │
  │  产出: bestPlan (包含 filters 排序 + planItems)              │
  └────────────────────────────┬─────────────────────────────────┘
                               │
  ┌────────────────────────────┴─────────────────────────────────┐
  │  阶段 2: 结果组装                                              │
  │                                                               │
  │  步骤 A: 移除无用索引条件                                      │
  │    bestPlan.removeUnusableIndexConditions()                   │
  │    └── 清理 start/end 条件中恒假的索引条件                     │
  │                                                               │
  │  步骤 B: 建立 TableFilter 链                                  │
  │    topFilter = bestPlan.filters[0]                            │
  │    for i = 0 to n-2:                                          │
  │      filters[i].addJoin(filters[i+1], false, null)            │
  │    └── 形成: topFilter → T2 → T3 → ... → Tn                  │
  │                                                               │
  │  步骤 C: 设置 PlanItem                                        │
  │    for each f in filters:                                     │
  │      f.setPlanItem(bestPlan.getItem(f))                       │
  │    └── 每个 TableFilter 获得选中的索引 + 代价 + 掩码           │
  │                                                               │
  │  产出: topTableFilter (完全配置, 可供执行)                   │
  └──────────────────────────────────────────────────────────────┘
```
**图 8-5: 拆解 optimize 计划生成与结果组装两阶段**

如图 8-5 所示，优化过程分为计划生成和结果组装两个阶段。计划生成阶段根据 `parse` 标志决定是否执行真实代价计算；结果组装阶段将最优计划转换为可执行的 TableFilter 链结构。这种分离使得优化器的核心逻辑（代价计算 + 策略选择）与后处理逻辑（链组装 + 属性设置）保持独立，便于测试和调试。

```text
optimize() 方法的 parse 参数影响
                        │
  optimize(boolean parse)
    │
    ├── parse = true (视图解析阶段)
    │     │
    │     ├── calculateBestPlan(true)
    │     │     ├── testPlan(list, true)
    │     │     │     └── Plan.calculateCost(session, ..., true)
    │     │     │           └── isSelectCommand = true
    │     │     │                → 跳过更新操作的代价检查
    │     │     └── 正常选择最优计划
    │     │
    │     └── 用途: 创建视图或子查询时的初始化
    │           只需生成基础计划结构, 不涉及实际执行
    │
    ├── parse = false (真实查询优化)
    │     │
    │     ├── calculateBestPlan(false)
    │     │     └── testPlan(list, false)
    │     │           └── Plan.calculateCost(session, ..., false)
    │     │                 └── isSelectCommand = false
    │     │                      → 考虑更新操作 (如 SELECT FOR UPDATE)
    │     │
    │     └── 后续操作:
    │           ├── bestPlan.removeUnusableIndexConditions()
    │           ├── linkJoin(topFilter, ...)
    │           └── 设置 PlanItem
    │
    └── getTopFilter() → 两种模式都返回配置好的 topFilter
```
**图 8-6: 对比 parse 真假两种模式下 optimize 的差异**

### 8.1.4 三种策略的调度

```java
// Optimizer.java:78
private void calculateBestPlan(boolean isSelectCommand) {
    cost = -1;
    if (filters.length == 1) {
        testPlan(filters, isSelectCommand);          // 单表，直接评估
    } else {
        startNs = System.nanoTime();
        if (filters.length <= MAX_BRUTE_FORCE_FILTERS) {
            calculateBruteForceAll(isSelectCommand);  // ≤7表: 暴力枚举
        } else {
            calculateBruteForceSome(isSelectCommand); // 8+表: 混合策略
            random = new Random(0);
            calculateGenetic(isSelectCommand);        // 遗传算法
        }
    }
}
```

如图 8-6 所示，决策树：

```text
TableFilter 数量
    │
    ├── 1 个 ─→ testPlan()：单表直接评估
    │
    ├── 2-7 个 ─→ calculateBruteForceAll()
    │      枚举所有排列 O(n!)
    │      2! = 2, 3! = 6, ..., 7! = 5040
    │
    └── 8+ 个 ─→ calculateBruteForceSome()
    │      暴力枚举前 m 个表 + 贪心选剩余
    │      +
    │      calculateGenetic()
    │      随机变异迭代 500 轮
    │
    └── 任一策略可被 canStop() 提前终止
```

每种策略的适用场景和性能特征可以通过以下对比表快速理解：

```text
如图 8-7 所示，三种策略对比
                        │
  ┌──────────────────┬────────────┬─────────────┬──────────────────────┐
  │ 策略              │ 适用表数   │ 时间复杂度  │ 计划质量              │
  ├──────────────────┼────────────┼─────────────┼──────────────────────┤
  │ testPlan (单表)   │ 1          │ O(1)        │ 最优 (只有一种选择)   │
  ├──────────────────┼────────────┼─────────────┼──────────────────────┤
  │ BruteForceAll    │ 2-7        │ O(n!)       │ 最优 (全覆盖)        │
  │                  │            │ 2!=2 ~ 7!=5040                    │
  ├──────────────────┼────────────┼─────────────┼──────────────────────┤
  │ BruteForceSome   │ 8+         │ O(P(n,m))   │ 接近最优             │
  │ + Genetic        │            │ + O(500)    │ 通常是前 90%         │
  └──────────────────┴────────────┴─────────────┴──────────────────────┘
```
**图 8-7: 对比三种策略的适用表数与时间复杂度**
```text
如图 8-8 所示，calculateBestPlan() 完整决策流程
                        │
  calculateBestPlan(isSelectCommand)
    │
    ├── cost = -1   (重置)
    │
    ├── filters.length == 1?
    │     └── YES → testPlan(filters, isSelectCommand)
    │
    ├── filters.length <= MAX_BRUTE_FORCE_FILTERS (7)?
    │     └── YES → calculateBruteForceAll(isSelectCommand)
    │           ├── Permutations.create(filters, list)
    │           └── for x: !canStop(x) && p.next()
    │                 └── testPlan(list, isSelectCommand)
    │
    └── filters.length >= 8?
          │
          ├── calculateBruteForceSome(isSelectCommand)
          │     └── 暴力前 m 个 + 贪心剩余
          │
          └── calculateGenetic(isSelectCommand)
                └── 500 轮随机变异
          │
          └── 保留两种策略中代价最低的 Plan
    │
    └── 结果: bestPlan (或 null 如无可行计划)
          └── cost = bestPlan.calculateCost() (最优代价)
```
**图 8-8: 追踪 calculateBestPlan 按表数派发策略**

### 8.1.5 提前终止机制

```java
private boolean canStop(int x) {
    return (x & 127) == 0
            && cost >= 0
            && System.nanoTime() - startNs > cost * 100_000L;
}
```

如图 8-7 所示，条件：每 128 次迭代检查一次，当已找到可行计划（cost >= 0）且耗时超过 `cost * 100μs` 时停止。这意味着如果当前最优代价为 1000，超过 100ms 后就停止搜索。

`canStop()` 的检查频次和停止条件可以通过以下判定流程理解：

```text
canStop() 判定流程与效果
                        │
  每 128 次迭代调用一次 canStop(x)
    │
    ├── (x & 127) == 0?
    │     ├── NO → 跳过, 继续搜索
    │     └── YES → 进入条件判断
    │
    ├── cost >= 0?
    │     ├── NO → 尚无可行计划, 继续搜索
    │     └── YES → 已找到至少一个可行计划
    │
    └── elapsed > cost * 100μs?
          ├── NO → 搜索时间未超阈值, 继续搜索
          └── YES → 停止搜索
                │
                └── 提前终止, 使用当前最优计划

  不同代价下的停止阈值:
  ┌──────────────┬────────────┬────────────────────────────────┐
  │ 最优代价     │ 停止阈值   │ 行为                           │
  ├──────────────┼────────────┼────────────────────────────────┤
  │ 1            │ 100μs     │ 非常容易触发 (几乎立即停止)     │
  │ 10           │ 1ms       │ 容易触发                       │
  │ 100          │ 10ms      │ 可能触发                       │
  │ 1000         │ 100ms     │ 较难触发 (搜索全部排列)         │
  │ 10000        │ 1s        │ 极难触发 (搜索全部排列)         │
  └──────────────┴────────────┴────────────────────────────────┘
```

以下三张图共同呈现 canStop 提前终止机制与 Optimizer 对象网络的衔接：图 8-9 拆解三层判定逻辑与不同代价下的停止阈值，图 8-10 演示六表场景下的终止行为差异，图 8-11 则概览 Optimizer 与核心协作对象的关系网络。

**图 8-9: 拆解 canStop 三层判定与不同代价的停止阈值**

如图 8-9 所示，提前终止机制的核心思想是"收益递减"：如果在当前最优计划的代价对应的搜索时间内没有找到更好的计划，那么继续搜索也不太可能找到显著更优的解。`cost * 100μs` 这个公式的含义是：搜索时间与当前最优计划的代价成正比——代价越高的查询（通常是全表扫描类型的查询），搜索空间越大，但优化器愿意为之付出的搜索时间也越多。

如图 8-10 所示，不同代价阈值下 canStop() 的触发时机和搜索范围有显著差异：

```text
如图 8-11 所示，canStop() 在实际搜索中的表现分析
                        │
  6 表连接: 6! = 720 种排列, 不同代价下的终止行为
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  发现代价为 10 的计划                                               │
  │    ├── threshold = 10 × 100μs = 1ms                                │
  │    ├── 搜索约 240 种排列后停止 (第 1/3 处)                         │
  │    └── 如果前 240 种排列已包含最优, 则无质量损失                   │
  │                                                                     │
  │  发现代价为 50 的计划                                               │
  │    ├── threshold = 50 × 100μs = 5ms                                │
  │    ├── 搜索约 600 种排列后停止 (接近全部)                           │
  │    └── 基本完成全部 720 种排列的评估                                │
  │                                                                     │
  │  发现代价为 100 的计划                                              │
  │    ├── threshold = 100 × 100μs = 10ms                              │
  │    ├── 10ms 远超评估全部 720 种排列所需时间                         │
  │    └── 搜索全部 720 种排列, canStop() 不会被触发                   │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  优点:
    ├── 高选择性查询: 快速找到好计划, 立即停止, 节省 CPU
    ├── 低选择性查询: 搜索全部排列, 不会过早停止
    └── 自动适应: 无需人工配置阈值参数
                        │
  潜在问题:
    └── 如果好计划出现在搜索空间的末尾 (例如第 700 种排列)
         但前 240 种排列中就找到了代价为 10 的计划
         则搜索会在 1ms 后停止, 错过末尾更好的计划
         → 但在实际中, 搜索空间是随机分布的, 好计划在各处均可能出现
```
**图 8-10: 演示 canStop 在六表搜索下的终止行为差异**

### 8.1.6 Optimizer 整体架构与对象关系

**图 8-11: 概览 Optimizer 与核心协作对象的关系网络**

```text
Optimizer 核心对象关系图:

┌──────────────────────────────────────────────────────────────────────────┐
│  Select.preparePlan()                                                    │
│    │                                                                     │
│    ├── new Optimizer(filters, condition, session)                        │
│    │      │                                                              │
│    │      │  Optimizer 对象                                              │
│    │      │  ┌────────────────────────────────────────────────────────┐  │
│    │      │  │  fields:                                              │  │
│    │      │  │    filters: TableFilter[]     ← 参与连接的所有表      │  │
│    │      │  │    condition: Expression       ← WHERE 条件           │  │
│    │      │  │    bestPlan: Plan              ← 当前最优计划         │  │
│    │      │  │    topFilter: TableFilter      ← 最优计划的头节点     │  │
│    │      │  │    cost: double                ← 最优计划代价         │  │
│    │      │  │                                 │                      │  │
│    │      │  │  constants:                    │                      │  │
│    │      │  │    MAX_BRUTE_FORCE_FILTERS = 7 │                      │  │
│    │      │  │    MAX_BRUTE_FORCE        = 2000│                      │  │
│    │      │  │    MAX_GENETIC            = 500│                      │  │
│    │      │  └────────────────────────────────┼──────────────────────┘  │
│    │      │                                   │                         │
│    │      │  Optimizer.optimize()             │                         │
│    │      │    │                              │                         │
│    │      │    ├── calculateBestPlan()        │                         │
│    │      │    │    │                         │                         │
│    │      │    │    ├── 单表: testPlan()      │                         │
│    │      │    │    ├── ≤7 表: bruteForceAll()│                         │
│    │      │    │    └── ≥8 表: bruteForceSome │                         │
│    │      │    │              + genetic()     │                         │
│    │      │    │                              │                         │
│    │      │    ├── 设置 topFilter 链          │                         │
│    │      │    └── 设置 planItem              │                         │
│    │      │                                   │                         │
│    │      └───────────────────────────────────┘                         │
│    │                                                                     │
│    ├── optimizer.getTopFilter()  ← 获取最优计划头节点                   │
│    │                                                                     │
│    └── topTableFilter = optimizer.getTopFilter()                         │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                          │
                          │  Plan 对象
                          │  ┌──────────────────────────────────────────┐
                          │  │  filters: TableFilter[]    ← 排列顺序   │
                          │  │  planItems: HashMap        ← 索引选择   │
                          │  │  allConditions: Expression[] ← 条件数组 │
                          │  │                                           │
                          │  │  calculateCost(session) → double         │
                          │  │    │                                      │
                          │  │    └── 迭代所有 TableFilter:             │
                          │  │          for each f in allFilters:       │
                          │  │            item = f.getBestPlanItem()    │
                          │  │            cost += cost * item.cost      │
                          │  │                                           │
                          │  └──────────────────────────────────────────┘
                          │
                          │  PlanItem 对象 (对应每个 TableFilter)
                          │  ┌──────────────────────────────────────────┐
                          │  │  cost: double           ← 估计代价      │
                          │  │  index: Index           ← 选中的索引    │
                          │  │  masks: int[]           ← 索引条件掩码  │
                          │  │  joinPlan: PlanItem     ← 连接子计划    │
                          │  │  nestedJoinPlan: PlanItem ← 嵌套连接    │
                          │  └──────────────────────────────────────────┘

如图 8-82 所示，调用流程:
  Select.preparePlan()
    → new Optimizer(filters, condition, session)
    → optimizer.optimize()
      → calculateBestPlan()
        → testPlan(list) 或 calculateBruteForceAll() 或 calculateGenetic()
          → new Plan(list, len, condition)
            → plan.calculateCost(session, ...)
              → tableFilter.getBestPlanItem(...)
                → table.getBestPlanItem(...)
                  → index.getCost(...)
```
**图 8-82: 概览 Optimizer 三层对象的调用栈**

该图展示了 Optimizer 核心的三个对象层次及其协作关系：

```text
如图 8-12 所示，Optimizer 运行时协作时序
                        │
  Select.preparePlan()
    │
    ├── 1. 构造 Optimizer 对象
    │      new Optimizer(filters, condition, session)
    │      │
    │      ├── filters[]: 参与连接的所有 TableFilter
    │      ├── condition: 完整 WHERE 表达式树
    │      └── session: 会话上下文 (含统计信息)
    │
    ├── 2. optimizer.optimize()  →  calculateBestPlan()
    │      │
    │      │  策略选择 (根据表数量):
    │      │    ├── 单表  → testPlan()
    │      │    │     └── Plan.calculateCost() → PlanItem 填充
    │      │    │
    │      │    ├── 2-7表 → calculateBruteForceAll()
    │      │    │     └── Permutations 生成 n! 种排列
    │      │    │         └── 每排列: new Plan → calculateCost()
    │      │    │
    │      │    └── ≥8表 → 混合 + 遗传算法
    │      │          ├── calculateBruteForceSome()
    │      │          └── calculateGenetic()
    │      │
    │      └── 结果: bestPlan (代价最低)
    │
    ├── 3. 计划落地
    │      ├── topFilter = bestPlan.filters[0]
    │      ├── linkJoin(topFilter, bestPlan.filters[1..n])
    │      └── 设置每个 TableFilter 的 PlanItem
    │
    └── 4. 执行阶段
           └── topFilter.next() 循环
                 ├── cursor.find() → 索引定位
                 ├── cursor.next() → 行迭代
                 └── join.next() → 内表嵌套循环
```
**图 8-12: 追踪 Optimizer 与子组件的运行时协作时序**

1. **Optimizer** 是策略调度器，持有完整的 TableFilter 数组和 WHERE 条件，负责根据表数量选择合适的连接顺序策略。通过 `calculateBestPlan()` 方法生成候选 Plan，并在所有 Plan 中选择代价最低的。最终通过 `getTopFilter()` 返回最优计划的头节点。

2. **Plan** 是一个候选执行计划，包含表的访问顺序（filters 数组）和每个表对应的 PlanItem。`calculateCost()` 方法计算该计划的总体代价，采用复合乘法公式逐步累加。无效计划（join condition 引用了尚未出现的表）的代价为无穷大。

如图 8-13 所示，3. **PlanItem** 是 Plan 的组成部分，为每个 TableFilter 记录选中的索引、估计代价和索引条件掩码。多个 PlanItem 通过 `joinPlan` 和 `nestedJoinPlan` 字段描述连接关系。

### 8.1.7 三种策略协作流程

**图 8-13: 串联三种策略在 calculateBestPlan 中的协作**

```text
如图 8-83 所示，calculateBestPlan() 三种策略协作概览
  │
  ├── 输入: filters[] (长度 n)
  │         condition (WHERE 条件)
  │         session (会话上下文)
  │
  ├── 步骤 1: 判断 n 值
  │     │
  │     ├── n == 1:
  │     │     testPlan(filters)           ← 单表, 直接评估
  │     │     (无排列组合, 仅需选择索引)
  │     │
  │     ├── 2 <= n <= 7:
  │     │     calculateBruteForceAll()    ← 暴力枚举
  │     │     枚举 n! 种排列
  │     │     每排列: testPlan(list)
  │     │     时间复杂度: O(n!)
  │     │
  │     └── n >= 8:
  │           │
  │           ├── calculateBruteForceSome()  ← 混合策略
  │           │     暴力枚举前 m 个位置
  │           │     贪心填充剩余位置
  │           │     m = getMaxBruteForceFilters(n)
  │           │     时间复杂度: O(P(n,m) × n²)
  │           │
  │           └── calculateGenetic()         ← 遗传算法
  │                 随机初始化排列
  │                 最多 500 轮迭代
  │                 每轮: 交换两表或完全洗牌
  │                 保留最优解
  │
  ├── 步骤 2: 汇总结果
  │     bestPlan = 代价最低的 Plan
  │     topFilter = bestPlan.filters[0]    ← 头节点
  │     linkJoin(topFilter, ...)           ← 连接 TableFilter 链
  │     for each f in bestPlan.filters:
  │         f.setPlanItem(bestPlan.getItem(f))  ← 设置索引选择
  │
  └── 输出: topTableFilter (已设置索引和 PlanItem)
```

下面三张图分别从输入分派、特性对比与判定决策三个角度刻画 calculateBestPlan 的策略调度：图 8-83 串联三种策略的输入分派与结果汇总，图 8-14 对比三种策略的搜索方式与计划质量，图 8-15 拆解 canStop 决策树及其对搜索行为的影响。

**图 8-83: 串联三种策略的输入分派与结果汇总**

该图将三种策略视为一个统一的调度框架。`calculateBestPlan()` 方法的职责不是自己搜索，而是根据输入特征（表数量）选择合适的搜索策略，并将最终结果组装为一致的输出格式（topFilter + PlanItems）。这种策略模式（Strategy Pattern）的设计使新增搜索策略较为容易——只需要实现一个新的策略方法，并在 `calculateBestPlan()` 中添加对应的调度条件。如图 8-14 所示，三种策略在搜索方式、时间复杂度和计划完备性上各有侧重。

```text
如图 8-15 所示，三种策略特性对比
                        │
  ┌────────────────────────────────────────────────────────────────────────┐
  │  维度            暴力枚举             混合策略             遗传算法    │
  ├────────────────────────────────────────────────────────────────────────┤
  │  适用表数        ≤7                   ≥8                  ≥8          │
  │  方法名          bruteForceAll()      bruteForceSome()    genetic()   │
  │  搜索方式        完全枚举             部分枚举+贪心        随机变异     │
  │  完备性          100%                 部分完备             不完备      │
  │  时间复杂度      O(n!)               O(P(n,m)×n²)        O(500)      │
  │  空间复杂度      O(n)                O(n)                O(n)        │
  │  计划质量        全局最优             近似最优             近似最优    │
  │  可提前终止      支持 (canStop)       支持 (canStop)       支持       │
  ├────────────────────────────────────────────────────────────────────────┤
  │                                                                        │
  │  阈值控制:                                                              │
  │    MAX_BRUTE_FORCE_FILTERS = 7   → 暴力枚举的最大表数                   │
  │    MAX_BRUTE_FORCE        = 2000 → 混合策略的最大评估次数               │
  │    MAX_GENETIC            = 500  → 遗传算法的最大迭代轮数               │
  │                                                                        │
  │  选择逻辑:                                                              │
  │    表数 1   → 直接评估, 无排列组合                                      │
  │    表数 2-7 → 暴力枚举全部排列                                          │
  │    表数 ≥8  → 同时运行混合 + 遗传, 取最优                              │
  └────────────────────────────────────────────────────────────────────────┘
```
**图 8-14: 对比三种策略的搜索方式与计划质量**

### 8.1.8 提前终止机制决策树

**图 8-15: 拆解 canStop 决策树及其对搜索行为的影响**

```text
canStop(x) 决策树                     x = 迭代次数
                                         │
  canStop(x)                             │
    return (x & 127) == 0               ├── 每 128 次迭代检查一次?
         && cost >= 0                   │     │
         && System.nanoTime()           │     ├── NO → 继续搜索
           - startNs > cost * 100_000L; │     │
                                         │     └── YES → 继续检查
                                         │           │
                                         ▼           ▼
                                    ┌────────────────────────────┐
                                    │ (x & 127) == 0 条件        │
                                    │ 仅当 x 是 128 的倍数时成立  │
                                    │ x=0, 128, 256, 384, ...    │
                                    └────────────┬───────────────┘
                                                 │
                                    ┌────────────▼───────────────┐
                                    │ cost >= 0?                 │
                                    │ (是否已有可行计划)          │
                                    │                            │
                                    │ YES → 继续检查耗时条件     │
                                    │ NO  → 继续搜索             │
                                    └────────────┬───────────────┘
                                                 │
                                    ┌────────────▼───────────────┐
                                    │ 耗时 > cost * 100μs?       │
                                    │                            │
                                    │ elapsed = nanoTime - start │
                                    │ threshold = cost * 100_000 │
                                    │                            │
                                    │ YES → 停止搜索              │
                                    │ NO  → 继续搜索              │
                                    └────────────┬───────────────┘
                                                 │
                                                 ▼
                                            停止 / 继续

  如图 8-84 所示，canStop 对搜索的影响 (以 6 表连接为例):
    │
    ├── 6! = 720 种排列
    │
    ├── 假设 testPlan 发现一个代价为 50 的计划
    │     │
    │     ├── threshold = 50 × 100μs = 5ms
    │     ├── 如果搜索超过 5ms 即停止
    │     └── 在 5ms 内通常可完成 720 种排列的评估
    │
    ├── 假设 testPlan 发现一个代价为 500 的计划
    │     │
    │     ├── threshold = 500 × 100μs = 50ms
    │     ├── 50ms 远超评估 720 种排列所需时间
    │     └── 意味着: 搜索实际上不会提前停止
    │
    └── 结论: canStop 在低成本 (高选择性) 查询中更有效
              低成本 → 阈值低 → 容易触发停止
              高成本 → 阈值高 → 搜索到全部排列
```
**图 8-84: 拆解 canStop 提前终止的判定决策树**

`canStop()` 是 H2 优化器的智能中止机制。其核心理念是：如果已经找到了足够好的计划，就不必浪费 CPU 时间来搜索所有排列。决策逻辑分为三个层次：

```text
如图 8-16 所示，canStop() 在不同查询类型中的效果对比
                        │
  查询类型 A: 高选择性 (等值条件, 主键查找)
    │
    WHERE id = 100       ← 主键等值
    │
    ├── 找到的 Plan:
    │     cost = 1 (主键等值查找)
    │
    ├── 停止阈值:
    │     threshold = 1 × 100μs = 100μs
    │
    ├── 实际行为:
    │     首次迭代 (x=0) 调用 canStop(0)
    │     (0 & 127) == 0 → YES
    │     cost >= 0      → YES (cost=1)
    │     elapsed > 100μs? → 几乎立即满足
    │
    └── 结果: 在几个微秒内停止, 几乎不搜索排列
                        │
  查询类型 B: 中等选择性 (范围条件)
    │
    WHERE status = 'ACTIVE'   ← 二级索引, 估计 30% 行
    │
    ├── 找到的 Plan:
    │     cost = 3000 (非唯一索引扫描)
    │
    ├── 停止阈值:
    │     threshold = 3000 × 100μs = 300ms
    │
    ├── 实际行为:
    │     可以评估相当多的排列后才停止
    │     对于 6 表连接 (720 排列), 通常可完成全部评估
    │     对于 8 表连接 (40320 排列), 会提前停止
    │
    └── 结果: 搜索充分, 找到接近最优的计划
                        │
  查询类型 C: 低选择性 (无过滤条件)
    │
    (无 WHERE)          ← 全表扫描
    │
    ├── 找到的 Plan:
    │     cost = 10000 (全表扫描)
    │
    ├── 停止阈值:
    │     threshold = 10000 × 100μs = 1s
    │
    ├── 实际行为:
    │     通常远超过暴力枚举或遗传算法的完成时间
    │     搜索完整轮次后才自然结束
    │
    └── 结果: 搜索全部排列, 不会提前终止
                        │
  总结:
    ┌────────────────────────────────────────────────────────────────┐
    │  查询类型        典型代价    阈值      搜索程度               │
    ├────────────────────────────────────────────────────────────────┤
    │  主键等值         1          100μs    几乎不搜索, 立即返回     │
    │  唯一索引等值     10         1ms      有限搜索                 │
    │  普通索引扫描     100-1000   10-100ms  搜索较充分              │
    │  全表扫描         10000+     1s+      搜索全部排列             │
    └────────────────────────────────────────────────────────────────┘
```
**图 8-16: 对比 canStop 在三类选择性下的效果差异**

1. **频率控制**：`(x & 127) == 0` 确保检查操作每 128 次迭代才执行一次，避免高频率的 `System.nanoTime()` 调用影响性能。

2. **可行性检查**：`cost >= 0` 确保至少已找到一个可行计划。如果在第 128 次迭代时尚未找到任何有效计划（所有候选计划均为无效），则继续搜索。

3. **收益/成本权衡**：`elapsed > cost * 100μs` 是核心的权衡条件。`cost` 是当前最优计划的估计代价，`100μs` 是"每代价单位愿意支付的搜索时间"。如果一个计划的代价为 100，则最多愿意花 10ms 来搜索更好的计划。当已用搜索时间超过这个阈值时，搜索提前终止。

这种机制在实际应用中表现良好：对于选择性高的查询（如主键等值查找），优化器很快找到低代价计划并提前终止；对于全表扫描型查询（代价高），优化器会搜索所有排列以确保找到最佳连接顺序。

---

## 8.2 三种连接顺序策略

### 8.2.1 暴力枚举 — `calculateBruteForceAll()`

源码位置：`Optimizer.java:107`

```java
private void calculateBruteForceAll(boolean isSelectCommand) {
    TableFilter[] list = new TableFilter[filters.length];
    Permutations<TableFilter> p = Permutations.create(filters, list);
    for (int x = 0; !canStop(x) && p.next(); x++) {
        testPlan(list, isSelectCommand);
    }
}
```

如图 8-11 所示，利用 `Permutations` 工具类生成所有排列，逐个评估代价。

排列数量：

| 表数 | 排列数 | 可行 |
|------|--------|------|
| 1    | 1      | 直接评估 |
| 2    | 2      | 暴力 |
| 3    | 6      | 暴力 |
| 4    | 24     | 暴力 |
| 5    | 120    | 暴力 |
| 6    | 720    | 暴力 |
| 7    | 5,040  | 暴力 |
| 8    | 40,320 | 混合 |

7! = 5040 仍在合理范围，8! = 40320 开始显著变慢，因此在 8 表及以上切换策略。

```text
如图 8-17 所示，calculateBruteForceAll() 执行流程
                        │
  输入: filters[] (n 个 TableFilter)
                        │
                        ▼
  1. 创建输出数组 list = new TableFilter[n]
                        │
                        ▼
  2. 创建排列生成器 p = Permutations.create(filters, list)
                        │
                        ▼
  3. 循环: for (x = 0; !canStop(x) && p.next(); x++)
                        │
     ┌──────────────────────────────────────────────────────┐
     │  每次迭代:                                            │
     │                                                      │
     │  步骤 A: p.next() 生成下一排列                        │
     │    ├── 第 1 次: [T1, T2, T3, T4]  (初始排列)         │
     │    ├── 第 2 次: [T1, T2, T4, T3]                     │
     │    ├── 第 3 次: [T1, T3, T2, T4]                     │
     │    ├── ...                                           │
     │    └── 第 n! 次: [T4, T3, T2, T1] (末排列)           │
     │                                                      │
     │  步骤 B: testPlan(list) 评估当前排列的代价           │
     │    ├── new Plan(list, n, condition)                  │
     │    ├── plan.calculateCost()                          │
     │    │     ├── 迭代所有 TableFilter                    │
     │    │     ├── 对每个表: getBestPlanItem + 代价计算     │
     │    │     └── 检测无效计划 (Infinity)                  │
     │    └── 更新 bestPlan (如果较低)                       │
     │                                                      │
     │  步骤 C: 检查 canStop(x)                             │
     │    ├── 每 128 次检查一次                              │
     │    ├── 耗时 > cost × 100μs?                         │
     │    └── 是 → 提前终止                                 │
     └──────────────────────────────────────────────────────┘
                        │
                        ▼
  输出: bestPlan (代价最低的执行计划)
       topFilter = bestPlan.filters[0]
```
**图 8-17: 追踪暴力枚举的排列生成与评估循环**
```text
如图 8-18 所示，排列生成迭代过程 — Permutations 内部状态变化
                        │
  输入: filters = [T1, T2, T3, T4]  (4 个 TableFilter)
                        │
  Permutations.create(filters, list) 初始化:
    ┌───────────────────────────────────────────────────────────┐
    │ 内部状态:                                                   │
    │   source = [T1, T2, T3, T4]  (原始顺序, 不修改)             │
    │   result = [T1, T2, T3, T4]  (输出数组, 首排列=原始)        │
    │   index  = [0, 0, 0, 0]      (控制排列生成的指针数组)        │
    └───────────────────────────────────────────────────────────┘
                        │
  每次 p.next() 调用:
                        │
    ┌─────────────────────────────────────────────────────────┐
    │ 迭代 1: result = [T1, T2, T3, T4]  index = [0,0,0,0]   │
    │   → testPlan([T1,T2,T3,T4])                             │
    │   → 交换 T3 ↔ T4                                        │
    │                                                         │
    │ 迭代 2: result = [T1, T2, T4, T3]  index = [0,0,1,0]   │
    │   → testPlan([T1,T2,T4,T3])                             │
    │   → 重置尾部, 交换 T2 ↔ T3                              │
    │                                                         │
    │ 迭代 3: result = [T1, T3, T2, T4]  index = [0,1,0,0]   │
    │   → testPlan([T1,T3,T2,T4])                             │
    │   → 交换 T2 ↔ T4                                        │
    │                                                         │
    │ 迭代 4: result = [T1, T3, T4, T2]  index = [0,1,1,0]   │
    │   → testPlan([T1,T3,T4,T2])                             │
    │   → ...                                                 │
    │                                                         │
    │ ...                                                     │
    │                                                         │
    │ 迭代 24: result = [T4, T3, T2, T1]  index = [0,0,0,0]  │
    │   → testPlan([T4,T3,T2,T1])                             │
    │   → p.next() 返回 false (遍历完成)                       │
    └─────────────────────────────────────────────────────────┘
                        │
  Permutations 算法特性:
    ├── 不重复: 每次 next() 生成字典序的下一个排列
    ├── 无额外内存: 在原数组上就地生成
    ├── 时间复杂度: O(n!) 次 next() 调用, 每次 O(1) 交换
    └── 提前停止: 可通过 canStop() 在任意迭代终止
```
**图 8-18: 演示 Permutations 字典序生成排列的状态变化**

### 8.2.2 混合策略 — `calculateBruteForceSome()`

源码位置：`Optimizer.java:115`

```java
private void calculateBruteForceSome(boolean isSelectCommand) {
    int bruteForce = getMaxBruteForceFilters(filters.length);
    TableFilter[] list = new TableFilter[filters.length];
    Permutations<TableFilter> p = Permutations.create(filters, list, bruteForce);
    for (int x = 0; !canStop(x) && p.next(); x++) {
        // 标记已使用的表
        for (TableFilter f : filters)
            f.setUsed(false);
        for (int i = 0; i < bruteForce; i++)
            list[i].setUsed(true);
        // 剩余位置用贪心算法填充
        for (int i = bruteForce; i < filters.length; i++) {
            double costPart = -1.0;
            int bestPart = -1;
            for (int j = 0; j < filters.length; j++) {
                if (!filters[j].isUsed()) {
                    list[i] = filters[j];
                    Plan part = new Plan(list, i + 1, condition);
                    double costNow = part.calculateCost(...);
                    if (costPart < 0 || costNow < costPart) {
                        costPart = costNow;
                        bestPart = j;
                    }
                }
            }
            filters[bestPart].setUsed(true);
            list[i] = filters[bestPart];
        }
        testPlan(list, isSelectCommand);
    }
}
```

如图 8-17 所示，算法描述：
1. 对前 `bruteForce` 个表暴力枚举所有排列
2. 对剩余位置，依次尝试每个未使用的表，选择当前代价最低的（贪心）

**`getMaxBruteForceFilters()` 计算**：

```java
private static int getMaxBruteForceFilters(int filterCount) {
    int i = 0, j = filterCount, total = filterCount;
    while (j > 0 && total * (j * (j - 1) / 2) < MAX_BRUTE_FORCE) {
        j--;
        total *= j;
        i++;
    }
    return i;
}
```

条件：`P(n, m) * C(n-m, 2) < 2000`，其中 `P(n, m)` 是前 m 个位置的排列数，`C(n-m, 2)` 是剩余位置的贪心组合数。

示例（10 表）：

| m | P(10, m) | C(10-m, 2) | 乘积 |
|---|----------|------------|------|
| 2 | 10×9=90  | C(8,2)=28  | 2520 → 超过 2000 |
| 1 | 10       | C(9,2)=36  | 360  → 可行 |

因此 `getMaxBruteForceFilters(10)` = 1，即暴力枚举第 1 个位置，贪心选其余 9 个。

```text
calculateBruteForceSome() 执行流程 (以 10 表为例)
                        │
  输入: filters[] (10 个 TableFilter)
                        │
                        ▼
  1. 计算暴力枚举位置数
     bruteForce = getMaxBruteForceFilters(10) = 1
                        │
                        ▼
  2. 创建排列生成器 (前 bruteForce 个位置)
     Permutations.create(filters, list, 1)
     → 生成 [T1], [T2], ..., [T10] 共 10 种前缀
                        │
                        ▼
  3. 外层循环: for each 排列前缀
                        │
     ┌─────────────────────────────────────────────────────┐
     │  示例: 当前前缀 [T5]                                 │
     │                                                     │
     │  3.1 标记已使用: T5.setUsed(true)                    │
     │                                                     │
     │  3.2 内层贪心循环 (填充位置 1..9):                   │
     │      for (i = 1; i < 10; i++)                       │
     │        bestCost = -1, bestPart = -1                 │
     │        for (j = 0; j < 10; j++)                     │
     │          if (!filters[j].isUsed())                   │
     │            list[i] = filters[j]                      │
     │            Plan part = new Plan(list, i+1, cond)    │
     │            costNow = part.calculateCost(...)         │
     │            if (bestCost < 0 || costNow < bestCost)   │
     │              bestCost = costNow                     │
     │              bestPart = j                           │
     │        filters[bestPart].setUsed(true)              │
     │        list[i] = filters[bestPart]                  │
     │                                                     │
     │  3.3 评估完整排列: testPlan(list, isSelectCommand)   │
     └─────────────────────────────────────────────────────┘
                        │
                        ▼
  4. 对所有前缀重复 → 取最优 Plan
                        │
  对比: 10! = 3,628,800  vs  混合策略 ≈ 450 次评估
  加速比: ≈ 8,064 倍
```
**图 8-19: 拆解混合策略暴力前缀加贪心填充流程**

### 8.2.3 遗传算法 — `calculateGenetic()`

如图 8-19 所示，源码位置：`Optimizer.java:153`

```java
private void calculateGenetic(boolean isSelectCommand) {
    TableFilter[] best = new TableFilter[filters.length];
    TableFilter[] list = new TableFilter[filters.length];
    for (int x = 0; x < MAX_GENETIC; x++) {
        if (canStop(x)) break;
        boolean generateRandom = (x & 127) == 0;
        if (!generateRandom) {
            System.arraycopy(best, 0, list, 0, filters.length);
            if (!shuffleTwo(list)) {
                generateRandom = true;  // 所有交换已尝试过
            }
        }
        if (generateRandom) {
            switched = new BitSet();
            System.arraycopy(filters, 0, best, 0, filters.length);
            shuffleAll(best);           // 全新随机排列
            System.arraycopy(best, 0, list, 0, filters.length);
        }
        if (testPlan(list, isSelectCommand)) {
            switched = new BitSet();
            System.arraycopy(list, 0, best, 0, filters.length);
        }
    }
}
```

算法特点：
- **迭代次数**: 最多 500 轮
- **变异方式**: 每 128 轮触发一次完全洗牌，其余轮次交换两个随机位置
- **保留最优**: 如果新计划优于当前最优，更新 `best` 数组
- **去重机制**: `shuffleTwo()` 使用 `switched` BitSet 记录已尝试的交换对，避免重复评估

```text
如图 8-20 所示，遗传算法 calculateGenetic() 决策流程
                        │
  进入循环: for (x = 0; x < 500; x++)
                        │
                        ▼
  ┌────────────────────────────────────────────┐
  │  canStop(x) ?   ← 提前终止检查              │
  │  ├── YES → break (退出循环)                 │
  │  └── NO  → 继续                            │
  └────────────────┬───────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────┐
  │  (x & 127) == 0 ?   ← 每 128 轮触发洗牌    │
  │  ├── YES → generateRandom = true           │
  │  │          shuffleAll(best) → 全新排列    │
  │  │          (探索: 跳出局部最优)            │
  │  │                                          │
  │  └── NO  → 复制 best 到 list               │
  │             shuffleTwo(list) → 交换两位置    │
  │             (利用: 在最优解附近微调)          │
  │            如果所有交换耗尽 → generateRandom │
  └────────────────┬───────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────┐
  │  generateRandom?                           │
  │  ├── YES → switched = new BitSet()         │
  │  │          shuffleAll(best)               │
  │  │          list = best (副本)              │
  │  │                                          │
  │  └── NO  → list 已就绪                      │
  └────────────────┬───────────────────────────┘
                   │
                   ▼
  ┌────────────────────────────────────────────┐
  │  testPlan(list) ?   ← 评估代价             │
  │  │                                         │
  │  ├── 新计划优于最优?                        │
  │  │    ├── YES → 更新 best = list           │
  │  │    │          switched = new BitSet()   │
  │  │    └── NO  → 保持当前最优               │
  │  │                                         │
  │  └── 继续下一轮迭代                         │
  └────────────────────────────────────────────┘
                   │
                   ▼
  循环结束 → 返回 bestPlan (最优排列)
```
**图 8-20: 追踪 calculateGenetic 的探索利用决策循环**
```text
遗传算法示例 (5 表):
  │
  初始: [T1, T2, T3, T4, T5]  (FROM 子句顺序)
  │
  迭代 1:  交换位置 2,4 → [T1, T4, T3, T2, T5]  代价 120  ← 保留
  迭代 2:  交换位置 1,3 → [T3, T4, T1, T2, T5]  代价 150
  迭代 3:  交换位置 0,2 → [T1, T4, T3, T2, T5]  代价 120  ← 恢复到最优
  ...
  迭代 128: 完全洗牌 → [T5, T2, T4, T1, T3]  代价 90  ← 新的最优
  ...
  迭代 500: 返回当前最优 [T5, T2, T4, T1, T3], 代价 90
```

### 8.2.4 策略选择总图

如图 8-21 所示，针对不同数量的表，`calculateBestPlan()` 会选择不同的搜索策略：

```text
calculateBestPlan()
  │
  ├─ filters.length == 1?
  │     └─ YES → testPlan(filters)
  │
  ├─ filters.length <= 7?
  │     └─ YES → calculateBruteForceAll()
  │              枚举 n! 种排列
  │              cost 低 → 耗时短
  │              cost 高 → canStop() 提前退出
  │
  └─ filters.length >= 8?
        │
        ├─ calculateBruteForceSome()
        │     前 m 个位置: 暴力枚举
        │     剩余位置: 贪心填充
        │     m 由 getMaxBruteForceFilters() 动态计算
        │
        └─ calculateGenetic()
              每 128 轮: 完全洗牌
              其余: 随机交换两表
              保留最优 plan
```

```text
如图 8-22 所示，策略选择场景示例
                        │
  场景 1: 单表查询
    SELECT * FROM users WHERE id = 1
    │
    └── filters.length = 1 → testPlan(filters)
          ├── 无排列组合
          └── 仅选择最佳索引 (主键 PK)
                        │
  场景 2: 3 表连接
    SELECT * FROM a JOIN b ON a.id = b.a_id
      JOIN c ON b.id = c.b_id
    │
    └── filters.length = 3 → calculateBruteForceAll()
          ├── 3! = 6 种排列
          ├── 评估全部排列
          └── 选择全局最优
                        │
  场景 3: 10 表连接
    SELECT * FROM t1 JOIN t2 ... JOIN t10
    │
    └── filters.length = 10 → 混合 + 遗传
          ├── calculateBruteForceSome()
          │     ├── bruteForce=1 (暴力第1个位置)
          │     └── 贪心填充剩余9个
          │
          └── calculateGenetic()
                ├── 500 轮随机变异
                └── 保留最优
          │
          └── 取两种策略中的最优 Plan
```

这组图把"策略选择—暴力枚举—代价分布"拆成三个层次：图 8-21 演示三类典型表数下的策略选择路径，图 8-22 展示四表暴力枚举二十四种排列的代价分布，图 8-85 则进一步标注最优排列的选取与 topFilter 链接。

**图 8-21: 演示三类典型表数下的策略选择路径**

### 8.2.5 暴力枚举排列生成可视化

**图 8-22: 演示四表暴力枚举二十四种排列的代价分布**

```text
如图 8-85 所示，暴力枚举: 4 表 (T1, T2, T3, T4) 的所有排列
                     │
                     ▼
  Permutations.create(filters) 生成 4! = 24 种排列:
                     │
  排列  1: [T1, T2, T3, T4]  cost = 198  ← 初始排列 (FROM 顺序)
  排列  2: [T1, T2, T4, T3]  cost = 215
  排列  3: [T1, T3, T2, T4]  cost = 175
  排列  4: [T1, T3, T4, T2]  cost = 190
  排列  5: [T1, T4, T2, T3]  cost = 230
  排列  6: [T1, T4, T3, T2]  cost = 210
  排列  7: [T2, T1, T3, T4]  cost = 145  ← 更优
  排列  8: [T2, T1, T4, T3]  cost = 150
  排列  9: [T2, T3, T1, T4]  cost = 120  ← 当前最优
  排列 10: [T2, T3, T4, T1]  cost = 135
  排列 11: [T2, T4, T1, T3]  cost = 160
  排列 12: [T2, T4, T3, T1]  cost = 155
  排列 13: [T3, T1, T2, T4]  cost = 90   ← 最优! (保留)
  排列 14: [T3, T1, T4, T2]  cost = 105
  排列 15: [T3, T2, T1, T4]  cost = 95
  排列 16: [T3, T2, T4, T1]  cost = 100
  排列 17: [T3, T4, T1, T2]  cost = 115
  排列 18: [T3, T4, T2, T1]  cost = 110
  排列 19: [T4, T1, T2, T3]  cost = 250
  排列 20: [T4, T1, T3, T2]  cost = 240
  排列 21: [T4, T2, T1, T3]  cost = 235
  排列 22: [T4, T2, T3, T1]  cost = 225
  排列 23: [T4, T3, T1, T2]  cost = 205
  排列 24: [T4, T3, T2, T1]  cost = 220
                     │
                     ▼
  最优: [T3, T1, T2, T4], cost = 90
  选择 topFilter = T3
  链接: T3 → T1 → T2 → T4
```
**图 8-85: 演示四表暴力枚举的排列代价分布**

该图以 4 表连接为例，展示了暴力枚举的实际运行过程。关键观察：

1. **初始排列**是 SQL 中 FROM 子句的书写顺序。这通常是 DBA 或 ORM 框架指定的顺序，但不一定是最优的
2. **排列生成**使用 `Permutations` 工具类，这是一个高效的排列迭代器，每次调用 `next()` 生成下一个排列。排列的顺序是字典序的
3. **代价分布**呈现非均匀特征：T3 作为头表的排列普遍代价较低（90-115），而 T4 作为头表的排列代价较高（205-250）。这表明 T3 是最佳驱动表
4. **搜索效率**：24 种排列在微秒级别内可完成评估。随着表数增长，评估时间呈阶乘增长——7 表的 5040 种排列仍在合理范围（毫秒级），8 表的 40320 种排列开始显著变慢

```text
暴力枚举代价分布与搜索效率
                        │
  4 表连接: 24 种排列的代价分布
                        │
  代价范围:
    ┌── 最优 [T3, T1, T2, T4]  cost = 90
    │
    ├── 良好 (90-120):   排列 9, 10, 13, 14, 15, 16  (6 种)
    │                    以 T2 或 T3 为头表
    │
    ├── 中等 (145-198):  排列 1, 3, 4, 7, 8, 17, 18  (7 种)
    │                    以 T1 为头表或 T2 为头表
    │
    └── 较差 (205-250):  排列 2, 5, 6, 19, 20, 21, 22, 23, 24  (9 种)
                         以 T4 为头表
                        │
  代价分布特征:
    头表选择对总代价的影响:
      T3 作为头表: cost = 90-115 (平均 103)
      T2 作为头表: cost = 120-160 (平均 138)
      T1 作为头表: cost = 175-230 (平均 203)
      T4 作为头表: cost = 205-250 (平均 228)

    如图 8-23 所示，结论: 头表选择是影响总代价的最关键因素
          T3 最适合作为驱动表 (选择性最高)
                        │
  表数增长对搜索空间的影响:
                        │
    表数   排列数    暴力枚举时间 (估计)
     4       24      < 1μs
     5      120      ~5μs
     6      720      ~30μs
     7     5,040     ~200μs
     8     40,320    ~2ms     ← 开始显著
     9     362,880   ~15ms    ← 不可接受
    10    3,628,800  ~150ms   ← 必须使用混合/遗传
```
**图 8-23: 对比不同表数下暴力枚举的代价分布与耗时**

如图 8-24 所示，头表的选择直接决定了中间结果的行数，对查询效率有数量级的影响：

```text
如图 8-25 所示，头表选择对查询效率的影响 — 行传递量对比
                        │
  SQL: SELECT * FROM T1, T2, T3, T4
       WHERE T1.id = T2.ref_id
         AND T2.id = T3.ref_id
         AND T3.id = T4.ref_id
                        │
  假设各表行数: T1=100, T2=1000, T3=10000, T4=100000
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  最优头表 T1 (最小表):                                               │
  │                                                                     │
  │  步骤  ├── 扫描 T1  (100 行)                                        │
  │        │    └── 对每行, 通过索引查找 T2.ref_id → 平均 1 行          │
  │        │        总行: T1(100) × T2(1) = 100                         │
  │        ├── 对每对 (T1, T2), 通过索引查找 T3.ref_id → 平均 0.1 行    │
  │        │        总行: 100 × 0.1 = 10                                │
  │        └── 对每对 (T1, T2, T3), 通过索引查找 T4.ref_id → 平均 0.01行│
  │                 总行: 10 × 0.01 = 0.1                               │
  │  总中间行数: 100 + 10 + 0.1 ≈ 110                                   │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  最差头表 T4 (最大表):                                               │
  │                                                                     │
  │  步骤  ├── 扫描 T4  (100000 行)                                     │
  │        │    └── 对每行, 全表扫描 T3 (无索引可用) → 10000 行/次      │
  │        │        总行: 100000 × 10000 = 1e9                          │
  │        ├── 对每对 (T4, T3), 全表扫描 T2 → 1000 行/次                │
  │        │        总行: 1e9 × 1000 = 1e12                             │
  │        └── 对每对 (T4, T3, T2), 全表扫描 T1 → 100 行/次             │
  │                 总行: 1e12 × 100 = 1e14                              │
  │  总中间行数: 天文数字, 不可执行                                       │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  结论: 头表选择决定连接查询的可行性
    最优: 小表驱动大表, 中间结果持续减小
    最差: 大表驱动小表, 中间结果爆炸增长
```
**图 8-24: 对比最优与最差头表的中间行传递量级差**

### 8.2.6 混合策略算法流程详图

**图 8-25: 演示十表混合策略的暴力前缀与贪心填充**

```text
如图 8-86 所示，混合策略执行示例: 10 表连接
                        │
  getMaxBruteForceFilters(10) 计算:
    │
    ├── m=2: P(10,2)=90, C(8,2)=28, 90×28=2520 > 2000  → 太大
    └── m=1: P(10,1)=10, C(9,2)=36, 10×36=360 < 2000  → 可行
                        │
  bruteForce = 1  (暴力枚举 1 个位置的 10 种选择)
                        │
  ┌────────────────────────────────────────────────────────────┐
  │  外层循环: 暴力枚举第 1 个位置 (10 种)                      │
  │                                                            │
  │  内层循环: 贪心填充位置 2~10 (每次选当前最优)               │
  │                                                            │
  │  示例: 第 1 个位置固定为 T5                                 │
  │    │                                                       │
  │    └── 位置 2: 尝试 {T1, T2, T3, T4, T6, T7, T8, T9, T10} │
  │          T1 cost_part=50 → 最优, 选 T1                     │
  │                                                            │
  │      位置 3: 尝试 {T2, T3, T4, T6, T7, T8, T9, T10}       │
  │          T3 cost_part=30 → 最优, 选 T3                     │
  │                                                            │
  │      位置 4: 尝试 {T2, T4, T6, T7, T8, T9, T10}           │
  │          T7 cost_part=45 → 最优, 选 T7                     │
  │                                                            │
  │      ...                                                   │
  │                                                            │
  │      位置 10: 剩余最后一个表                                │
  │          cost_part = 最终的 Plan 总代价                     │
  │                                                            │
  │  testPlan([T5, T1, T3, T7, ..., 最后一个表])               │
  │                                                            │
  │  ← 重复 10 次 (每个表作为第 1 位置一次)                     │
  └────────────────────────────────────────────────────────────┘
                        │
  总评估次数: 10 次 (每次评估包含 9+8+...+1 = 45 次贪心选择)
  对比暴力枚举 10!: 10! = 3,628,800
  加速比: 3,628,800 / (10 × 45) ≈ 8,064 倍
```

以下三张图共同呈现混合策略与遗传算法的搜索特征：图 8-86 拆解外层暴力与内层贪心的协作，图 8-26 对比暴力枚举与混合策略的搜索空间增长，图 8-27 追踪遗传算法五百轮迭代的代价进化轨迹。

**图 8-86: 拆解混合策略外层暴力与内层贪心的协作**

混合策略是 H2 在处理 8 表以上连接时的关键技术，其核心思想是"部分暴力 + 剩余贪心"。`getMaxBruteForceFilters()` 方法动态计算有多少个位置值得暴力搜索——在 `MAX_BRUTE_FORCE = 2000` 的约束下，找到使 `P(n,m) × C(n-m, 2)` 不超过 2000 的最大 m 值。

对于 10 表连接，m=1 意味着暴力枚举第 1 个位置（10 种可能），剩余的 9 个位置用贪心算法填充。贪心算法的每一步都尝试所有未使用的表，选择使当前局部代价最低的表。这种贪心策略虽然不能保证全局最优，但在表数较多时能快速找到可接受的计划。

混合策略将评估次数从 10! ≈ 360 万次降低到约 450 次，加速比超过 8000 倍，而计划质量通常只比全局最优差 10-20%。如图 8-26 所示，不同表数下暴力枚举与混合策略的搜索空间呈现截然不同的增长曲线。

```text
如图 8-27 所示，暴力枚举 vs 混合策略搜索空间对比
                        │
  不同表数下的搜索空间 (评估次数):
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  表数    暴力枚举 (n!)     混合策略 (评估次数)    加速比          │
  ├────────────────────────────────────────────────────────────────────┤
  │   8      40,320            2,184                 18x              │
  │   9      362,880           756                   480x             │
  │  10      3,628,800         450                   8,064x           │
  │  11      39,916,800        396                   100,800x         │
  │  12      479,001,600       430                   1,113,958x       │
  │  13      6,227,020,800     400                   15,567,552x      │
  │  14      87,178,291,200    520                   167,650,560x     │
  └────────────────────────────────────────────────────────────────────┘
                        │
  关键分析:
    ├── 8 表: 暴力枚举仍可接受 (4 万次评估), 混合策略优势不大
    ├── 10 表: 暴力枚举 360 万次 vs 混合策略 450 次, 差异巨大
    ├── 12 表以上: 暴力枚举完全不可行, 混合策略保持 <500 次
    └── 混合策略的评估次数在表数增长时保持稳定 (约 400-500 次)
         这是因为 getMaxBruteForceFilters() 自动调整暴力位置数
```
**图 8-26: 对比暴力枚举与混合策略的搜索空间增长**

### 8.2.7 遗传算法进化过程可视化

**图 8-27: 追踪遗传算法五百轮迭代的代价进化轨迹**

```text
如图 8-87 所示，遗传算法进化过程 (8 表连接, 500 轮迭代)
                        │
  初始: [T1, T2, T3, T4, T5, T6, T7, T8]  cost = 850
                        │
  迭代轮次  当前序列                       代价    备注
   ───────  ────────────────────────────  ─────   ──────────────────
      0     [T1, T2, T3, T4, T5, T6, T7, T8]  850  初始 (FROM 顺序)
      ↓
      1     [T1, T5, T3, T4, T2, T6, T7, T8]  820  交换 1↔4
      2     [T1, T5, T3, T4, T2, T6, T7, T8]  820  未改善, 保持最优
      3     [T5, T1, T3, T4, T2, T6, T7, T8]  760  交换 0↔1, 新最优
      ↓
      ...   (继续随机交换)
      ↓
     10     [T5, T1, T7, T4, T2, T6, T3, T8]  700  交换 2↔6
     15     [T5, T1, T7, T4, T2, T6, T3, T8]  700  未改善
     22     [T5, T1, T7, T3, T2, T6, T4, T8]  680  交换 3↔6
      ↓
    128     [T8, T3, T6, T1, T5, T2, T7, T4]  550  完全洗牌! 新最优
      ↓
    129     [T8, T3, T6, T1, T5, T2, T7, T4]  550  未改善
    135     [T8, T3, T6, T7, T5, T2, T1, T4]  530  交换 3↔6
      ↓
    256     [T3, T8, T5, T1, T2, T6, T4, T7]  480  完全洗牌! 新最优
      ↓
    300     [T3, T8, T5, T1, T2, T4, T6, T7]  475  交换 5↔6
      ↓
    384     [T1, T4, T6, T2, T5, T8, T3, T7]  420  完全洗牌! 新最优
      ↓
    420     [T1, T4, T6, T2, T5, T8, T3, T7]  420  未改善
    455     [T1, T4, T6, T5, T2, T8, T3, T7]  418  交换 3↔4
      ↓
    500     [T1, T4, T6, T5, T2, T8, T3, T7]  418  最终最优
                        │
                        ▼
  最终选择: [T1, T4, T6, T5, T2, T8, T3, T7], cost = 418
  对比初始: 从 850 降低到 418, 优化了 50.8%
  对比暴力: 8! = 40320 种排列, 遗传算法仅评估 500 种
           搜索效率: 500/40320 ≈ 1.24%
```
**图 8-87: 演示遗传算法八表连接的进化采样轨迹**

该图展示了遗传算法在 500 轮迭代中的进化轨迹。算法特点包括：

1. **探索与利用的平衡**：每 128 轮触发一次"完全洗牌"（全部随机化），对应算法中的"探索"阶段，帮助跳出局部最优解。其余轮次执行"随机交换两个位置"，对应"利用"阶段，在当前最优解附近微调。

2. **最优解保留**：`testPlan()` 方法返回 true 表示当前计划优于最优计划时，更新 `best` 数组。这意味着算法始终保持从初始到当前轮次遇到的最佳解。

3. **去重机制**：`shuffleTwo()` 使用 `switched` BitSet 记录已尝试的交换对。当所有可能的交换都已尝试过后，`shuffleTwo()` 返回 false，触发下一轮完全洗牌。这避免了重复评估相同的排列。

4. **收敛速度**：从进化轨迹可以看到，最初的 128 轮中代价快速下降（850 → 550），后续的完整洗牌周期性地将解拉出局部最优。到第 384 轮后，改进速度明显放缓，说明算法已接近收敛。

5. **效率对比**：对于 8 表连接，暴力枚举需要评估 40320 种排列，而遗传算法仅评估 500 种（1.24% 的搜索空间），通常能找到接近最优的解。

```text
如图 8-28 所示，遗传算法收敛速度与效果分析
                        │
  8 表连接: 暴力枚举 40320 种 vs 遗传算法 500 种
                        │
  代价收敛轨迹 (每 50 轮采样):
                        │
    轮次    当前最优代价    较初始改善    阶段说明
    ─────   ───────────   ──────────   ─────────────────
      0         850          0%        初始排列 (FROM 顺序)
     50         700         17.6%      快速下降阶段
    100         650         23.5%      探索+利用
    150         580         31.8%      第一次完全洗牌后改善
    200         550         35.3%      持续优化
    250         500         41.2%      第二次完全洗牌后改善
    300         475         44.1%      微调阶段
    350         450         47.1%      接近收敛
    400         420         50.6%      第三次完全洗牌后改善
    450         418         50.8%      收敛
    500         418         50.8%      最终最优
                        │
  收敛特征分析:
    ├── 阶段 1 (0-128 轮): 快速下降
    │     代价从 850 降至 550, 降幅 35%
    │     通过局部交换快速找到较优解
    │
    ├── 阶段 2 (128-384 轮): 周期性跳跃
    │     每 128 轮完全洗牌产生的"探索"脉冲
    │     帮助跳出局部最优, 带来新的下降
    │
    └── 阶段 3 (384-500 轮): 收敛
          改善幅度 < 5%, 接近全局最优
          即使继续迭代, 改善空间有限
                        │
  质量评估:
    遗传算法最终代价 418
    对比暴力枚举理论最优 ≈ 400-450 (估计)
    偏差: 约 0-5% (在可接受范围内)
    搜索效率: 仅使用 1.24% 的搜索空间
```
**图 8-28: 对比遗传算法各阶段代价下降速度与收敛点**
```text
如图 8-29 所示，遗传算法操作算子 — 交换与洗牌对比
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  算子 1: shuffleTwo() — 随机交换两个位置                             │
  │                                                                     │
  │  当前最优: [T1, T4, T6, T2, T5, T8, T3, T7]                       │
  │                        │                                            │
  │  第 1 步: 随机选择两个不同位置                                        │
  │           位置 3 = T2, 位置 5 = T8                                   │
  │                        │                                            │
  │  第 2 步: 交换两者                                                    │
  │           结果: [T1, T4, T6, T8, T5, T2, T3, T7]                   │
  │                        │                                            │
  │  第 3 步: 记录已尝试交换对                                            │
  │           switched[3] = {5}, switched[5] = {3}                      │
  │           (BitSet 跟踪, 避免重复)                                    │
  │                        │                                            │
  │  试探评估 → 新代价 vs 当前最优                                         │
  │    ├── 更优 → 更新 best 数组, 重置 switched                          │
  │    └── 更差 → 恢复原顺序, switched 记录阻止重复                       │
  │                                                                     │
  │  当 switched 中所有交换对都已尝试 → 返回 false, 触发洗牌              │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  算子 2: 完全洗牌 — 随机化全部顺序                                    │
  │                                                                     │
  │  触发条件:                                                          │
  │    ├── shuffleTwo() 返回 false (所有交换对已尝试)                     │
  │    └── 或 每 128 轮强制执行一次 (探索脉冲)                            │
  │                                                                     │
  │  执行过程:                                                          │
  │    当前最优: [T1, T4, T6, T2, T5, T8, T3, T7]                     │
  │                        │                                            │
  │    ↓ 随机洗牌:                                                       │
  │                        │                                            │
  │    新序列: [T8, T3, T6, T1, T5, T2, T7, T4]                       │
  │                        │                                            │
  │    保留: current best 不变 (保留历史最优)                             │
  │    重置: switched BitSet 清空 (允许新的交换组合)                      │
  │                                                                     │
  │  设计目的:                                                          │
  │    ├── 跳出局部最优解                                               │
  │    ├── 探索新的搜索区域                                             │
  │    └── 避免过早收敛到次优解                                          │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  两种算子的协作节奏:
    交换(利用) ──→ 洗牌(探索) ──→ 交换(利用) ──→ 洗牌(探索)
     128 轮          1 轮          128 轮          1 轮
```
**图 8-29: 对比 shuffleTwo 局部交换与完全洗牌的作用**

---

## 8.3 代价模型

### 8.3.1 `Plan` 类

源码位置：`org/h2/table/Plan.java`

```java
public class Plan {
    private final TableFilter[] filters;
    private final HashMap<TableFilter, PlanItem> planItems = new HashMap<>();
    private final Expression[] allConditions;
    private final TableFilter[] allFilters;
}
```

如图 8-20 所示，`Plan` 表示一个候选执行计划，包含表的访问顺序和使用的索引。

```text
如图 8-30 所示，Plan 类在优化过程中的角色
                        │
  Optimizer.optimize()
    │
    ├── 创建 Plan 对象
    │     new Plan(list, len, condition)
    │     │
    │     ├── filters: TableFilter[]   ← 传入当前排列顺序
    │     ├── planItems: HashMap       ← 初始化空集合
    │     └── allConditions:           ← 全部条件表达式
    │
    ├── Plan.calculateCost()           ← 评估此排列的代价
    │     │
    │     ├── 遍历 filters 数组
    │     ├── 对每个 TableFilter:
    │     │     ├── 选择最佳索引
    │     │     ├── 累加代价 (复合乘法)
    │     │     └── 标记可求值
    │     └── 返回总代价
    │
    ├── Plan 的比较与选择
    │     if (plan.calculateCost() < bestPlan.calculateCost())
    │         bestPlan = plan
    │
    └── 最终 bestPlan 的使用
          ├── bestPlan.filters[0] → topFilter
          ├── bestPlan.getPlanItem(filter) → PlanItem
          └── 设置每个 TableFilter 的索引和掩码
```
**图 8-30: 概览 Plan 类在优化过程中承担的角色**
```text
如图 8-31 所示，Plan 对象的创建 → 评估 → 选择完整流程
                        │
  ┌─────────────────────────────────────────────────────────────────┐
  │  Optimizer.optimize()                                           │
  │    │                                                             │
  │    ├── 阶段 1: 策略选择                                            │
  │    │     ├── tryBruteForce()     ← 表数 ≤7                       │
  │    │     ├── tryBruteForceSome() ← 表数 8-10                    │
  │    │     └── tryGenetic()        ← 表数 ≥11                     │
  │    │                                                             │
  │    └── 阶段 2: 排列生成与 Plan 创建                                │
  │          │                                                       │
  │          ├── for each 排列:                                      │
  │          │     │                                                  │
  │          │     ├── new Plan(filters, len, condition)             │
  │          │     │     ├── 保存 filters 数组 (当前排列顺序)          │
  │          │     │     ├── 初始化 planItems = new HashMap<>()       │
  │          │     │     └── 保存 allConditions 引用                  │
  │          │     │                                                  │
  │          │     ├── plan.calculateCost()                          │
  │          │     │     ├── 遍历 filters, 计算每个表的 cost          │
  │          │     │     ├── 复合乘法累加                            │
  │          │     │     └── 返回总代价或 Infinity (无效计划)         │
  │          │     │                                                  │
  │          │     ├── cost < bestCost?                              │
  │          │     │     ├── YES → bestPlan = plan, bestCost = cost  │
  │          │     │     └── NO  → 丢弃 plan (GC 回收)               │
  │          │     │                                                  │
  │          │     └── canStop()? → 提前终止                         │
  │          │                                                       │
  │          └── 完成: bestPlan.filters[0] → topFilter               │
  └─────────────────────────────────────────────────────────────────┘
```
**图 8-31: 追踪 Plan 对象的创建评估选择完整流程**

### 8.3.2 `calculateCost()` — 代价计算

源码位置：`Plan.java:103`

```java
public double calculateCost(SessionLocal session, AllColumnsForPlan allColumnsSet,
                            boolean isSelectCommand) {
    double cost = 1;
    boolean invalidPlan = false;
    for (int i = 0; i < allFilters.length; i++) {
        TableFilter tableFilter = allFilters[i];
        PlanItem item = tableFilter.getBestPlanItem(session, allFilters,
                    i, allColumnsSet, isSelectCommand);
        planItems.put(tableFilter, item);
        cost += cost * item.cost;           // 复合乘法
        setEvaluatable(tableFilter, true);
        // 检查条件是否可求值
        Expression on = tableFilter.getJoinCondition();
        if (on != null && !on.isEverything(EVALUATABLE_VISITOR)) {
            invalidPlan = true;
            break;
        }
    }
    if (invalidPlan) cost = Double.POSITIVE_INFINITY;  // 无效计划
    return cost;
}
```

如图 8-30 所示，**复合乘法**含义：
- `cost = 1 + cost × item.cost`
- 初始 cost = 1
- 每个表的代价叠加：`new_cost = current_cost + current_cost × item_cost`
- 等价于：`total_cost = ∏(1 + item_cost[i]) - 1`
- 这也等于所有中间行数的乘积和

例如 3 表连接：
- T1 代价 10，T2 代价 5，T3 代价 2
- cost = 1
- T1 后: 1 + 1×10 = 11
- T2 后: 11 + 11×5 = 66
- T3 后: 66 + 66×2 = 198
- 总代价 198

**无效计划**：如果某个 join condition 引用了尚未出现在计划中的表（即条件不可求值），则该计划代价为 `Infinity`，不会被选中。

```text
如图 8-32 所示，calculateCost() 代价累加过程详解
                        │
  Plan 排列: [T1, T2, T3]
                        │
  ┌──────────────────────────────────────────────────────────────────────┐
  │  cost = 1 (初始值)                                                   │
  │                                                                      │
  │  ┌──────────────────────────────────────────────────────────────────┐│
  │  │ i=0: TableFilter = T1                                            ││
  │  │  ├── getBestPlanItem(T1)  → item1 (cost=10, index=IDX_A)        ││
  │  │  ├── planItems.put(T1, item1)                                    ││
  │  │  ├── cost = 1 + 1×10 = 11                                       ││
  │  │  ├── setEvaluatable(T1, true)                                    ││
  │  │  └── T1.joinCondition → null (无连接条件)                       ││
  │  └──────────────────────────────────────────────────────────────────┘│
  │                              ↓                                       │
  │  ┌──────────────────────────────────────────────────────────────────┐│
  │  │ i=1: TableFilter = T2                                            ││
  │  │  ├── getBestPlanItem(T2)  → item2 (cost=5, index=PK_B)          ││
  │  │  ├── planItems.put(T2, item2)                                    ││
  │  │  ├── cost = 11 + 11×5 = 66                                      ││
  │  │  ├── setEvaluatable(T2, true)                                    ││
  │  │  └── T2.joinCondition: T2.b_id = T1.id                          ││
  │  │        → T1 已标记 evaluatable ✓  (条件可求值)                   ││
  │  └──────────────────────────────────────────────────────────────────┘│
  │                              ↓                                       │
  │  ┌──────────────────────────────────────────────────────────────────┐│
  │  │ i=2: TableFilter = T3                                            ││
  │  │  ├── getBestPlanItem(T3)  → item3 (cost=2, index=PK_C)          ││
  │  │  ├── planItems.put(T3, item3)                                    ││
  │  │  ├── cost = 66 + 66×2 = 198                                     ││
  │  │  ├── setEvaluatable(T3, true)                                    ││
  │  │  └── T3.joinCondition: T3.c_id = T2.id                          ││
  │  │        → T2 已标记 evaluatable ✓  (条件可求值)                   ││
  │  └──────────────────────────────────────────────────────────────────┘│
  │                              ↓                                       │
  │  return 198                                                          │
  └──────────────────────────────────────────────────────────────────────┘
```
**图 8-32: 拆解 calculateCost 三表代价累加的逐步过程**
```text
如图 8-33 所示，无效计划判定 — Join Condition 不可求值检测
                        │
  Plan 排列: [T3, T1, T2]  (假设 3 表连接)
                        │
  ┌─────────────────────────────────────────────────────────────────┐
  │  i=0: TableFilter = T3                                          │
  │    ├── getBestPlanItem(T3) → item3                              │
  │    ├── setEvaluatable(T3, true)                                 │
  │    └── T3.joinCondition = null  ← 无连接条件                    │
  │        → 通过                                 ✓                  │
  ├─────────────────────────────────────────────────────────────────┤
  │  i=1: TableFilter = T1                                          │
  │    ├── getBestPlanItem(T1) → item1                              │
  │    ├── setEvaluatable(T1, true)                                 │
  │    └── T1.joinCondition: T1.id = T3.id                          │
  │        → T3 已 evaluatable → 条件可求值    ✓                    │
  ├─────────────────────────────────────────────────────────────────┤
  │  i=2: TableFilter = T2                                          │
  │    ├── getBestPlanItem(T2) → item2                              │
  │    ├── setEvaluatable(T2, true)                                 │
  │    └── T2.joinCondition: T2.ref = T4.id                         │
  │        → T4 未出现在计划中!                                      │
  │        → 条件不可求值                    ✗ 无效计划!              │
  │        → cost = Infinity                                         │
  └─────────────────────────────────────────────────────────────────┘
                        │
  无效计划判定规则:
    ├── joinCondition 中引用的表必须已在之前的位置出现
    ├── 通过 setEvaluatable(filter, true) 标记可求值表
    ├── on.isEverything(EVALUATABLE_VISITOR) 检查所有引用是否可求值
    └── 无效计划会被暴力枚举和混合策略自动排除, 不被选为 bestPlan
```
**图 8-33: 演示 join 条件不可求值导致计划判定无效**

### 8.3.3 `PlanItem` 结构

源码位置：`org/h2/table/PlanItem.java`

```java
public class PlanItem {
    double cost;            // 估计代价
    private int[] masks;    // 索引条件掩码
    private Index index;    // 选中的索引
    private PlanItem joinPlan;       // 连接的子计划
    private PlanItem nestedJoinPlan; // 嵌套连接的子计划
}
```

如图 8-32 所示，`PlanItem` 封装了一个表在特定连接顺序下的最佳索引选择和代价。

```text
如图 8-34 所示，PlanItem 与 Plan、TableFilter 的关系
                        │
  Plan (一个候选执行计划)
    │
    ├── filters: TableFilter[]          ← 表访问顺序
    │     filters[0] = T1 (驱动表)
    │     filters[1] = T2
    │     filters[2] = T3
    │
    └── planItems: HashMap<TableFilter, PlanItem>
          │
          ├── T1 → PlanItem { cost=10, index=IDX_A, masks=[...] }
          │               └── joinPlan → T2 的 PlanItem
          │
          ├── T2 → PlanItem { cost=5, index=PK_B, masks=[...] }
          │               └── joinPlan → T3 的 PlanItem
          │
          └── T3 → PlanItem { cost=2, index=PK_C, masks=[...] }
                        └── joinPlan = null (末尾表)
                        │
  PlanItem 字段详解:
    ┌─────────────────────────────────────────────────────────────────┐
    │  cost: double     索引扫描估计代价 (由 Index.getCost() 返回)    │
    │  index: Index     该表选中的最优索引                            │
    │  masks: int[]     与索引列对应的条件掩码                        │
    │  joinPlan:        普通连接的下一个表 PlanItem (Nested Loop)     │
    │  nestedJoinPlan:  嵌套连接的子计划 (LEFT JOIN 等)              │
    └─────────────────────────────────────────────────────────────────┘
```
**图 8-34: 概览 PlanItem 在 Plan 中的字段关系**

### 8.3.4 代价模型工作图

如图 8-35 所示，H2 的代价模型通过复合乘法公式逐步累加各表的访问代价：

```text
Plan.calculateCost()
  │
  ├── cost = 1
  │
  ├── i=0: tableFilter = T1
  │     ├── getBestPlanItem(T1, filters, 0)
  │     ├── item.cost = 10 (索引扫描)
  │     └── cost = 1 + 1×10 = 11
  │
  ├── i=1: tableFilter = T2
  │     ├── getBestPlanItem(T2, filters, 1)
  │     ├── item.cost = 5 (唯一索引查找)
  │     ├── setEvaluatable(T2, true)
  │     ├── 检查 join condition 是否可求值
  │     └── cost = 11 + 11×5 = 66
  │
  ├── i=2: tableFilter = T3
  │     ├── getBestPlanItem(T3, filters, 2)
  │     ├── item.cost = 2 (主键查找)
  │     ├── setEvaluatable(T3, true)
  │     └── cost = 66 + 66×2 = 198
  │
  └── return 198
```

```text
如图 8-36 所示，代价模型核心公式对比
                        │
  不同连接顺序下的代价差异 (3 表连接)
                        │
  ┌──────────────────────────────────────────────────────────────────────┐
  │  排列              代价计算                        总代价           │
  ├──────────────────────────────────────────────────────────────────────┤
  │  [T1, T2, T3]     1+10=11, 11+55=66, 66+132=198   198              │
  │  [T1, T3, T2]     1+10=11, 11+22=33, 33+165=198   198              │
  │  [T2, T1, T3]     1+5=6, 6+60=66, 66+132=198      198              │
  │  [T2, T3, T1]     1+5=6, 6+12=18, 18+180=198      198              │
  │  [T3, T1, T2]     1+2=3, 3+30=33, 33+165=198      198              │
  │  [T3, T2, T1]     1+2=3, 3+15=18, 18+180=198      198              │
  └──────────────────────────────────────────────────────────────────────┘
                        │
  注: 在 item_cost 固定的情况下 (T1=10, T2=5, T3=2)
      所有排列的总代价相同, 均为 198
                        │
  原因: 复合乘法公式 total = ∏(1 + item_cost[i]) - 1
        乘法满足交换律: (1+10)(1+5)(1+2) = (1+5)(1+2)(1+10) = 11×6×3 = 198
                        │
  但实际 item_cost 并非固定:
    连接顺序影响索引选择 → 影响 item_cost → 影响总代价
    例如: T3 作为驱动表时, T3 的索引选择可能更优
          T1 作为驱动表时, T1 的扫描代价可能不同
                        │
  实际场景中的代价差异来源:
    ├── 驱动表的选择影响全表扫描 vs 索引扫描
    ├── 中间结果行数影响后续查找的重复次数
    └── 索引条件掩码匹配在不同顺序下效果不同
```
**图 8-35: 对比同代价表在六种排列下的总代价**

### 8.3.5 代价复合乘法公式可视化

如图 8-37 所示，复合乘法公式的展开揭示了不同连接顺序下代价差异的根本来源。

**图 8-36: 拆解 calculateCost 复合乘法的逐步累加过程**

```text
复合乘法公式推导与可视化

公式: total_cost = ∏(1 + item_cost[i]) - 1
                  i=0..n-1

物理含义: 每次累加的 cost 等于"当前中间结果行数 × 当前表扫描代价"
          ┌─────────────────────────────────────────────┐
          │  cost = 1  (初始: 1 行虚拟输入)              │
          │                                              │
          │  第 i 步: 扫描表 i 的代价 = item_cost[i]      │
          │           当前中间结果行数 = cost (之前累加)    │
          │           本次累加 = cost × item_cost[i]      │
          │           新 cost = cost + cost × item_cost[i]│
          └─────────────────────────────────────────────┘

3 表连接示例 (cost: T1=10, T2=5, T3=2):

  第 0 步: T1 代价 10
    cost = 1 + 1×10 = 11
    ├── 1 → 虚拟输入行
    └── 10 → T1 的扫描代价 (全表扫描或索引扫描)
    含义: 读取 T1 所有匹配行的代价 = 11

  第 1 步: T2 代价 5
    cost = 11 + 11×5 = 66
    ├── 11 → T1 返回的行数
    └── 5 → T2 的查找代价 (对 T1 的每一行, 在 T2 中查找)
    含义: 对 T1 的 11 行, 每行在 T2 中查找代价 5, 总代价 = 11×5 = 55
          加上之前的 11 → 66

  第 2 步: T3 代价 2
    cost = 66 + 66×2 = 198
    ├── 66 → T1 与 T2 连接后的行数
    └── 2 → T3 的查找代价
    含义: 对中间结果的 66 行, 每行在 T3 中查找代价 2, 总代价 = 66×2 = 132
          加上之前的 66 → 198

  最终代价 198 的物理意义:
    ├── 读取初始数据: 10 (T1)
    ├── 第一次连接: 11 × 5 = 55 (T1 结果驱动的 T2 查找)
    ├── 第二次连接: 66 × 2 = 132 (中间结果驱动的 T3 查找)
    └── 总代价: 10 + 55 + 132 = 197 ≈ 198 (含初始 1)

  如图 8-88 所示，不同连接顺序的代价差异:
    ├── [T1, T2, T3] cost = 198  (T1 驱动, 先连接 T2)
    ├── [T3, T2, T1] cost = 2 + 2×5 + 12×10 = 2+10+120 = 132
    │   (T3 驱动, 中间结果更小)
    └── 最佳顺序: 选择性最高的表在先, 最小化中间结果
```
**图 8-88: 演示三表连接复合乘法公式的展开过程**

复合乘法的本质是**中间结果行数的乘积和**。设第 i 个表的扫描代价为 c_i，总代价可展开为：

total_cost = 1 + c_0 + (1+c_0) × c_1 + (1+c_0)(1+c_1) × c_2 + ... = 1 + c_0 + c_1 + c_0c_1 + c_2 + c_0c_2 + c_1c_2 + c_0c_1c_2 + ...

展开后可以看到，总代价是所有可能连接路径的代价之和。低代价表先扫描的优势在于：其较小的中间结果作为后续连接的输入，大幅降低了连接的总代价。这就是为什么优化器总是倾向于将选择性高（过滤后行数少）的表放在连接顺序的前面。例如在 3 表连接中，如果将 T3（代价最低的表）放在前面，总代价从 198 降低到 132，优化了 33%。

```text
如图 8-38 所示，复合乘法公式展开与物理含义
                        │
  公式展开: total = ∏(1 + c_i) - 1
                 = c_0 + c_1 + c_2
                 + c_0·c_1 + c_0·c_2 + c_1·c_2
                 + c_0·c_1·c_2
                        │
  3 表示例 (T1=10, T2=5, T3=2):
                        │
  一阶项 (单表扫描代价):
    ┌── c_0 = 10          ← 读取 T1 的代价
    ├── c_1 = 5           ← 第一次连接的 T2 查找代价
    └── c_2 = 2           ← 第二次连接的 T3 查找代价
                        │
  二阶项 (中间结果代价):
    ┌── c_0·c_1 = 10×5 = 50    ← T1 驱动 T2 的中间结果代价
    ├── c_0·c_2 = 10×2 = 20    ← T1 驱动 T3 的中间结果代价
    └── c_1·c_2 = 5×2 = 10     ← T2 驱动 T3 的中间结果代价
                        │
  三阶项 (全连接代价):
    └── c_0·c_1·c_2 = 100      ← T1→T2→T3 全连接代价
                        │
  总代价 = 10 + 5 + 2 + 50 + 20 + 10 + 100 = 197 (+1 初始 = 198)
                        │
  物理含义:
    总代价 = 所有表扫描代价 + 所有中间结果连接代价
           = 17 + 80 + 100 = 197
           ≈ 1 + c_0 + c_0(1+c_1) + c_0(1+c_1)(1+c_2)
                        │
  不同顺序下二阶项差异:
    [T1,T2,T3]: c_0·c_1 = 50, c_0·c_2 = 20, c_1·c_2 = 10  → 二阶项=80
    [T3,T2,T1]: c_0·c_1 = 2,  c_0·c_2 = 10, c_1·c_2 = 5   → 二阶项=17
    ↑ 因为 T3 代价最小, 作为驱动表产生的中间结果也最小
```
**图 8-37: 拆解复合乘法公式的一二三阶项物理含义**

### 8.3.6 PlanItem 结构详细图

如图 8-39 所示，PlanItem 的执行路径揭示了代价在嵌套连接中的递归分配过程。

**图 8-38: 拆解 PlanItem 结构及其嵌套连接递归关系**

```text
PlanItem 对象结构:

如图 8-89 所示，┌─────────────────────────────────────────────────────────────────┐
│  PlanItem                                                       │
│                                                                 │
│  ├── cost: double                      ← 当前表的估计扫描代价   │
│  │     该代价由 Index.getCost() 返回                            │
│  │     物理含义: 扫描索引返回匹配行的估计代价                    │
│  │     示例: 主键等值查找 cost≈1                                │
│  │           非唯一索引 cost≈匹配行数 × 索引深度                 │
│  │           全表扫描 cost≈表总行数                              │
│  │                                                              │
│  ├── index: Index                       ← 选中的最优索引        │
│  │     类型: B-Tree 索引 / 哈希索引 / 空间索引 / 无索引(全表扫描) │
│  │     在 getBestPlanItem() 阶段确定                            │
│  │                                                              │
│  ├── masks: int[]                       ← 索引条件掩码          │
│  │     掩码用于指示 IndexCondition 与索引列的匹配关系            │
│  │     每个索引列对应一个掩码值:                                │
│  │       mask[i] = 0       → 该列无匹配条件                     │
│  │       mask[i] = EQUALITY → 该列有等值匹配                    │
│  │       mask[i] = START   → 该列有范围起始条件                 │
│  │       mask[i] = END     → 该列有范围结束条件                 │
│  │                                                              │
│  ├── joinPlan: PlanItem                 ← 普通连接的子计划      │
│  │     当 TableFilter 有 join 关系时, joinPlan 描述右侧表的    │
│  │     最优访问路径。递归结构, 对应 Nested Loop Join 的内表     │
│  │                                                              │
│  └── nestedJoinPlan: PlanItem           ← 嵌套连接的子计划      │
│        当 TableFilter 有 nestedJoin 关系时, 描述嵌套连接内部的  │
│        最优计划。用于处理 LEFT JOIN 等特殊连接类型               │
│                                                                 │
│  PlanItem 递归结构示例:                                          │
│    topFilter (T1)                                               │
│      └── planItem                                               │
│            ├── index: PK_T1                                     │
│            ├── cost: 10                                         │
│            ├── masks: [1, 0, 0]                                 │
│            ├── joinPlan → T2 的 PlanItem                        │
│            │     ├── index: IDX_T2_C1                           │
│            │     ├── cost: 5                                    │
│            │     ├── masks: [0, 2, 0]                           │
│            │     └── joinPlan → T3 的 PlanItem                  │
│            │           ├── index: IDX_T3_C2                     │
│            │           ├── cost: 2                              │
│            │           └── masks: [0, 0, 1]                     │
│            └── nestedJoinPlan: null                             │
└─────────────────────────────────────────────────────────────────┘
```

下面三张图分别从字段结构、执行路径与计划判定三个角度刻画 PlanItem：图 8-89 拆解五个字段及其嵌套关系，图 8-39 追踪 PlanItem 在嵌套循环中的执行路径，图 8-40 追踪 calculateCost 判定计划有效性的循环。

**图 8-89: 拆解 PlanItem 五个字段及其嵌套关系**

PlanItem 是代价模型中粒度为单个表的数据结构。其递归结构（`joinPlan` 字段指向下一个表的 PlanItem）反映了 Nested Loop Join 的执行模型：头表驱动外层循环，后续表依次作为内层循环。`masks` 数组存储了索引条件与索引列的对应关系，在执行阶段指导 `cursor.find()` 如何利用索引定位。`nestedJoinPlan` 和 `joinPlan` 的分离使得 H2 可以同时处理普通连接（JOIN）和嵌套连接（LEFT JOIN / RIGHT JOIN）的不同语义。

```text
如图 8-40 所示，PlanItem 执行路径与代价分配
                        │
  Nested Loop Join 执行时, PlanItem 指导每个表的访问方式
                        │
  执行顺序 (自上而下):
                        │
  TopFilter (驱动表 T1)
    │
    ├── PlanItem: cost=10, index=IDX_T1_A
    │     └── cursor.find() → 使用 IDX_T1_A 定位
    │
    ├── join.next() → T2
    │     │
    │     ├── PlanItem: cost=5, index=IDX_T2_B
    │     │     └── cursor.find(T1.col) → 利用 T1 当前值查找
    │     │
    │     └── join.next() → T3
    │           │
    │           ├── PlanItem: cost=2, index=PK_T3
    │           │     └── cursor.find(T1.col, T2.col) → 精确查找
    │           │
    │           └── join = null (末尾表)
    │
    └── 执行代价分配:
          ├── T1: 访问表 T1, 代价 10
          ├── T2: 对 T1 每行访问 T2, 代价 10 × 5 = 50
          └── T3: 对 T1,T2 每组合访问 T3, 代价 50 × 2 = 100
               总执行代价 ≈ 10 + 50 + 100 = 160
               (与优化器估计的 198 略有差异, 因不含初始值)
```
**图 8-39: 追踪 PlanItem 在嵌套循环中的执行路径**

### 8.3.7 无效计划判定流程

**图 8-40: 追踪 calculateCost 判定计划有效性的循环**

```text
如图 8-90 所示，无效计划判定流程
                        │
  输入: Plan 对象 (包含 filters 排列顺序和 condition)
                        │
                        ▼
  calculateCost() 循环:
    │
    for i = 0 to allFilters.length - 1:
      │
      ├─ tableFilter = allFilters[i]         ← 当前处理的表
      │
      ├─ item = getBestPlanItem(...)         ← 选择索引
      │
      ├─ cost += cost * item.cost            ← 累加代价
      │
      └─ setEvaluatable(tableFilter, true)   ← 标记此表为可求值
           │
           ├── 检查当前 TableFilter 的 join condition:
           │     on = tableFilter.getJoinCondition()
           │     │
           │     ├── on == null ?
           │     │     ├── YES → 无条件, 继续循环
           │     │     └── NO  → 检查条件可求值性
           │     │
           │     └── on.isEverything(EVALUATABLE_VISITOR) ?
           │           │
           │           ├── YES → 条件可求值, 继续循环
           │           │
           │           └── NO  → 条件不可求值
           │                  │
           │                  └── invalidPlan = true
           │                        break (退出循环)
           │
           └── 示例: 无效计划判定
                 │
                 ┌──────────────────────────────────────────────┐
                 │  连接顺序: [T3, T1, T2]                      │
                 │                                              │
                 │  i=0: T3  setEvaluatable(T3)=true            │
                 │       T3.joinCondition = T3.a = T1.b        │
                 │       T1 尚未被标记为 evaluatable!           │
                 │       → 条件不可求值 → 无效计划              │
                 │                                              │
                 │  i=1: T1  setEvaluatable(T1)=true            │
                 │       T1.joinCondition = T1.c = T2.d        │
                 │       T2 尚未被标记为 evaluatable!           │
                 │       → 条件不可求值 → 无效计划              │
                 │                                              │
                 │  结论: [T3, T1, T2] 是无效连接顺序           │
                 │                                              │
                 │  尝试: [T1, T3, T2]                          │
                 │  i=0: T1, T1.a = T3.b → T3 未标记 → 无效    │
                 │                                              │
                 │  尝试: [T1, T2, T3]                          │
                 │  i=0: T1, 无 join condition                 │
                 │  i=1: T2, T2.c = T3.d → T3 未标记 → 无效    │
                 │                                              │
                 │  尝试: [T2, T1, T3]                          │
                 │  i=0: T2, 无 join condition                 │
                 │  i=1: T1, T1.a = T3.b → T3 未标记 → 无效    │
                 │                                              │
                 │  尝试: [T2, T3, T1]                          │
                 │  i=0: T2, 无 join condition                 │
                 │  i=1: T3, T3.a = T1.b → T1 未标记 → 无效    │
                 │                                              │
                 │  尝试: [T3, T2, T1] (需 T2 先于 T1)          │
                 │  i=0: T3, 无 join condition                 │
                 │  i=1: T2, 无 join condition                 │
                 │  i=2: T1, T1.a = T3.b → T3 已标记 ✓         │
                 │       T1.c = T2.d → T2 已标记 ✓             │
                 │       → 所有条件可求值 → 有效计划!           │
                 └──────────────────────────────────────────────┘
                        │
                        ▼
  结果: 有效计划 [T3, T2, T1] 推进 T3→T2→T1
       无效计划 cost = Infinity (被优化器排除)
```
**图 8-90: 演示六种排列下的有效性判定结果**

`setEvaluatable()` 机制是 H2 保证连接顺序合法性的核心约束。在 `calculateCost()` 循环中，每当处理一个 TableFilter 后，就将其标记为"可求值"。后续表的 join condition 引用的表必须已被标记为可求值，否则计划无效。

这种约束反映了 Nested Loop Join 的物理执行模型：驱动表（外循环）必须先出现，内层循环的表才能引用驱动表的列值。如果 join condition 引用了尚未出现的表，意味着在执行当前表时无法计算该条件——因为它需要的数据尚未被读取。

图中所示的示例展示了 3 表连接的搜索空间约束：在 6 种排列中，只有那些满足"被引用表先于引用表出现"约束的排列才是有效的。这种约束大幅缩小了搜索空间，减少了需要评估的排列数量。在真实场景中，多表连接通常包含多个交叉引用的 join condition，实际有效的排列数远小于 n!。

```text
如图 8-41 所示，无效计划判定: 依赖关系与搜索空间缩减
                        │
  3 表连接示例: T1, T2, T3
  连接条件: T1.a = T3.b, T1.c = T2.d
                        │
  依赖关系图:
    T1 ←── T3  (T3 需要 T1 已标记)
    T1 ←── T2  (T2 需要 T1 已标记)
    │
    关键词: T1 必须先于 T2 和 T3 出现
                        │
  搜索空间缩减:
                        │
  全部 6 种排列:
    ┌────────────────────────────────────────────────────────────────┐
    │  排列              有效性    原因                              │
    ├────────────────────────────────────────────────────────────────┤
    │  [T1, T2, T3]     有效      T1→T2 ✓, T1→T3 ✓               │
    │  [T1, T3, T2]     有效      T1→T3 ✓, T1→T2 ✓               │
    │  [T2, T1, T3]     有效      T2 无条件, T1→T2 ✓, T1→T3 ✓   │
    │  [T2, T3, T1]     无效      T3 需要 T1 → T1 未标记 ✗       │
    │  [T3, T1, T2]     无效      T3 需要 T1 → T1 未标记 ✗       │
    │  [T3, T2, T1]     无效      T3 需要 T1 → T1 未标记 ✗       │
    └────────────────────────────────────────────────────────────────┘
                        │
  有效排列: [T1,T2,T3], [T1,T3,T2], [T2,T1,T3]
  搜索空间缩减: 6 → 3 (减少 50%)
                        │
  多表场景 (n 表, 全连接):
    如果所有表之间都有连接, 有效排列数 = n!
    (因为任何表都可以引用已出现的表)
                        │
  实际场景:
    连接条件通常是星型或雪花型
    事实表引用维度表
    有效排列数通常介于 n!/2 到 n! 之间
    具体取决于依赖关系图的拓扑结构
```
**图 8-41: 拆解依赖关系对三表排列搜索空间的缩减**

---

## 8.4 索引选择机制

### 8.4.1 `TableFilter.getBestPlanItem()`

源码位置：`org/h2/table/TableFilter.java:209`

为当前表从所有候选索引中选出代价最低的一个：

```text
TableFilter.getBestPlanItem(session, filters, filter, allColumnsSet, isSelectCommand)
  │
  ├── 1. 构建 masks 数组
  │     遍历 indexConditions，对每个条件设置对应列的掩码
  │
  ├── 2. 调用 table.getBestPlanItem(session, masks, filters, ...)
  │     遍历表的所有索引:
  │     ├── 对每个索引，根据 masks 判断适用性
  │     ├── 调用 index.getCost() 估算代价
  │     └── 选取最低代价索引
  │
  ├── 3. 代价调整
  │     item.cost -= item.cost × indexConditions.size() / 100 / (filter + 1)
  │     索引条件越多，代价越低，使条件多的表更早执行
  │
  └── 4. 处理嵌套连接和普通连接
        ├── nestedJoinPlan: 递归计算
        └── joinPlan: 递归计算
```

```text
如图 8-42 所示，getBestPlanItem() 与代价调整机制
                        │
  代价调整公式:
    item.cost = item.cost - item.cost × n / 100 / (filter + 1)
                      原始代价        索引条件数   位置权重
                        │
  示例 1: T1 (第1个位置, 有2个索引条件)
    item.cost = 50 - 50 × 2 / 100 / (0 + 1) = 50 - 1 = 49
    ↓ 条件数量大会降低代价, 使该表更可能被前置
                        │
  示例 2: T3 (第3个位置, 有2个索引条件)
    item.cost = 50 - 50 × 2 / 100 / (2 + 1) = 50 - 0.33 = 49.67
    ↓ 位置越靠后, 调整幅度越小
                        │
  示例 3: T1 (第1个位置, 无索引条件)
    item.cost = 50 - 50 × 0 / 100 / (0 + 1) = 50
    ↓ 无索引条件时, 代价不做调整
                        │
  调整效果: 索引条件多的表被"鼓励"放在连接顺序的前面
    原因: 条件多的表能更早过滤大量行, 减少后续连接代价
```
**图 8-42: 拆解 getBestPlanItem 代价调整公式**
```text
如图 8-43 所示，嵌套连接与普通连接的递归计算路径
                        │
  TableFilter.getBestPlanItem(session, filters, filterIndex, ...)
    │
    ├── Step 1: 为当前 TableFilter 选择最佳单表访问路径
    │     ├── 构建 masks → table.getBestPlanItem()
    │     └── 返回 PlanItem (含 selectedIndex, cost, masks)
    │
    ├── Step 2: 检查是否有嵌套连接 (nestedJoin)
    │     │
    │     ├── nestedJoin != null?
    │     │     │
    │     │     ├── YES → 递归计算嵌套连接
    │     │     │     │
    │     │     │     ├── nestedJoin.getBestPlanItem(session, ...)
    │     │     │     │     ├── 递归调用自身
    │     │     │     │     ├── 为嵌套子查询选择最佳索引
    │     │     │     │     └── 返回子 PlanItem (含子代价)
    │     │     │     │
    │     │     │     └── item.nestedJoinPlan = subPlanItem
    │     │     │
    │     │     └── NO → 跳过
    │     │
    │     └── 检查是否有普通连接 (join)
    │           │
    │           ├── join != null?
    │           │     │
    │           │     ├── YES → 递归计算连接子表
    │           │     │     │
    │           │     │     ├── join.getBestPlanItem(session, ...)
    │           │     │     │     ├── 递归到 join 链的下一节点
    │           │     │     │     └── 累加子代价
    │           │     │     │
    │           │     │     └── item.joinPlan = subPlanItem
    │           │     │
    │           │     └── NO → 完成
    │           │
    │           └── 递归终止条件: join == null && nestedJoin == null
    │
    └── return item (含完整子树 PlanItem 链)
```
**图 8-43: 对比嵌套连接与普通连接的递归计算路径**

### 8.4.2 `IndexCondition` 类型

源码位置：`org/h2/index/IndexCondition.java`

```java
public class IndexCondition {
    public static final int EQUALITY           = 1;   // 等值条件 =
    public static final int START              = 2;   // 范围起始 >= >
    public static final int END                = 4;   // 范围结束 <= <
    public static final int RANGE              = 6;   // BETWEEN (START|END)
    public static final int ALWAYS_FALSE       = 8;   // 恒假条件
    public static final int SPATIAL_INTERSECTS = 16;  // 空间交叉
}
```

如图 8-34 所示，条件通过**掩码**与索引匹配。每个 `IndexCondition` 都绑定到一个特定的列和一个比较类型。

```text
IndexCondition 类型与掩码取值
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  常量名              值   含义            SQL 示例                 │
  ├────────────────────────────────────────────────────────────────────┤
  │  EQUALITY            1    等值条件       col = 100                │
  │  START               2    范围起始       col > 10, col >= 5      │
  │  END                 4    范围结束       col < 20, col <= 100    │
  │  RANGE               6    范围           col BETWEEN 1 AND 100   │
  │  ALWAYS_FALSE        8    恒假           col IS NULL (无匹配)    │
  │  SPATIAL_INTERSECTS  16   空间交叉       ST_INTERSECTS(col, ...) │
  └────────────────────────────────────────────────────────────────────┘
                        │
  掩码组合规则:
    ├── 同一列上可以有多个条件
    │     col > 5 AND col < 20 → START | END = 2 | 4 = 6 (RANGE)
    │
    ├── 掩码用于与索引列匹配:
    │     如果 mask[column_id] != 0, 则该列有索引可用条件
    │     掩码值越大, 条件精度越高 (EQUALITY > START > END)
    │
    └── 掩码存储位置:
          masks 数组的长度 = 表的总列数
          masks[column_id] = 该列上的条件掩码 (多个条件按位或)
```
**图 8-44: 罗列 IndexCondition 六种类型与掩码取值**

### 8.4.3 条件提取过程

如图 8-44 所示，在 `Select.preparePlan()` 阶段，`TableFilter.createIndexConditions()` 将 WHERE 条件拆解为与当前表相关的 `IndexCondition`：

```text
WHERE T1.a = 10 AND T1.b > 5 AND T2.c = 'x'
  │
  ├── T1 的 IndexConditions:
  │     ├── [a EQUALITY 10]     掩码: 1
  │     └── [b START 5]        掩码: 2
  │
  └── T2 的 IndexConditions:
        └── [c EQUALITY 'x']    掩码: 1
```

```text
条件提取完整流程
                        │
  SQL: SELECT * FROM t1 JOIN t2 ON t1.id = t2.t1_id
       WHERE t1.status = 'ACTIVE' AND t2.amount > 100
                        │
                        ▼
  Select.preparePlan()
    │
    ├── 1. 解析 WHERE 为表达式树
    │     AND
    │     ├── Comparison(t1.status = 'ACTIVE')
    │     └── Comparison(t2.amount > 100)
    │
    ├── 2. 绑定列到 TableFilter
    │     t1.status → TableFilter(T1), column=2
    │     t2.amount → TableFilter(T2), column=3
    │
    ├── 3. TableFilter(T1).createIndexConditions()
    │     ├── 遍历 T1 的表达式: [t1.status = 'ACTIVE']
    │     ├── t1.status 在 T1 的列中 → 创建 IndexCondition
    │     └── 结果: [status EQUALITY 'ACTIVE', mask=1]
    │
    ├── 4. TableFilter(T2).createIndexConditions()
    │     ├── 遍历 T2 的表达式: [t2.amount > 100]
    │     ├── t2.amount 在 T2 的列中 → 创建 IndexCondition
    │     └── 结果: [amount START 100, mask=2]
    │
    └── 5. 每个 TableFilter 的 indexConditions 就绪
          准备在 getBestPlanItem() 中使用
```

这组图把"条件提取—代价估算—选择性影响"拆成三个层次：图 8-45 追踪 WHERE 条件提取索引条件的完整流程，图 8-46 对比六种索引访问方式的代价估算，图 8-47 标注不同条件选择性对索引代价的影响。

**图 8-45: 追踪 WHERE 条件提取索引条件的完整流程**

### 8.4.4 索引代价估算

如图 8-45 所示，`Index.getCost()` 基于统计信息返回大致行数：

- **主键/唯一索引**: cost ≈ 1（等值匹配时）
- **普通索引 (范围扫描)**: cost ≈ 估计匹配行数 × 索引深度
- **全表扫描**: cost ≈ 表总行数

```text
如图 8-46 所示，索引代价估算示例 (表 TEST, 10000 行)
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  索引类型           查询条件                  代价估算              │
  ├─────────────────────────────────────────────────────────────────────┤
  │  主键 PK(id)        id = 100                 1                     │
  │                     (等值匹配, B+树精确查找)                         │
  │                                                                     │
  │  唯一索引 UX(email)  email = 'a@b.com'       1                     │
  │                     (唯一索引等值, 与主键相同)                       │
  │                                                                     │
  │  非唯一索引          name = 'John'            50 ← 估计行数 × 1    │
  │  IDX_NAME(name)     (等值匹配, 非唯一)        (10000 × 0.5% 选择率) │
  │                                                                     │
  │  非唯一索引          name LIKE 'J%'           200                   │
  │  IDX_NAME(name)     (前缀范围)               (10000 × 2% 选择率)    │
  │                                                                     │
  │  非唯一索引          age > 18                 8000                  │
  │  IDX_AGE(age)       (范围扫描, 80% 行)        (10000 × 80%)        │
  │                                                                     │
  │  无索引 (全表扫描)   status = 'ACTIVE'        10000                 │
  │                     (逐行检查)               (全部 10000 行)        │
  └─────────────────────────────────────────────────────────────────────┘
```
**图 8-46: 对比六种索引访问方式的代价估算**
```text
如图 8-47 所示，索引选择性比较 — 不同查询条件的匹配行占比
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  表 TEST (10000 行)                                                  │
  │                                                                     │
  │  索引 IDX_NAME(name) 的列值分布:                                     │
  │                                                                     │
  │  值           频率          选择性                                   │
  │  ──────────   ──────────    ─────────────────────────               │
  │  'John'       50 行         0.5%   ← 高选择性, 适合索引              │
  │  'Jane'       80 行         0.8%   ← 高选择性                       │
  │  'Smith'      200 行        2.0%   ← 中等选择性                     │
  │  'Lee'        500 行        5.0%   ← 低选择性                       │
  │  '' (空串)    1000 行       10.0%  ← 很低选择性                      │
  │  NULL         200 行        2.0%   ← 不参与索引                      │
  │  ──────────   ──────────                                             │
  │  合计         10000 行      100%                                     │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  选择性对代价的影响:
                        │
  ┌─────────────────────────────────────────────────────────────────┐
  │  条件           选择性   索引代价   回表代价   总代价    建议      │
  │  ─────────────  ───────  ────────  ────────  ───────  ───────── │
  │  name = 'John'   0.5%     1          49       50      使用索引  │
  │  name = 'Lee'    5.0%     1         499      500     使用索引  │
  │  name > 'A'     90.0%     1        8999     9000    全表扫描   │
  │                    (几乎全部行, 索引+回表不如全表扫描)             │
  │  name IS NULL    2.0%    无法使用索引 → 全表扫描                  │
  │                    (NULL 不存储在非唯一索引中)                     │
  └─────────────────────────────────────────────────────────────────┘
                        │
  选择率阈值规则:
    当选择率 > 15-20% 时, 全表扫描通常比索引扫描更快
    原因: 索引扫描需要随机 I/O (回表), 而全表扫描是顺序 I/O
```
**图 8-47: 对比不同条件选择性对索引代价的影响**

### 8.4.5 索引条件匹配图

```text
索引选择过程
  │
  Table: TEST (10000 行)
  │
  索引:
    PK(ID)           → 唯一, B-Tree
    IDX_NAME(NAME)   → 非唯一, B-Tree
    IDX_AGE(AGE)     → 非唯一, B-Tree
  │
  WHERE: name = 'John' AND age > 25
  │
  ▼
  TableFilter.getBestPlanItem()
  │
  ├── masks: [name → EQUALITY, age → START]
  │
  ├── PK(ID): mask[ID]=0 → 不匹配, cost 忽略
  │
  ├── IDX_NAME(NAME):
  │     ├── mask[NAME]=EQUALITY (匹配)
  │     ├── 估计匹配行: 50 (根据统计)
  │     ├── cost ≈ 50
  │     └── 可以配合 age 条件做 filter
  │
  ├── IDX_AGE(AGE):
  │     ├── mask[AGE]=START (匹配)
  │     ├── 估计匹配行: 3333 (age > 25)
  │     ├── cost ≈ 3333
  │     └── 必须配合 name 条件做 filter
  │
  └── 选择: IDX_NAME (cost=50)
```

```text
如图 8-48 所示，索引选择决策流程 (多索引候选比较)
                        │
  输入: masks = [name → EQUALITY, age → START]
                        │
                        ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  索引候选 1: PK(ID)                                             │
  │  ├── 索引列: [ID]                                               │
  │  ├── masks[ID]=0 → 无匹配                                       │
  │  └── 结论: 不适用, 跳过                                        │
  ├─────────────────────────────────────────────────────────────────┤
  │  索引候选 2: IDX_NAME(NAME)                                     │
  │  ├── 索引列: [NAME]                                             │
  │  ├── masks[NAME]=EQUALITY → 等值匹配 ✓                          │
  │  ├── getCost(): 估计 50 行                                      │
  │  └── 代价: cost = 50                                            │
  ├─────────────────────────────────────────────────────────────────┤
  │  索引候选 3: IDX_AGE(AGE)                                       │
  │  ├── 索引列: [AGE]                                              │
  │  ├── masks[AGE]=START → 范围起始匹配 ✓                          │
  │  ├── getCost(): 估计 3333 行                                    │
  │  └── 代价: cost = 3333                                          │
  └─────────────────────────────────────────────────────────────────┘
                        │
                        ▼
  选择: IDX_NAME (cost=50), 因为 50 < 3333
                        │
  代价调整:
    ├── indexConditions.size() = 2 (name 等值 + age filter)
    ├── filter = 0 (第 1 个位置)
    └── adjusted_cost = 50 - 50 × 2 / 100 / 1 = 50 - 1 = 49
```
**图 8-48: 拆解 getBestPlanItem 三索引候选比较**

### 8.4.6 索引覆盖扫描

如图 8-49 所示，当索引包含了查询所需的所有列时，H2 可以使用索引覆盖扫描（Index-Only Scan），跳过表数据访问：

```text
查询: SELECT name FROM test WHERE name = 'John'
索引: IDX_NAME(name)        ← name 列在索引中
      └── 无需回表，直接从索引读取
```

```text
如图 8-50 所示，索引覆盖扫描 vs 非覆盖扫描对比
                        │
  场景: 查询 name 列, 条件 name = 'John'
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  覆盖扫描 (Index-Only Scan):                                      │
  │                                                                   │
  │  SELECT name FROM test WHERE name = 'John'                        │
  │  索引 IDX_NAME(name): 包含 name 列                                │
  │                                                                   │
  │  B+树定位 → 叶子节点读取 → 直接返回 name                         │
  │  ┌──────────┐    ┌──────────┐    ┌──────────┐                    │
  │  │ 根节点    │ →  │ 分支节点  │ →  │ 叶子节点  │ → name 值        │
  │  └──────────┘    └──────────┘    └──────────┘                    │
  │                                   key='John'                     │
  │                                                                   │
  │  I/O: 仅索引页 (3-4 次索引页读取)                                  │
  └────────────────────────────────────────────────────────────────────┘
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  非覆盖扫描 (需回表):                                              │
  │                                                                   │
  │  SELECT name, status FROM test WHERE name = 'John'                │
  │  索引 IDX_NAME(name): 包含 name 但不包含 status                   │
  │                                                                   │
  │  B+树定位 → 叶子节点读取 → 根据 rowId 回表 → 返回完整行          │
  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
  │  │ 根节点    │ →  │ 分支节点  │ →  │ 叶子节点  │ →  │ 数据页   │    │
  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘    │
  │                                   key='John'    rowId=123        │
  │                                                                   │
  │  I/O: 索引页 + 数据页 (4-5 次页面读取)                            │
  └────────────────────────────────────────────────────────────────────┘
                        │
  何时能使用覆盖扫描?
    ├── 索引包含 SELECT 所有列
    ├── 索引包含 WHERE 所有条件列
    └── 无需访问表数据即可完成查询
```
**图 8-49: 对比索引覆盖扫描与回表访问的 IO 路径**

### 8.4.7 索引条件掩码匹配过程详细图

如图 8-51 所示，不同查询条件下掩码匹配的效率决定了索引的实际可用性。

**图 8-50: 演示 masks 数组与多索引列的匹配过程**

```text
索引条件掩码匹配过程

如图 8-91 所示，输入: WHERE T1.a = 10 AND T1.b > 5 AND T1.c BETWEEN 1 AND 100
                        │
                        ▼
  步骤 1: 从 WHERE 条件提取 T1 的 IndexConditions
    │
    ├── condition: T1.a = 10    → IndexCondition(EQUALITY, column=a)
    ├── condition: T1.b > 5     → IndexCondition(START, column=b)
    └── condition: T1.c BETWEEN 1 AND 100
                                → IndexCondition(RANGE, column=c)
                        │
                        ▼
  步骤 2: 构建 masks 数组 (长度 = 表的总列数)
    │
    ┌─────────────────────────────────────────────────────────┐
    │                   列索引: 0    1    2    3    4          │
    │                   列名:  ID   A    B    C    D          │
    │                   masks: [0,   1,   2,   6,   0]       │
    │                           │    │    │    │              │
    │                           │    │    │    └── mask[3]=6 │
    │                           │    │    │        (START|END │
    │                           │    │    │         = RANGE)  │
    │                           │    │    └─── mask[2]=2     │
    │                           │    │            (START)     │
    │                           │    └─── mask[1]=1          │
    │                           │            (EQUALITY)       │
    │                           └─── mask[0]=0               │
    │                                       (无条件)          │
    └─────────────────────────────────────────────────────────┘
                        │
                        ▼
  步骤 3: 遍历所有索引, 比对 masks 与索引列
    │
    ├── 主键 PK(ID): 索引列 [ID]
    │     mask[0]=0 → 无匹配条件
    │     cost = 10000 (全表扫描等效代价)
    │
    ├── 索引 IDX_A(A, B): 索引列 [A, B]
    │     mask[1]=1 (EQUALITY) → A 列匹配等值条件  ✓
    │     mask[2]=2 (START)   → B 列匹配起始条件  ✓
    │     掩码覆盖: 前 2 列完全匹配
    │     cost = 50  (等值≈10行, 范围≈5倍)
    │
    ├── 索引 IDX_C(C): 索引列 [C]
    │     mask[3]=6 (RANGE) → C 列匹配范围条件     ✓
    │     但只有 C 列, 缺少 A 和 B 条件
    │     cost = 100 (范围扫描, 匹配行较多)
    │
    └── 索引 IDX_D(D): 索引列 [D]
          mask[4]=0 → 无匹配条件
          cost = 10000 (全表扫描等效代价)
                        │
                        ▼
  步骤 4: 选择最低代价索引 → IDX_A(A, B) cost=50
    │
    代价调整: item.cost = 50 - 50 × 2/100 / (0+1) = 49
    因为 T1 有 2 个索引条件, 代价微调 -1%
```

以下三张图共同呈现 masks 匹配机制与索引效率：图 8-91 拆解 masks 数组与候选索引的逐步匹配，图 8-51 对比五种条件类型与组合索引的利用效率，图 8-52 对比多种查询条件下九种索引的代价。

**图 8-91: 拆解 masks 数组与候选索引的逐步匹配**

掩码匹配是 H2 索引选择的核心算法。`masks` 数组的长度等于表的总列数，每个元素的取值表示该列上索引条件的类型（0=无条件, 1=等值, 2=范围起始, 4=范围结束, 6=范围, 8=恒假）。遍历索引时，将索引的列顺序与 `masks` 数组按位比对：对于索引的第 i 列，如果 `masks[columnId] != 0`，则该索引在该列上有匹配条件。匹配的列越多、条件类型越精确（等值优先于范围），索引的代价越低。

```text
如图 8-52 所示，索引掩码匹配效率分析
                        │
  不同条件类型的匹配效果排序:
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  优先级   条件类型     掩码值   索引利用效率          示例         │
  ├────────────────────────────────────────────────────────────────────┤
  │  最高     等值         1      精确定位到一行       id = 100       │
  │  ↑       范围起始     2      定位到起始位置       age > 18       │
  │  │       范围结束     4      定位到结束位置       price <= 100   │
  │  │       范围(BTW)    6      定位起止范围         date BETWEEN   │
  │  最低    恒假         8      永不匹配             false条件      │
  └────────────────────────────────────────────────────────────────────┘
                        │
  组合索引匹配示例:
                        │
  索引 IDX_A_B(A, B):
  ┌────────────────────────────────────────────────────────────────────┐
  │  查询条件                    A 列掩码   B 列掩码   是否可用       │
  ├────────────────────────────────────────────────────────────────────┤
  │  WHERE a = 1                 EQUALITY   0         可用 (前缀等值)│
  │  WHERE a = 1 AND b = 2      EQUALITY   EQUALITY   可用 (完全匹配)│
  │  WHERE a = 1 AND b > 5      EQUALITY   START      可用 (范围扫描)│
  │  WHERE a > 1                 START      0         可用 (范围扫描)│
  │  WHERE b = 2                 0          EQUALITY   不可用         │
  │                              (缺少前缀列 a, 无法利用索引)          │
  └────────────────────────────────────────────────────────────────────┘
```
**图 8-51: 对比五种条件类型与组合索引的利用效率**

### 8.4.8 索引选择代价比较图

如图 8-53 所示，不同索引在不同查询条件下的代价差异显著，选择合适的索引对查询性能至关重要。

**图 8-52: 对比多种查询条件下九种索引的代价**

```text
索引代价比较 (表 TEST, 10000 行)
                        │
  ┌───────────────────────────────────────────────────────────┐
  │  索引类型          WHERE 条件              估计代价       │
  ├───────────────────────────────────────────────────────────┤
  │  PK(ID)           id = 100                1       ← 最低 │
  │  PK(ID)           id > 5000               5000           │
  │  IDX_NAME(NAME)   name = 'John'           50             │
  │  IDX_NAME(NAME)   name LIKE 'J%'          200            │
  │  IDX_AGE(AGE)     age = 25                40             │
  │  IDX_AGE(AGE)     age > 18                8000           │
  │  IDX_AGE(AGE)     age BETWEEN 20 AND 30   1000           │
  │  IDX_CAT(CAT)     cat IN ('A','B','C')    300            │
  │  (全表扫描)        无条件                   10000          │
  └───────────────────────────────────────────────────────────┘
                        │
                        ▼
  组合索引优势:

  ┌───────────────────────────────────────────────────────────┐
  │  索引                      WHERE 条件          cost      │
  ├───────────────────────────────────────────────────────────┤
  │  IDX_A_B(A, B)          a=1 AND b=10          1          │
  │  IDX_A_B(A, B)          a=1                   10         │
  │  IDX_A_B(A, B)          b=10                  10000      │
  │                         (b 的等值条件无法使用               │
  │                          因为缺少 a 条件)                  │
  │  IDX_B_A(B, A)          b=10 AND a=1          1          │
  │  IDX_B_A(B, A)          b=10                  50         │
  └───────────────────────────────────────────────────────────┘
                        │
                        ▼
  选择率对代价的影响:

  如图 8-92 所示，查询: status = 'PAID' AND amount > 100
    │
    ├── IDX_STATUS(status): cost = 3000
    │     等值匹配 status='PAID' → 约 3000 行
    │     amount>100 作为 filter 条件
    │
    └── IDX_AMOUNT(amount): cost = 5000
          范围匹配 amount>100 → 约 5000 行
          status='PAID' 作为 filter 条件
```

下面三张图分别从选择性影响、案例对比与覆盖扫描三个角度刻画索引代价选择：图 8-92 对比不同选择性条件下索引的代价，图 8-53 演示订单查询六种索引的代价选择，图 8-54 对比覆盖扫描与回表访问的执行路径差异。

**图 8-92: 对比不同选择性条件下索引的代价**

该图总结了 H2 索引代价估算的典型值。核心原则：**等值条件优于范围条件，前缀匹配优于非前缀匹配**。组合索引的列顺序至关重要——最左前缀原则决定了哪些查询能有效利用索引。在缺少索引前缀列的情况下（如图中 `b=10` 查询无法使用 `IDX_A_B(A,B)`），优化器退化为全表扫描。

```text
如图 8-54 所示，索引代价选择的实际案例对比
                        │
  案例: 订单查询
    SELECT * FROM orders
    WHERE customer_id = 123
      AND status = 'PAID'
      AND amount > 100
                        │
  可用索引及代价估算:
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  索引                           估计代价    选择理由              │
  ├────────────────────────────────────────────────────────────────────┤
  │  PK(id)                         10000      无法使用 (条件无 id)  │
  │  IDX_CUSTOMER(customer_id)      50          等值匹配, 约 50 行   │
  │  IDX_STATUS(status)             3333        等值, 但 33% 行      │
  │  IDX_AMOUNT(amount)             8000        范围, 80% 行         │
  │  IDX_C_S(customer, status)      5           双等值匹配, 约 5 行  │
  │  IDX_C_S_A(c, status, amount)   5          覆盖+双等值+范围     │
  └────────────────────────────────────────────────────────────────────┘
                        │
  最佳选择: IDX_C_S_A (覆盖索引, 不需要回表)
    └── cost = 5 (双等值条件高度精确)
                        │
  次优选择: IDX_C_S (双等值, 但需要回表读 amount)
    └── cost = 5 (但需要额外回表 I/O)
                        │
  最差选择: 全表扫描
    └── cost = 10000 (读全部 10000 行)
```
**图 8-53: 演示订单查询六种索引的代价选择**

### 8.4.9 索引覆盖扫描与回表访问对比

**图 8-54: 对比覆盖扫描与回表访问的执行路径差异**

```text
索引覆盖扫描 vs 回表访问

场景 1: 索引覆盖扫描 (无需回表)
  ┌─────────────────────────────────────────────────────────────┐
  │  查询: SELECT name FROM test WHERE name = 'John'            │
  │  索引: IDX_NAME(name)                                       │
  │                                                            │
  │  执行路径:                                                  │
  │    cursor.find(name='John')    ← B-Tree定位到叶子节点        │
  │    leaf_node: [key='John', value=name值]                    │
  │    ↓                                                        │
  │    cursor.next()               ← 读取下一叶子节点           │
  │    leaf_node: [key='John2', value=name值]                   │
  │    ↓                                                        │
  │    直接返回 name 值, 无需访问表数据                         │
  │    I/O: 仅索引页读取                                         │
  └─────────────────────────────────────────────────────────────┘

场景 2: 普通索引访问 (需要回表)
  ┌─────────────────────────────────────────────────────────────┐
  │  查询: SELECT name, status FROM test WHERE name = 'John'    │
  │  索引: IDX_NAME(name)                                       │
  │                                                            │
  │  执行路径:                                                  │
  │    cursor.find(name='John')    ← B-Tree定位到叶子节点        │
  │    leaf_node: [key='John', rowId=123]                      │
  │    ↓                                                        │
  │    table.getRow(rowId=123)     ← 根据 rowId 回表读取数据   │
  │    data_page: [id=123, name='John', status='A', ...]       │
  │    ↓                                                        │
  │    返回 name + status 值, 需要索引 + 表两次访问             │
  │    I/O: 索引页 + 数据页读取                                  │
  └─────────────────────────────────────────────────────────────┘

场景 3: 全表扫描 (无索引)
  ┌─────────────────────────────────────────────────────────────┐
  │  查询: SELECT * FROM test WHERE status = 'ACTIVE'           │
  │  (status 列无索引)                                          │
  │                                                            │
  │  执行路径:                                                  │
  │    tableScan.next()              ← 顺序扫描表数据          │
  │    ↓                                                        │
  │    row[0]: [id=1, name='A', status='ACTIVE']               │
  │    filter: status='ACTIVE' → 匹配 ✓                        │
  │    ↓                                                        │
  │    row[1]: [id=2, name='B', status='INACTIVE']             │
  │    filter: status='ACTIVE' → 不匹配 ✗                      │
  │    ↓                                                        │
  │    ... (遍历所有 10000 行)                                  │
  │    I/O: 全部数据页读取                                       │
  └─────────────────────────────────────────────────────────────┘

  如图 8-93 所示，代价对比:
  ┌───────────────────────────────────────────────────────────┐
  │  访问方式            I/O 次数        适用场景              │
  ├───────────────────────────────────────────────────────────┤
  │  索引覆盖扫描         索引页数        SELECT 列均在索引中 │
  │  普通索引访问       索引页+数据页     SELECT 列超出索引   │
  │  全表扫描             全部数据页       无条件或全量查询    │
  └───────────────────────────────────────────────────────────┘
```
**图 8-93: 对比三种数据访问方式的 IO 路径**

三种数据访问方式在执行路径上有本质差异：索引覆盖扫描最理想（仅索引页读取），普通索引访问需要索引 + 回表两步操作，全表扫描需要顺序读取全部数据页。优化器会根据查询的列选择性和可用索引，在三种方式中选择代价最低的方案。

```text
如图 8-55 所示，如何判断能否使用索引覆盖扫描?
                        │
  查询: SELECT a, b FROM test WHERE a = 1 AND c > 5
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  步骤 1: 列出查询所需的所有列                                      │
  │    ├── SELECT 列: a, b                                             │
  │    ├── WHERE 条件列: a, c                                          │
  │    └── 全部所需列: {a, b, c}                                      │
  │                                                                     │
  │  步骤 2: 检查候选索引是否包含所有列                                │
  │    ├── IDX_A(a): 包含 {a} → 缺少 b, c → 需回表                    │
  │    ├── IDX_A_B(a, b): 包含 {a, b} → 缺少 c → 需回表              │
  │    ├── IDX_A_C(a, c): 包含 {a, c} → 缺少 b → 需回表              │
  │    └── IDX_A_B_C(a, b, c): 包含 {a, b, c} → 覆盖扫描!            │
  │                                                                     │
  │  步骤 3: 选择覆盖索引或最低代价索引                                 │
  │    如果存在覆盖索引 → 优先选择 (避免回表 I/O)                       │
  │    否则 → 选择代价最低的普通索引                                    │
  └────────────────────────────────────────────────────────────────────┘
                        │
  覆盖索引的收益量化:
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  场景              覆盖扫描 I/O    普通索引 I/O     节省          │
  ├────────────────────────────────────────────────────────────────────┤
  │  等值 50 行        索引页 3 次      索引 3 + 数据 50   94%        │
  │  范围 1000 行      索引页 3 次      索引 3 + 数据 1000 99.7%      │
  │  全表扫描           全部数据页        —                —          │
  └────────────────────────────────────────────────────────────────────┘
```
**图 8-55: 拆解覆盖索引判定步骤及节省的 IO 收益**

---

## 8.5 TableFilter 与条件求值

### 8.5.1 `TableFilter.next()` — 行迭代

源码位置：`org/h2/table/TableFilter.java:438`

`TableFilter.next()` 是整个查询执行的核心循环：

```java
public boolean next() {
    if (state == BEFORE_FIRST) {
        cursor.find(session, indexConditions);              // 首次：初始化游标
    } else if (state == FOUND && join != null && join.next())
        return true;                                        // 连接表有更多行
    while (true) {
        if (cursor.isAlwaysFalse()) state = AFTER_LAST;
        else if (cursor.next()) { currentSearchRow = cursor.getSearchRow(); state = FOUND; }
        else state = AFTER_LAST;
        // 嵌套连接处理（含外连接 NULL 行补全）
        if (nestedJoin != null && state == FOUND && !nestedJoin.next()) {
            state = AFTER_LAST;
            if (joinOuter && !foundOne) setNullRow();
            else continue;
        }
        if (!isOk(filterCondition)) continue;               // 过滤条件检查
        boolean joinConditionOk = isOk(joinCondition);
        if (state == FOUND) {
            if (joinConditionOk) foundOne = true; else continue;
        }
        if (join != null) { join.reset(); if (!join.next()) continue; }
        return true;
    }
}
}
```

如图 8-46 所示，`TableFilter.next()` 状态机：

```text
状态迁移:
          next() 首次调用
BEFORE_FIRST ────────────────→ cursor.find() 初始化
     │
     │ cursor.next() = true
     ├────────────────────────→ FOUND
     │                           │
     │                           ├── isOk(filter) = false → continue
     │                           ├── isOk(joinCondition) = false → continue
     │                           └── join.next() = false → continue
     │
     │ cursor.next() = false
     └────────────────────────→ AFTER_LAST
                                 │
                                 ├── joinOuter && !foundOne → NULL_ROW
                                 └── return false
```

```text
TableFilter.next() 完整执行流程
                        │
  next() 调用
    │
    ├── state == BEFORE_FIRST?
    │     └── YES → cursor.find(indexConditions) ← 游标初始化
    │
    ├── state == FOUND && join != null?
    │     └── YES → join.next()? ← 先尝试内表
    │           ├── YES → return true
    │           └── NO  → 进入 while 循环获取下一行
    │
    └── while(true) 主循环:
          │
          ├── cursor.isAlwaysFalse()?
          │     └── YES → state = AFTER_LAST
          │
          ├── cursor.next()?
          │     ├── YES → state = FOUND
          │     │         currentSearchRow = 当前行
          │     │         current = null (清除缓存的行)
          │     │
          │     │         ├── nestedJoin 处理
          │     │         │     ├── nestedJoin.next()? NO
          │     │         │     │     └── joinOuter && !foundOne?
          │     │         │     │           ├── YES → setNullRow()
          │     │         │     │           └── NO  → continue
          │     │         │     └── YES → 继续
          │     │         │
          │     │         ├── isOk(filterCondition)?
          │     │         │     ├── NO → continue (跳过)
          │     │         │     └── YES → 继续
          │     │         │
          │     │         ├── isOk(joinCondition)?
          │     │         │     ├── NO → continue (跳过)
          │     │         │     └── YES → foundOne = true
          │     │         │
          │     │         ├── join != null?
          │     │         │     ├── YES → join.reset() + join.next()?
          │     │         │     │     ├── YES → return true
          │     │         │     │     └── NO  → continue
          │     │         │     └── NO  → return true
          │     │         │
          │     │         └── return true (找到有效行)
          │     │
          │     └── NO → state = AFTER_LAST
          │
          └── AFTER_LAST → return false (行耗尽)
```
**图 8-56: 追踪 TableFilter.next 的完整执行流程**

### 8.5.2 JOIN 处理

如图 8-56 所示，`TableFilter` 通过 `join` 字段形成链表结构：

```text
TableFilter 链:
            join        join
  topFilter ────→ T2 ────→ T3
     │
     │ 外循环: 遍历 T1
     │    └── 内循环: 遍历 T2 (受 T1 当前行约束)
     │        └── 内循环: 遍历 T3 (受 T1, T2 当前行约束)
     │
     └── 嵌套循环连接 (Nested Loop Join)
```
```text

**外连接处理**：
```
```java
if (joinOuter && !foundOne) {
    setNullRow();  // 返回 NULL 扩展行
}
```

当内表无匹配行时，填充 NULL 值并返回一行。

```text
TableFilter JOIN 链表结构与执行模型
                        │
  物理结构:
    topFilter (T1)
      ├── join = T2 (TableFilter 引用)
      │     ├── join = T3 (TableFilter 引用)
      │     │     └── join = null
      │     └── nestedJoin = null (或 LEFT JOIN 子计划)
      └── nestedJoin = null
                        │
  执行模型 (Nested Loop Join):
    ┌─────────────────────────────────────────────┐
    │  T1.next() 返回一行                          │
    │    └── T1.join = T2                          │
    │          │                                   │
    │          T2.reset() + T2.next()              │
    │            ├── 使用 T1 当前行作为查找条件     │
    │            └── 返回 T2 匹配行                │
    │                │                             │
    │                └── T2.join = T3              │
    │                      │                       │
    │                      T3.reset() + T3.next()  │
    │                        ├── 使用 T1,T2 查找   │
    │                        └── 返回 T3 匹配行    │
    └─────────────────────────────────────────────┘
                        │
  深度优先执行:
    T1_row1 → T2_row1 → T3_row1 (输出)
    T1_row1 → T2_row1 → T3_row2 (输出)
    T1_row1 → T2_row2 → T3_row1 (输出)
    T1_row1 → T2_row2 → T3_row2 (输出)
    T1_row2 → T2_row1 → T3_row1 (输出)
    ...
```
**图 8-57: 拆解 TableFilter join 链与嵌套循环执行**

### 8.5.3 条件求值阶段

如图 8-57 所示，条件分为两类：
1. **Index Conditions** — 用于索引定位（start/end），在 `cursor.find()` 阶段使用
2. **Filter Condition** — 索引无法处理的条件，在 `isOk()` 阶段逐行过滤

```text
表 TEST: 10000 行, 索引 IDX_NAME(name)
查询: SELECT * FROM TEST WHERE name = 'John' AND status = 'ACTIVE'
  │
  ├── Index Condition: name = 'John'
  │     → cursor.find() 直接定位到 name='John' 的记录
  │     → 约 50 行
  │
  └── Filter Condition: status = 'ACTIVE'
        → isOk(filterCondition) 对 50 行逐行检查
        → 最终返回约 30 行
```

如图 8-58 所示，两阶段求值将条件分离为索引条件和过滤条件，显著提升了查询效率：

```text
如图 8-59 所示，条件求值阶段与执行效率分析
                        │
  两阶段条件求值:
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  阶段 1: Index Conditions (索引条件)                               │
  │                                                                     │
  │  时机: cursor.find() 时                                             │
  │  位置: 索引层 (B-Tree遍历)                                           │
  │  效果: 直接定位到满足条件的起始/结束位置                            │
  │  开销: O(log n) 索引树深度                                          │
  │                                                                     │
  │  示例: name = 'John' → B-Tree定位到 'John' 的叶子节点               │
  │        只读取 name='John' 的 50 行                                  │
  │        避免扫描全部 10000 行                                        │
  └────────────────────────────────────────────────────────────────────┘
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  阶段 2: Filter Conditions (过滤条件)                              │
  │                                                                     │
  │  时机: cursor.next() 后, isOk() 调用                               │
  │  位置: TableFilter 层 (行过滤)                                      │
  │  效果: 逐行检查剩余条件                                             │
  │  开销: O(m) m = 索引扫描返回的行数                                  │
  │                                                                     │
  │  示例: status = 'ACTIVE' → 对 50 行逐行检查                        │
  │        最终返回约 30 行                                             │
  └────────────────────────────────────────────────────────────────────┘
                        │
  效率分析:
    索引条件 + 过滤条件 = 避免全表扫描
    10000 行 → 索引定位到 50 行 → 过滤到 30 行
    效率提升: 10000/30 ≈ 333 倍
```
**图 8-58: 对比索引条件与过滤条件两阶段求值的效率**

### 8.5.4 TableFilter 状态机增强版

如图 8-60 所示，TableFilter 在不同状态间的转移决定了查询执行的下一步行为。

**图 8-59: 拆解 TableFilter 三态状态机的生命周期**

```text
如图 8-94 所示，TableFilter 完整生命周期状态机
                        │
                        ▼
  ┌────────────────┐
  │  BEFORE_FIRST   │  ← TableFilter 初始状态
  │  state = -1     │
  └───────┬────────┘
          │
          │  next() 首次调用
          ▼
  ┌────────────────┐
  │  cursor.find()  │  ← 初始化游标 (索引定位)
  │  session,       │     根据 indexConditions 设置起始/结束位置
  │  indexConditions│
  └───────┬────────┘
          │
          ├──── 游标无数据? ────→ ┌────────────────┐
          │                      │  AFTER_LAST     │
          │                      │  return false   │
          │                      └────────────────┘
          │
          ├──── cursor.next() ───→ ┌────────────────┐
          │    成功                │  FOUND          │
          │                       │  state = 0      │
          │                       └───────┬────────┘
          │                               │
          │                      ┌────────┴──────────┐
          │                      │                   │
          │              ┌──────────────┐   ┌──────────────────┐
          │              │  嵌套连接?   │   │  isOk(filter)?   │
          │              │   inner      │   │                  │
          │              │  next() 检查 │   │  通过 → 继续     │
          │              └──────┬───────┘   │  失败 → continue │
          │                     │          └──────────────────┘
          │                     ▼
          │           ┌──────────────────┐
          │           │  外连接?         │
          │           │  joinOuter=false │
          │           │  无匹配→NULL行   │
          │           └──────────────────┘
          │                     │
          │                     ▼
          │              ┌──────────────────┐
          │              │  isOk(join)?     │
          │              │  通过 → 继续     │
          │              │  失败 → continue │
          │              └──────┬───────────┘
          │                     │
          │                     ▼
          │              ┌──────────────────┐
          │              │  join.next()     │
          │              │  内表迭代        │
          │              │  失败 → continue │
          │              └──────────────────┘
          │                     │
          │                     ▼
          │              ┌──────────────────┐
          │              │  return true     │
          │              │  成功返回一行    │
          │              └──────────────────┘
          │
          └──── 后续 next() 调用 ────→ ┌────────────────┐
               (state == FOUND)        │  处理连接表    │
                                       │  join.next()   │
                                       │  或用 cursor   │
                                       │  读取下一行    │
                                       └────────────────┘
```
**图 8-94: 追踪 TableFilter 状态机的完整生命周期**

该图将 `TableFilter.next()` 方法的状态转移展开为完整的状态机模型。`BEFORE_FIRST` → `FOUND` → `AFTER_LAST` 是三个核心状态，对应游标的初始化、迭代和耗尽阶段。嵌套循环连接在 `FOUND` 状态下通过递归调用 `join.next()` 驱动内表迭代，而 `isOk(filterCondition)` 和 `isOk(joinCondition)` 在两个关键检查点执行条件过滤。

```text
如图 8-61 所示，状态转移场景示例
                        │
  场景 1: 正常扫描 (有数据)
                        │
  BEFORE_FIRST
    │ next() 首次调用
    ▼
  cursor.find() → cursor.next() = true
    │
    ▼
  FOUND
    │ isOk(filter) = true
    │ isOk(join) = true
    │ join.next() = true
    ▼
  return true (输出一行)
    │
    │ 后续 next() 调用
    ▼
  FOUND (state 不变)
    │ join.next() = true → return true
    │ join.next() = false → 进入 while 循环
    │ cursor.next() = true → FOUND, 重复
    │ cursor.next() = false
    ▼
  AFTER_LAST → return false (行耗尽)
                        │
  场景 2: 空结果集
                        │
  BEFORE_FIRST
    │ next() 首次调用
    ▼
  cursor.find() → cursor.isAlwaysFalse() = true
    │
    ▼
  AFTER_LAST → return false (立即返回无数据)
                        │
  场景 3: 过滤条件全部不匹配
                        │
  BEFORE_FIRST → cursor.find() → cursor.next() = true
    │
    ▼
  FOUND → isOk(filter) = false → continue
    │       重新进入 while 循环
    │       cursor.next() = true → FOUND
    │       isOk(filter) = false → continue
    │       ... (循环直到耗尽)
    │
    ▼
  AFTER_LAST → return false
```
**图 8-60: 演示 TableFilter 在三类查询下的状态转移**

如图 8-60 所示，这些场景展示了 TableFilter 在不同查询条件下的完整行为模式。

### 8.5.5 Nested Loop Join 执行模型

**图 8-61: 演示三表嵌套循环连接的逐行物理执行**

```text
如图 8-95 所示，3 表 Nested Loop Join 执行模型 (T1 → T2 → T3)
                        │
  外层循环 (T1):        │   中层循环 (T2):        │   内层循环 (T3):
                        │                         │
  T1.next()             │                         │
    │                   │                         │
    ├─ cursor.find()    │                         │
    ├─ cursor.next()    │                         │
    │  → row T1_1       │                         │
    │                   │                         │
    ├───────────────────┼── T2.reset()             │
    │                   │    │                     │
    │                   │    ├─ T2.next()          │
    │                   │    │  ├─ cursor.find(T1) │
    │                   │    │  │  (利用 T1 当前行  │
    │                   │    │  │  作为查找条件)    │
    │                   │    │  ├─ cursor.next()   │
    │                   │    │  │  → row T2_1      │
    │                   │    │  │                  │
    │                   │    │  ├──────────────────┼── T3.reset()
    │                   │    │  │                  │    │
    │                   │    │  │                  │    ├─ T3.next()
    │                   │    │  │                  │    │  ├─ cursor.find(T1,T2)
    │                   │    │  │                  │    │  ├─ cursor.next()
    │                   │    │  │                  │    │  │  → row T3_1
    │                   │    │  │                  │    │  │
    │                   │    │  │                  │    │  ├─ isOk(filter)
    │                   │    │  │                  │    │  │  → 通过
    │                   │    │  │                  │    │  │
    │                   │    │  │                  │    │  ├─ isOk(join)
    │                   │    │  │                  │    │  │  → 通过
    │                   │    │  │                  │    │  │
    │                   │    │  │                  │    │  └─ return true
    │                   │    │  │                  │    │     → 输出行
    │                   │    │  │                  │    │       [T1_1, T2_1, T3_1]
    │                   │    │  │                  │    │
    │                   │    │  │                  │    ├─ T3.next()
    │                   │    │  │                  │    │  → row T3_2
    │                   │    │  │                  │    │  → [...]
    │                   │    │  │                  │    │
    │                   │    │  │                  │    └─ T3.next() = false
    │                   │    │  │                  │       → T3 耗尽
    │                   │    │  │                  │
    │                   │    │  └─ T3 循环结束     │
    │                   │    │                     │
    │                   │    ├─ T2.next()          │
    │                   │    │  → row T2_2         │
    │                   │    │  → [...]            │
    │                   │    │                     │
    │                   │    └─ T2.next() = false  │
    │                   │       → T2 耗尽          │
    │                   │                          │
    ├─ T1.next()        │                          │
    │  → row T1_2       │                          │
    │  → [...]          │                          │
    │                   │                          │
    └─ T1.next() = false                            │
       → T1 耗尽                                   │
                                                   ▼
  输出行序列:
    [T1_1, T2_1, T3_1]    ← T1 第一行 → T2 第一行 → T3 第一行
    [T1_1, T2_1, T3_2]    ← T1 第一行 → T2 第一行 → T3 第二行
    [T1_1, T2_2, T3_1]    ← T1 第一行 → T2 第二行 → T3 第一行
    [T1_1, T2_2, T3_2]    ← T1 第一行 → T2 第二行 → T3 第二行
    [T1_2, T2_1, T3_1]    ← T1 第二行 → T2 第一行 → T3 第一行
    ...
```
**图 8-95: 演示 Nested Loop Join 三表的输出行序列**

嵌套循环连接是 H2 唯一的连接算法。外层循环每行触发中层循环完整扫描，中层循环每行触发内层循环完整扫描，依此类推。执行顺序如同三层嵌套 for 循环：

```text
for each row in T1:       ← 外层 (驱动表)
  for each row in T2:     ← 中层 (内表 1)
    for each row in T3:   ← 内层 (内表 2)
      if (filter condition and join condition):
        output row
```

关键优化点在于：内层表 `cursor.find()` 可以利用外层表当前行值作为查找条件。例如，T2 索引扫描条件可能包含 `T2.foreign_key = T1.id`，当 T1 遍历到 `id=100` 的行时，T2 游标自动定位到 `foreign_key=100` 的位置。这种**索引驱动的嵌套循环连接**避免了内层表全表扫描，是 H2 连接性能的核心保障。如图 8-62 所示，索引驱动的嵌套循环连接与全表扫描版本在代价上差异巨大。

```text
如图 8-63 所示，Nested Loop Join 代价分析
                        │
  3 表连接 (T1 → T2 → T3), 每表 10000 行
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  场景 A: 全表扫描 (无索引)                                         │
  │                                                                     │
  │  T1 扫描: 10000 行                                                 │
  │  T2 扫描: 对 T1 每行 → 10000 × 10000 = 100,000,000 行             │
  │  T3 扫描: 对 T1,T2 每组合 → 10⁸ × 10000 = 10¹² 行                 │
  │                                                                     │
  │  总行比较: 约 10¹²                                                  │
  │  性能: 完全不可接受!                                               │
  └────────────────────────────────────────────────────────────────────┘
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  场景 B: 索引驱动 (内表有索引)                                      │
  │                                                                     │
  │  T1 扫描: 100 行 (有过滤条件)                                      │
  │  T2 查找: 对 T1 每行 → 100 × O(log 10000) ≈ 100 × 14 = 1400      │
  │  T3 查找: 对每组合 → (100 × 5) × 14 ≈ 7000                       │
  │                                                                     │
  │  总操作: 约 8500 次                                                 │
  │  性能: 极快!                                                       │
  └────────────────────────────────────────────────────────────────────┘
                        │
  对比: 场景 A vs 场景 B
    全表扫描 NLJ: 10¹² 次操作 ≈ 数小时
    索引驱动 NLJ: 8500 次操作 ≈ 毫秒级
    差距: 超过 1 亿倍
                        │
  结论: Nested Loop Join 在内表无索引时性能灾难
        内表连接列必须有索引!
```
**图 8-62: 对比 NLJ 索引驱动与全表扫描的代价量级**

### 8.5.6 内外连接处理对比

**图 8-63: 对比内外 JOIN 的处理路径差异**

```text
INNER JOIN vs LEFT JOIN 处理路径对比

INNER JOIN (普通内连接):
  topFilter.next()
    │
    ├── cursor.find() → cursor.next()
    │   → 找到一行
    │
    ├── isOk(filterCondition)?
    │   ├── 通过 → 继续
    │   └── 失败 → continue (跳过此行)
    │
    ├── isOk(joinCondition)?
    │   ├── 通过 → 继续
    │   └── 失败 → continue (跳过此行)
    │
    └── join.reset() → join.next()
        ├── 找到匹配 → return true
        └── 无匹配 → continue (跳过此行)

LEFT JOIN (左外连接):
  topFilter.next()
    │
    ├── cursor.find() → cursor.next()
    │   → 找到一行
    │
    ├── nestedJoin 处理
    │   │
    │   ├── nestedJoin.next()?
    │   │   ├── 找到匹配 → 正常处理
    │   │   │
    │   │   └── 无匹配 → joinOuter 检查
    │   │         │
    │   │         ├── joinOuter && !foundOne?
    │   │         │   │
    │   │         │   ├── YES → setNullRow()
    │   │         │   │        为内表列填充 NULL 值
    │   │         │   │        返回一行 (含左侧真实值 + 右侧 NULL)
    │   │         │   │
    │   │         │   └── NO → continue (跳过此行)
    │   │         │
    │   │         └── 关键差异: 外连接不会丢弃左行!
    │   │             即使右侧无匹配, 左行仍然保留
    │   │
    │   └── (继续处理)
    │
    ├── isOk(filterCondition)
    └── return true

  如图 8-96 所示，NULL 行结构:
  ┌────────────────────────────────────────────┐
  │  LEFT JOIN orders ON ...                   │
  │                                            │
  │  customers.id  = 100   ← 左表真实值       │
  │  customers.name = 'X'  ← 左表真实值       │
  │  orders.id     = NULL  ← 右表填充 NULL    │
  │  orders.total  = NULL  ← 右表填充 NULL    │
  └────────────────────────────────────────────┘
```

**图 8-96: 对比内连接与外连接的处理路径差异**

INNER JOIN 与 LEFT JOIN 在行保留策略上有本质区别。INNER JOIN 要求内表必须有匹配行，无匹配时丢弃外层行（`continue`）。LEFT JOIN 则保证左表所有行都出现在结果中——即使内表无匹配，左表行也保留，内表列填充 NULL 值。

`setNullRow()` 方法是 LEFT JOIN 实现的关键。当 `nestedJoin.next()` 返回 false 且 `joinOuter=true` 且 `foundOne=false` 时，`setNullRow()` 将当前 TableFilter 的行数据全部置为 NULL，但外层的 `currentSearchRow` 保持不变。这样返回给上层的结果行中，左表列包含真实值，右表列全是 NULL。

```text
如图 8-64 所示，INNER JOIN vs LEFT JOIN 结果行对比示例
                        │
  表数据:
    customers (左表):                orders (右表):
    ┌────┬─────────┐                ┌────┬─────────────┬────────┐
    │ id │ name    │                │ id │ customer_id │ total  │
    ├────┼─────────┤                ├────┼─────────────┼────────┤
    │ 1  │ Alice   │                │ 1  │ 1           │ 100.00 │
    │ 2  │ Bob     │                │ 2  │ 1           │ 200.00 │
    │ 3  │ Charlie │                │ 3  │ 3           │ 150.00 │
    └────┴─────────┘                └────┴─────────────┴────────┘
                        │
  INNER JOIN 结果:
    SELECT * FROM customers c INNER JOIN orders o ON c.id = o.customer_id
    ┌────┬─────────┬──────┬─────────────┬────────┐
    │ id │ name    │ id   │ customer_id │ total  │
    ├────┼─────────┼──────┼─────────────┼────────┤
    │ 1  │ Alice   │ 1    │ 1           │ 100.00 │
    │ 1  │ Alice   │ 2    │ 1           │ 200.00 │
    │ 3  │ Charlie │ 3    │ 3           │ 150.00 │
    └────┴─────────┴──────┴─────────────┴────────┘
    Bob (id=2) 无匹配行 → 被丢弃
                        │
  LEFT JOIN 结果:
    SELECT * FROM customers c LEFT JOIN orders o ON c.id = o.customer_id
    ┌────┬─────────┬──────┬─────────────┬────────┐
    │ id │ name    │ id   │ customer_id │ total  │
    ├────┼─────────┼──────┼─────────────┼────────┤
    │ 1  │ Alice   │ 1    │ 1           │ 100.00 │
    │ 1  │ Alice   │ 2    │ 1           │ 200.00 │
    │ 2  │ Bob     │ NULL │ NULL        │ NULL   │ ← 保留左行, 右列填充 NULL
    │ 3  │ Charlie │ 3    │ 3           │ 150.00 │
    └────┴─────────┴──────┴─────────────┴────────┘
    Bob (id=2) 保留 → 右表列填充 NULL
```
**图 8-64: 对比 INNER 与 LEFT JOIN 的结果行差异**

---

## 8.6 优化实践建议

### 8.6.1 索引设计原则

```text
等值条件优先
  │
  WHERE a = 1 AND b > 10
  │
  ├── 最优索引: INDEX(a, b) 或 INDEX(a)
  │     a 的等值条件可精确定位
  │     b 的范围条件在索引中连续扫描
  │
  └── 次优索引: INDEX(b)
        b 的范围条件只能扫描大量行
        a 的等值条件只能作为 filter
```

```text
如图 8-65 所示，索引设计原则详解
                        │
  核心原则: 等值条件列放在索引最左列
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  WHERE a = 1 AND b > 10                                           │
  │                                                                     │
  │  索引 (a, b):  定位 a=1, 范围扫描 b>10      ✅ 最佳               │
  │  索引 (a):     定位 a=1, 过滤 b>10          ✅ 良好               │
  │  索引 (b, a):  范围扫描 b>10, 过滤 a=1      ❌ 差                 │
  │  索引 (b):     范围扫描 b>10, 过滤 a=1      ❌ 最差               │
  └────────────────────────────────────────────────────────────────────┘
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  WHERE a = 1 AND b = 2 AND c > 3                                  │
  │                                                                     │
  │  索引 (a, b, c): 定位 a=1,b=2, 范围 c>3    ✅ 最佳 (最左前缀)    │
  │  索引 (a, b):    定位 a=1,b=2, 过滤 c>3    ✅ 良好               │
  │  索引 (a, c, b): 定位 a=1, 范围 c>3, 过滤 b=2 ❌ 差 (b 走 filter) │
  └────────────────────────────────────────────────────────────────────┘
                        │
  更多原则:
    ├── 选择性高的列优先: 区分度高的列在前, 快速缩小范围
    ├── 避免冗余索引: (a) 和 (a, b) 同时存在时, (a) 通常可省略
    └── 索引不是越多越好: 每个索引增加 DML 维护成本
```
**图 8-65: 罗列复合索引列顺序的核心设计原则**

### 8.6.2 LIKE 与索引

LIKE 'prefix%'  → 可使用索引 (转为 START/END 条件)
LIKE '%suffix'  → 无法使用索引 (需要全扫描)
LIKE '%mid%'    → 无法使用索引 (需要全扫描)

```text
如图 8-66 所示，LIKE 模式与索引使用对照
                        │
  LIKE 模式转换过程:
    LIKE 'prefix%' → START(prefix) + END(prefix )
    → 索引范围扫描: 从 'prefix' 到 'prefix '
    → 效率等同于 col >= 'prefix' AND col < 'prefix '
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  LIKE 模式       索引可用    B-Tree行为                            │
  ├────────────────────────────────────────────────────────────────────┤
  │  'prefix%'       可用       范围扫描 (前缀匹配)                    │
  │  '%suffix'       不可用     无法确定起始位置 (后缀未知)            │
  │  '%mid%'         不可用     无法确定起始位置 (任意位置)            │
  │  'exact'         可用       等值查找 (无通配符时)                  │
  │  'pre_fix'       部分可用   通配符前的前缀可走索引                 │
  └────────────────────────────────────────────────────────────────────┘
                        │
  优化建议:
    ├── 优先使用前缀匹配 LIKE 'prefix%'
    ├── 后缀匹配 LIKE '%suffix' 考虑全文索引
    ├── 大文本搜索考虑第三方搜索引擎
    └── 必要时使用函数索引 (H2 支持虚拟列索引)
```
**图 8-66: 对比五种 LIKE 模式与索引可用性**

### 8.6.3 JOIN 顺序

```sql
-- 建议: 选择性高的表在前
SELECT * FROM orders o
  JOIN customers c ON o.customer_id = c.id
  JOIN order_items i ON o.id = i.order_id
WHERE c.country = 'CN'
  AND o.status = 'PAID'
```

如图 8-59 所示，优化器选择逻辑：
- `customers` (country='CN' 选择性高，过滤后行数少) 排在前
- `orders` (status='PAID' 选择性中等) 排在中间
- `order_items` (无过滤条件) 排在最后

```text
JOIN 顺序优化可视化
                        │
  查询:
    SELECT * FROM orders o
      JOIN customers c ON o.customer_id = c.id
      JOIN order_items i ON o.id = i.order_id
    WHERE c.country = 'CN' AND o.status = 'PAID'
                        │
  优化前 (FROM 顺序):          优化后 (优化器选择):
  orders → customers → items   customers → orders → items
    │                            │
  10000 行                      │
    │                           c: 500 行 (country='CN')
    ↓                            │
  customers (无索引扫描)         ↓
    │                           o: 100 行 (关联 orders)
    10000 × 1 = 10000            │
    ↓                            ↓
  items                        i: 500 行 (关联 items)
    │                           │
    全表扫描 → 性能差            索引驱动 → 性能优
                        │
  优化原理:
    ├── customers 有过滤条件 country='CN'
    │   选择性高 → 先执行, 中间结果小
    ├── orders 有 status='PAID' 过滤
    │   选择性中等 → 中间执行
    └── order_items 无过滤条件
        最后执行, 通过索引连接
```
**图 8-67: 对比 JOIN 顺序优化前后的中间结果**

### 8.6.4 IN 列表优化

如图 8-67 所示，对于 `IN` 常量列表，H2 使用 `ConditionInConstantSet` 转化为哈希集合：

```sql
WHERE id IN (1, 2, 3, 100, 200)
  │
  └── ConditionInConstantSet: {1, 2, 3, 100, 200} → HashSet
        ├── 可配合索引使用
        └── 常量越多优势越大
```
```text
IN 列表优化原理
                        │
  SQL: WHERE id IN (1, 2, 3, 100, 200)
                        │
  优化前: 逐 OR 比较
    id = 1 OR id = 2 OR id = 3 OR id = 100 OR id = 200
    → 对每行执行 5 次比较
    → O(n × m) 其中 n=行数, m=IN 列表大小
                        │
  优化后: 哈希集合
    ConditionInConstantSet 创建 HashSet
    → contains() 检查: O(1) 每次
    → set.contains(id) → 快速判断
                        │
  性能对比:
    ┌────────────────────────────────────────────────────────────────────┐
    │  IN 列表大小    OR 比较 (每行)    哈希集合 (每行)   加速比       │
    ├────────────────────────────────────────────────────────────────────┤
    │  5             5 次比较          1 次哈希          5x            │
    │  10            10 次比较         1 次哈希          10x           │
    │  100           100 次比较        1 次哈希          100x          │
    │  1000          1000 次比较       1 次哈希          1000x         │
    └────────────────────────────────────────────────────────────────────┘
                        │
  注意: IN 列表可与索引配合使用
    WHERE id IN (1, 2, 3) → 索引范围扫描
    WHERE name IN ('a', 'b') → 非唯一索引 + 哈希过滤
```
**图 8-68: 对比 OR 比较与哈希集合的 IN 优化效果**

### 8.6.5 EXPLAIN PLAN

如图 8-68 所示，使用 `EXPLAIN` 查看执行计划：

```sql
EXPLAIN SELECT t.name FROM test t WHERE t.id = 1;
-- SELECT
--     "T"."NAME"
-- FROM "PUBLIC"."TEST" "T"
-- /* public.test.tableScan */
-- WHERE "T"."ID" = 1
```

注释部分显示使用的索引（`tableScan` 表示全表扫描）。

```sql
EXPLAIN SELECT t.name FROM test t WHERE t.name = 'John';
-- SELECT
--     "T"."NAME"
-- FROM "PUBLIC"."TEST" "T"
-- /* public.test.idx_name */
-- WHERE "T"."NAME" = 'John'
```

此处显示使用了 `idx_name` 索引。

```text
如图 8-69 所示，EXPLAIN 输出解读对比
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  输出中的索引注释          含义                     建议           │
  ├────────────────────────────────────────────────────────────────────┤
  │  tableScan               全表扫描                  需要建索引      │
  │  schema.table.index_name 使用了索引                OK             │
  │  (无注释)                可能是子查询或表达式      检查执行计划    │
  └────────────────────────────────────────────────────────────────────┘
                        │
  如何通过 EXPLAIN 诊断性能问题:
                        │
  问题 1: 期望使用索引但显示 tableScan
    原因: 查询条件不满足最左前缀原则
    解决: 检查索引列顺序是否与 WHERE 条件匹配
                        │
  问题 2: 使用了索引但查询仍慢
    原因: 索引选择性差 (匹配行太多)
    解决: 增加更精确的条件或创建复合索引
                        │
  问题 3: JOIN 查询显示内表 tableScan
    原因: 连接列缺少索引
    解决: 在连接列上创建索引 (紧急!)
```
**图 8-69: 解读 EXPLAIN 输出注释与三类性能问题**
```text
如图 8-70 所示，EXPLAIN 输出结构分解 — 注释字段含义
                        │
  EXPLAIN SELECT t.name FROM test t WHERE t.id = 1;
                        │
  ┌─────────────────────────────────────────────────────────────────┐
  │  SELECT                                                         │
  │      "T"."NAME"                   ← 投影列 (SELECT 子句)         │
  │  FROM "PUBLIC"."TEST" "T"         ← 数据源 (FROM 子句)           │
  │  /* public.test.tableScan */     ← 访问方法注释                  │
  │  WHERE "T"."ID" = 1              ← 过滤条件 (WHERE 子句)         │
  └─────────────────────────────────────────────────────────────────┘
                        │
  注释字段 /* ... */ 的格式:
    ┌─────────────────────────────────────────────────────────────┐
    │  /* schema.table.access_method */                            │
    │                                                              │
    │  schema:   数据库 Schema (通常为 PUBLIC)                      │
    │  table:    表名                                              │
    │  access_method: 访问方法                                      │
    │    ├── tableScan        → 全表扫描 (无可用索引)                │
    │    ├── index_name        → 使用指定索引                        │
    │    └── (无注释)           → 可能是子查询或函数表达式             │
    └─────────────────────────────────────────────────────────────┘
                        │
  多表连接时的 EXPLAIN 输出:
                        │
  EXPLAIN SELECT * FROM t1, t2 WHERE t1.id = t2.ref;
                        │
  SELECT
      "T1"."ID", "T2"."REF", ...
  FROM "PUBLIC"."T1" "T1"
  /* PUBLIC.T1.tableScan */     ← t1 的访问方法 (驱动表, 全表扫描)
  INNER JOIN "PUBLIC"."T2" "T2"
  /* PUBLIC.T2.idx_ref */       ← t2 的访问方法 (内表, 使用索引)
  ON 1=1
  WHERE "T1"."ID" = "T2"."REF"
```
**图 8-70: 拆解 EXPLAIN 注释字段的格式与含义**

### 8.6.6 常见优化检查表

| 场景 | 检查项 | 说明 |
|------|--------|------|
| WHERE 条件 | 是否有索引覆盖等值列 | 等值条件应放在索引最左列 |
| JOIN | 连接列是否有索引 | 内表的连接列必须建索引 |
| LIKE | 是否以前缀开头 | `'prefix%'` 可用索引 |
| 排序 | ORDER BY 列是否在索引中 | 避免文件排序 |
| 分组 | GROUP BY 列是否在索引中 | 索引分组排序优化 |
| 子查询 | 能否改写为 JOIN | JOIN 通常更高效 |
| IN 列表 | 是否为常量列表 | 常量列表用哈希集合优化 |

如图 8-72 所示，基于上述检查表，以下诊断流程可以帮助定位和解决查询性能问题：

```text
如图 8-71 所示，常见优化问题诊断流程
                        │
  查询慢? → EXPLAIN 查看执行计划
    │
    ├── 显示 tableScan?
    │     ├── YES → WHERE 条件有索引吗?
    │     │     ├── NO  → 创建索引
    │     │     └── YES → 索引列顺序匹配吗?
    │     │           ├── YES → 索引选择性高吗?
    │     │           │     ├── YES → 检查是否被函数/类型转换阻止
    │     │           │     └── NO  → 考虑复合索引
    │     │           └── NO  → 调整索引列顺序
    │     └── NO → 索引扫描但慢?
    │           ├── YES → 检查索引选择性
    │           └── NO  → 检查 JOIN 条件和 WHERE 过滤
    │
    ├── JOIN 查询慢?
    │     ├── 内表连接列有索引吗?
    │     │     ├── NO  → 立即创建索引! (紧急)
    │     │     └── YES → 驱动表选择是否最优?
    │     │           └── 将选择性高的表前置
    │
    ├── ORDER BY 慢?
    │     ├── ORDER BY 列在索引中吗?
    │     └── NO → 创建包含排序列的复合索引
    │
    └── GROUP BY 慢?
          ├── GROUP BY 列在索引中吗?
          └── NO → 创建包含分组列的复合索引
```

这组图把"诊断—优先级—决策"拆成三个层次：图 8-71 拆解四类查询性能问题的诊断决策路径，图 8-72 罗列四级优化手段的预期效果与实施成本，图 8-73 进一步拆解三类查询模式的索引设计决策路径。

**图 8-71: 拆解四类查询性能问题的诊断决策路径**
```text
如图 8-73 所示，优化优先级排序 — 不同优化手段的性价比
                        │
  ┌──────────────────────────────────────────────────────────────────────┐
  │  优先级                                 预期效果    实施成本           │
  │  ──────────────────────────────────────  ────────  ────────           │
  │                                                                      │
  │  P0 — 紧急 (必须立即修复)                                              │
  │    ├── JOIN 内表连接列缺少索引          10-1000×   低 (CREATE INDEX) │
  │    ├── WHERE 条件列无索引               5-100×     低                │
  │    └── 全表扫描大表                     10-100×   低                │
  │                                                                      │
  │  P1 — 重要 (应尽快优化)                                                │
  │    ├── 索引列顺序不匹配 WHERE 条件       2-10×     低                │
  │    ├── ORDER BY 无索引覆盖              2-5×      低                │
  │    ├── GROUP BY 无索引覆盖              2-5×      低                │
  │    └── 子查询可改写为 JOIN              1.5-3×    中 (SQL 改写)     │
  │                                                                      │
  │  P2 — 建议 (性能调优)                                                  │
  │    ├── IN 列表过长 (改为临时表 JOIN)    1.5-2×    中                │
  │    ├── LIKE 前缀通配符 ('%abc')          2-5×     低 (SQL 改写)     │
  │    ├── 函数/类型转换阻止索引            1.5-3×    低 (SQL 改写)     │
  │    └── SELECT * 可改为列清单             1.2-1.5×  低                │
  │                                                                      │
  │  P3 — 高级 (覆盖扫描优化)                                              │
  │    ├── 创建覆盖索引 (含 SELECT 列)       1.2-2×    中 (更大索引)     │
  │    └── 表分区 (超大型表)                 1.5-3×    高 (架构变更)     │
  └──────────────────────────────────────────────────────────────────────┘
                        │
  诊断工作流建议:
    1. EXPLAIN 查看所有慢查询的执行计划
    2. 优先修复 P0 问题 (JOIN 和 WHERE 的索引缺失)
    3. 检查索引列顺序是否匹配查询模式
    4. 分析覆盖索引的收益是否大于额外存储开销
    5. 定期复查索引使用情况, 移除未使用的索引
```
**图 8-72: 罗列四级优化手段的预期效果与实施成本**

### 8.6.7 索引设计完整决策树

如图 8-74 所示，合理的索引设计需要综合考虑查询模式、列选择性和维护成本。

**图 8-73: 拆解三类查询模式的索引设计决策路径**

```text
索引设计决策树
                        │
  查询模式分析
    │
    ├── WHERE 条件分析:
    │     │
    │     ├── 是否有等值条件 (col = value)?
    │     │     ├── YES → 将等值列放在索引最左前缀
    │     │     └── NO  → 考虑范围条件列
    │     │
    │     ├── 是否有范围条件 (col > value, col BETWEEN)?
    │     │     ├── YES → 放在等值列之后
    │     │     └── NO  → 考虑排序列
    │     │
    │     └── 是否有排序条件 (ORDER BY col)?
    │           ├── YES → 如果索引已包含排序列, 避免文件排序
    │           └── NO  → 考虑 SELECT 列
    │
    ├── SELECT 列分析:
    │     │
    │     └── SELECT 列是否都在索引中?
    │           ├── YES → 索引覆盖扫描 (Index-Only Scan)
    │           └── NO  → 需要回表访问
    │
    └── 决策结果:

  ┌─────────────────────────────────────────────────────────────┐
  │  WHERE a=1 AND b>10 ORDER BY c                              │
  │                                                             │
  │  最优: 复合索引(a, c, b) 或 (a, b, c)                       │
  │  ├── a: 等值条件 → 索引最左列                               │
  │  ├── c: 排序列 → 索引第二列 (避免文件排序)                   │
  │  └── b: 范围条件 → 索引第三列 (范围扫描)                     │
  │                                                             │
  │  备选: 索引(a) + 文件排序                                    │
  │  备选: 单独索引(b) (不推荐, 范围扫描代价高)                  │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │  WHERE status='PAID' AND created_at > '2024-01-01'         │
  │  SELECT id, status, amount                                  │
  │                                                             │
  │  最优: 索引(status, created_at, amount)                     │
  │  ├── status: 等值条件, 过滤大量行, 可大幅缩小范围           │
  │  ├── created_at: 范围条件, 进一步缩小                       │
  │  └── amount: 包含在索引中, 实现覆盖扫描                     │
  │                                                             │
  │  次优: 单独索引(status) + 回表读取 created_at 和 amount     │
  └─────────────────────────────────────────────────────────────┘

  如图 8-97 所示，┌─────────────────────────────────────────────────────────────┐
  │  JOIN orders ON orders.customer_id = customers.id           │
  │                                                             │
  │  必须: orders.customer_id 上有索引                          │
  │  原因: 对 customers 的每行, 需要在 orders 中快速查找        │
  │  无索引时: 对每行 customer, 全表扫描 orders → 性能灾难     │
  └─────────────────────────────────────────────────────────────┘
```

以下三张图共同呈现索引设计的完整指导：图 8-97 拆解索引设计的完整决策树与原则，图 8-74 罗列八种查询模式的推荐索引策略，图 8-75 解读 EXPLAIN 输出的四种执行计划场景。

**图 8-97: 拆解索引设计的完整决策树与原则**

该图提供了从查询模式到索引设计的完整决策路径。核心原则：

1. **等值条件列优先放在索引最左列**：等值条件可以将 B-Tree定位到精确的叶子节点，过滤效果最好
2. **排序列紧随等值列之后**：如果索引顺序与 ORDER BY 一致，可以避免文件排序
3. **范围条件放在最后**：范围条件只能匹配索引的一列，之后的索引列无法参与条件匹配
4. **SELECT 列尽量包含在索引中**：实现索引覆盖扫描，避免回表 I/O
5. **JOIN 连接列必须有索引**：否则嵌套循环连接退化为全表扫描，性能灾难

```text
如图 8-75 所示，索引设计决策速查表
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  查询模式                     推荐索引策略           覆盖列        │
  ├─────────────────────────────────────────────────────────────────────┤
  │  WHERE a = 1                  INDEX(a)               a            │
  │  WHERE a = 1 AND b = 2       INDEX(a, b)            a, b          │
  │  WHERE a = 1 ORDER BY c      INDEX(a, c)            a, c          │
  │  WHERE a > 1 ORDER BY b      INDEX(a, b)            a, b          │
  │  WHERE a = 1 AND b > 2       INDEX(a, b)            a, b          │
  │  WHERE a LIKE 'pre%'          INDEX(a)               a             │
  │  JOIN t ON t.a = t2.b        INDEX(a) (在 t 表)     a             │
  │  SELECT a, b WHERE a = 1     INDEX(a, b)            a, b (覆盖)   │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  反模式 (应避免的设计):
    ├── 过多单列索引: INDEX(a), INDEX(b), INDEX(c)
    │    → 应合并为复合索引 INDEX(a, b, c)
    │
    ├── 索引列顺序不当: INDEX(b, a) 当查询是 a = 1 AND b = 2
    │    → 等值条件 a 应在前
    │
    └── 索引不包含 SELECT 列: SELECT a, b 索引 INDEX(a)
          → 改为 INDEX(a, b) 实现覆盖扫描
```
**图 8-74: 罗列八种查询模式的推荐索引策略**

### 8.6.8 执行计划可视化解构

如图 8-76 所示，EXPLAIN 输出的每一部分都可以映射到优化器的具体决策。

**图 8-75: 解读 EXPLAIN 输出的四种执行计划场景**

```text
EXPLAIN 输出解读

示例 1: 全表扫描
  EXPLAIN SELECT * FROM test WHERE name = 'John';
  ─────────────────────────────────────────────────────────────
  SELECT
      "TEST"."ID",
      "TEST"."NAME",
      "TEST"."STATUS"
  FROM "PUBLIC"."TEST" "TEST"       /* PUBLIC.TEST.tableScan */
  WHERE "TEST"."NAME" = 'John'
  ─────────────────────────────────────────────────────────────
  索引注释解读: tableScan
    ├── 没有合适的索引可以使用
    ├── 执行方式: 顺序扫描全部数据行
    └── 每次读取一行 → 检查 name='John' → 匹配则返回

示例 2: 索引扫描
  EXPLAIN SELECT * FROM test WHERE name = 'John';
  (假设 name 上有索引 idx_name)
  ─────────────────────────────────────────────────────────────
  SELECT
      "TEST"."ID",
      "TEST"."NAME",
      "TEST"."STATUS"
  FROM "PUBLIC"."TEST" "TEST"       /* PUBLIC.TEST.idx_name */
  WHERE "TEST"."NAME" = 'John'
  ─────────────────────────────────────────────────────────────
  索引注释解读: idx_name
    ├── 使用索引 idx_name 进行查找
    ├── 执行方式: B-Tree定位 → 回表读取完整行
    ├── I/O 成本: 索引树深度次索引页读取 + 数据页读取
    └── 适用于: 等值匹配或前缀范围匹配

示例 3: 索引覆盖扫描
  EXPLAIN SELECT name FROM test WHERE name = 'John';
  (假设 name 上有索引 idx_name)
  ─────────────────────────────────────────────────────────────
  SELECT
      "TEST"."NAME"
  FROM "PUBLIC"."TEST" "TEST"       /* PUBLIC.TEST.idx_name */
  WHERE "TEST"."NAME" = 'John'
  ─────────────────────────────────────────────────────────────
  差异: SELECT 仅包含 name 列
    ├── idx_name 索引包含 name 列
    ├── 无需回表: 直接从索引读取 name 值
    └── I/O 成本: 仅索引页读取 (比示例 2 少一次数据页读取)

如图 8-98 所示，示例 4: 多表连接
  EXPLAIN SELECT * FROM customers c
    JOIN orders o ON c.id = o.customer_id
    WHERE c.country = 'CN';
  ─────────────────────────────────────────────────────────────
  SELECT
      ...
  FROM "PUBLIC"."CUSTOMERS" "C"    /* PUBLIC.CUSTOMERS.idx_country */
      INNER JOIN "PUBLIC"."ORDERS" "O" /* PUBLIC.ORDERS.idx_customer */
  WHERE "C"."COUNTRY" = 'CN'
  ─────────────────────────────────────────────────────────────
  解读:
    ├── CUSTOMERS 使用 idx_country 过滤 country='CN'
    ├── ORDERS 使用 idx_customer 进行连接查找
    └── 执行顺序: CUSTOMERS (驱动表) → ORDERS (内表)
```
**图 8-98: 对比四种 EXPLAIN 输出的访问方式**

EXPLAIN 输出的注释部分是理解 H2 执行计划的关键。注释格式为 `/* schema.table.INDEX */`（INDEX 为索引名），其中索引名指示了优化器选择的访问路径。`tableScan` 表示全表扫描，是优化器无法使用索引时的兜底策略。通过对比不同查询的 EXPLAIN 输出，可以快速定位索引设计中的问题——例如，预期使用索引但实际显示 `tableScan`，通常意味着索引列顺序与查询条件不匹配。

```text
如图 8-77 所示，EXPLAIN 输出快速解读卡
                        │
  输出格式: /* schema.table.索引名 */
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  索引名                   含义                        行动          │
  ├─────────────────────────────────────────────────────────────────────┤
  │  tableScan               全表扫描                     检查索引      │
  │  PRIMARY_KEY_XX          主键索引                     OK            │
  │  <索引名>                普通/唯一索引                 OK            │
  │  sys:<编号>              系统内部索引                 通常 OK       │
  └─────────────────────────────────────────────────────────────────────┘
                        │
  常见 EXPLAIN 场景识别:
                        │
  ┌─────────────────────────────────────────────────────────────────────┐
  │  场景 1: 索引缺失                                                  │
  │  SELECT * FROM t WHERE name = 'x'                                  │
  │  → /* PUBLIC.T.tableScan */                                        │
  │  → 建议: 在 name 列上创建索引                                      │
  │                                                                     │
  │  场景 2: 最左前缀不匹配                                             │
  │  SELECT * FROM t WHERE b = 1                                       │
  │  索引: INDEX(a, b)                                                  │
  │  → /* PUBLIC.T.tableScan */                                        │
  │  → 原因: 查询未使用前缀列 a, 索引不可用                            │
  │  → 建议: 创建 INDEX(b) 或调整查询                                  │
  │                                                                     │
  │  场景 3: 索引选择性差                                               │
  │  SELECT * FROM t WHERE status = 'ACTIVE'                           │
  │  索引: INDEX(status) (50% 行是 ACTIVE)                             │
  │  → /* PUBLIC.T.idx_status */                                       │
  │  → 虽然使用了索引, 但因匹配行太多, 可能不如全表扫描                │
  │  → 建议: 增加额外条件或创建复合索引                                │
  └─────────────────────────────────────────────────────────────────────┘
```
**图 8-76: 解读 EXPLAIN 索引注释的三种典型场景**

如图 8-76 所示，EXPLAIN 输出的解读方法对理解优化器决策至关重要。

### 8.6.9 优化器工作流与调优总结

**图 8-77: 概览查询优化器从 SQL 到执行计划的四阶段**

```text
如图 8-99 所示，H2 查询优化器完整工作流
                        │
  ┌────────────────────────────────────────────────────────────┐
  │  阶段 1: 解析                                               │
  │  SQL ──→ Parser.parse(sql) ──→ 抽象语法树 (AST)             │
  │  产出: Select / Insert / Update / Delete 等 Prepared 对象  │
  └──────────────────────────┬─────────────────────────────────┘
                             │
  ┌──────────────────────────▼─────────────────────────────────┐
  │  阶段 2: 语义分析                                           │
  │  Select.init()                                              │
  │    ├── expandSelectList()   ← 展开 SELECT *                 │
  │    ├── mapColumns()         ← 列名绑定到 TableFilter        │
  │    ├── resolveTypes()       ← 确定每列的数据类型            │
  │    └── createIndexConditions() ← 提取索引可用条件           │
  └──────────────────────────┬─────────────────────────────────┘
                             │
  ┌──────────────────────────▼─────────────────────────────────┐
  │  阶段 3: 优化                                               │
  │  Select.preparePlan() → Optimizer.optimize()                │
  │    ├── 连接顺序选择: 暴力/贪心/遗传                          │
  │    ├── 索引选择: 掩码匹配 → 代价最小化                       │
  │    └── 计划组装: topFilter 链 + PlanItem 配置               │
  └──────────────────────────┬─────────────────────────────────┘
                             │
  ┌──────────────────────────▼─────────────────────────────────┐
  │  阶段 4: 执行                                               │
  │  Select.queryWithoutCache()                                 │
  │    ├── topTableFilter.next() 循环                           │
  │    ├── cursor.find() → cursor.next() → 索引驱动扫描         │
  │    ├── isOk(filterCondition) → 过滤条件检查                 │
  │    ├── isOk(joinCondition) → 连接条件检查                   │
  │    ├── join.next() → 内表嵌套循环                           │
  │    └── expressions.getValue() → 列值求值                    │
  └──────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
                       结果集输出
                        │
  优化器调优清单:
    │
    ├── [ ] 检查 EXPLAIN 输出, 确认使用了预期索引
    ├── [ ] 将等值条件列放在复合索引的最左列
    ├── [ ] 将选择性高的表的条件放在 WHERE 前面
    ├── [ ] JOIN 连接列是否有索引? (内表必须有索引)
    ├── [ ] ORDER BY 是否能利用索引排序? (避免文件排序)
    ├── [ ] 子查询能否改写为 JOIN? (通常更高效)
    ├── [ ] 是否使用了 SELECT *? (仅选择需要的列)
    ├── [ ] LIKE 是否以前缀开头? ('prefix%' 可用索引)
    └── [ ] 索引列是否过多? (维护成本 vs 查询收益)
```
**图 8-99: 汇总优化器四阶段工作流与九项调优清单**

该图将查询执行的完整流程总结为四个阶段：解析、语义分析、优化和执行，并提供了优化器调优的实用清单。优化器调优的核心思想是"帮助优化器做出更好的选择"——通过合理创建索引、优化查询写法、使用 EXPLAIN 验证执行计划，将查询性能提升到最优。

```text
如图 8-78 所示，优化效果量化对比
                        │
  以一个典型 Web 查询为例:
    SELECT o.*, c.name, i.product_name
    FROM orders o
      JOIN customers c ON o.customer_id = c.id
      JOIN order_items i ON o.id = i.order_id
    WHERE c.email = 'user@example.com'
      AND o.status = 'PAID'
                        │
  ┌────────────────────────────────────────────────────────────────────┐
  │  优化级别          执行方式                       响应时间        │
  ├────────────────────────────────────────────────────────────────────┤
  │  无优化            全表扫描全部表                  30 秒+         │
  │  基本索引          内表连接列建索引                500 毫秒       │
  │  复合索引          等值列复合索引                  10 毫秒        │
  │  覆盖索引          SELECT 列在索引中               2 毫秒         │
  └────────────────────────────────────────────────────────────────────┘
                        │
  优化收益总结:
    ├── 索引优化: 从 30 秒到 500 毫秒 (60x)
    ├── 复合索引: 从 500 到 10 毫秒 (50x)
    ├── 覆盖索引: 从 10 到 2 毫秒 (5x)
    └── 总优化: 从 30 秒到 2 毫秒 (15000x)
```
**图 8-78: 对比四级索引优化下查询响应时间的差异**

> **参考**: H2 官方文档《Performance》(`h2/src/docsrc/html/performance.html#explain_plan`)
> 描述了如何使用 EXPLAIN PLAN 分析查询执行计划并进行调优。

---

## 8.7 ASCII 优化流程图

```text
如图 8-79 所示，优化器全流程总览
                        │
  输入: SQL 查询
                        │
                        ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  阶段 1: 解析与条件提取                                            │
  │    Parser → Expression Tree → createIndexConditions()              │
  │    产出: TableFilter 列表 + IndexCondition 数组                    │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  阶段 2: 连接顺序优化                                              │
  │    calculateBestPlan()                                             │
  │      ├── 单表: testPlan()                                          │
  │      ├── ≤7: 暴力枚举 n! 排列                                     │
  │      └── ≥8: 混合策略 + 遗传算法                                   │
  │    产出: bestPlan (最优连接顺序 + 索引选择)                        │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  阶段 3: 执行                                                      │
  │    topTableFilter.next() 循环                                       │
  │      ├── cursor.find() → 索引定位                                  │
  │      ├── cursor.next() → 行迭代                                    │
  │      ├── isOk(filterCondition) → 过滤                              │
  │      ├── isOk(joinCondition) → 连接条件                            │
  │      ├── join.next() → 内表循环                                    │
  │      └── getValue() → 列值求值                                    │
  │    产出: 结果行                                                    │
  └───────────────────────────────┬─────────────────────────────────────┘
                                  │
                                  ▼
  输出: 结果集 (Result Set)
```
**图 8-79: 概览优化器从解析到执行的三阶段流程**
```text

如图 8-80 所示，SQL WHERE 子句
    │
    ▼
  Parser 解析 WHERE 条件
    │
    ├── 拆解为 Comparison、ConditionAndOr 等表达式树
    ├── mapColumns() 将列引用绑定到 TableFilter
    └── createIndexConditions() 提取索引可用条件
    │
    ▼
  每个 TableFilter 提取 IndexConditions:
    │
    ├── WHERE T1.a=1 AND T1.b>5 AND T2.c='x'
    │
    ├── T1.indexConditions:
    │     ├── [a, EQUALITY, value=1]
    │     └── [b, START, value=5]
    │
    └── T2.indexConditions:
          └── [c, EQUALITY, value='x']
    │
    ▼
  对每个表遍历索引:
    ┌─────────────────────────────────────────────┐
    │ TableFilter.getBestPlanItem()               │
    │                                             │
    │  1. 构建 masks 数组                          │
    │     mask[columnId] |= condition.getMask()   │
    │                                             │
    │  2. 对每个索引:                              │
    │     a. 比对 masks 与索引列                    │
    │     b. 调用 index.getCost() 估算代价          │
    │     c. 选择最低代价索引                       │
    │                                             │
    │  3. 代价调整:                                │
    │     cost -= cost × conditionsCount / 100    │
    │     / (filter + 1)                          │
    └─────────────────────────────────────────────┘
    │
    ▼
  枚举连接顺序:
    │
    ├── 1 个表: 直接评估
    │
    ├── ≤7 个表: 暴力枚举 O(n!)
    │     ├── 生成所有排列
    │     ├── 计算每个 Plan 的代价
    │     └── 选择总代价最低的
    │
    └── ≥8 个表: 混合 + 遗传
          ├── 混合: 暴力前 m 个 + 贪心填充剩余
          ├── 遗传: 随机变异 × 500 轮
          └── 取两者中的最优
    │
    ▼
  选中最优 Plan:
    │
    ├── topTableFilter = plan.filters[0]
    ├── 链接 TableFilter 链 (addJoin)
    └── 设置每个 TableFilter 的 PlanItem (索引 + 掩码)
    │
    ▼
  执行阶段:
    │
    ┌─────────────────────────────────────────────┐
    │ topTableFilter.next() 循环                   │
    │                                             │
    │  while (topTableFilter.next()):             │
    │    ├── cursor.find()  → 索引定位             │
    │    ├── cursor.next()  → 读取下一行            │
    │    ├── isOk(filterCondition) → 过滤           │
    │    ├── isOk(joinCondition)  → 连接条件        │
    │    ├── join.next()       → 内表迭代           │
    │    └── row[i] = expressions[i].getValue()   │
    │        → 最终结果行                          │
    └─────────────────────────────────────────────┘
    │
    ▼
  结果返回给 JDBC
```

### 8.7.1 优化器全流程集成

**图 8-80: 汇总优化器各组件集成的端到端架构**

```text
如图 8-100 所示，优化器全流程集成架构
                        │
  SQL 查询 ──→ Parser 解析
                        │
                        ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  Select.preparePlan()                                        │
  │                                                              │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 1: createIndexConditions()                       │  │
  │  │    输入: WHERE t1.a=1 AND t1.b>5 AND t2.c='x'        │  │
  │  │    输出:                                                │  │
  │  │      T1.indexConditions ← [a:EQUALITY, b:START]       │  │
  │  │      T2.indexConditions ← [c:EQUALITY]                 │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  │                              ▼                               │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 2: new Optimizer(topArray, condition, session)   │  │
  │  │    输入: TableFilter[] = [T1, T2, T3]                 │  │
  │  │    常量: MAX_BRUTE_FORCE_FILTERS=7                    │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  │                              ▼                               │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 3: calculateBestPlan()                          │  │
  │  │    决策: 表数 = 3 ≤ 7 → 暴力枚举                       │  │
  │  │    枚举 3! = 6 种排列                                  │  │
  │  │    for each 排列:                                      │  │
  │  │      Plan = new Plan(filters, condition)               │  │
  │  │      cost = Plan.calculateCost(session, ...)           │  │
  │  │    bestPlan = 最低 cost 的排列                          │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  │                              ▼                               │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 4: Plan.calculateCost()                         │  │
  │  │    cost = 1                                            │  │
  │  │    i=0: T1.cost=10, cost=1+1×10=11                    │  │
  │  │    i=1: T2.cost=5,  cost=11+11×5=66                   │  │
  │  │    i=2: T3.cost=2,  cost=66+66×2=198                  │  │
  │  │    return PlanItem[cost=198]                           │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  │                              ▼                               │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 5: TableFilter.getBestPlanItem()                 │  │
  │  │    输入: indexConditions → masks 数组                  │  │
  │  │    过程: 遍历所有索引 → 掩码匹配 → 代价估算            │  │
  │  │    输出: PlanItem{index: IDX_AB, cost: 10}            │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  │                              ▼                               │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  Step 6: 结果组装                                      │  │
  │  │    topFilter = bestPlan.filters[0]                     │  │
  │  │    linkJoin(topFilter, T2, T3)                         │  │
  │  │    for each f: f.setPlanItem(planItem)                 │  │
  │  │    输出: topFilter → T2 → T3 (已配置索引和条件)        │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                              │                               │
  └──────────────────────────────┼───────────────────────────────┘
                                 │
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  执行阶段: Select.queryWithoutCache()                       │
  │    topTableFilter.next()循环                                 │
  │      → cursor.find(masks)  ← 使用 PlanItem 的索引和掩码    │
  │      → cursor.next()       ← 游标遍历                      │
  │      → isOk(filter)       ← WHERE 条件求值                 │
  │      → join.next()        ← 内表嵌套循环                   │
  │      → expressions[i].getValue() ← SELECT 列求值            │
  └──────────────────────────────────────────────────────────────┘
```
**图 8-100: 汇总优化器六步流水线从 SQL 到计划的集成**

该图将第 8 章讨论的所有优化器组件——索引条件提取、连接顺序策略、代价计算、索引选择和结果组装——集成为一个完整的六步流水线。每一步的输入、输出和核心逻辑都展示在图中，形成了一个从原始 SQL 到可执行计划的端到端视图。优化器是一个转换器：将逻辑的 SQL 查询（声明式）转换为物理的执行计划（过程式），并在转换过程中通过代价模型选择最优的物理实现。

```text
优化器核心数据流
                        │
  从 SQL 到执行计划的关键数据变换:
                        │
  SQL 文本
    │ Parser 解析
    ▼
  抽象语法树 (AST)
    │ Select.init() → mapColumns() → resolveTypes()
    ▼
  Prepared Select 对象
    │ createIndexConditions()
    ▼
  TableFilter[] + IndexCondition[]
    │ Optimizer.optimize() → calculateBestPlan()
    ▼
  Plan (bestPlan)
    │ plan.calculateCost() → 遍历 allFilters
    ▼
  PlanItem[] (每个表的最优索引和代价)
    │ setPlanItem() + linkJoin()
    ▼
  可执行计划 (topFilter → T2 → T3 ...)
    │ Select.queryWithoutCache()
    ▼
  结果集
                        │
  关键决策点:
    ├── createIndexConditions(): 哪些条件可通过索引定位?
    ├── calculateBestPlan(): 哪种连接顺序代价最低?
    ├── getBestPlanItem(): 哪个索引最适合当前表?
    └── canStop(): 搜索是否已产生足够好的计划?
```

**图 8-81: 追踪优化器六层数据结构的转换链路**

---

## 8.8 本章小结

如图 8-81 所示，前面第7章完整追踪了一条 SQL 从 JDBC 到存储层的全部流程。核心链路由三个阶段组成：

1. **准备阶段**：`JdbcStatement` 发起 `prepareCommand()`，经 `SessionLocal.prepareLocal()` 到 `Parser` 解析为语法树，再通过 `Select.init()` 和 `Select.prepare()` 完成语义分析和计划生成
2. **缓存复用**：`queryCache`（`SmallLRUCache`）对相同 SQL 文本缓存已编译的 `CommandContainer`，减少重复解析代价
3. **执行阶段**：`CommandContainer.query()` 调用 `Select.queryWithoutCache()`，驱动 `TableFilter.next()` 迭代循环，通过 `Expression.getValue()` 多态求值输出结果行

第 8 章深入了查询优化器的三个核心引擎：

1. **连接顺序策略**：根据表数量动态选择 — 单表直接评估、`≤7` 表暴力枚举全排列、`≥8` 表混合暴力+贪心+遗传三种策略的组合
2. **代价模型**：`Plan.calculateCost()` 使用复合乘法公式 `cost = cost + cost × item_cost` 累计估计，无效计划标记为无穷大代价
3. **索引选择**：`TableFilter.getBestPlanItem()` 通过掩码匹配 `IndexCondition` 与索引列，选取 `Index.getCost()` 最低的索引，并通过代价调整使条件更多的表优先执行

上述 SQL 执行流程和查询优化器的工作建立在存储引擎的持久化机制和并发控制之上。第9-10章《持久化引擎与锁实现》将深入 MVStore 的文件格式、Chunk 生命周期、崩溃恢复以及五层并发控制模型，揭示执行计划落盘和并发访问的底层保障。

---

## 8.9 延展阅读

- H2 官方文档《Advanced》(`h2/src/docsrc/html/advanced.html`) — 结果集处理和大对象存储说明
- H2 官方文档《Performance》(`h2/src/docsrc/html/performance.html#database_performance_tuning`) — 数据库性能调优指南
- 本书第6章§6.8《Optimizer — 查询优化器》 — 优化器连接顺序选择算法
- 本书第6章§6.10《Parser — 递归下降解析》 — SQL 解析的底层实现
- 本书第5章§5.1-5.4 — DML 流程入口与 Command 层的关系
