# 图示升级实施计划：ASCII → 结构化图

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1
> 定位：**图示升级的动作与判据**——分几个阶段做、每阶段的产物与通过条件、成本与回退。
> 设计理由看同目录 `design.md`，全书门禁与阈值归属看 `testplan.md` /
> `technical.md` §3.2。追踪编号只在 `plan.md` 的计划项里。

---

## 1. 前提

- 设计已定：图注仍为文本判据，图源新增 SVG 形态，两种形态并存（见设计文档 §3）。
- 判据先行：任何一张图进入手稿之前，`diagrams.py`、`verify_pdf.py`、`verify_epub.py`
  必须已经认识"图片型图源"，否则升级期间会出现"图存在但无人检查"的窗口。
- 一次只动一章：试点图集中在一章内，便于单点回退与对照。

---

## 2. 阶段与动作

依赖关系：阶段 1 是所有后续的前置（判据先行）；阶段 2 必须在 3 与 4 之前（两个出口都吃 HTML）；
阶段 3 与 4 互不依赖，可交换顺序；阶段 5 必须最后（它需要三个出口都已通过）。

### 阶段 1：判据先行（不动手稿）

**动作**
1. `diagrams.py`：识别图片型图源块，输出"图片型图 N 个（不受 ASCII 宽度约束）"，
   并继续审计 ASCII 围栏；两种形态的计数都进 JSON 报告（C-09）。
2. `links.py`：把手稿中 `assets/diagrams/*.svg` 的相对路径纳入可解析性检查，并限定扩展名白名单
   （只允许 `.svg`）。
3. 新增统计函数占位：`verify_pdf.py` / `verify_epub.py` 先只统计图片数，不失败。此占位不得长期
   停留：阶段 3、4 必须把它升级为硬判据，否则就是死代码。
4. 新增配置键 `[paths] diagrams`（值为手稿目录下的 `assets/diagrams`）与 `_config` 访问器；
   同时改 `style_schema` 的键声明，缺失时回退默认值，不阻塞尚无图片的仓库。

**产物**：`diagrams.py`、`links.py`、`style_schema.py` 与两个出口校验脚本的改动 + 配置键 + 用例；
`make.py check` 全绿。
**提交与回滚**：单一变更提交；回滚即恢复脚本与键声明（不影响任何手稿）。
**命令**：`books/scripts/bookctl check`；`python books/src/python/audit/diagrams.py --json`。
**通过条件**：混入一张图片引用后，`diagrams.py` 能报出"图片型图 1 个"，且不误判为 ASCII 图。
**回退**：整阶段是只读改造，回退即恢复脚本。

### 阶段 2：HTML 出口

**动作**
1. `to_html.py`：新增 `![alt](src)` 分支，输出 `<figure class="diagram"><img …></figure>`；
   围栏内的图片语法不得被解析（fence 优先）。
2. 构建期把 SVG 读成 `data:image/svg+xml;base64,…` 内联；资产缺失、非合法 XML、含外链或
   `<script>` 时**构建失败**并点名文件。
3. **片段缓存键改造**：`render/html_cache.py` 的键加入该章引用资产的哈希，否则 md 未变而图变了
   会复用旧内联图。
4. 补 CSS（`img` 自适应、`figure` 间距、打印 `page-break-inside:avoid`）。
5. 输出报告：内联资产数量与总字节数。

**产物**：HTML 渲染器 + 缓存键 + 用例（资产缺失 / 非法 SVG / 改图后缓存失效）。
**体量动作**：替换后该章行数会下降，同一变更里跑 `audit/content_volume.py` 并按
`quality-model.md` §4 重记基线（具名评审人，否则拒绝记账）；不得直接改阈值。
**提交**：单章单提交，图资产与手稿同行提交，便于单章 revert。
**命令**：`books/scripts/bookctl build`；两次构建对比 `sha256`。
**报告字段**：内联资产数、内联字节数进构建输出与 `--json`（C-09）。
**提交与回滚**：单一变更提交；回滚后更新一次 `build` 让缓存回到旧键。
**通过条件**：同一份手稿连续渲染两次字节一致；资产缺失时退出码非 0 且报出文件名；
`structure.py`、`figures.py`、`captions.py`、`link`/`crossrefs` 均绿。

### 阶段 3：PDF 出口

**动作**
1. 试产一份含 2 张试点图的 PDF，人工确认图清晰、未被页边界切断。
2. `verify_pdf.py` 由"先统计"升级为硬判据：**渲染出的图片对象数 == 合并稿里的图片引用数**
   （不与图注总数比较；纯 ASCII 章没有图片，那样会误报）。
3. 体积核对：页数与字节数在 `pdf_max_mb` 内。

**通过条件**：`verify_pdf.py` 绿，且用"故意删图"的产物能真的报红。
**命令**：`books/scripts/bookctl deliver`；`python books/src/python/render/verify_pdf.py --json`。
**回退**：把该章图改回 ASCII 围栏，PDF 链路回到升级前行为。

### 阶段 4：EPUB 出口

**动作**
1. `to_epub.py`：补 `--resource-path=<手稿目录>:<dist>`；pandoc 退出码非 0 即失败。
2. `verify_epub.py`：每个图片资源必须在 manifest 中、media-type 正确、href 可解析；
   **图片资源数 == 合并稿里的图片引用数**。
3. 实际打开产物核对（不只信 manifest）。

**通过条件**：`verify_epub.py` 绿；删除一张图后能报红；EPUB 体积在阈值内。
**回退**：回退 `--resource-path` 与判据即可，源图不动。

### 阶段 5：试点铺开判定

**动作**
1. 在一章内落地 2 张试点图。候选判定可执行：跑 `audit/diagrams.py --json`，取
   “宽度最接近 `ascii_max_cols` 且围栏行数最多”的两张（画得从容的图不是候选）。
2. 跑完整链路：`build` → `check` → `deliver`。
3. 记录三项成本：HTML 体积增量、PDF 页数增量、EPUB 体积增量。
4. 复核图簇判据：`figure_clusters.py` 的窗口是“相邻图之间的行距”，图片只有 1 行，
   替换后簇识别会变松；如果教程出现误报/漏报，调 `style.json [clusters]` 的 `window_lines`，
   不改判据代码。

**通过条件**：`make.py check` 全绿、`deliver` 全绿；三项增量都在阈值内；
试点的两张图在三个出口上均可读。
**回退**：逐张退回 ASCII；判据保留（它们对 ASCII 图同样无害）。

---

## 3. 成本与取舍

| 阶段 | 主要成本 | 收益 |
| --- | --- | --- |
| 1 判据先行 | 五个脚本 + 配置键 + 用例 | 升级期间不出现"无人检查"的图 |
| 2 HTML | 渲染器新增分支与内联逻辑 | 单文件产物仍可离线阅读 |
| 3 PDF | 一次试产与人工核查 | 复杂图在纸面上真正可读 |
| 4 EPUB | 一个 pandoc 参数 + 校验 | 图不再被静默丢弃 |
| 5 试点 | 两张图的绘制成本 | 验证铺开是否值得 |

不做阶段 1 直接上图的代价是：图存在但万无一失地"绿"——这比不做升级更糟。

---

## 4. 判据一览（对应 `plan.md` 的验收）

| 验收条目（`plan.md` plan-6） | 本计划的落地判据 |
| --- | --- |
| 换图后 `diagrams.py` 绿 | 阶段 1：图片型图源计数 + ASCII 围栏继续审计 |
| `figures.py` 绿 | 图注行不变；图数/引用/桥接句判据不动 |
| `verify_pdf.py` 绿 | 阶段 3：图片对象数 == 图片引用数 + 体积上限 |
| `verify_epub.py` 绿 | 阶段 4：manifest/href/media-type + 图片数 |
| 图号引用不变 | 图号只来自图注行，资产文件名与图号一一对应 |

---

## 5. 风险清单

风险与静默失败点的完整论述在 `design.md` §6/§7；本节只留阶段内要盯的三件事：

| 盯什么 | 何时 | 处置 |
| --- | --- | --- |
| 内联后的 HTML 体积与构建时间 | 阶段 2 | 报告字节数；单图超 256 KB 先拆图 |
| PDF 图清晰与页边界 | 阶段 3 | 人工看一页；`page-break-inside:avoid` |
| EPUB 里图是否真的在 | 阶段 4 | manifest 判据 + 实际打开产物 |

---

## 6. 完成定义

1. 三种图源形态（ASCII / 图片 / 无图）在门禁里都有明确归宿，没有“无人检查”的形态。
2. 三个出口各自有“图消失了会红”的判据，且每条判据都有一条能红的用例。
3. 片段缓存键含资产哈希：改图不必改 md 也能重建出新的 HTML。
4. 试点图在 HTML / PDF / EPUB 上人工确认可读，三项体积增量在阈值内。
5. `make.py check`、`make.py deliver` 全绿。
6. 任何一张图都能单独退回 ASCII，且退回后门禁不必修改。

## 7. 责任与回归命令

| 环节 | 命令 | 跑它的时点 |
| --- | --- | --- |
| 门禁（含新增判据） | `books/scripts/bookctl check` | 每个阶段末 |
| 构建幂等 | 两次 `bookctl build` + `sha256sum` | 阶段 2 |
| 交付链 | `books/scripts/bookctl deliver` | 阶段 3、4、5 |
| 单图回退 | 改回 ASCII 后重跑 `build` + `check` | 任何失控时 |

## 8. 本计划的边界（不做）

- 不新建绘图工具或模板工程；作图在仓库外完成，只交 SVG。
- 不为图片新建一套图号体系，也不允许一图多用（图号与文件名一一对应）。
- 不引入新的体积阈值键；用既有 `pdf_max_mb` / `epub_max_mb` 与人工核查。
- 不在本项同时改图注体例（`style-guide.md` §14 不动）。
- 不改 ASCII 图的既有判据（宽度、围栏配对照旧）。

## 9. 文档同步清单

| 文件 | 变更点 |
| --- | --- |
| `technical.md` §4.4 / §4.5 | 渲染链新增图片分支与内联；门禁新增图片类判据 |
| `technical.md` §3.2 | 新增 `[paths] diagrams`，并在同一变更里补 `style_schema` 的键声明 |
| `testplan.md` | 图注与图源的判据（性质层面）改成形态无关的说法；体例本身仍归 `style-guide.md` §14 |
| `style-guide.md` §14 | 补充图片型图源的图注与 alt 写法 |
| `folder.md` | 新增 `docs/plan/diagram-upgrade/` 与图目录两项 |
| `plan.md` | `plan-6` 完成后移除，摘要进 `changelog.md` |

## 10. 判据与命令对照（可执行断言）

本节只给命令与期望，不重复判据描述（判据的映射在 §4，设计口径在 `design.md` §6.1）。
每一条“通过条件”都必须能落到下面的形式：命令 + 期望结果。

| 判据 | 命令 | 期望 |
| --- | --- | --- |
| 图片型图源被识别 | `python books/src/python/audit/diagrams.py --json` | 报告里 `images_*` 计数等于手稿图片引用数 |
| 资产可解析 | `python books/src/python/audit/links.py` | 退出码 0；删掉一张图即非 0 并点名文件 |
| 构建幂等 | 连续两次 `bookctl build` 后 `sha256sum dist/*.html` | 两次哈希相同（第二次大量命中缓存） |
| 改图能重建 | 只改一张 SVG，再 `bookctl build` | HTML 哈希变化；片段计数显示该章重渲 |
| PDF 图未丢 | `python books/src/python/render/verify_pdf.py` | 退出码 0；图片对象数 == 图片引用数 |
| EPUB 图未丢 | `python books/src/python/render/verify_epub.py` | 退出码 0；manifest 里图片资源数 == 图片引用数 |
| alt 与图注一致 | `python books/src/python/audit/captions.py` | 退出码 0；改错一处 alt 即非 0 |
| 体量未变薄 | `python books/src/python/audit/content_volume.py` | 退出码 0；若确实下降则基线已按流程重记 |
| 门禁全绿 | `books/scripts/bookctl check` | 全部步骤 OK（步骤数随项目变化，不写死） |

**负向用例的造法**（不做这一步，就无法证明判据有效）：

| 要证明什么 | 怎么造 |
| --- | --- |
| HTML 路径判据能红 | 把一张图的 `src` 改成不存在的文件名 |
| PDF 数图判据能红 | 从已生成的 HTML 里删掉一段 `data:image/svg+xml` 后重跑 `verify_pdf` |
| EPUB manifest 判据能红 | 先 `deliver` 出 EPUB，再从压缩包里删一张图后重跑 `verify_epub` |
| 缓存能失效 | 改一张 SVG（不动 md）后重构建，正文应出现新的内联字节 |

## 11. 计划变更与完成衔接

- **发现设计错误**：先改 `design.md`，再改本计划；不允许只改计划而不改设计（否则两者又分叉）。
- **阶段范围变动**：不得跨阶段合并；一次变更只完成一个阶段的全部产物与判据。
- **失败登记**：实现中发现的真实缺陷按 `review-findings.md` 编号登记；本计划只留“做完没做完”。
- **完成时**：删 `plan.md` 的 `plan-6` 段，在 `changelog.md` 写一条完成为止；两份 plan 文件留作设计与判据的依据，不归档。
- **不铺开的判决**：阶段 5 完成后若三项增量不可接受（例如 PDF 页数或 HTML 体积超过人工阀值），
  就把试点图退回 ASCII，并把结论写成“哪些图适合 ASCII”写回 `style-guide.md` §14；
  它比“不了了之”更有价值。
