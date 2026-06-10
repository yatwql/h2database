# U8 排版品质提升 — 工作量评估与执行计划

> **类型**: refactor（工具链）
> **状态**: active
> **最后更新**: 2026-06-10
> **基线**: v4.24（`docs-stm/tools/generate_html.py` 428 行, `generate_pdf.py` 401 行, `final_check.py` 179 行）
> **前置**: U0-U4 已完成（管理迁移、前件、后件、模板、通检）

---

## 问题框架

当前 HTML/PDF 生成工具（`generate_html.py` 428 行 + `generate_pdf.py` 401 行）使用内联 CSS 的单文件架构，其渲染品质处于"功能完整、视觉基础"的水平。规划中的 U8 将 11 项增强需求列为一个单元，但实际评估表明这些需求涉及三种不同难度层级的技术工作，不宜混为一谈。

### 现状基线

**已有功能（无需重复实现）：**
- 表格斑马纹 ✅（`tr:nth-child(even)` 已存在）
- 封面页全屏深色渐变 ✅
- 侧边栏 TOC 滚动高亮 ✅
- 响应式布局（≤768px 折叠侧边栏） ✅
- 代码框左侧蓝条边框 ✅
- TOC 页完整目录（h1-h4） ✅
- PDF Document Outline 书签 ✅
- PDF 正文前目录可点击链接 ✅
- ASCII 图框内中文正体渲染 ✅（Consolas/DengXian font-family）

**缺失功能（需要新增）：**
- 章首页装饰性分隔 / 章标题视觉突出 — **CSS only，低难度**
- 代码块行号显示 — **JS 注入，中难度**
- 代码块复制按钮 — **JS 注入，中难度**
- 面包屑导航（当前位置高亮） — **JS + 标题结构理解，中难度**
- 上一章/下一章按钮 — **JS + 章边界检测，中难度**
- 图注样式优化（与正文视觉区隔） — **CSS only，低难度**
- 打印样式优化（`@media print`） — **CSS only，低难度**
- PDF 章首页（独立章标题页） — **Playwright 渲染策略改动，高难度**
- PDF 页眉页脚（章标题 + 页码） — **Playwright 配置，中难度**
- PDF 代码块跨页控制 — **CSS + Playwright，中难度**
- PDF 目录页排版优化 — **CSS only，低难度**

---

## 关键决策

### KTD-1: 按难度分层执行，不做单体 U8

11 项增强不能全部塞进一个单元执行。按技术栈和风险分为三层：

| 层 | 类型 | 项数 | 难度 | 风险 |
|----|------|------|------|------|
| CSS-only | 纯样式 | 5 | 低 | TOC 断链/围栏平衡无影响 |
| JS 注入 | JavaScript + CSS | 4 | 中 | 需测试 `<script>` 注入兼容性 |
| PDF 架构 | Playwright 渲染策略 | 2 | 高 | 可能影响 PDF 三步验证 |

### KTD-2: JS 注入使用内联脚本，不引入外部依赖

`generate_html.py` 当前是零外部依赖的单文件脚本。JS 功能（行号、复制按钮、面包屑、导航）使用内联 `<script>` 注入 HTML 输出，不引入 npm、webpack 或其他构建工具。一致性：已有 scrollspy observer 就是内联 JS 模式。

### KTD-3: PDF 章首页需重构 generate_pdf.py 的渲染策略

当前 `page.pdf()` 使用单一 `margin` 参数渲染全部页面。章首页需要：
- 每遇 `h1` 标题时插入分页符
- 章首页使用不同 margin（无页眉页脚）或独立渲染
- 通过 Playwright `page.add_style_tag()` 注入章首页样式

这是 U8 中风险最高的部分，应放在最后执行。

---

## 实施单元

---

### U8a. CSS-only 样式增强（低难度，5 项）

- **目标**: 通过纯 CSS 修改提升基本排版品质，零 JS 零架构改动
- **依赖**: 无（可立即执行）

**文件:**
- `docs-stm/tools/generate_html.py`（修改内联 CSS 区域 lines 59-217）

**方法:**
1. **章首页装饰性分隔**: 在 `h1` 样式前添加 `::before` 伪元素，插入渐变分隔线或装饰性色块：
   ```css
   h1 { margin-top: 2em; position: relative; }
   h1::before {
     content: ''; display: block; width: 60px; height: 4px;
     background: linear-gradient(90deg, #1565C0, #4fc3f7);
     border-radius: 2px; margin-bottom: 12px;
   }
   ```
   或将此效果限制在 `#content h1`（正文 h1，不包含封面的 `#cover h1`）。

2. **图注样式优化**: 为包裹图注的 `<strong>` 添加独立样式，使之与正文视觉区隔：
   ```css
   #content strong:has(> :only-child:contains("图"))  /* fallback */ 
   ```
   由于 CSS `:has()` 兼容性限制，改用类标记方案：在 `md_to_html()` 中将 `**图 X-Y:**` 包裹为 `<strong class="fig-caption">`。

3. **打印样式强化**: 在 `@media print` 块中新增：
   ```css
   @media print {
     pre { page-break-inside: avoid; }
     table { page-break-inside: avoid; }
     h1, h2, h3, h4 { page-break-after: avoid; }
     #sidebar { display: none; }
     #content { margin-left: 0; max-width: 100%; }
   }
   ```

4. **表格斑马纹优化**: 当前已有 `tr:nth-child(even)`。可增强：表头固定、hover 高亮：
   ```css
   th { position: sticky; top: 0; }
   tr:hover { background: #e3f2fd; }
   ```

5. **整体间距微调**: 调整 `#content` 的 `padding`、`max-width`，优化阅读宽度。

**测试场景:**
- Happy path: `generate_html.py` 输出完整，HTML 在 Chrome 中渲染无错误
- Integration: `final_check.py` 79/79 全部通过（CSS 修改不应影响任何功能性检查）
- Edge: `@media print` 样式不影响屏幕渲染
- Visual: 章首页出现装饰性分隔线

**验证:** `final_check.py` 全部通过；人工在 Chrome 中打开 HTML 确认装饰效果

---

### U8b. JS 注入增强（中难度，4 项）

- **目标**: 为 HTML 添加行号、复制按钮、面包屑导航和章导航按钮
- **依赖**: U8a 推荐在前（CSS 基础样式就绪后再加交互）

**文件:**
- `docs-stm/tools/generate_html.py`（在 `<script>` 区域新增 JS 函数）

**方法:**
1. **代码块行号**: 在现有 `<pre><code>` 输出后，通过 JS 为每个 `<pre>` 计算行数并注入行号列：
   ```javascript
   document.querySelectorAll('pre code').forEach(block => {
     const lines = block.innerHTML.split('\n');
     const lineCount = lines.length;
     const lineNum = document.createElement('div');
     lineNum.className = 'line-numbers';
     for (let i = 1; i <= lineCount; i++) {
       lineNum.innerHTML += i + '\n';
     }
     block.parentElement.insertBefore(lineNum, block);
   });
   ```
   CSS 配套：`.line-numbers { float: left; ... }` 行号列样式。新增内联 CSS 约 15 行。

2. **复制按钮**: 每个 `<pre>` 右上角添加复制按钮：
   ```javascript
   document.querySelectorAll('pre').forEach(pre => {
     const btn = document.createElement('button');
     btn.className = 'copy-btn';
     btn.textContent = '复制';
     btn.onclick = () => { navigator.clipboard.writeText(pre.textContent); };
     pre.style.position = 'relative';
     pre.appendChild(btn);
   });
   ```
   CSS：`.copy-btn { position: absolute; top: 4px; right: 4px; ... }`

3. **面包屑导航**: 在 `#content` 顶部注入面包屑，显示当前 H1 → H2 层级路径。利用标题 ID 和 IntersectionObserver 实时更新。

4. **上一章/下一章按钮**: 在 `#content` 底部注入导航按钮。通过预定义的章边界映射表（硬编码，与 `rebuild_merged.py` 的章节顺序一致）确定前后章节链接。

**测试场景:**
- Happy path: 代码块正确显示行号和复制按钮
- Happy path: 面包屑在滚动时更新当前章节
- Integration: `final_check.py` 全部通过（JS 不影响 Markdown→HTML 转换的正确性）
- Edge: 复制按钮在 file:// 协议下可能不可用（`navigator.clipboard` 需要 HTTPS），提供降级提示
- Edge: 行号列在窄屏上不换行，设置 `overflow:hidden`
- Visual: 面包屑和导航按钮不遮挡正文内容

**验证:** 浏览器中打开 HTML 验证各 JS 功能正常工作；`final_check.py` 全部通过

---

### U8c. PDF 排版增强（高难度，2 项）

- **目标**: 为 PDF 添加章首页和页眉页脚
- **依赖**: U8a ✅, U8b 可选

**文件:**
- `docs-stm/tools/generate_pdf.py`（重构渲染策略）
- `docs-stm/tools/final_check.py`（可选：新增 PDF 排版检查）

**方法:**
1. **PDF 页眉页脚**: 启用 Playwright 的 `display_header_footer` 并在 HTML 中注入页眉页脚模板：
   ```python
   page.pdf(
     path=pdf_path,
     display_header_footer=True,
     header_template='<div style="font-size:8px;...">H2 Database 源码分析</div>',
     footer_template='<div style="font-size:8px;...">第 <span class="pageNumber"></span> 页</div>',
   )
   ```
   注意：Playwright 的页眉页脚仅支持简单的 HTML 模板，不支持动态内容。章标题页眉需通过 JS 在每页注入，超出 Playwright 内置能力。**评估结论：只设置简单的"第 N 页"页脚，页眉保持精简"H2 Database 源码分析"。**

2. **PDF 章首页**: 采用 CSS `page-break-before: always` 策略。在每个 `h1` 前插入分页，并为章首页添加特殊样式：
   ```css
   .chapter-page { page-break-before: always; }
   .chapter-page h1 { 
     text-align: center; font-size: 2em; margin-top: 30vh;
     border-bottom: none;
   }
   ```
   `generate_html.py` 中，在每个 `h1` 前注入 `<div class="chapter-page">` 包装器。需要验证此改动不影响 HTML 侧边栏 TOC 的锚点定位。

**PDF 架构限制（重要）：**
- Playwright `display_header_footer` 的页眉页脚只支持纯文本模板，不支持每页动态章标题。要实现"每页页眉显示当前章标题"，需在渲染前通过 JS 分割页面范围，超出当前单次 `page.pdf()` 的能力范围。
- **评估结论：章首页可实施，但动态页眉（章标题随页变化）搁置。**

**测试场景:**
- Happy path: PDF 生成成功，验证三步通过
- Integration: `final_check.py` 全部通过
- Edge: 章首页分页符不影响正文内容完整性
- Edge: 页脚页码连续正确
- Visual: 章首页在 PDF reader 中正确渲染

**验证:** `python docs-stm/tools/generate_pdf.py && python docs-stm/tools/add_pdf_toc_links.py && python docs-stm/tools/verify_pdf.py` 三步通过

---

### U8d. 排版检查项增强

- **目标**: 在 `final_check.py` 中新增 CSS/HTML 排版相关检查
- **依赖**: U8a 之后

**文件:**
- `docs-stm/tools/final_check.py`

**方法:**
新增 1 项非阻塞检查（warning 级别）：
- `CSS 样式完整性`：检查 `generate_html.py` 中 STYLE 字符串是否包含预期的关键 CSS 规则（`h1::before`、`.copy-btn`、`@media print` 等）。使用字符串包含检测，仅 warning 不 blocking。

**测试场景:**
- Happy path: 新增检查项在 U8a-U8c 实施后通过
- Error: 样式缺失时打印 warning 但不阻断流程

**验证:** `final_check.py` 在 U8a 实施后通过

---

## 工作量评估汇总

| 单元 | 项数 | 难度 | 预估代码改动 | 风险评估 | 是否推荐 |
|------|------|------|-------------|----------|---------|
| **U8a** CSS-only | 5 | 低 | +~80 行 CSS | 极低 | **✅ 强烈推荐，可立即执行** |
| **U8b** JS 注入 | 4 | 中 | +~120 行 JS + CSS | 低 | **✅ 推荐** |
| **U8c** PDF 增强 | 2 | 高 | +~50 行 Python | 中：分页可能影响 PDF 验证 | ⚠️ 评估后可执行 |
| **U8d** 检查项 | 1 | 低 | +~15 行 Python | 极低 | **✅ 推荐** |

**建议执行顺序**: U8a → U8b → U8d → U8c（风险递进）

**不建议纳入 U8 的工作**（标记为推迟）:
- 代码语法高亮（需要引入 highlight.js 等外部依赖，超出单文件脚本架构）
- 动态 PDF 页眉（每页章标题需复杂渲染策略重构）
- Mermaid 图表迁移（已有 P3 规划）
- 黑暗模式（新增维护面过大）

---

## 风险与应对

| 风险 | 影响 | 概率 | 应对 |
|------|------|------|------|
| JS 注入破坏现有 HTML 结构 | U8b | 低 | 用 `final_check.py` 验证 TOC 条目数和锚点完整性 |
| 复./button Clipboard API 在 file:// 协议不可用 | U8b | 中 | 添加 `if (!navigator.clipboard) btn.style.display='none'` 降级 |
| PDF 分页导致 Outline 页码偏移 | U8c | 中 | 在 add_pdf_toc_links.py 之后运行 verify_pdf.py 验证 |
| CSS-only 修改意外影响封面或侧边栏 | U8a | 低 | 使用 `#content` 命名空间限定正文样式 |

---

## 依赖关系

```
U8a (CSS-only) ── 无依赖
  └── U8b (JS 注入) ── 建议 U8a 之后（CSS 基线就绪）
  └── U8d (检查项) ── U8a 之后（检查 U8a 的样式）
       └── U8c (PDF) ── U8a+U8d 之后（CSS 基线 + 验证就绪后再改 PDF）
```

推荐执行顺序：**U8a → U8b + U8d (可并行) → U8c**

---

## 最终建议

U8 不应作为一个整体单元执行。**推荐立即执行 U8a（CSS-only，5 项增强，~80 行代码，零风险）**，U8b 和 U8d 紧随其后。U8c（PDF 章首页）评估后决定是否执行—其收益（章首页）与风险（PDF 验证可能中断）需权衡。

U8a 的 5 项 CSS 增强可在 15 分钟内完成，并立即改善阅读体验，是当前阶段回报率最高的投入。