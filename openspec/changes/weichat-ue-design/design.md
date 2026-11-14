# Design

## Context

首页为 Next.js App Router 的 Server Component（`frontend/app/page.tsx`），当前是「Hero + 搜索框 + 静态分类 chips + 数据说明」的极简结构。可复用的既有资产：`SearchForm`、`DataProvenance`、`StateMessage`、`Pagination`、`MetricGrid`，`lib/api.ts`（`getJson` 封装 + `ApiError`）、`lib/format.ts`（`formatMetric` 对 `null` 返回「暂不可用」）、`lib/types.ts` 的数据契约，以及 `globals.css` 以 CSS 变量驱动的深色主题与网格工具类（`.card-grid`、`.chip-row`、`.metric-grid`、`.notice` 等）。数据模型无「分类」字段，账号/文章均带 `provider` 与 `last_synced_at` / `metrics_observed_at`，可支撑「来源 + 采集时间」溯源。动因与范围见 `proposal.md`，行为契约见本变更 `specs/web-app` 与 `specs/query-api`。

## Goals / Non-Goals

**Goals:**
- 将首页重构为「分区式产品首页」，沿用西瓜数据首页的分区节奏（Hero → 能力卡片 → 数据大屏 → 账号/分类入口 → 内容双栏 → 底部说明），但每一处数字与状态都取自真实数据。
- 用一个新的只读聚合端点统一供给「数据覆盖概览」与「最近更新内容」，避免首页散落多请求。
- 首页各数据区块独立降级，任一块失败不影响搜索入口与其余区块。
- 复用既有组件与主题变量，保持视觉与交互一致；移动端优先、深色主题、无第三方 UI 依赖。

**Non-Goals:**
- 不实现西瓜数据式的营销漏斗、登录注册墙、投放评估工具、付费转化等（本项目无用户系统）。
- 不展示粉丝数、预算、投放 ROI 等平台无法获取或需虚构的指标。
- 不改动搜索页、详情页、文章页的既有行为与契约。
- 不引入图表库；概览概览不画趋势/对比图（数据为单点快照语义）。

## Decisions

### 1. 信息架构：沿用西瓜数据分区节奏，内容替换为真实数据语义

将参考站的分区逐段映射为本项目首页（保持视觉节奏与信息密度，替换掉无法兑现的营销内容）：

| 序号 | 西瓜数据分区 | 本项目首页分区 | 数据来源 / 落地方式 |
| --- | --- | --- | --- |
| 1 | 大 Hero + CTA + Tab（投放评估/营销洞察/行业聚焦） | Hero：价值主张 + 主搜索框 + 「按分类浏览」锚点 | 静态文案 + 现有 `SearchForm` |
| 2 | 能力卡片（数据真实性/精准匹配/KOL洞察/竞品追踪/营销投放） | 能力卡片：数据真实性、统一数据源、指标溯源、历史快照 | 静态文案（与平台真实能力一致，不写未实现功能） |
| 3 | 数据大屏（粉丝数/品牌收录/行业用户/投放经验） | 数据覆盖概览：已收录公众号、已收录文章、接入数据源、最近更新时间 | `GET /api/v1/overview` 真实聚合 |
| 4 | KOL 账号墙 + 分类 Tab（资讯/情感/教育/美妆/职场） | 分类入口 + 最近更新账号 | 分类为关键词 chips；账号来自 overview 的最近更新列表 |
| 5 | 行业聚焦 / 优号推荐 双栏资讯 | 最近更新 / 最新收录 双栏（账号或文章） | overview 最近更新列表 + `DataProvenance` |
| 6 | 页脚（关于/友链/关注） | 数据说明条：来源、覆盖范围、null≠0 | 静态文案 + 现有 `.notice` |

**理由**：用户明确要求「沿用分区结构与节奏，内容贴合真实数据语义」。直接照搬营销数字会违反项目「数据真实性优先、null≠0」的核心约束，因此仅保留版式语言。**替代方案**：像素级复刻营销落地页——否决，会引入虚构指标与不可兑现承诺。

### 2. 数据供给：单一只读聚合端点 `GET /api/v1/overview`

首页的「数据覆盖概览」与「最近更新内容」共用一个新端点，Server Component 在服务端 `fetch`（`cache: "no-store"`，与现有 API 封装一致）。响应形如：

```ts
interface OverviewResponse {
  accounts_count: number;        // 已收录公众号
  articles_count: number;        // 已收录文章
  providers_count: number;       // 接入数据源
  last_updated_at: string | null;// 最近数据更新时间；null = 尚无数据
  recent_accounts: AccountOut[]; // 最近更新账号（少量，用于内容区块）
}
```

后端以只读聚合 SQL（`COUNT(*)` + `MAX(last_synced_at)` + 取最近 N 条）实现，复用既有 Pydantic 响应模型与统一错误信封，**不调用第三方、不产生费用、无数据库结构变更**。

**理由**：首页若分别调用搜索/详情接口拼装统计，既无「全量列表」语义又会放大请求；单端点更省、更稳、更易局部降级。**替代方案 A**：前端硬编码营销数字——违反数据真实性，否决。**替代方案 B**：在前端用多个既有接口聚合——无合适的全量/聚合接口，且首屏请求变多，否决。

### 3. 渲染与局部降级：Server Component + 分区块独立状态

`HomePage` 作为 Server Component，用 `Promise.allSettled` 分别拉取 overview；每块按结果渲染三态：

- 成功：渲染真实值（数字用 `formatMetric` 语义，`last_updated_at` 用 `formatDateTime`）。
- 无数据：`accounts_count` 等为 0、`last_updated_at` 为 `null` 时，概览显示「暂无」并配「数据正在积累」说明；内容区块显示 `StateMessage` 空态。
- 失败：该区块渲染局部 `StateMessage`（`tone="error"`，可重试提示），其余区块与搜索入口不受影响。

Hero、能力卡片、分类入口、底部说明为纯静态，不依赖网络，始终可用。这样满足 `web-app` 的「首页分区局部降级」要求。

### 4. 组件拆分：新增首页展示组件，复用既有原子件

沿用仓库现有 PascalCase 组件文件命名（如 `SearchForm.tsx`、`StateMessage.tsx`），新增：

- `components/home/HeroSection.tsx`（或直接内联于 page）：Hero 标题、副标题、`SearchForm`、分类锚点。
- `components/home/CapabilityGrid.tsx`：能力卡片网格（静态数据驱动）。
- `components/home/OverviewStats.tsx`：数据覆盖概览（接收 overview 数据，含缺失/错误态）。
- `components/home/RecentContent.tsx`：最近更新内容列表/双栏（复用 `DataProvenance`）。
- `components/Section.tsx`（可选）：统一分区容器（标题 + 间距），避免每段重复结构。

页面只负责取数与编排；组件保持单一职责、无副作用，数据经 props 注入，便于测试与复用。

### 5. 分类入口：无分类字段，用关键词搜索承接

数据模型无 `category` 字段，因此「分类」沿用现状：一组静态分类名（科技/财经/生活方式/教育/健康等）作为 chips，点击跳转 `/search?q=<分类>`。这是「入口」而非「已分类数据」；文案需避免暗示存在真实分类索引。**替代方案**：新增分类字段与后端分面——超出本变更范围，留待后续数据能力变更。

### 6. 样式：扩展既有 CSS 变量与网格，不引入 UI 库

在 `globals.css` 追加首页新区块的样式：`.hero`（强化版）、`.capability-grid`、`.stat-band`/`.stat`、`.recent-columns`、`.section + .section` 间距等，复用现有变量（`--surface`、`--accent`、`--radius`、`--shadow`）与 `.card`/`.chip`/`.notice` 工具类，保持深色主题一致；用 `@media (max-width: 640px)` 做移动端堆叠（stat 与能力卡改为单/双列）。

**理由**：项目现状为纯 CSS + CSS 变量（未接入 Tailwind/shadcn），保持一致、避免引入新依赖与构建改动。**替代方案**：引入 Tailwind/shadcn——与既有代码风格冲突、改动面大，本变更不建议。

## Risks / Trade-offs

- **早期数据量小，概览数字很小或不佳** → 如实展示 + 「数据正在积累」文案，不美化；必要时概览在无数据时整体显示引导态而非一排 0。
- **新增端点增加后端面** → 只读聚合、无第三方调用、无结构变更，成本极低；用统一错误信封与既有响应模型降低维护成本。
- **参考站视觉复刻偏离深色主题** → 只借版式（分区、卡片网格、双栏、统计条），配色仍走现有深色主题变量。
- **「分类」被误解为真实分类索引** → chips 即关键词搜索入口，文案明确「按关键词/分类浏览」。
- **首页区块增多影响首屏性能** → 仅一次 overview 请求，其余静态；首屏 Server 渲染，无额外客户端请求。

## Migration Plan

1. 后端先落地 `GET /api/v1/overview`（只读聚合），本地 `/health` + 端点自测通过。
2. 前端新增数据类型与 `getOverview()` 调用，再改 `page.tsx` 编排与新增首页组件、样式。
3. 渐进式：首页新结构对现有路由无破坏；灰度可先隐藏内容区块（`SHOULD`）。
4. 回滚：前端回滚即恢复旧 `page.tsx`；后端端点独立、无迁移无副作用，可直接下线。

## Open Questions

- 「最近更新内容」优先展示最近更新的账号还是最新文章，取决于上线时哪类数据更丰富；端点已支持最近账号，后续可加最新文章列表而不改首页结构。
- 能力卡片与 Hero 的最终文案需产品/运营定稿，不影响版式与实现结构。
