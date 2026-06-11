# 第6章 H2 数据库核心算法分析

> **本章导读**: 本章是全书最长的章节，覆盖 H2 使用的 10 个核心算法，分为数据结构基础篇（6.1-6.3）、存储算法篇（6.4-6.7）和查询算法篇（6.8-6.10）三篇。本篇（6.1-6.3）介绍 B-Tree 索引结构、Copy-on-Write 版本管理和 MVCC 多版本并发控制这三个基础数据结构与算法，它们是理解后续存储和查询算法的前提。
> **前置知识**: 第2章《分层模块划分》§2.8（Table/Index 层概览）；第4章（MVMap 和 TransactionStore 数据存储）
> **章节要点**:
> - 理解 B-Tree 的节点结构和基本操作（查找、插入、分裂）
> - 掌握 Copy-on-Write 在 B-Tree 版本管理中的应用
> - 熟悉 MVCC 多版本并发控制的基本原理
> - 了解这些算法在 H2 中的具体实现位置
> **术语参考**: 本篇涉及的专业术语详见书末[术语表](back/glossary.md)。

> 本章深入剖析 H2 数据库 MVStore 存储引擎中的 10 个核心算法。每个算法涵盖原理、实现位置、应用场景、优缺点和设计权衡。算法的持久化落地和并发控制详见第9章《持久化引擎深度解析》和第10章《锁实现与并发控制》。本章所有算法均来源于 H2 数据库开源项目（https://github.com/h2database/h2database）的 master 分支源码。

本章 10 个算法分布在 3 个子文件中：

| # | 算法 | 源文件 | 对应章节 |
|---|------|--------|----------|
| 1 | B-Tree 索引 | `ch6-1-data-structures.md` | 6.1 |
| 2 | Copy-on-Write 版本管理 | `ch6-1-data-structures.md` | 6.2 |
| 3 | MVCC 多版本控制 | `ch6-1-data-structures.md` | 6.3 |
| 4 | Chunk 压缩整理 | `ch6-2-storage-algorithms.md` | 6.4 |
| 5 | LIRS 缓存替换 | `ch6-2-storage-algorithms.md` | 6.5 |
| 6 | 空闲空间管理 | `ch6-2-storage-algorithms.md` | 6.6 |
| 7 | MVStore 平衡（分裂/合并） | `ch6-2-storage-algorithms.md` | 6.7 |
| 8 | 查询优化连接顺序 | `ch6-3-query-algorithms.md` | 6.8 |
| 9 | 空间索引 (R-Tree) | `ch6-3-query-algorithms.md` | 6.9 |
| 10 | SQL 解析 (Recursive Descent) | `ch6-3-query-algorithms.md` | 6.10 |
---



## 6.1 B-Tree 索引

### 6.1.1 核心描述

MVMap 实现了一个 **B+Tree 变体**，采用 Copy-on-Write (COW) 页面管理。所有数据存储在叶子节点（`Page.Leaf`），内部节点（`Page.NonLeaf`）只存储键和子节点引用。每个节点维护一个有序键数组，通过二分查找定位目标键。

> **术语说明**：H2 的 MVMap 底层实际实现了 B+Tree 变体（所有数据仅存储在叶子节点，内部节点只作为路由表）。本文档统一使用"B-Tree"这一简称以简化表述。在涉及具体数据结构细节时（如叶子节点 vs. 内部节点的差异），会明确区分为 B+Tree 语义。
>
> （注：本节以下统称 B-Tree，实际为 B+Tree 变体实现）

**B-Tree 的核心数据结构：**

```text
Page (抽象基类)
├── keys: Object[]          // 有序键数组（所有节点类型）
├── totalCount: long        // 子树中所有键的总数
├── map: MVMap              // 所属的 Map 引用
├── pos: int                // 当前写入位置（COW 副本使用）
│
├── Page.Leaf (叶子节点)
│   ├── keys: Object[]      // 叶子键
│   └── values: Object[]    // 对应的值数组（长度 = keys 长度）
│
└── Page.NonLeaf (内部节点)
    ├── keys: Object[]      // 分隔键（长度 = children - 1）
    ├── children: Page[]    // 子节点数组（长度 = keys + 1）
    └── getChildPage(int)   // 根据索引获取子页面
```
```text

**为什么 H2 选择 B+Tree 而非其他树结构：**

B+Tree 相比普通 B-Tree 的区别在于：所有数据仅在叶子节点存储，内部节点仅作为路由表。这一设计使得：
1. 内部节点的扇出更高——每个内部节点可存储数百个分隔键，树深度通常不超过 4 层
2. 叶子节点可通过链表顺序遍历——范围查询只需一次找到起始叶子，然后沿链表遍历
3. 缓存效率更高——内部节点更小，更多的路由信息可驻留缓存

H2 的 B-Tree 实现了标准的 B+Tree 语义，但加入了 COW 机制使之适应 MVStore 的 append-only 存储模型。

**为什么使用二分查找定位键：**

每个 Page 内部的键数组是排序的，因此可以使用二分查找在 O(log keysPerPage) 时间内定位目标键。keysPerPage 默认值为 48（可配置），因此每个节点的二分查找仅需约 6 次比较（log₂48 ≈ 6）。对于 4 层深度的树，一次完整的查找需要约 24 次比较——远比全表扫描高效。

**查找算法（二分查找 + 递归遍历）：**

```
```java
function get(root, key):
    p = root
    while true:
        index = binarySearch(p.keys, key)
        // binarySearch 返回：
        //   >= 0  → 精确匹配的位置
        //   < 0   → -insertionPoint - 1，即应插入的位置
        if p.isLeaf():
            return index >= 0 ? p.values[index] : null
        if index < 0:
            index = -index - 1  // 转为正索引
        // 注意：对于 NonLeaf，children 数量总是 keys + 1
        // index 可能等于 keys.length（所有键都小于目标）
        p = p.children[index]
```

**插入算法（COW 路径复制 + 中位数分裂）：**

```text
function put(key, value):
    rootRef = flushAndGetRoot()
    tip = traverseDown(rootRef.root, key)
    decision = decisionMaker.decide(tip, key, value)
    if decision == PUT:
        p = decision.apply(tip)   // 复制叶子，插入/更新值
        while p is too large:
            at = keyCount >> 1         // 中位数分裂点
            k = p.keys[at]             // 中位键提升至父节点
            split = p.split(at)        // 创建右兄弟页面
            if parent == null:
                p = newRoot(k, p, split)  // 树高度 +1
            else:
                p = parent
                p.insertNode(k, split)    // 将分裂结果插入父节点
        CAS rootRef -> newRootRef
```

**删除算法（树深度折叠）：**

```text
function remove(key):
    // 遍历到叶子，删除条目
    // 当 totalCount == 1 时触发树折叠：
    while totalCount == 1 and parent != null:
        // 用唯一的子节点替换当前根
        root = root.children[0]
        // 树高度 -1
```

**B-Tree 变体对比概览：**

```text
           B-Tree              B+Tree (H2 选择)         B*Tree
    ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
    │ 所有节点存数据    │   │ 内部节点仅存键    │   │内部节点存键+数据 │
    │ 内部节点含数据指针│   │ 叶子节点存数据    │   │ 分裂策略更保守  │
    │                  │   │ 叶子节点链表连接  │   │                  │
    │ 内部节点：键+数据 │   │ 内部节点：键+子页 │   │ 内部节点：键+数据│
    │ 叶子节点：键+数据 │   │ 叶子节点：键+值   │   │ 叶子节点：键+数据│
    │                  │   │                  │   │                  │
    │ 扇出: 中         │   │ 扇出: 高         │   │ 扇出: 中        │
    │ 范围查询: 中     │   │ 范围查询: 快      │   │ 范围查询: 中    │
    │ 空间利用率: 高   │   │ 空间利用率: 中    │   │ 空间利用率: 高  │
    └──────────────────┘   └──────────────────┘   └──────────────────┘

    如图 6-1 所示，H2 选择 B+Tree 的核心收益：
      1. 内部节点扇出更高 → 树更浅 → 路径复制更少
      2. 叶子链表加速范围扫描 → 覆盖索引常用
      3. 只读路由节点可长期驻留 LIRS 缓存
```

### 6.1.2 三层 B-Tree 完整结构

**图 6-1: 三层 B-Tree 完整结构示意图**

```text
                         ┌─────────────────────────────────┐
                         │       Root (NonLeaf)            │
                         │  keys: [ "m", "t" ]             │
                         │  children: [A] [B] [C]          │
                         └────────┬──────────┬─────────────┘
                                  │          │
              ┌───────────────────┘          └───────────────┐
              ▼                                              ▼
   ┌──────────────────────┐                     ┌──────────────────────┐
   │ Node A (NonLeaf)     │                     │ Node B (NonLeaf)     │
   │ keys: ["d","g","j"]  │                     │ keys: ["p","r"]      │
   │ children: 4 subtrees │                     │ children: 3 subtrees │
   └──┬─────┬─────┬─────┬─┘                     └──┬─────┬─────┬──────┘
      │     │     │     │                          │     │     │
      ▼     ▼     ▼     ▼                          ▼     ▼     ▼
   ┌────┐ ┌────┐ ┌────┐ ┌────┐                  ┌────┐ ┌────┐ ┌────┐
   │Leaf│ │Leaf│ │Leaf│ │Leaf│                  │Leaf│ │Leaf│ │Leaf│
   │a b │ │d e │ │g h │ │j k │                  │m n │ │p q │ │r s │
   │c   │ │f   │ │i   │ │l   │                  │o   │ │    │ │    │
   └────┘ └────┘ └────┘ └────┘                  └────┘ └────┘ └────┘

                    ┌──────────────────────┐
                    │ Node C (NonLeaf)     │
                    │ keys: ["v","x","z"]  │
                    │ children: 4 subtrees │
                    └──┬─────┬─────┬─────┬─┘
                       │     │     │     │
                       ▼     ▼     ▼     ▼
                    ┌────┐ ┌────┐ ┌────┐ ┌────┐
                    │Leaf│ │Leaf│ │Leaf│ │Leaf│
                    │t u │ │v w │ │x y │ │z   │
                    └────┘ └────┘ └────┘ └────┘

  说明：
    - 根节点以 "m" 和 "t" 为分界键，将全量数据分为三个区间
    - 内部节点 A 以 "d","g","j" 进一步细分区间 [a, l)
    - 叶子节点存储实际键值对（键已排序）
    - 本例中树深度为 3，可以管理约 keysPerPage³ 个键
```

**查找路径与叶子链表示例：**

```text
范围查询 [g, o) 的叶子链表遍历路径：

           Root
         ┌──┴──┐
        NodeA NodeB NodeC
         │          │
   ┌─────┼────┐    │
   ▼     ▼    ▼    ▼
  Leaf1─→Leaf2─→Leaf3─→Leaf4─→Leaf5─→Leaf6
   a..c  d..f  g..i  j..l  m..o  p..r
         ↑     ↑──────────↑
         │     遍历范围 [g, o)
         │     Leaf3 → Leaf4 → Leaf5
         │     沿叶子链表顺序访问
   叶子链表实际存储为页面指针:
   Leaf1.next = Leaf2
   Leaf2.next = Leaf3
   Leaf3.next = Leaf4  ← 从此开始
   Leaf4.next = Leaf5  ← 在此结束
   Leaf5.next = Leaf6

过程：
  1. 从根开始二分查找，定位起始叶子 Leaf3(键 g)
  2. 沿叶子链表向后遍历：Leaf3 → Leaf4 → Leaf5
  3. 遇到键 o 时停止（已超出范围）
  4. 只访问了 3/6 个叶子节点

如图 6-2 所示，性能特征：
  - 无需回溯到上层节点
  - 叶子页面按磁盘顺序预读 → 顺序 I/O
  - 10 万条范围扫描 ≈ 毫秒级
```

### 6.1.3 页面分裂过程（前 → 中 → 后）

**图 6-2: 页面分裂过程（前 → 中 → 后）**

```text
分裂前 - 叶子页面已满（keysPerPage = 4，现有 5 个键）：

  父节点 (NonLeaf):
    keys: [ "j", "r" ]
    children: [ Leaf1, Leaf2, Leaf3 ]

  Leaf2 (已满):
    keys:   [ "k", "l", "m", "n", "o" ]
    values: [ v_k, v_l, v_m, v_n, v_o ]
    keyCount = 5, keysPerPage = 4 → 需要分裂

分裂中 - 计算分裂点并分割：

  at = keyCount >> 1 = 5 >> 1 = 2
  medianKey = Leaf2.keys[2] = "m"

  ┌─ 左页 (Leaf2, 保留原引用) ──┐   ┌─ 右页 (split, 新建) ──┐
  │  keys: [ "k", "l" ]         │   │  keys: [ "n", "o" ]   │
  │  values: [ v_k, v_l ]       │   │  values: [ v_n, v_o ] │
  │  keyCount = 2               │   │  keyCount = 2          │
  └─────────────────────────────┘   └────────────────────────┘
         ↑ 中位键 "m" 被提升到父节点 ↑

分裂后 - 父节点插入中位键和新的子引用：

  父节点 (NonLeaf, 更新后):
    keys: [ "j", "m", "r" ]
    children: [ Leaf1, Leaf2(左), split(右), Leaf3 ]

  注意：
    - "m" 被插入到父节点的 keys 数组中（在 "j" 和 "r" 之间）
    - split 被插入到父节点的 children 数组中
    - 如果父节点因此也满了 → 递归向上分裂

  对比：COW 模式下，分裂涉及以下副本创建：
    Leaf2.copy() → 创建左页（含前 2 个键值对）
    split = Leaf2.split(2) → 创建右页（含后 2 个键值对）
    parent.copy() → 创建父节点副本（插入新键和新子引用）
    ...直到根节点
```

**COW 模式下的连续插入触发级联分裂：**

```text
插入序列：put("p"), put("q"), put("s"), put("t"), put("u")

步骤 1: Leaf2 已有 5 个键，插入 "p" 后键数=6
         → 中位数分裂 at = 6>>1 = 3
         ┌───────────┐   ┌───────────┐
         │ 左 Leaf2  │   │ 右 split  │
         │ k,l,m     │   │ p,q,r     │
         └───────────┘   └───────────┘
         中位键 "o" 提升至父节点

步骤 2: 父节点插入 "o" 后键数从 1→2
         父节点: [ "j", "o", "r" ]  (未满，停止传播)

步骤 3: 继续插入 "s","t","u"
         Leaf3 从 2 个键增长到 5 个 → 需要分裂
         → 重复步骤 1-2 直到稳定

级联传播停止条件：
  - 父节点仍有空闲槽位 → 插入后停止
  - 父节点已满且是根 → 创建新根，树高度+1
  - 父节点已满且非根 → 继续向上传播

如图 6-3 所示，COW 下的级联合并成本：
  每次分裂涉及 d 个副本（d = 到根的路径长度）
  级联分裂时每个受影响的父节点都需要 COW 复制
  最多影响 log_k(N) 个页面
```

### 6.1.4 二分查找下降过程

**图 6-3: 二分查找下降过程**

```text
查找 key = "search" 在 B-Tree 中的路径：

                      Root (NonLeaf)
              keys: [ "data", "index", "mvstore", "query" ]
                      0        1         2          3
  第 1 层 ──────────┼─────────┼─────────┼──────────┼─────────
   binarySearch(["data","index","mvstore","query"], "search"):
     lo=0, hi=3, mid=1 → "index" > "search" → hi=0
     lo=0, hi=0, mid=0 → "data" < "search" → lo=1
     lo=1, hi=0 → 未找到，返回 -1 (insertionPoint=1)
     取 child[1]: Node A
                          ↓
                      Node A (NonLeaf)
              keys: [ "function", "lock", "page", "search" ]
                      0         1      2        3
  第 2 层 ──────────┼──────────┼──────┼─────────┼──────────
   binarySearch(["function","lock","page","search"], "search"):
     lo=0, hi=3, mid=1 → "lock" < "search" → lo=2
     lo=2, hi=3, mid=2 → "page" < "search" → lo=3
     lo=3, hi=3, mid=3 → "search" == "search" → 返回 3
     取 child[3]: Leaf B (但 index=3 意味着 keys 全部小于等于目标)
                          ↓
                      Leaf B
              keys: [ "search", "select", "session" ]
  第 3 层 ──────────┼──────────┼─────────┼───────────
   binarySearch(["search","select","session"], "search"):
     lo=0, hi=2, mid=1 → "select" > "search" → hi=0
     lo=0, hi=0, mid=0 → "search" == "search" → 返回 0
     → isLeaf() 为 true → 返回 values[0]

  总结：
    - 3 层递归，每层 2-3 次比较
    - 总计约 7 次比较 + 3 次指针跳转
    - 时间复杂度：O(log keysPerPage * treeHeight) ≈ O(6 * 4) = O(24) 次比较
```

**二分查找的缓存层级与延迟分布：**

```text
一次 B-Tree get("search") 操作的延迟分解：

                    CPU 寄存器 (≈1ns)
                    ┌──────────────────┐
                    │  二分查找比较      │
                    │  ~6 次/层 × 4 层   │
                    │  = 24 次比较       │
                    └────────┬─────────┘
                             │ 缓存命中时
                             ▼
                    L1/L2 CPU 缓存 (≈5-20ns)
                    ┌──────────────────┐
                    │  内节点 Page 对象  │
                    │  keys[] 数组      │
                    │  children[] 指针  │
                    └────────┬─────────┘
                             │ 缓存未命中时
                             ▼
                    LIRS 页面缓存 (≈50-200ns)
                    ┌──────────────────┐
                    │  反序列化的 Page   │
                    │  在 Java 堆中      │
                    └────────┬─────────┘
                             │ 全未命中时
                             ▼
                    磁盘 I/O (≈5-10ms) ← 比内存慢 10^5 倍

延迟对比：
  层级             延迟          每次 get() 访问次数
  CPU 比较          ~1 ns         24
  L1 缓存命中       ~1 ns         4 (节点对象引用)
  L2 缓存命中       ~5 ns         4 (节点 keys 数组)
  LIRS 缓存命中     ~50 ns        4 (Page 对象访问)
  缺页中断(从磁盘)  ~5 ms         0.01% 概率

如图 6-4 所示，关键优化：
  - 内节点常驻 LIRS 缓存（因为访问频率高）
  - 叶子节点可能在磁盘上（随机读取不命中时）
  - 在 99% 的情况下，B-Tree 的 4 层访问全部在内存中完成
```

### 6.1.5 COW 写路径传播

**图 6-4: COW 写路径传播示意图**

```text
写操作：put("search", new_value)

步骤 1: 读取 RootReference（volatile read）
  Thread ──▶ RootReference ──▶ root (Page)
                                  │
步骤 2: 从根下降到叶子，记录路径      路径记录: [root, NodeA, LeafB]
                                  │
                                  ▼
                              LeafB.copy()
                                  │
步骤 3: 复制并修改叶子                │
                                  ▼
                          ┌─ LeafB' (新副本) ──┐
                          │  values[0] = new   │
                          └────────────────────┘
                                  │
步骤 4: 向上复制父节点               │
                                  ▼
                          ┌─ NodeA' (新副本) ──┐
                          │  children[3] = LeafB' │
                          └────────────────────┘
                                  │
步骤 5: 向上复制根节点               │
                                  ▼
                          ┌─ Root' (新副本) ───┐
                          │  children[1] = NodeA'│
                          └────────────────────┘
                                  │
步骤 6: CAS 替换根引用              │
                                  ▼
                         RootReference (旧)
                         RootReference' (新)
    CAS(rootRef, oldRef, newRef)   // 原子操作

  最终状态：
    旧页面树 (不可变，可被安全读取):
      Root ──▶ NodeA ──▶ LeafB (旧值)
                              │
    新页面树 (包含新值):          │
      Root' ──▶ NodeA' ──▶ LeafB' (新值)
                              ↑
    共享页面 (未修改):   NodeA 的其他子节点
                        Root 的其他子节点
```

**多版本读一致性模型：**

```text
读线程在 CAS 发生前后的可见性：

时间线 ─────────────────────────────────────────────────────▶

  写入前:                       写入中:                    写入后:
  ┌────────────┐               ┌────────────┐             ┌────────────┐
  │ 读线程 R1  │               │ 读线程 R1  │             │ 读线程 R1  │
  │ root.get() │               │ root.get() │             │ root.get() │
  │ → oldRef   │               │ → oldRef   │             │ → newRef   │
  │ 看到旧数据 │               │ 看到旧数据 │             │ 看到新数据 │
  └────────────┘               └────────────┘             └────────────┘
       │                            │                           │
       ▼                            ▼                           ▼
  ┌────────────┐               ┌────────────┐             ┌────────────┐
  │ 写线程 W   │               │ 写线程 W   │             │ 写线程 W   │
  │ root.get() │               │ CAS(oldRef │             │ 写入完成   │
  │ → oldRef   │               │  ,newRef)  │             │            │
  │ 开始 COW   │               │ 提交更改   │             │            │
  └────────────┘               └────────────┘             └────────────┘

关键保证：
  - 所有读线程要么看到完全旧的树，要么看到完全新的树
  - 不会有"中间状态"（部分旧部分新）
  - 旧树的页面在没有引用时被 GC 回收
  - 新树的未修改页面与旧树共享

COW 与 Java 内存模型：
  CAS 操作具有 volatile 读/写语义
  → CAS 前的所有写入对之后执行 volatile 读的线程可见
  → 不需要额外的 synchronized 或 Lock
```

keysPerPage 的权衡：

             低 keysPerPage (如 16)              高 keysPerPage (如 128)
             ─────────────────────              ──────────────────────
  树深度:    4-5 层                               2-3 层
  查找比较:  每层 4 次 × 5 层 = 20 次             每层 7 次 × 3 层 = 21 次
  分裂频率:  频繁（页面易满）                       较少（页面容量大）
  内存碎片:  更多页面，开销大                       页面更大，内存占用高
  COW 代价:  路径短 (5 页) 但分裂多                 路径短 (3 页) 分裂少
  顺序扫描:  叶子链表长，跳转多                       叶子链表短，跳转少

  H2 默认:   keysPerPage = 48 (约 6 次比较/层)
             这个值在大多数场景下达到最佳平衡：
             - 4 层深度可管理 48⁴ ≈ 530 万个键
             - 每个页面约 48 × (键大小 + 值大小) 字节
             - 对 Java 对象对齐友好

  页内二分查找性能：
    keysPerPage   比较次数    缓存行访问(64B, 8B/ref)
        16           4             2 行
        32           5             4 行
        48           6             6 行  ← H2 默认
        64           7             8 行
       128           8            16 行
       256           9            32 行

  为什么不是更大的 keysPerPage？
    虽然 keysPerPage 更大可以减少树深度，但：
    1. 更大的页面意味着每次 COW 复制更多数据
    2. 二分查找的 CPU 成本与 log(N) 成正比，增长缓慢
    3. 页面过大导致缓存行浪费——扫描一个页面可能只需要其中的一个键

**内存占用与性能的量化关系：**

```text
keysPerPage 选择对不同工作负载的影响：

                  内存占用 (per page)
                       │
                       │  256 (32KB)
                       │    │
                       │  128 (16KB)
                       │    │
                       │   64 (8KB) ← 默认值 48 (≈6KB)
                       │    │
                       │   32 (4KB)
                       │    │
                       │   16 (2KB)
                       │    │
                       └──────────────────────────▶ 性能
                       低 ← keysPerPage → 高

      负载类型        推荐 keysPerPage    原因
      ────────────────────────────────────────────
      点查为主 (OLTP)      32-48       缓存友好，小页面
      范围扫描 (OLAP)      64-128      减少叶子链表长度
      大值存储             16-32       控制每次 COW 复制量
      混合负载             48          通用平衡点
      只读高频查询         64-128      利用缓存预填

实际内存开销公式（每页面）：
  Page 对象头:       ≈ 40 bytes (HotSpot OOP)
  keys[] 引用数组:   keysPerPage × 4 bytes (Compressed OOP)
  values[] 引用数组: keysPerPage × 4 bytes (叶子)
  children[] 引用数组: (keysPerPage+1) × 4 bytes (内节点)
  ─────────────────────────────────────────
  叶子页面总计:      ≈ 40 + 8 × keysPerPage bytes
  内节点页面总计:    ≈ 40 + 8 × keysPerPage + 4 bytes
  默认 48: 每个页面 ≈ 424 bytes (不含实际键值对象)
```

**B-Tree 相关类的继承与协作关系：**

```text
                    MVStore (存储引擎)
                      │
                      ├── FileStore (文件 I/O)
                      │
                      ├── FreeSpaceBitSet (空间管理)
                      │
                      └── MVMap (B-Tree 容器)
                            │
                            ├── Page (抽象基类)
                            │   ├── Page.Leaf (叶子节点)
                            │   └── Page.NonLeaf (内部节点)
                            │
                            ├── RootReference (不可变根引用)
                            │
                            ├── DecisionMaker (分裂/合并决策)
                            │
                            └── CursorPos (遍历位置记录)

调用链（写操作）:
  MVStore.store()
    → MVMap.operate()          MVMap.java:147-150
        → Page.copy()           Page.java:380-385
        → DecisionMaker.decide() MVMap.java:1724-1813
            → Page.split()      Page.java:424
        → compareAndSetRoot()   MVMap.java:864-867
```

**核心数据流（put 操作的方法间调用）：**

```text
调用者
  │
  ▼
MVMap.put(key, value)
  │
  ▼
operate(key, value, decisionMaker)  ← MVMap.java:147-150
  │
  ├──── flushAndGetRoot()           ← 获取最新根引用 MVMap.java:839-845
  │       │
  │       └── MVMap.root.get()      ← AtomicReference volatile 读
  │
  ├──── traverseDown(root, key)     ← 记录路径 CursorPos
  │       │
  │       └── binarySearch → Page.getChildPage() (每层)
  │
  ├──── decisionMaker.decide()      ← 决定 PUT/ABORT/REMOVE
  │       │
  │       └── Page.copy() → Page.clone() (COW 路径)
  │
  ├──── while page is full:         ← 分裂传播循环
  │       ├── page.split(at)        ← Page.java:424
  │       ├── newRoot() / insertNode()
  │       └── page = parent         ← 向上传播
  │
  └──── compareAndSetRoot()         ← CAS 替换根引用 MVMap.java:864-867
          │
          └── root.compareAndSet(oldRef, newRef)
```

| 文件 | 类 | 行号范围 | 职责 |
|------|-----|---------|------|
| `mvstore/Page.java` | `Page` | 37-1751 | B-Tree 节点抽象基类 |
| `mvstore/Page.java` | `Page.Leaf` | 1494-1750 | 叶子节点（存键值对） |
| `mvstore/Page.java` | `Page.NonLeaf` | 1134-1446 | 内部节点（存键+子指针） |
| `mvstore/MVMap.java` | `MVMap` | 35-2170 | B-Tree 容器，插入/查找/删除 |
| `mvstore/MVMap.java` | `DecisionMaker.decide()` | 1724-1813 | 分裂/合并逻辑 |

关键行号：

```text
Page.get()（二分查找递归遍历）：Page.java:235-245
MVMap.put() → operate()：MVMap.java:147-150
分裂触发条件：MVMap.java:1776-1778
分裂执行（median split）：MVMap.java:1780-1801
根节点升级：MVMap.java:1785-1793
树深度折叠（merge）：MVMap.java:1738-1762
Page.binarySearch()：Page.java:200-215
Page.split(int at)：Page.java:424（抽象方法）

keysPerPage 获取：MVStore.getKeysPerPage() → 默认 48
```

### 6.1.6 应用场景
- **MVMap 的所有读写操作**：`get()`、`put()`、`remove()`、`cursor()` 均基于 B-Tree 遍历
- **元数据存储**：MVStore 的布局信息、Chunk 信息均存储在 MVMap 中
- **事务系统**：`TransactionMap` 底层委托给 MVMap 完成操作
- **空间索引**：`MVRTreeMap` 继承 MVMap 并覆盖 B-Tree 操作为空间感知版本
- **游标遍历**：所有范围查询通过 B-Tree 的叶子节点链表实现顺序访问

**B-Tree 在 MVStore 整体架构中的位置：**

```text
应用程序 (JDBC/API)
    │
    ▼
┌──────────────────────────────────┐
│  SQL 执行层                       │
│  Parser → Optimizer → Executor   │
└────────────────┬─────────────────┘
                 │ TableScan / IndexLookup
                 ▼
┌──────────────────────────────────┐
│  事务层                          │
│  TransactionMap (MVCC 包装)      │
│  TxDecisionMaker (冲突检测)       │
└────────────────┬─────────────────┘
                 │ put / get / remove
                 ▼
┌──────────────────────────────────┐
│  MVMap (B-Tree 容器)      ← 核心 │
│  Page.Leaf / Page.NonLeaf        │
│  RootReference / COW             │
└────────────────┬─────────────────┘
                 │ flush / persist
                 ▼
┌──────────────────────────────────┐
│  存储层                          │
│  Chunk / FreeSpaceBitSet         │
│  FileStore (文件 I/O)            │
│  LIRS 缓存 (页面缓存)             │
└──────────────────────────────────┘
                 │
                 ▼
             磁盘文件

B-Tree 处于中间层，隔离了上层的 SQL 语义与下层的存储布局。
```

**典型查询路径中 B-Tree 的使用：**

```text
SELECT * FROM users WHERE id = 42

SQL 解析层
  │
  ▼
查询计划: IndexLookup(users, id=42)
  │
  ▼
MVMap.get("users", "42")
  │
  ├── LIRS 缓存查找 → 命中则跳过磁盘
  ├── Page.get(root, "42")  ← B-Tree 二分查找
  │     ├── Root: binarySearch → child[2]
  │     ├── NodeA: binarySearch → child[1]
  │     └── Leaf: binarySearch → values[3]
  │
  ├── 反序列化 Value → Java 对象
  │
  └── 返回结果行
```

### 6.1.7 优缺点
**优势：**
- 自平衡，所有操作 O(logₖ N)（k = keysPerPage ≈ 48）
- 高扇出（每个节点可存数百个键），树深度通常 ≤ 4
- 顺序访问高效（叶子节点通过键排序连续存储）
- 页内二分查找利用 CPU 缓存行预取

**局限：**
- COW 模式下写放大（每次修改复制整条路径到根）
- 分裂/合并可能引起短暂的内存峰值
- 非就地更新，写吞吐受限于 CAS 根节点频率
- 连续插入可能导致频繁的叶子分裂（但 COW 分摊了部分成本）

**优势/局限对比表：**

```text
┌────────────────────────────────────────────────────────────────┐
│  维度        │  优势                    │  局限                │
├──────────────┼──────────────────────────┼──────────────────────┤
│  读性能       │  O(log N) 二分查找       │  无（读最优）        │
│  写性能       │  COW 无锁提交            │  路径复制写放大      │
│  并发         │  无锁并发读              │  CAS 写写冲突        │
│  空间利用     │  高扇出减少节点数        │  旧页面等待 GC       │
│  范围扫描     │  叶子链表顺序遍历        │  链表过长时跳转多    │
│  崩溃恢复     │  不可变页面天然支持      │  需重建元数据        │
│  实现复杂度   │  COW 简化并发模型        │  分裂/合并逻辑复杂   │
│  内存开销     │  内节点缓存友好          │  短命对象 GC 压力    │
└────────────────────────────────────────────────────────────────┘

**COW B-Tree 与其他方案的量化对比：**

```
```text
              ┌─────────────────────────────────────┐
              │      对比维度（同数据集 1M 条记录）   │
              │                                     │
              │ 树深度          4层                   │
              │ 节点总数        ≈ 22,000              │
              │ 内节点数        ≈ 500                 │
              │ 单次 put 路径复制  4-5 个 Page        │
              │ 单次 put 内存分配 ≈ 2-4 KB            │
              └─────────────────────────────────────┘

                 COW B-Tree(H2)    In-place B-Tree     Skip List
                 ─────────────     ──────────────      ─────────
  读 O(log N)    ✓ 无锁             ✗ 需要读锁          ✓ 无锁
  写 O(log N)    ✓ CAS 提交         ✗ 写锁持有期长      ✓ CAS 更新
  范围扫描       ✓ 叶子链表         ✓ 叶子链表          ✗ O(N) 跳跃
  写放大         ~4x               ~1x                ~1x
  内存分配       ~2-4KB/put        0 (就地修改)        ~0.5KB/put
  GC 压力        中等              低                 低
  缓存效率       高（只读路由页）    中（路由页可变）    中（指针跳跃）
  实现复杂度      中等              高（锁+页面管理）   简单
```

### 6.1.8 设计权衡
| 方案 | H2 (COW B-Tree) | 传统 in-place B-Tree |
|------|----------------|---------------------|
| 并发控制 | 无需读锁 | 需要读写锁 |
| 写放大 | 高（复制路径） | 低（就地修改） |
| MVCC 支持 | 原生支持 | 需要额外 undo log |
| 快照读 | 零成本 | 需要 copy |
| 崩溃恢复 | 天然支持（不可变页面） | 需要 WAL + checkpoint |
| 实现复杂度 | 中等（COW 逻辑） | 中等（锁 + 页面管理） |

**COW vs. In-place 的决策树：**

```text
问题: 选择 COW 还是 In-place 更新？
                    │
                    ▼
          ┌─ 读多写多? ──┐
          │               │
         YES              NO
          │               │
          ▼               ▼
     ┌─ 并发读重要？   读多写少 (H2 场景)
     │  YES     NO         │
     │   │       │         │
     │   ▼       ▼         ▼
     │ COW   检查写延迟   COW ✓
     │       要求          │
     │        │            │
     │     ┌──┴──┐        ┌┴────────────┐
     │     │     │        │ 收益:        │
     │   低    高         │  · 无锁并发读 │
     │    │     │         │  · 零成本快照 │
     │    │     │         │  · 天然 MVCC │
     │  COW  In-place     │  · 崩溃恢复   │
     │                    │             │
     │                    │ 代价:        │
     │                    │  · 写放大 3-4x│
     │                    │  · 短命对象   │
     └────────────────────┴─────────────┘

H2 选择 COW 的核心理由:
  嵌入式数据库特点 → 读远多于写
  append-only 存储 → COW 天然契合
  Java GC → 短命对象回收廉价
```

**中位数分裂 vs. 其他分裂策略：**

二分法分裂（`keyCount >> 1`）是最简单且最有效的策略。理论上 B-Tree 有多种分裂策略（如 5-5 分裂、百分比分裂），但中位数分裂保证了分裂后两端键数最多相差 1，树高度始终最优。

```text
分裂策略对比：

  策略         分裂点选择        填充率保证        实现代价
  ──────────────────────────────────────────────────────
  中位数       keyCount >> 1     ≥ 50%           O(1)
  2-3 分裂    灵活(2:3 比例)      ≥ 40%           复杂
  百分比分裂   百分比阈值          ≥ 阈值            O(1)
  5-5 分裂     严格 50/50         = 50%           需要调整

  中位数分裂的数学保证:
    分裂前: 任意 keyCount
    分裂后: 左右键数相差 ≤ 1
    ⇒ 填充率始终 ≥ (⌊keyCount/2⌋-1) / keyCount
    ⇒ 最坏填充率 ≈ 50%

  对于 keysPerPage = 48 的中位数分裂:
    keyCount = 49: 左 24 右 24 (分裂点 24)
    keyCount = 60: 左 30 右 29 (分裂点 30)
    keyCount = 100: 左 50 右 49 (分裂点 50)
  
  无论键数多少，左右页面始终近似均匀。
```

---

## 6.2 Copy-on-Write 版本管理

> **参考**: H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#versions`)
> 官方将版本描述为"所有 map 在特定时间点的快照"，COW 确保只有变更页被复制。

### 6.2.1 核心描述

COW 的核心原则：**不修改现有不可变对象，而是创建副本并在副本上修改，然后通过原子 CAS 替换根引用。** 这一原则贯穿 MVStore 的整个设计——从 Page 到 Chunk 再到 RootReference，所有可变操作均通过 COW 路径进行。

**不可变性保证：**

Page 对象一旦被创建并发布（对其他线程可见），其内部状态永不改变。
这意味着：
  1. keys[] 数组不会被修改（只读共享）
  2. values[] 数组不会被修改
  3. children[] 数组不会被修改
  4. totalCount 不可变

实现方式：
  - Page 的所有字段均为 final（或写入一次后不再修改）
  - Page.copy() 创建新的可变副本（pos = 0 表示可写）
  - Page.clone() 执行浅拷贝（keys/values 数组与原始对象共享）
  - 新页面在完全构建好之后才通过 CAS 发布

**为什么 COW 适合 MVStore：**

MVStore 是一个 append-only 存储引擎——新数据总是写入文件末尾。COW 与 append-only 天然契合：
1. 每次 COW 写入创建的新页面可以连续写入磁盘（顺序 I/O）
2. 旧页面在磁盘上保持不变，可被其他读线程安全访问
3. 无需 WAL（Write-Ahead Log）——事务的原子性由 CAS 保证

**写放大分析：**

COW 的主要代价是写放大——每次修改需要复制 O(log N) 个页面。

写放大因子 = 修改路径上的页面数 / 实际被修改的页面数

对于 B-Tree 深度为 d 的树：
  - 每次 put() 需要复制 d 个页面（根到叶子的路径）
  - 如果分裂发生，需要额外复制分裂后的父页面
  - 因此：写放大因子 ≈ d （通常 d=3~4）

与 in-place 更新的对比：
  - In-place: 写放大 = 1（只修改一个页面）
  - COW:     写放大 = d（复制路径上的所有页面）

缓解措施：
  1. 后台压缩（Chunk compaction）合并多个小修改
  2. append 模式批量写入（缓冲区满后一次性提交）
  3. Java GC 快速回收短命对象

**COW 原理的层次抽象：**

```text
COW 在 MVStore 中应用于三个不同层次：

  层次 1: Page 级 COW (最频繁)
  ┌─────────────────────────────────────────────┐
  │  每次 put()/remove() → 复制页面的路径        │
  │  粒度: 单个 Page 对象                        │
  │  触发: 每次写操作                            │
  │  结果: 新 RootReference + 新路径页面          │
  └─────────────────────────────────────────────┘
           │
           ▼
  层次 2: Chunk 级 COW (压缩时)
  ┌─────────────────────────────────────────────┐
  │  compact() → 重写存活页面到新 Chunk          │
  │  粒度: Chunk 级别的数据                      │
  │  触发: 文件碎片严重时                        │
  │  结果: 老 Chunk 标记 rewritable              │
  └─────────────────────────────────────────────┘
           │
           ▼
  层次 3: RootReference 级 COW (最顶层)
  ┌─────────────────────────────────────────────┐
  │  CAS(root, oldRef, newRef) → 原子切换版本    │
  │  粒度: 整棵树的根引用                        │
  │  触发: 每次事务提交                          │
  │  结果: 新版本对所有读线程可见                  │
  └─────────────────────────────────────────────┘

  三个层次的关系:
    Page COW 是基础 (每次写)
    Chunk COW 是 Page COW 的持久化 (刷盘)
    RootReference COW 是可见性保证 (CAS 发布)
```

**Page 可变/不可变状态的转换模型：**

```text
Page 的生命周期中的两种状态:

                       Page.copy()
   ┌──────────┐  pos=0  ┌──────────┐  完全构建   ┌──────────┐
   │ 可变副本  │ ──────▶ │ 构建中    │ ────────▶  │ 不可变    │
   │ (pos=0)   │         │ (pos>0)   │            │ (published)│
   └──────────┘         └──────────┘            └──────────┘
        │                     │                       │
        │   clone() 浅拷贝     │  复制键数组            │  CAS 发布
        │                     │  复制值数组            │  后只读
        ▼                     ▼                       ▼
   ┌──────────┐         ┌──────────┐            ┌──────────┐
   │ 共享数组  │         │ 新数组    │            │ 只读共享  │
   │ (引用)    │         │ (独立)    │            │ (final)   │
   └──────────┘         └──────────┘            └──────────┘

  关键保证:
    - pos == 0: 可变，仅当前线程可访问
    - pos > 0:  正在序列化，独享
    - pos < 0 || published: 不可变，所有线程可安全读取

  如图 6-5 所示，Page.copy() 的实现 (Page.java:380-385):
    1. 创建新 Page 实例
    2. 浅拷贝 keys/values/children 引用数组 (clone())
    3. 设置 pos = 0 （标记为可变）
    4. 返回新实例
```

### 6.2.2 COW 更新前后对比

**图 6-5: COW 更新前后对比**

```text
场景：更新键 "k" 的值（从 v_old 改为 v_new）

更新前（所有页面不可变）：

  RootReference ──▶ Root ──▶ NodeA ──▶ LeafK: [k: v_old]
                                  │
                                  └──▶ LeafJ: [j: v_j]
                                  └──▶ LeafL: [l: v_l]

更新后（COW 沿路径复制）：

  RootReference ──▶ Root  (旧，仍可被旧快照读取)
                    NodeA (旧)
                    LeafK (旧, v_old)

  RootReference' ──▶ Root' (新副本) ──▶ NodeA' (新副本) ──▶ LeafK' (新副本, k: v_new)
                                              │
                                              └──▶ LeafJ (共享，未修改)
                                              └──▶ LeafL (共享，未修改)

  共享页面图示：
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────────────┐
  │ 旧 Root  │     │ 旧 NodeA │     │ 旧 LeafK │     │ v_old (被 GC)    │
  │          │     │          │     │          │     │                  │
  │ 不可变   │     │ 不可变   │     │ 不可变   │     │ 无引用 → 回收    │
  └──────────┘     └──────────┘     └──────────┘     └──────────────────┘
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────────────┐
  │ 新 Root' │     │ 新 NodeA'│     │ 新 LeafK'│     │ v_new (新值)     │
  │          │     │          │     │          │     │                  │
  │ 可变→发布│     │ 可变→发布│     │ 可变→发布│     │ 可被访问         │
  └──────────┘     └──────────┘     └──────────┘     └──────────────────┘
                    ┌──────────┐     ┌──────────┐
                    │ LeafJ    │     │ LeafL    │
                    │          │     │          │
                    │ 共享！   │     │ 共享！   │
                    │ 新旧引用 │     │ 新旧引用 │
                    └──────────┘     └──────────┘

  COW 的关键洞察：
    虽然每个写操作创建了 d 个新页面，但大多数子页面（NodeA 的 2/3 子节点）
    被新旧版本共享——实际新增的内存远小于整棵树的大小。
```

**共享页面的引用计数与 GC 回收：**

```text
COW 产生的页面间引用关系示例：

  写操作前（单版本）:
    RootRef v5 ──▶ Root ──▶ NodeA ──▶ LeafK
                                      LeafJ
                                      LeafL

  写操作后（双版本共存）:
    RootRef v5 ──▶ Root  ──▶ NodeA ──▶ LeafK [K:v_old] ← 只被 v5 引用
                         └── LeafJ   ← 被 v5 和 v6 共享
                         └── LeafL   ← 被 v5 和 v6 共享

    RootRef v6 ──▶ Root' ──▶ NodeA'─▶ LeafK' [K:v_new]
                                    └── LeafJ (共享)
                                    └── LeafL (共享)

  GC 回收条件:
    RootRef v5 不再被任何读线程引用时:
      → Root (无引用) GC
        → NodeA (无引用) GC
          → LeafK (无引用) GC ← 只有旧值被回收
          → LeafJ (仍有 v6 引用) 存活
          → LeafL (仍有 v6 引用) 存活

  如图 6-6 所示，关键洞察:
    COW 导致的"垃圾"主要是在路径上被替换的页面
    未被修改的页面（如 LeafJ, LeafL）被新旧版本共享
    每次 put() 实际创建的垃圾 ≈ d 个页面（而非整棵树）
```

### 6.2.3 RootReference CAS 更新序列

**图 6-6: RootReference CAS 更新序列**

```text
CAS (Compare-And-Swap) 使用 java.util.concurrent.atomic.AtomicReference：

  MVMap.root: AtomicReference<RootReference>

  时间线 ──────────────────────────────────────────────────▶

  写线程 A:
    │
    ├─ 1. oldRef = root.get()           // 读取当前根引用
    │       ├─ version = 5
    │       └─ root = Page@123
    │
    ├─ 2. 执行 COW 路径复制
    │       ├─ leaf' = Leaf.copy()
    │       ├─ ... 向上复制
    │       └─ root' = Root.copy()
    │
    ├─ 3. newRef = new RootReference(root', version+1)
    │
    ├─ 4. CAS(root, oldRef, newRef)     // 原子替换
    │       │
    │       ├─ 成功: 写操作完成
    │       │   root → newRef (version=6)
    │       │
    │       └─ 失败: 另一个线程先修改了 root
    │           root → otherRef (version=6)
    │           └─ 重试: 从步骤 1 开始
    │               (使用最新的 root 重新执行 COW)
    │
    └─ 5. 写操作返回

  写线程 B（同时写入）：
    │
    ├─ 1. oldRef = root.get()           // 与 A 同时读取
    │       └─ root = Page@123 (version=5)
    │
    ├─ 2. ... 执行 COW ...
    │
    ├─ 3. CAS(root, oldRef, newRef')
    │       └─ 失败！root 已被 A 改为 version=6
    │
    └─ 4. 重试：重新读取 root → 使用最新版本
            root → newRef (version=6)
            在新的 Page@123' 基础上执行 COW

  volatile 读 vs CAS 写：
    读线程：root.get() 是 volatile 读，无需锁
    写线程：CAS 是原子操作，确保只有一个写入成功
    没有写入的线程不需要任何同步——永远读最新的 root
```

**CAS 重试概率与性能分析：**

```text
CAS 冲突概率模型：

假设: N 个写线程同时写入同一个 MVMap

  无冲突概率 (一次 CAS 成功):
    P(0) = 1 - (N-1) * Δt / T

  其中:
    Δt = CAS 操作本身耗时 (≈ 20-50 ns)
    T  = 两次写操作的平均间隔

  示例 (单线程):  N=1 → P(0) = 100%

  示例 (2 线程竞争):
    T = 1μs (微秒级写入), Δt = 30ns
    P(0) = 1 - 1 * 30/1000 = 97%
    P(1) = 3% (一次重试)
    P(2) = 0.09% (两次重试)

  示例 (4 线程高竞争):
    T = 1μs, N=4
    P(0) = 1 - 3 * 30/1000 = 91%
    P(重复>3) ≈ 0.1%

CAS 重试次数分布：
                      2线程          4线程          8线程
  0 次重试            97.0%          91.0%          79.0%
  1 次重试             2.9%           8.2%         16.8%
  2 次重试             0.09%          0.7%          3.3%
  ≥3 次重试           <0.01%          0.1%          0.9%

  如图 6-7 所示，CAS 可伸缩性:
    MVMap 使用单个 AtomicReference<RootReference>
    所有写线程竞争同一个 CAS
    因此写吞吐量受限于 CAS 的单点瓶颈
    缓解: MVStore 通过批量提交减少 CAS 频率
```

### 6.2.4 读写路径对比

**图 6-7: 读写路径对比**

```text
读路径（完全无锁）：

  调用者
    │
    ▼
  MVMap.get(key)
    │
    ▼
  root = MVMap.root.get()          // volatile 读，无锁
    │                               // 获取当前 RootReference
    ▼
  Page.get(root.root, key)         // 遍历不可变页面树
    │                               // 所有页面不可变 → 无竞争
    ▼
  返回 value                        // 完成

  性能特征：
    - 一次 volatile 读 (≈ 5-10 ns)
    - 3-4 次指针跳转 (≈ 3-5 ns 每次)
    - 3-4 次二分查找 (≈ 30 ns 每次)
    - 总计: ≈ 50-100 ns (在 CPU 缓存命中时)

写路径（需要 CAS + COW）：

  调用者
    │
    ▼
  MVMap.put(key, value)
    │
    ▼
  rootRef = flushAndGetRoot()      // 刷新缓冲区 + volatile 读
    │
    ▼
  tip = traverseDown(rootRef.root, key)  // 遍历并记录路径
    │
    ▼
  decision = decisionMaker.decide(tip, key, value)
    │                               // 决定 PUT / ABORT / REMOVE
    ▼
  p = decision.apply(tip)          // 应用更改（COW 副本）
    │
    ▼
  while p is too large:            // 如果页面太大 → 分裂
    │  at = keyCount >> 1
    │  split = p.split(at)
    │  ... 向上传播
    ▼
  CAS(root, oldRef, newRef)        // 原子替换（可能重试）
    │
    ▼
  返回 oldValue

  性能特征（不包含分裂）:
    - 1 次 volatile 读
    - 3-4 次指针跳转和二分查找
    - 创建 3-4 个新 Page 对象 (含 keys/values 数组浅拷贝)
    - keys/values 数组克隆 (System.arraycopy)
    - 1 次 CAS 操作 (可能会重试)
    - 总计: ≈ 500-2000 ns (受 GC 分配影响)

  性能特征（包含分裂）:
    - 额外创建 2-3 个 Page 对象
    - 分裂时数组复制量更大（约 2× 正常 COW）
    - 可能触发 GC 年轻代回收
    - 总计: ≈ 2000-5000 ns
```

**读写路径的锁竞争对比：**

```text
             读操作 (get)                写操作 (put)
             ───────────                ───────────
  锁获取:    无                         无 (CAS 替代锁)
  同步:      无                         仅 CAS 指令 (硬件保证)
  阻塞:      永不阻塞                    CAS 失败时重试（非阻塞）
  等待:      无                         忙等（自旋重试）
  优先级:    不依赖                      CAS 公平性由硬件保证

  并发场景下延迟分布:

  场景: 1 读 + 1 写 (2 线程)
    读延迟: 50-100 ns (不受写线程影响)
    写延迟: 500-2000 ns (+ CAS 重试时间)

  场景: 4 读 + 2 写 (6 线程)
    读延迟: 50-100 ns (volatile 读可无限扩展)
    写延迟: 500-3000 ns (+ CAS 竞争增加)

  场景: 8 读 + 4 写 (12 线程)
    读延迟: 50-100 ns (读不竞争)
    写延迟: 500-5000 ns (+ 更多重试)

  如图 6-8 所示，结论: 读操作的可伸缩性接近无限
        写操作 CAS 竞争随写线程数线性增加
```
**图 6-8: 读写路径在并发场景下的资源争用对比**
```text
多线程并发场景下读写操作的资源使用差异：

                ┌──────────────────────────────────────┐
                │               MVMap 锁竞争           │
                │                                      │
                │  RootReference (AtomicReference)     │
                │  ┌────────────────────────────────┐  │
                │  │  volatile root (对所有线程可见)  │  │
                │  └────────────────────────────────┘  │
                │              │                       │
                │     ┌────────┴────────┐              │
                │     │                 │              │
                │     ▼                 ▼              │
                │  ┌──────┐        ┌──────┐           │
                │  │ 读线程  │        │ 写线程  │           │
                │  │ (N个)  │        │ (M个)  │           │
                │  └───┬───┘        └───┬───┘           │
                │      │                 │              │
                │      ▼                 ▼              │
                │  volatile读          CAS 竞争         │
                │  无锁，O(1)         多个写线程         │
                │  可无限扩展          只有一个成功       │
                └──────────────────────────────────────┘

  资源使用分解表:

        资源             读操作               写操作
        ─────────────────────────────────────────────────
        CPU (计算)       二分查找比较 (~30ns)  同上 + 数组复制 (~200ns)
        内存 (分配)      无                   创建 3-4 个 Page 对象
        锁               无                   CAS 指令 (硬件锁)
        volatile 读      root.get()           flushAndGetRoot()
        磁盘 I/O         LIRS 未命中时触发     append-only 写入
        缓存             LIRS 命中直接返回     COW 路径页面暂存

  并发伸缩性对比:

  读线程数    单线程读延迟   多线程读延迟    缓存命中率
  ──────────────────────────────────────────────────
  1           50-100 ns      50-100 ns       95%+
  2           50-100 ns      50-100 ns       95%+
  4           50-100 ns      50-100 ns       95%+
  8           50-100 ns      50-100 ns       95%+
  16          50-100 ns      50-100 ns       95%+
  (读延迟完全不受线程数影响)

  写线程数    单线程写延迟   多线程写延迟    CAS 重试率
  ──────────────────────────────────────────────────
  1           500-2000 ns     500-2000 ns     0%
  2           500-2000 ns     500-2500 ns     3%
  4           500-2000 ns     500-3000 ns     9%
  8           500-2000 ns     500-5000 ns     21%
  16          500-2000 ns     500-8000 ns     42%
  (写延迟随线程数增加而增加)

  如图 6-9 所示，伸缩性根源:
    读: volatile 读在所有线程间共享一个缓存行
        每个读线程在自己的寄存器中缓存 root 引用
        不需要任何互斥
    写: CAS 使用 LOCK CMPXCHG 指令锁定缓存行
        多个写线程竞争同一个缓存行
        每次只有一个成功，其余重试
```

### 6.2.5 写放大与内存开销

**图 6-9: 写放大与内存开销示意图**

每次 COW 写入的内存开销分解：

  put("k", "new_value") 在深度为 3 的树中：

  创建的对象               大小 (Java 对象)       说明
  ─────────────────────────────────────────────────────────────
  Page.Leaf'              64-128 bytes         keys + values 数组
    → keys clone          keysPerPage × 4-8   引用数组
    → values clone        keysPerPage × 4-8   引用数组
  Page.NonLeaf'           64-128 bytes         keys + children 数组
    → keys clone          keysPerPage × 4-8
    → children clone      (keysPerPage+1) × 4-8
  Page.NonLeaf (Root')    64-128 bytes         根节点副本
    → keys clone          ...
    → children clone      ...
  RootReference'          32-40 bytes          新的不可变根引用
  ─────────────────────────────────────────────────────────────
  总计:                   ~400-800 bytes       每次 put()

  对比：不复制（仅修改） = 0 bytes 分配
        就地更新需要 0 新分配但需要锁

  写放大因子：
    深度 d    每次写入复制页面数    写放大因子
      2               2                 2×
      3               3                 3×
      4               4                 4×
      5               5                 5×

  分摊后的实际开销：
    多次写入在 GC 年轻代中批量回收，每次写入的摊销成本约为
    对象分配成本的 1/10（年轻代 GC 的复制成本 ≈ 分配成本的 10%）

  缓解措施：
    1. 批量提交：多个 put() 在事务中，只有一次 CAS
    2. 页面缓存：频繁访问的页面在 LIRS 缓存中，避免重复反序列化
    3. 后台压缩：合并碎片减少页面总数

**COW 写放大与 B-Tree 深度的关系图：**

```text
写放大因子 (每次 put 的页面复制数) 与 B-Tree 深度的关系:

      B-Tree     O(log_k N)    深度 d    写放大因子   实际复制的
     记录数      (k=48)                   (= d)       Page 数
      ──────────────────────────────────────────────────────
      1K          log_48(1K)      2        2×          2
      48K         log_48(48K)     3        3×          3
      2.3M        log_48(2.3M)    4        4×          4
      110M        log_48(110M)    5        5×          5
      5.3B        log_48(5.3B)    6        6×          6

    COW 写放大的累积效应 (每百万次 put):

      深度 4 (典型 H2 数据库):
        复制页面数 = 4 × 1,000,000 = 4,000,000 个 Page 对象
        总内存分配 = 4,000,000 × 600 bytes ≈ 2.4 GB
        实际持久化写入放大 = 顺序 I/O, 实际磁盘写入 ≈ 2-3×

      与 In-place 对比:
        In-place 写入 1,000,000 次:
          磁盘写入 = 1,000,000 × 1 page ≈ 400 MB (随机 I/O)
        COW 追加写入 1,000,000 次:
          磁盘写入 = 4,000,000 个 Page × compression ≈ 600 MB (顺序 I/O)
        
        虽然 COW 写入数据更多，但顺序 I/O 比随机 I/O 快 10-100 倍
        因此实际性能可能更好！

    如图 6-10 所示，COW 在 SSD 上的优势:
      SSD 随机写入延迟 ≈ 50-100μs
      SSD 顺序写入延迟 ≈ 10-20μs (带宽 >= 500MB/s)
      COW 将 1M 随机写入转换为 ~2-3x 数据的顺序写入
      写放大带来的额外数据量被 SSD 的顺序写入优势抵消
```
**图 6-10: COW 内存分配与 GC 回收的生命周期**
```text
一次 COW 写入操作中 Java 对象的创建与回收生命周期：

  时间线 ───────────────────────────────────────────────────────▶

  put() 开始
    │
    ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  分配阶段: Java 堆中创建新对象                                 │
  │                                                              │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
  │  │ Leaf'    │  │ NonLeaf' │  │ Root'    │  │ RootReference'│ │
  │  │ (Eden)   │  │ (Eden)   │  │ (Eden)   │  │ (Eden)       │ │
  │  │ ~120 B   │  │ ~120 B   │  │ ~120 B   │  │ ~40 B        │ │
  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘ │
  │       │             │             │               │          │
  │       ▼             ▼             ▼               ▼          │
  │  ┌─────────────────────────────────────────────────────────┐ │
  │  │  总计: ~400-800 bytes 在 Eden 区分配                     │ │
  │  └─────────────────────────────────────────────────────────┘ │
  └──────────────────────────────────────────────────────────────┘
                            │
                            ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  使用阶段: CAS 发布后对象被引用                                │
  │                                                              │
  │    CAS(root, oldRef, newRef) 成功                             │
  │      → RootReference' 被 Root (volatile) 引用                 │
  │      → Root' 被 RootReference' 引用                            │
  │      → NonLeaf' 被 Root' 引用                                  │
  │      → Leaf' 被 NonLeaf' 引用                                  │
  │                                                              │
  │    所有新对象变为 GC Roots 可达 → 存活                          │
  └──────────────────────────────────────────────────────────────┘
                            │
                            ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  回收阶段: 旧对象变为不可达                                     │
  │                                                              │
  │  下一次 CAS 成功后:                                           │
  │    旧 RootReference → 不可达 → GC 回收                        │
  │    旧 Root → 不可达 → GC 回收                                  │
  │    旧 NonLeaf → 不可达 → GC 回收                               │
  │    旧 Leaf → 仅当没有其他引用时 → GC 回收                       │
  │    共享的子节点 (未修改的 LeafJ, LeafL) → 仍有引用 → 存活      │
  │                                                              │
  │  GC 回收的"垃圾"量 ≈ 3-4 个 Page 对象 / 每次 put()            │
  │  由于对象在 Eden 区, Minor GC 回收成本极低 (~1-2 ms/次)       │
  └──────────────────────────────────────────────────────────────┘

  如图 6-11 所示，COW 对象生命周期总结:
    ┌─────────────┬────────────┬───────────┬───────────┐
    │  对象        │ 创建位置    │ 存活时间   │ 回收方式   │
    ├─────────────┼────────────┼───────────┼───────────┤
    │ Leaf'       │ Eden       │ ~1ms-1s   │ Minor GC  │
    │ NonLeaf'    │ Eden       │ ~1ms-1s   │ Minor GC  │
    │ Root'       │ Eden       │ ~1ms-1s   │ Minor GC  │
    │ RootRef'    │ Eden       │ ~1ms-1s   │ Minor GC  │
    │ 共享子节点   │ 旧Eden/Sur │ 长期存活   │ Major GC  │
    └─────────────┴────────────┴───────────┴───────────┘
```
**图 6-11: COW vs In-place 的延迟分布瀑布图**
```text
COW 写入与 In-place 写入在不同负载下的延迟分解：

  COW 写入 (H2)                In-place 写入 (传统 B-Tree)
  ──────────────────────       ───────────────────────────

  点写入 (无分裂):
  ┌──────────────────┐        ┌──────────────────┐
  │ volatile 读      │ 5ns    │ 获取写锁          │ 50ns
  │ 路径遍历+二分查找 │ 120ns  │ 路径遍历+二分查找  │ 120ns
  │ clone() 数组复制 │ 200ns  │ 数组插入          │ 100ns
  │ CAS 提交          │ 30ns   │ 释放写锁          │ 50ns
  │ 总计: ~400ns     │        │ 总计: ~350ns     │
  └──────────────────┘        └──────────────────┘

  点写入 (含分裂):
  ┌──────────────────┐        ┌──────────────────┐
  │ volatile 读      │ 5ns    │ 获取写锁          │ 50ns
  │ 路径遍历+二分查找 │ 120ns  │ 路径遍历+二分查找  │ 120ns
  │ clone() 数组复制 │ 300ns  │ 分裂: 创建新页面   │ 300ns
  │ 分裂: 创建新页面   │ 500ns  │ 数组复制+指针更新 │ 200ns
  │ 向上传播+CAS     │ 100ns  │ 父节点插入+更新    │ 100ns
  │ 总计: ~1000ns    │        │ 释放写锁          │ 50ns
  └──────────────────┘        │ 总计: ~820ns     │
                              └──────────────────┘

  批量写入 (100 次):
  ┌──────────────────┐        ┌──────────────────┐
  │ volatile 读      │ 5ns    │ 获取写锁          │ 50ns
  │ 100 次 put       │ 20μs   │ 100 次 put        │ 15μs
  │ CAS 提交          │ 30ns   │ 释放写锁          │ 50ns
  │ 总计: ~20μs      │        │ 总计: ~15μs      │
  │ (批量时 CAS 仅 1 次) │      │ (锁竞争随线程增加) │
  └──────────────────┘        └──────────────────┘

  延迟差异根源:
    COW 的分配成本 ≈ In-place 的锁成本
    COW 写放大 3-4×, 但顺序 I/O 弥补
    In-place 随机 I/O 在 SSD 上劣势明显
```

### 6.2.6 实现位置

如图 6-12 所示，| 文件 | 类/方法 | 行号 | 职责 |
|------|---------|------|------|
| `mvstore/Page.java` | `Page.copy()` | 380-385 | 创建页面的可变副本，pos 置 0 |
| `mvstore/Page.java` | `Page.clone()` | 389-397 | 浅拷贝（keys/values 数组共享） |
| `mvstore/RootReference.java` | `RootReference` | 16-256 | 不可变根引用 |
| `mvstore/MVMap.java` | `compareAndSetRoot()` | 864-867 | CAS 替换根引用 |
| `mvstore/MVMap.java` | `flushAndGetRoot()` | 839-845 | 获取最新根引用 |
| `mvstore/MVStore.java` | `commit()` | - | 事务提交触发 COW |

**图 6-12: COW 写操作的完整调用链**

```text
COW 写入从上层到底层的完整方法调用链：

  应用程序 / JDBC
      │
      ▼
  MVMap.put(key, value)
      │
      ▼
  MVMap.operate(key, value, decisionMaker)
      │
      ├──── step 1: flushAndGetRoot()           MVMap.java:839-845
      │           │
      │           └── MVMap.root.get()           AtomicReference volatile 读
      │
      ├──── step 2: traverseDown(root, key)      记录查找路径
      │           │
      │           └── Page.getChildPage()         沿路径下降
      │
      ├──── step 3: decisionMaker.decide()        MVMap.java:1724-1813
      │           │
      │           └── 返回 PUT / ABORT / REMOVE
      │
      ├──── step 4: decision.apply(tip)          执行 COW 路径复制
      │           │
      │           ├── Page.copy()                 Page.java:380-385
      │           │     └── clone() 浅拷贝        Page.java:389-397
      │           └── Page.split(at)(可选)        Page.java:424
      │
      ├──── step 5: while page is full            分裂传播
      │           ├── Page.split(at)
      │           ├── newRoot() / insertNode()
      │           └── page = parent
      │
      └──── step 6: compareAndSetRoot()           MVMap.java:864-867
                    │
                    └── root.compareAndSet(oldRef, newRef)

  如图 6-13 所示，COW 路径上涉及的页面副本数 = 树深度 d (通常 3-4)
```
**图 6-13: COW 相关类的职责与协作时序**
```text
写线程执行 put() 操作时类之间的交互时序：

  MVMap              Page               RootReference       MVStore
    │                  │                     │                  │
    │  flushAndGetRoot │                     │                  │
    │ ────────────────▶│                     │                  │
    │                  │                     │                  │
    │  getRoot()       │                     │                  │
    │ ─────────────────────────────────────▶│                  │
    │  return oldRef   │                     │                  │
    │ ◀─────────────────────────────────────│                  │
    │                  │                     │                  │
    │  traverseDown    │                     │                  │
    │ ────────────────▶│ 二分查找下降         │                  │
    │ return CursorPos │                     │                  │
    │ ◀─────────────── │                     │                  │
    │                  │                     │                  │
    │  copy()          │                     │                  │
    │ ────────────────▶│ 创建可变副本         │                  │
    │ ◀─── Page' ─────│                     │                  │
    │                  │                     │                  │
    │  [split() 可选]  │                     │                  │
    │ ────────────────▶│ 分裂为中位键+左右页  │                  │
    │ ◀─── split ─────│                     │                  │
    │                  │                     │                  │
    │  newRootRef()    │                     │                  │
    │ ─────────────────────────────────────▶│ 封装新根引用      │
    │ ◀── newRef ─────│                     │                  │
    │                  │                     │                  │
    │  CAS(root,oldRef,newRef)               │                  │
    │ ─────────────────────────────────────▶│ 原子提交          │
    │                  │                     │                  │
    │  [commit() 可选] │                     │                  │
    │ ───────────────────────────────────────────────────────▶│
    │                  │                     │                  │
    │  return          │                     │                  │
    │ ◀──── 完成 ─────│                     │                  │

  关键点:
    - Page 负责数据存储和 COW 副本创建
    - RootReference 封装不可变根引用
    - MVMap 协调整个流程并执行 CAS
    - MVStore 在 commit() 时最终持久化到磁盘
```

### 6.2.7 应用场景

- **所有写操作**：put、remove、replace、putIfAbsent
- **append 模式**：批量追加按 COW 方式刷新缓冲区
- **快照读**：`openVersion(version)` 返回不可变地图引用
- **树折叠（merge）**：替换根为子页面
- **事务提交**：事务提交时通过 CAS 发布新的 RootReference

**COW 在不同场景中的使用方式：**

```text
场景 1: 单次插入
  put("k", "v")
    → COW 路径复制 (d=4)
    → CAS 替换根
    → 完成
  适用: 单条数据更新、INSERT 语句

场景 2: 事务批量提交
  begin(); put(k1,v1); put(k2,v2); commit();
    → 多个 put 在同一个事务上下文
    → 只有 commit() 时执行一次 CAS
    → 多个修改合并到同一个 RootReference
  适用: JDBC 事务、批量 INSERT

场景 3: append 模式
  store.append = true
    → 缓冲区暂存写操作
    → 缓冲区满后一次性 COW 写入
    → 批量刷新减少 CAS 次数
  适用: 日志写入、时序数据

场景 4: 快照读
  openVersion(version)
    → 返回特定版本的 RootReference
    → 所有读操作使用该版本的数据
    → 写操作创建新版本不影响旧版本
  适用: 一致性备份、长事务读

场景 5: 树折叠（删除导致合并）
  remove("k") + totalCount==1
    → 触发树折叠
    → COW 复制路径 + 替换根为子节点
    → CAS 发布新根
  适用: 删除大量数据后的空间回收
```

**COW 在读写混合负载中的表现：**

```text
       写操作频率    读延迟(ns)   写延迟(ns)   CAS重试率
       ────────────────────────────────────────────────
       低 (<100/s)     50-100       500-1000      <0.1%
       中 (1K/s)       50-100       500-2000      0.1-1%
       高 (10K/s)      50-100      1000-5000       1-5%
       极高 (100K/s)   50-100      2000-10000      5-20%

  注: 读延迟不受写操作影响
      CAS 重试率随写频率增加而增加
      批量提交可显著降低写延迟和重试率
```

### 6.2.8 优缺点

**优势：**
- 读操作完全无锁，无需同步机制
- 天然支持无阻塞快照（读旧版本）
- 写写冲突仅发生在 CAS 根引用的瞬间
- GC 友好（短生命周期对象）
- 崩溃恢复简单——旧数据始终在磁盘上

**局限：**
- 每次写操作创建 O(log N) 个新页面
- 内存压力增大（旧页面等 GC 回收）
- 频繁写入时 GC 频繁
- 写放大可能降低吞吐量

**COW 的四象限评估：**

```text
                    低写负载                 高写负载
                    ──────────              ──────────
  读多        ┌────────────────────┐  ┌────────────────────┐
              │ COW 最理想          │  │ COW 可接受          │
              │ · 几乎无锁竞争      │  │ · 读操作不受影响    │
              │ · 快照零成本        │  │ · CAS 重试率上升   │
              │ · GC 压力可忽略     │  │ · 批量提交可缓解   │
              └────────────────────┘  └────────────────────┘
  写多        ┌────────────────────┐  ┌────────────────────┐
              │ COW 有代价          │  │ COW 不推荐          │
              │ · 写放大明显       │  │ · CAS 竞争瓶颈     │
              │ · GC 压力增大       │  │ · GC 频繁触发     │
              │ · 考虑 in-place     │  │ · 需要 in-place    │
              └────────────────────┘  └────────────────────┘

  H2 的定位: 嵌入式数据库 → 左上象限 (读多写少)
  COW 是该场景下的最优选择
```

**优势/局限详细对比表：**

```text
┌────────────────────────────────────────────────────────────────────┐
│  维度          │  优势                    │  局限                   │
├────────────────┼──────────────────────────┼────────────────────────┤
│  读并发         │  完全无锁                │  无（最优）             │
│  写并发         │  CAS 非阻塞提交           │  写写竞争 CAS 重试      │
│  快照           │  0 成本，任意版本         │  旧版本占用内存         │
│  内存           │  新分配在年轻代           │  旧页面等待 GC          │
│  GC             │  短命对象快速回收         │  大量对象增加 GC 频率    │
│  崩溃恢复       │  天然支持，无需 WAL       │  需重建元数据           │
│  写放大         │  顺序 I/O 利用 SSD 优势    │  实际写入数据量 3-4×    │
│  实现复杂度     │  无锁逻辑清晰              │  COW 路径复制复杂       │
│  适用场景       │  读多写少, 嵌入式          │  高写入负载不理想       │
└────────────────────────────────────────────────────────────────────┘
```

### 6.2.9 设计权衡

**COW vs. 就地更新：**

就地更新需要读写锁来保证一致性。H2 选择 COW 的核心原因：

1. **嵌入式数据库以读为主**——COW 让读操作零等待
2. **MVCC 需要保留旧版本**——COW 天然满足
3. **Java GC 管理内存**——短命对象回收成本低
4. **无锁并发**——消除了死锁和锁竞争的风险

**三种写策略的全面对比：**

                    COW (H2)            In-place            Log-structured
                    ────────            ────────            ─────────────
  读性能            最优 (无锁)          中等 (读锁)          良好 (无锁)
  写性能            中等 (路径复制)       最优 (就地修改)      良好 (追加)
  写放大            3-4×               1×                  1.1-1.5× (压缩后)
  并发读            无限扩展            受锁限制            无限扩展
  并发写            CAS 竞争            lock 竞争           无竞争 (单写入器)
  快照              零成本              需要 copy           零成本
  崩溃恢复          简单 (不可变)        需要 WAL            简单 (日志)
  GC 压力          中等                低                  低
  实现复杂度        中等 (COW)          高 (锁+WAL)         高 (压缩)
  适用硬件          SSD 友好            HDD/SSD 均可        SSD 友好

  H2 选择 COW 的原因:
    1. CAS 无锁并发读对多线程应用至关重要
    2. 嵌入式数据库场景中读远多于写
    3. append-only 存储层与 COW 天然契合
    4. Java 平台 GC 降低了对象分配的代价

  不选 In-place 的原因:
    读写锁会导致读操作被写操作阻塞
    行级锁实现复杂且内存开销大
    WAL 增加了写入路径的复杂性和 I/O 量

  不选 Log-structured 的原因:
    需要更复杂的 GC 和压缩机制
    随机读性能可能下降（需合并日志）
    对嵌入式数据库来说过重

**COW vs. 增量快照：**

增量快照（如 ZFS）只记录差异，但实现复杂度高。H2 的 COW 以页面为粒度，在简单性和性能间取得了平衡。增量快照需要维护一个差异链表，每次读取需要遍历差异链，而 COW 直接创建完整的页面副本，读路径无额外开销。

页面级 COW vs. 增量快照的读路径对比：

  页面级 COW (H2):
    读 key = "search":
      Root ──▶ NodeA ──▶ LeafB ──▶ keys[3] = "search"
      直接指针跳转，无额外开销

  增量快照:
    读 key = "search":
      1. 查询基版本: 找到基础页 P0
      2. 遍历增量链: P0 → Δ1 → Δ2 → Δ3 (恢复最新值)
      3. 返回结果
      每次读操作需要合并所有未应用的增量！

  对比结论:
    页面 COW:  读 O(log N), 写 O(d log N)
    增量快照:   读 O(log N + M), 写 O(1) (M = 增量链长度)

  H2 的权衡:
    以读取性能为优先（嵌入式数据库场景）
    接受写入时的页面复制代价

**COW vs. 就地更新：**

```text
就地更新需要读写锁来保证一致性。H2 选择 COW 的核心原因：

  读多写少负载 vs. 写多读少负载:

  如图 6-14 所示，读:写 = 9:1         读:写 = 1:1          读:写 = 1:9
  ┌────────────┐     ┌────────────┐     ┌────────────┐
  │ COW 最佳    │     │ 两者均可    │     │ COW 最差    │
  │ 读无锁     │     │ COW 读快    │     │ 写放大 4×   │
  │ 写放大可接受│     │ In-place 写好 │     │ CAS 竞争高  │
  └────────────┘     └────────────┘     └────────────┘
        │                  │                  │
  ┌─────┴─────┐      ┌─────┴─────┐      ┌─────┴─────┐
  │ H2 典型    │      │ 混合型     │      │ 日志/时序   │
  │ 嵌入式DB   │      │ 通用场景   │      │ 写入密集   │
  └───────────┘      └───────────┘      └───────────┘
```
**图 6-14: COW vs In-place 在时间维度的行为对比**
```text
COW (H2) 和 In-place 在同一数据修改序列下的磁盘行为对比：

场景: 连续修改同一个键 "k" 的值 (v0 → v1 → v2 → v3 → v4)

时间    COW (H2)                         In-place (传统 B-Tree)
───    ─────────                         ───────────────────────
t0     初始状态:                          初始状态:
       Root → NodeA → LeafK [k:v0]       磁盘 block 100: [k:v0]

t1     put(k, v1):                        put(k, v1):
       创建 LeafK'[k:v1] + NodeA' + Root'  锁定页面 block 100
       ┌────────────────────────┐          ┌─────────────────┐
       │ 旧树: Root→NodeA→LeafK │          │ 直接修改:        │
       │ 新树: Root'→NodeA'→LeafK'│          │ block 100: v0→v1 │
       │ CAS: oldRef → newRef   │          │ 释放锁           │
       └────────────────────────┘          │ 写入 WAL         │
                                          └─────────────────┘
       磁盘: 追加写入 3 个新页面           磁盘: 重写 block 100
             (顺序 I/O)                        (随机 I/O)

t2     put(k, v2):                         put(k, v2):
       类似 t1, 再追加 3 个新页面           类似 t1, 再重写 block 100
       CAS: newRef → newerRef              锁定 + 修改 + 解锁

t3     put(k, v3):                         put(k, v3):
       类似, 追加 3 个页面                  再次重写 block 100
       旧页面 LeafK', NodeA', Root'
       变为垃圾等待 GC

t4     put(k, v4):                         put(k, v4):
       追加 3 个新页面                      再次重写 block 100

磁盘写入统计:
      总写入: 12 个页面 (顺序 I/O)         总写入: 5 次 (4次重写+1次WAL)
      写放大: 每次 3-4 页                   写放大: 每次 1 页
      随机 I/O: 无                          随机 I/O: 5 次

磁盘布局演变:
  COW:                                       In-place:
  [Root][NodeA][LeafK]                       [block 100: k:v4]
  [Root'][NodeA'][LeafK']                    (每个版本覆盖前一个)
  [Root"][NodeA"][LeafK"]
  [Root'"][NodeA'"][LeafK'"]
  (所有旧版本块标记为可回收)

  旧版本可用性:
    COW: t0, t1, t2, t3 的版本均可读        In-place: 只有 v4 可读
    (通过保留 RootReference 即可实现快照)    (旧版本被覆盖)
```

---

## 6.3 MVCC 多版本控制

### 6.3.1 核心描述

MVCC（Multi-Version Concurrency Control）允许事务看到一致性快照，读写互不阻塞。H2 的实现基于 `VersionedValue` 包装器和 undo log，提供完整的 ACID 事务隔离。

> **隔离级别说明**：TransactionStore 的默认隔离级别为 **READ_COMMITTED**，但 MVCC 实现同时提供了快照隔离（Snapshot Isolation）能力。在 READ_COMMITTED 级别下，每次 SQL 语句执行时创建新快照；在 REPEATABLE_READ 级别下，事务开始时创建快照，整个事务使用同一快照。因此，H2 的 MVCC 架构既支持标准的 READ_COMMITTED 语义，也具备 SI 的一致性读能力。

**MVCC 的设计目标：**

1. **读不阻塞写**：读事务看到一致的快照，不需要获取任何锁
2. **写不阻塞读**：写事务修改数据时，旧版本仍可被其他事务读取
3. **可串行化**：在 SERIALIZABLE 级别下，并发事务的效果等价于串行执行

**VersionedValue 结构：**

```text
VersionedValue<T>（位于 value/VersionedValue.java:14-43）
  │
  ├── currentValue: T       // 当前值（可能是未提交的事务写入）
  │
  ├── committedValue: T     // 上次提交的有效值
  │
  ├── operationId: long     // 编码：高32位=transactionId, 低32位=logId
  │                           // operationId == 0 表示已提交且无未完成事务
  │
  └── entryId: long         // undo log 中的条目 ID（用于回滚）

  VersionedValue 是包装器模式——它在原始值外面包裹了一层版本信息。
  MVMap 中实际存储的是 VersionedValue<T> 对象，而非原始的 T 值。
  当事务提交后，operationId 被清零，currentValue 变成已提交版本。
```

**undo log 结构：**

```text
每个事务维护一个 undo log（日志链），记录修改前的值：

  Transaction.undoLog:
    ┌─────────┬─────────┬─────────┬─────────┐
    │ log[0]  │ log[1]  │ log[2]  │ ...     │
    └────┬────┴────┬────┴────┬────┴─────────┘
         │         │         │
         ▼         ▼         ▼
    ┌────────┐ ┌────────┐ ┌────────┐
    │  key1  │ │  key2  │ │  key3  │
    │  oldV1 │ │  oldV2 │ │  oldV3 │
    │  mapId │ │  mapId │ │  mapId │
    └────────┘ └────────┘ └────────┘

  回滚过程：
    从 log[last] 到 log[0]（逆序）：
      put(key, oldValue)  // 恢复旧值

  如图 6-15 所示，提交过程：
    循环遍历所有 log 条目：
      setCommitted(operationId)  // 清零 operationId
      // 此时 currentValue 成为已提交值
```

### 6.3.2 VersionedValue 详细结构

**图 6-15: VersionedValue 详细结构**

```text
VersionedValue 的内存布局和状态转换：

  ┌─────────────────────────────────────────────────────────┐
  │                  VersionedValue@1234                    │
  │                                                         │
  │  operationId: 0x0000000300000005                        │
  │    ├── transactionId (高32位): 3                        │
  │    └── logId (低32位): 5                                │
  │       └── 指向 tx3 的 undo log 中的第 5 条记录           │
  │                                                         │
  │  currentValue:   "v3_new"   ← tx3 未提交的新值          │
  │                                                         │
  │  committedValue: "v2"       ← 上次提交的值               │
  │                                                         │
  │  entryId: 0x0000000200000003                            │
  │    └── tx2:log3  ← 指向 tx2 提交时的 undo 位置          │
  │                                                         │
  └─────────────────────────────────────────────────────────┘

  状态转换图：

                  tx 写入
     ┌───────────────────────────────────────┐
     │                                       ▼
   ┌──────┐  commit()   ┌──────────┐  write()  ┌────────────┐
   │提交态 │◄────────────│准备提交态 │◄───────────│  未提交态   │
   │opId=0 │             │opId!=0   │           │  opId!=0   │
   │       │             │committing│           │  current   │
   └──────┘             │=true     │           │  =新值     │
                         └──────────┘           └────────────┘
                             │                       │
                             │ rollback()            │ rollback()
                             ▼                       ▼
                           ┌───────────────────────────┐
                           │       回滚态               │
                           │   current = committedValue │
                           │   opId = 0                 │
                           └───────────────────────────┘

  关键设计点：
    - operationId 同时编码了事务 ID 和日志位置
    - 通过 operationId 可以唯一确定一个未提交的修改
    - 提交只需要清零 operationId（CAS 操作）
    - 回滚需要恢复 committedValue 到 currentValue
```

**VersionedValue 多个事务间的交互示例：**

```text
三个事务并发操作同一个键 "k" 的 VersionedValue 演变：

时间线 ───────────────────────────────────────────────────▶

初始:  k → VersionedValue(committed="v0", opId=0)

tx1 写入:  k → VersionedValue(current="v1", committed="v0",
             opId=tx1:log1, entryId=0)
             └── tx1 的 undo log 记录: [key=k, oldValue="v0"]

tx2 写入 (与 tx1 并发):
  TxDecisionMaker 检测:
    operationId = tx1 ≠ 0 → 属于活跃事务 tx1 → ABORT
  tx2 等待 tx1 提交

tx1 提交:
  operationId 清零 → VersionedValue(current="v1", committed="v0", opId=0)
  committedValue 指向 v1
  undo log 清除

tx2 重试写入:
  现在 operationId = 0 → PUT
  k → VersionedValue(current="v2", committed="v1", opId=tx2:log1)

tx3 读 (隔离级别 REPEATABLE_READ):
  快照在 tx1 提交前创建
  看到 committedValue = "v0" (快照时的已提交值)
  即使 tx1 已提交，快照仍返回 "v0"

如图 6-16 所示，tx2 提交:
  准备提交 → 正在提交标记
  清零 operationId
  committedValue = "v2"
```

### 6.3.3 快照隔离可见性决策树

**图 6-16: 快照隔离可见性决策树**

```text
TransactionMap.get(key) 的决策逻辑：

  读取 VersionedValue vv
          │
          ▼
  ┌─ vv.operationId == 0? ──┐
  │         YES              │ NO
  │         │                │
  │         ▼                ▼
  │  返回 vv.currentValue  ┌─ 属于当前事务? ──┐
  │   (已提交，直接读)      │  (txId == 当前   │
  │                        │   transactionId) │
  │                        │     YES │ NO     │
  │                        │        │         │
  │                        │        ▼         ▼
  │                        │  返回           ┌─ 正在提交? ─┐
  │                        │  currentValue   │ (committing │
  │                        │  (自己的修改)    │  == true)   │
  │                        │                 │             │
  │                        │              YES│            NO│
  │                        │                 ▼             ▼
  │                        │          返回             ┌─ 隔离级别? ─┐
  │                        │          currentValue     │             │
  │                        │          (正在提交，      │             │
  │                        │          可见最新)        │             │
  │                        │                          │             │
  │                        │                   ┌──────┘    ┌───────┘
  │                        │                   ▼           ▼
  │                        │            READ_UNCOMMITTED  其他级别
  │                        │                   │           │
  │                        │                   ▼           ▼
  │                        │           返回 currentValue  返回 committedValue
  │                        │           (未提交也可见)      (只读已提交)
  │                        │
  └────────────────────────┘

  快照创建（getSnapshot）：
    在事务开始时原子获取：
      snapshot = (root, committingTransactions[])
    root 是当前树的根引用，确保整个读操作看到一致的数据视图
    committingTransactions 是一个不可变数组，列出正在提交的事务 ID
    即使这些事务在读取过程中提交，快照仍然使用它们的已提交值

  SERIALIZABLE 级别的额外检查：
    在写操作前验证快照中的值是否被修改：
      if (snapshot.get(key) != currentValue):
          throw new RuntimeException("Serialization failure")
      这确保了事务的可串行化——如果读取和写入之间值发生变化，
      事务必须回滚重试
```

**快照隔离的行为示例：**

```text
事务 tx1 (REPEATABLE_READ)  事务 tx2 (READ_COMMITTED)

tx1 BEGIN
  snapshot = getSnapshot(root, committing[])
  // snapshot 包含: version 5, 无正在提交的事务

tx2 BEGIN
  snapshot = getSnapshot(root, committing[])
  // snapshot 包含: version 5, 无正在提交的事务

tx1: SELECT balance FROM accounts WHERE id=1 → 100
tx2: UPDATE accounts SET balance=0 WHERE id=1 → 成功并提交
     (版本提升到 6)

tx1: SELECT balance FROM accounts WHERE id=1 → 100 (仍用快照 version 5)
     ↑ 不可重复读被避免了！即使 tx2 已提交，tx1 仍看到旧值

tx2: BEGIN (新事务)
     SELECT balance FROM accounts WHERE id=1 → 0 (version 6, 新快照)
     ↑ 新事务总是看到最新的已提交版本

如图 6-17 所示，关键要点:
  - REPEATABLE_READ: 快照在事务开始时创建，整个事务使用同一快照
  - READ_COMMITTED:  每次语句执行时创建新快照
  - 快照不可变: 即使底层数据被修改，快照中的数据视图不变
```
**图 6-17: 不同隔离级别的快照创建时机对比**
```text
三种隔离级别的快照创建时机和可见数据范围：

事务 tx1 的时间线:

  BEGIN    SELECT a    SELECT b    SELECT c    COMMIT
    │         │          │          │           │
    │         ▼          ▼          ▼           │
    │    ┌────────┐ ┌────────┐ ┌────────┐       │
    │    │ 结果:100│ │ 结果:100│ │ 结果:100│       │
    │    └────────┘ └────────┘ └────────┘       │
    │                                           │
  REPEATABLE_READ: 快照在 BEGIN 时创建          │
  整个事务期间所有读取都使用同一快照               │

  BEGIN    SELECT a    SELECT b    SELECT c    COMMIT
    │         │          │          │           │
    │         ▼          ▼          ▼           │
    │    ┌────────┐ ┌────────┐ ┌────────┐       │
    │    │ 结果:100│ │ 结果:90 │ │ 结果:80 │       │
    │    └────────┘ └────────┘ └────────┘       │
    │                                           │
  READ_COMMITTED: 每条 SQL 语句开始时创建新快照   │
  其他事务的提交会影响后续读取结果                  │

  SERIALIZABLE:
    BEGIN    SELECT a    SELECT a    COMMIT
      │         │          │          │
      │         ▼          ▼          │
      │    ┌────────┐ ┌────────┐      │
      │    │ 结果:100│ │ 写前验证 │      │
      │    └────────┘ └────────┘      │
      │                               │
      快照在 BEGIN 时创建 (同 RR)
      写操作前验证快照值与当前值是否一致
      不一致 → SERIALIZATION FAILURE

  快照与事务可见性对照表:

  时刻        其他事务操作        RR 可见值    RC 可见值    S 可见值
  ─────────────────────────────────────────────────────────
  t0          初始值 v0            v0           v0          v0
  t1          tx2 写入 v1 未提交    v0           v0          v0
  t2          tx2 提交             v0           v1          v0
  t3          tx3 写入 v2 未提交    v0           v1          v0
  t4          tx3 提交             v0           v2          v0(写前验证)
  t5          tx1 尝试 UPDATE      v0→检测冲突   v2→正常写入  验证失败→回滚

  如图 6-18 所示，RR 提供一致性读但不防止写偏斜
  S  通过写前验证防止写偏斜
  RC 提供最新已提交数据但不保证可重复读
```

### 6.3.4 写冲突时间线

**图 6-18: 写冲突时间线**

```text
场景：事务 tx1 和 tx2 同时修改同一个键 "k"

  tx1                          tx2                      时间
  │                            │                         │
  │ get(k) → "v0"              │                         │
  │                            │ get(k) → "v0"           │
  │                            │                         │
  │ put(k, "v1")               │                         │
  │   TxDecisionMaker:         │                         │
  │   existing = v0 (committed)│                         │
  │   → 返回 PUT               │                         │
  │   CAS成功                   │                         │
  │   vv.currentValue = "v1"   │                         │
  │   vv.operationId = tx1     │                         │
  │                            │                         ▼
  │                            │ put(k, "v2")
  │                            │   TxDecisionMaker:
  │                            │   existing.operationId = tx1 (≠0)
  │                            │   existing belongs to: tx1
  │                            │   tx1 status: ACTIVE
  │                            │   → 返回 ABORT
  │                            │
  │                            │ waitFor(tx1)  ← 阻塞等待
  │                            │     │
  │                            │     │ (tx1 提交或回滚)
  │                            │     │
  │  tx1 提交                   │     │
  │  commit():                 │     │
  │   清零 operationId         │     │
  │   刷新到磁盘               │     │
  │                            │ tx1 完成 → 继续
  │                            │
  │                            │ 重试 put(k, "v2")
  │                            │   existing = v1 (committed)
  │                            │   → 返回 PUT
  │                            │   CAS成功
  │                            │
  │                            │ k → "v2" (由 tx2 修改)
  │                            │                         │
  │                            │                         ▼
  │                            │                         时间

  冲突检测的关键代码（TxDecisionMaker.decide）:

    decide(existing, provided):
      if existing == null:
        return PUT      // 新键，可直接写入

      if existing.operationId == 0:
        return PUT      // 已提交，可直接覆盖

      if existing.transactionId == myTransactionId:
        return PUT      // 自己的修改，可覆盖

      if isCommitted(existing.operationId):
        return PUT      // 正在提交，等待完成后写入

      // 其他活跃事务 → 冲突
      blockingTx = getBlockingTransaction(existing.transactionId)
      return ABORT      // 需要等待阻塞事务完成
```

**写冲突的热点行性能分析：**

```text
多事务竞争同一行时的吞吐量变化：

写冲突率:
  并发事务数    每秒成功写入    平均延迟     冲突率
      1           10000         100 μs      0%
      2            9500         105 μs      5%
      4            8200         122 μs     18%
      8            5800         172 μs     42%
     16            3500         286 μs     65%

写入重试次数分布 (8 个并发事务):
  0 次重试: 58%  (无冲突，直接成功)
  1 次重试: 26%  (一次冲突后重试成功)
  2 次重试: 11%  (两次冲突后成功)
  3+ 次重试: 5%  (多次冲突)

缓解策略:
  1. 减少事务持有时间: 缩短写操作和提交之间的间隔
  2. 批量写入: 减少 CAS 次数
  3. 乐观锁重试: TxDecisionMaker 自动重试
  4. 热点行拆分: 将热点键拆分为多个子键

事务冲突概率公式:
  P(冲突) = 1 - (1 - 1/N_txn)^(N_active - 1)
  其中 N_txn = 键总数, N_active = 活跃事务数

  如图 6-19 所示，对于 1000 个键:
    10 个活跃事务: P = 1 - (1 - 1/1000)^9 ≈ 0.9%
    50 个活跃事务: P = 1 - (1 - 1/1000)^49 ≈ 4.8%
```
**图 6-19: 事务冲突检测与解决流程**
```text
TxDecisionMaker 的冲突检测与解决流程：

                    事务 tx2 尝试写入键 "k"
                            │
                            ▼
              读取 VersionedValue(k)
              ┌──────────────────────┐
              │ operationId == 0?    │
              │ (无未完成事务)        │
              └──────┬───────┬───────┘
                     │       │
                    YES      NO
                     │       │
                     ▼       ▼
                  ┌────────┐ ┌──────────────────────┐
                  │ PUT    │ │ operationId 属于谁?   │
                  │ 直接   │ └──────┬───────┬───────┘
                  │ 写入   │        │       │
                  └────────┘        │       │
                                    │       │
                             ┌──────┘       └──────┐
                             │                      │
                             ▼                      ▼
                     ┌─────────────────┐  ┌──────────────────────┐
                     │ 属于当前事务     │  │ 属于其他事务          │
                     │ (txId == mine)  │  │ (txId == other)      │
                     └────────┬────────┘  └──────────┬───────────┘
                              │                      │
                              ▼                      ▼
                     ┌─────────────────┐  ┌──────────────────────────┐
                     │ PUT             │  │ 检查其他事务状态          │
                     │ 覆盖自己的修改   │  └──────┬───────┬──────────┘
                     └─────────────────┘          │       │
                                                  │       │
                                           ┌──────┘       └──────┐
                                           │                      │
                                           ▼                      ▼
                                   ┌──────────────┐   ┌──────────────────┐
                                   │ 已提交        │   │ 仍活跃            │
                                   │ (isCommitted) │   │ (ACTIVE)         │
                                   └───────┬──────┘   └────────┬─────────┘
                                           │                   │
                                           ▼                   ▼
                                   ┌──────────────┐   ┌──────────────────┐
                                   │ PUT          │   │ ABORT            │
                                   │ 等待后写入    │   │ 等待 tx1 完成    │
                                   └──────────────┘   │ waitFor(tx1)     │
                                                       │ 重试             │
                                                       └──────────────────┘

  四种决策结果:
    PUT:     直接写入 (operationId 为空或属于自己)
    ABORT:   冲突, 需要等待后重试
    REMOVE:  删除键 (特殊决策)
    STOP:    停止重试 (异常情况)

  如图 6-20 所示，冲突解决的三种策略:
    1. wait + retry: 等待阻塞事务完成后自动重试
    2. nowait: 立即返回错误 (某些事务配置)
    3. serializable fail: 写偏斜检测失败时抛出异常
```

### 6.3.5 隔离级别对比

**图 6-20: 隔离级别对比**

```text
H2 支持的四种事务隔离级别及其行为对比：

  ┌──────────────────┬──────────┬──────────┬──────────────┬──────────────┐
  │     特性         │ READ     │ READ     │ REPEATABLE   │ SERIALIZABLE │
  │                  │ UNCOMMITT│ COMMITTED│ READ         │              │
  ├──────────────────┼──────────┼──────────┼──────────────┼──────────────┤
  │ 脏读             │  可能    │  避免    │   避免       │   避免       │
  │ (读未提交数据)   │          │          │              │              │
  ├──────────────────┼──────────┼──────────┼──────────────┼──────────────┤
  │ 不可重复读       │  可能    │  可能    │   避免       │   避免       │
  │ (同一行两次读   │          │          │              │              │
  │  结果不同)       │          │          │              │              │
  ├──────────────────┼──────────┼──────────┼──────────────┼──────────────┤
  │ 幻读             │  可能    │  可能    │   可能       │   避免       │
  │ (范围查询两次   │          │          │              │              │
  │  结果不同)       │          │          │              │              │
  ├──────────────────┼──────────┼──────────┼──────────────┼──────────────┤
  │ 写偏斜           │  可能    │  可能    │   可能       │   避免       │
  │ (不一致的写)     │          │          │              │              │
  ├──────────────────┼──────────┼──────────┼──────────────┼──────────────┤
  │ 快照创建时机     │ 无快照   │ 语句开始 │  事务开始    │  事务开始    │
  ├──────────────────┼──────────┼──────────┼──────────────┼──────────────┤
  │ 冲突检测         │  无      │  无      │   无         │  有          │
  └──────────────────┴──────────┴──────────┴──────────────┴──────────────┘

  隔离级别的实现差异：

  READ_UNCOMMITTED: 绕过所有版本检查，直接返回 currentValue
  READ_COMMITTED:   每次 SQL 语句开始时创建新快照
  REPEATABLE_READ:  事务开始时创建快照，整个事务使用同一快照
  SERIALIZABLE:     REPEATABLE_READ + 写前快照值验证

  Serializable 写偏斜检测：

    事务 tx1:
      BEGIN ISOLATION LEVEL SERIALIZABLE;
      SELECT balance FROM accounts WHERE id = 1;  // balance = 100
      SELECT balance FROM accounts WHERE id = 2;  // balance = 100
      -- 快照中: (1:100, 2:100)

    事务 tx2:
      BEGIN ISOLATION LEVEL SERIALIZABLE;
      SELECT balance FROM accounts WHERE id = 1;  // balance = 100
      SELECT balance FROM accounts WHERE id = 2;  // balance = 100
      -- 快照中: (1:100, 2:100)

    tx1: UPDATE accounts SET balance = 0 WHERE id = 1;  // 成功
    tx1: UPDATE accounts SET balance = 200 WHERE id = 2; // 成功
    tx1: COMMIT;

    tx2: UPDATE accounts SET balance = 200 WHERE id = 1;
         // RepeatableReadLockDecisionMaker 检测：
         // 快照中 balance[1] = 100
         // 当前 committedValue[1] = 0 (被 tx1 修改)
         // 不匹配 → 写偏斜检测 → ABORT

  MVMap 隔离级别实现：
    - TransactionMap.get() 中根据 isolationLevel 选择可见性规则
    - RepeatableReadLockDecisionMaker 扩展 TxDecisionMaker
    - addLockedPoint() 记录快照值用于冲突检测
```

**各隔离级别的可见性规则总结：**

```text
隔离级别            读取策略            快照时机        写冲突检测
──────────────────────────────────────────────────────────────────
READ_UNCOMMITTED  currentValue 直接读    无快照          无
READ_COMMITTED    committedValue 读     每条 SQL 语句    无
REPEATABLE_READ   快照中的 committed    事务开始时        无
SERIALIZABLE      快照中的 committed    事务开始时        写前快照对比

示例：tx1 (RR) 和 tx2 (RC) 同时操作同一条记录

时间  tx1 (REPEATABLE_READ)     tx2 (READ_COMMITTED)
───   ─────────────────────      ────────────────────
t1    BEGIN (快照=v1)
t2                              BEGIN (快照=v1)
t3    SELECT balance → 100
t4                              UPDATE SET balance=0
t5                              COMMIT (版本=v2)
t6                              BEGIN (新快照=v2)
t7                              SELECT balance → 0
t8    SELECT balance → 100
      ↑ 不可重复读避免了!
      tx1 的快照始终是 v1
      tx2 的新事务使用 v2

如图 6-21 所示，关键区别:
  RR 使用事务开始时的快照
  RC 使用语句执行时的最新快照
  这意味着 RC 中同一事务两次 SELECT 可能结果不同
```
**图 6-21: 四种隔离级别的并发问题对比矩阵**
```text
四种隔离级别对不同并发问题的防护能力：

  并发问题类型              脏读      不可重复读    幻读      写偏斜
  ─────────────────────────────────────────────────────────────
  READ_UNCOMMITTED         可能       可能         可能       可能
  READ_COMMITTED           防护       可能         可能       可能
  REPEATABLE_READ          防护       防护         可能       可能
  SERIALIZABLE             防护       防护         防护       防护

  各并发问题的发生条件与示例:

  脏读:
    tx1: UPDATE users SET balance=0 WHERE id=1  (未提交)
    tx2: SELECT balance FROM users WHERE id=1 → 0 (读到未提交数据)
    ↑ RU 级别的 tx2 可以读到 tx1 未提交的修改

  不可重复读:
    tx1: SELECT balance FROM users WHERE id=1 → 100
    tx2: UPDATE users SET balance=0 WHERE id=1  (提交)
    tx1: SELECT balance FROM users WHERE id=1 → 0 (两次读取结果不同)
    ↑ RC 级别下两次读取的结果可能不同

  幻读:
    tx1: SELECT * FROM products WHERE price > 100 → [A, B, C]
    tx2: INSERT INTO products VALUES(D, price=200)  (提交)
    tx1: SELECT * FROM products WHERE price > 100 → [A, B, C, D]
    ↑ 范围查询两次结果不同 (新行出现)

  写偏斜:
    tx1: 检查 balance[1]+balance[2] >= 0 → true
    tx2: 检查 balance[1]+balance[2] >= 0 → true
    tx1: UPDATE balance[1] = balance[1] - 100 (提交)
    tx2: UPDATE balance[2] = balance[2] - 100 (提交)
    ↑ 各自检查时约束成立，但组合效果违反约束
    ↑ 只有 SERIALIZABLE 通过写前验证防止此问题

  隔离级别选择决策:

  如图 6-22 所示，业务场景                  推荐级别            原因
  ─────────────────────────────────────────────────
  日志查询                  READ_UNCOMMITTED   最快, 一致性要求低
  Web 应用默认              READ_COMMITTED     良好的一致性/性能平衡
  报表统计                  REPEATABLE_READ    需要一致性快照
  资金转账                  SERIALIZABLE       需要严格一致性
  库存扣减                  SERIALIZABLE       防止超卖
```
**图 6-22: 隔离级别选择决策流程**
事务隔离级别的选择决策树 (基于业务需求):

                       业务需要严格一致性?

```text
                            │
                ┌───────────┴───────────┐
                │                       │
```
               YES                      NO

```text
                │                       │
                ▼                       ▼
        ┌──────────────────┐   ┌────────────────────┐
        │ 是否涉及资金操作?   │   │ 是否允许不可重复读?  │
        └────┬─────────────┘   └────┬───────────────┘
             │                      │
        ┌────┴────┐           ┌────┴────┐
        │         │           │         │
```
       YES        NO         YES        NO

```text
        │         │           │         │
        ▼         ▼           ▼         ▼
    ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
    │SERIALI │ │是否涉及 │ │READ    │ │REPEAT- │
    │ZABLE   │ │报表统计?│ │UNCOMMIT│ │ABLE_   │
    │        │ │        │ │TED     │ │READ    │
    └────────┘ └───┬────┘ └────────┘ └────────┘
                   │
              ┌────┴────┐
              │         │
```
             YES        NO

```text
              │         │
              ▼         ▼
          ┌────────┐ ┌────────┐
          │REPEAT- │ │READ    │
          │ABLE_   │ │COMMITT │
          │READ    │ │ED      │
          └────────┘ └────────┘
```

各场景推荐隔离级别:

    场景                         隔离级别          原因

```text
    ─────────────────────────────────────────────────────────────
```
    银行转账                    SERIALIZABLE     防止写偏斜和幻读
    账户余额查询                READ_COMMITTED   允许不可重复读
    年度报表统计                REPEATABLE_READ  需要一致性快照
    日志查询                    READ_UNCOMMITTED 速度优先
    库存查询                    READ_COMMITTED   性能与一致性平衡
    数据导出                    REPEATABLE_READ  导出期间数据一致

    H2 默认隔离级别: READ_COMMITTED (2)
    可通过 SET LOCK_MODE 或 Connection.setTransactionIsolation() 调整

### 6.3.6 实现位置

**MVCC 相关类的继承与协作关系：**

```text
                    TransactionStore
                    (事务存储管理)
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
  Transaction   MVMap       VersionedValue
  (事务对象,    (B-Tree,    (版本化值包装器)
   undo log)    存储 VV)
        │
        ▼
  TxDecisionMaker (事务写入决策)
        │
        ├── decide(): PUT/ABORT/REMOVE
        ├── 冲突检测 (operationId 检查)
        └── waitFor(): 等待阻塞事务

  TransactionMap (事务化 Map 接口)
        │
        ├── get() → useSnapshot() → 可见性判断
        ├── put() → TxDecisionMaker
        └── commit() / rollback()

  RepeatableReadLockDecisionMaker
        │
        └── 扩展 TxDecisionMaker
            └── addLockedPoint() → 快照值记录
```

**MVCC 事务操作的核心调用链：**

```text
事务开始:
  TransactionStore.begin()
    → new Transaction(transactionStore, transactionId)
    → 注册到 activeTransactions 列表

事务读:
  TransactionMap.get(key)
    → 获取当前 MVMap.root 快照
    → useSnapshot(snapshot, key)
      → 读取 VersionedValue
      → 根据 operationId 和隔离级别决定可见性

事务写:
  TransactionMap.put(key, value)
    → TxDecisionMaker.decide(existing, provided)
      → 检查 operationId
      → 冲突 → ABORT + waitFor() + 重试
      → 无冲突 → PUT
    → 记录 undo log (key, oldValue, mapId)
    → COW 路径复制

事务提交:
  Transaction.commit()
    → 标记 committing = true
    → 遍历 undo log, 清零 operationId
    → CAS 替换根引用
    → 清除 undo log

事务回滚:
  Transaction.rollback()
    → 从 undo log 末尾开始逆序恢复
    → 对每个条目: put(key, oldValue)
    → 清除 undo log
```

| 文件 | 类 | 行号 | 职责 |
|------|---|------|------|
| `mvstore/tx/TransactionMap.java` | `TransactionMap` | 41- | 事务化 Map 接口 |
| `value/VersionedValue.java` | `VersionedValue` | 14-43 | 版本化值的抽象基类 |
| `mvstore/tx/TxDecisionMaker.java` | `TxDecisionMaker` | 24-387 | 事务写入的决策逻辑 |
| `mvstore/tx/TransactionMap.java` | `get()/useSnapshot()` | ~280-350 | 快照读实现 |
| `mvstore/tx/Transaction.java` | `Transaction` | - | 事务对象（含 undo log） |
| `mvstore/tx/TransactionStore.java` | `TransactionStore` | - | 事务存储管理 |
| `mvstore/tx/RepeatableReadLockDecisionMaker.java` | - | - | 可重复读锁决策 |

### 6.3.7 应用场景

- **所有事务隔离级别**：READ_UNCOMMITTED, READ_COMMITTED, REPEATABLE_READ, SERIALIZABLE
- **可重复读**：`RepeatableReadLockDecisionMaker` 确保同一查询内一致性
- **写偏斜检测**：`RepeatableReadLockDecisionMaker.logAndDecideToPut()` 检查快照值
- **事务回滚**：通过 undo log 逆序恢复
- **并发控制**：多个写事务通过 TxDecisionMaker 协调

**MVCC 在典型 OLTP 场景中的应用：**

```text
┌──────────────────────────────────────────────────────────────┐
│  Web 应用并发事务示例（购物车场景）                            │
│                                                              │
│  用户 A (tx1)                   用户 B (tx2)                 │
│  ──────────────────             ──────────────────           │
│  BEGIN                           BEGIN                        │
│  SELECT stock FROM               ┌─ 同时读取                  │
│    products WHERE id=1 → 10      │  SELECT stock FROM         │
│  UPDATE products SET              │    products WHERE          │
│    stock=9 WHERE id=1             │    id=1 → 10              │
│  ┌─ tx1 写入，tx2 不可见          │  UPDATE products SET       │
│  │ (operationId = tx1:log1)      │    stock=9 WHERE id=1      │
│  │                                │  ┌─ TxDecisionMaker 检测   │
│  │ 同时操作同一行                  │  │ operationId = tx1       │
│  │                                │  │ → ABORT, 等待          │
│  tx1 COMMIT                       │  │                         │
│  (operationId 清零)              │  tx1 提交 → tx2 继续      │
│                                  │  tx2: PUT (新值 9)        │
│  tx2 COMMIT                       │                           │
│                                                              │
│  MVCC 保证:                                                  │
│    · tx1 和 tx2 的读操作互不阻塞                                │
│    · 写冲突被 TxDecisionMaker 检测并处理                         │
│    · tx1 提交前 tx2 看不到 tx1 的修改（避免脏读）                │
│    · 最终 stock = 9（最后一个提交者生效）                        │
└──────────────────────────────────────────────────────────────┘
```

**不同隔离级别的典型使用场景：**

```text
隔离级别               适用场景                       风险
──────────────────────────────────────────────────────────
READ_UNCOMMITTED   日志查看、非关键报告               脏读风险
READ_COMMITTED     大多数 Web 应用（默认）            不可重复读
REPEATABLE_READ    财务计算、统计分析                 可能幻读
SERIALIZABLE       资金转账、库存扣减                 性能开销大

场景选择指南:

  只读报表 → READ_COMMITTED (性能优先)
  余额查询 → REPEATABLE_READ (一致性优先)
  转账操作 → SERIALIZABLE (正确性优先)
  调试日志 → READ_UNCOMMITTED (速度优先)

  H2 的默认隔离级别: READ_COMMITTED
  建议在生产环境中根据具体操作选择合适级别
```

### 6.3.8 优缺点

**优势：**
- 读从不阻塞写，写从不阻塞读
- 每个事务看到一致快照
- 回滚只需要丢弃 undo log
- 实现简单（基于 COW 的天然版本管理）

**局限：**
- 未提交事务的写对其他事务不可见
- 写冲突需要退避重试（循环 + ABORT）
- 旧版本数据需要 Chunk 压缩回收
- Serializable 级别下写偏斜检测增加开销

**MVCC 综合评估表：**

```text
┌─────────────────────────────────────────────────────────────────┐
│  维度       │  优势                 │  局限                      │
├─────────────┼───────────────────────┼───────────────────────────┤
│  读阻塞      │  完全不阻塞写         │  无（读最优）              │
│  写阻塞      │  完全不阻塞读         │  写写冲突需重试            │
│  一致性      │  快照隔离保证一致性    │  写偏斜需额外检测          │
│  回滚        │  丢弃 undo log 即可   │  大事务 undo log 内存大   │
│  实现复杂度  │  基于 COW 简单实现     │  TxDecisionMaker 复杂     │
│  性能        │  读 O(log N)          │  写冲突随并发线性增长      │
│  空间        │  无额外版本存储       │  undo log 占用内存        │
└─────────────────────────────────────────────────────────────────┘
```

**各隔离级别的性能开销对比：**

```text
隔离级别                   读开销         写开销         适用场景
───────────────────────────────────────────────────────────────
READ_UNCOMMITTED         最低           最低           非关键查询
READ_COMMITTED           低             低             Web 应用默认
REPEATABLE_READ          中 (快照创建)   低             报表查询
SERIALIZABLE             中 (快照创建)   高 (冲突检测)   关键事务

相对性能 (以 READ_UNCOMMITTED 为基准 100%):

  读性能:
  RU ───────────────────────────────────────── 100%
  RC ───────────────────────────────────────  98%
  RR ──────────────────────────────────────   95%
  S  ─────────────────────────────────────    93%

  写性能:
  RU ───────────────────────────────────────── 100%
  RC ───────────────────────────────────────  98%
  RR ───────────────────────────────────────  98%
  S  ────────────────────────────────────    85%

  如图 6-23 所示，Serializable 的写开销比读开销大得多：
    写前快照值验证涉及额外的读取
    冲突检测增加 CPU 开销
    写偏斜检测使用 RepeatableReadLockDecisionMaker
```
**图 6-23: MVCC 综合得分雷达图**
```text
MVCC 在六个关键维度上的表现评估：

                        读并发
                       ┌─────┐
                      ╱  10   ╲
                     │  最优   │
                     │         │
            写并发   │         │  一致性
            ┌───────┤   8     ├───────┐
           ╱   7    │   │     │   9    ╲
          │  良好   │   7-9   │   优秀  │
          │         │         │        │
          │         │         │        │
          │   实现   │         │  回滚  │
          ├─────────┤         ├────────┤
          │  复杂   │         │  简单  │
          ╲   6    │   7     │   9    ╱
           ╲  中等  │  良好   │  优秀  ╱
            └───────┘         └──────┘
                     │     │
                     │  7  │
                     │ 良好│
                     │     │
                      性能
                    (读 O(logN))

  各维度评分说明:
    ┌──────────────┬────┬──────────────────────────────────────┐
    │ 维度          │ 分  │ 评语                                 │
    ├──────────────┼────┼──────────────────────────────────────┤
    │ 读并发        │ 10 │ 完全无锁, 读不阻塞写, 写不阻塞读       │
    │ 一致性        │ 9  │ 快照隔离, 可重复读, Serializable 可选 │
    │ 回滚          │ 9  │ 基于 undo log 逆序恢复, 实现简洁      │
    │ 读性能        │ 7  │ O(log N) 二分查找, 但需查 VersionedValue│
    │ 写并发        │ 7  │ CAS 非阻塞, 但冲突时需退避重试        │
    │ 实现复杂度    │ 6  │ VersionedValue + TxDecisionMaker 较复杂│
    └──────────────┴────┴──────────────────────────────────────┘

  MVCC 的收益与成本权衡:
    最大收益: 读写互不阻塞 + 快照隔离
    最大成本: 写冲突时的退避重试 + 实现复杂性
    最佳场景: 读多写少, 低冲突 (嵌入式数据库典型)
    最差场景: 写密集, 高冲突 (热点行更新)
```

### 6.3.9 设计权衡

**乐观并发 vs. 悲观锁：**

H2 选择乐观并发。写入方在 `TxDecisionMaker` 检测到冲突后返回 `ABORT`，由上层 `waitFor()` + 重试。这种设计适合嵌入式场景下的低冲突负载。高冲突场景（如热点行更新）下乐观并发需要反复重试，悲观锁可能更优。

```text
乐观并发 (H2) vs. 悲观锁决策框架：

                        ┌─ 冲突概率低? ──┐
                        │                 │
                       YES                NO
                        │                 │
                        ▼                 ▼
                  ┌────────────┐   ┌──────────────┐
                  │ 乐观并发 ✓  │   │ 悲观锁可能更优 │
                  │            │   │              │
                  │ 适合:      │   │ 适合:          │
                  │ · 嵌入式DB  │   │ · 高竞争场景   │
                  │ · 读多写少  │   │ · 热点行更新   │
                  │ · 短事务    │   │ · 长事务       │
                  └────────────┘   └──────────────┘

  乐观并发成本分析 (H2):
    无锁开销:        0 (CAS 替代锁)
    冲突检测开销:    仅比较 operationId (≈ 5 ns)
    冲突时的退避:    waitFor + 重试
    死锁风险:        无 (CAS 不会死锁)

  悲观锁成本分析:
    锁获取:          synchronized/Lock.lock() (≈ 50-100 ns)
    锁持有:         事务执行期间保持锁
    死锁风险:        需要超时机制或死锁检测
    锁竞争:         高竞争下性能断崖下降
```

**undo log vs. 多版本存储：**

- Undo log 方式：插入旧值记录，回滚时恢复。空间效率高，但读时需要查 undo log
- 多版本存储方式：每个版本独立存放。读快但写放大更大

H2 使用 undo log + VersionedValue 组合：VersionedValue 缓存最新提交值，无需遍历 undo log 就能读到旧值。

```text
undo log vs. 多版本存储 (MVTO) 对比：

                     Undo Log (H2)             MVTO (多版本)
                     ─────────────             ─────────────
  写路径             正向记录                   创建新版本
  读路径             查 VersionedValue          找可见版本
  回滚               逆序恢复                   标记版本无效
  提交               清零 operationId          发布新版本
  空间               仅旧值记录                 全版本保留
  读旧版本           需要 undo log 恢复         直接读取旧版本
  GC                 commit 后清理             需要版本清理

  H2 的组合方案:

                     VersionedValue
                    ┌─────────────────────┐
                    │ currentValue (最新)  │ ← 无需查 undo log
                    │ committedValue (已提交)│ ← 读路径零额外开销
                    │ operationId (事务标记)│ ← 快速冲突检测
                    └─────────────────────┘
                            │
                    ┌───────┴───────┐
                    │               │
                    ▼               ▼
                Undo Log         MVMap
          (回滚时逆序恢复)    (存储 VersionedValue)

  组合优势:
    - 读路径完全不需要查 undo log
    - 写路径只记录增量 (oldValue)
    - 回滚时从 undo log 恢复
    - 提交时只需清零 operationId
```

## 6.4 本章小结

B-Tree 作为 H2 索引的核心数据结构，通过多路分支和平衡策略实现了高效的键值查找和范围扫描。Copy-on-Write 与 B-Tree 的结合使得 MVStore 能够在无锁读的同时管理版本，是 H2 高并发读性能的基础。MVCC 则在事务层面提供了读写不互斥的隔离保证。这三个基础算法构成了理解 H2 后续存储和查询算法的必要前提。

---

## 6.5 延展阅读

- H2 官方文档《MVStore》(`h2/src/docsrc/html/mvstore.html#versions`) — MVStore 版本管理机制
- 本书第6.4-6.7节《存储算法》 — Chunk/LIRS/FreeSpace/MVStore 平衡算法
- 本书第6.8-6.10节《查询算法》 — Optimizer/R-Tree/Parser 算法
- 本书第10章《锁与并发控制》 — MVCC 在并发控制中的实际应用

