# Tasks

## 1. Backend: overview 聚合端点

- [ ] 1.1 在 `backend/app/schemas/` 新增 `OverviewResponse`（字段：`accounts_count`、`articles_count`、`providers_count`、`last_updated_at`、`recent_accounts`），验证 `python -c "import app.schemas"` 导入通过且字段与 design.md 一致
- [ ] 1.2 在 `backend/app/repositories/` 增加只读聚合查询（`COUNT` 公众号/文章/数据源、`MAX(last_synced_at)`、最近 N 个账号），验证新增 pytest 用例在种子数据下返回正确计数
- [ ] 1.3 新增 `backend/app/api/v1/overview.py` 路由并在 `router.py` 注册 `GET /api/v1/overview`，验证无数据时返回 0/`null`/空列表、有数据时数值与本地库一致
- [ ] 1.4 新增 `backend/tests/test_overview.py` 覆盖「有数据 / 无数据 / 聚合失败返回统一错误信封」，验证 `cd backend && pytest -q` 全部通过
- [ ] 1.5 在 `docs/development.md` 补充 `GET /api/v1/overview` 的说明与示例，验证文档中的 `curl` 命令可实际跑通

## 2. Frontend: 数据层

- [ ] 2.1 在 `frontend/lib/types.ts` 增加 `OverviewResponse` 与最近更新账号类型，验证 `npm run build`（或 `tsc --noEmit`）类型检查通过
- [ ] 2.2 在 `frontend/lib/api.ts` 增加 `getOverview()`，复用 `getJson`，验证 `npm run build` 通过且错误时抛出 `ApiError`

## 3. Frontend: 首页组件与编排

- [ ] 3.1 新增 `Section` 容器与 `CapabilityGrid`（静态能力卡片，文案与平台真实能力一致），验证 `npm run dev` 下首页可渲染且无控制台报错
- [ ] 3.2 新增 `OverviewStats` 组件，按成功/无数据/失败三态渲染（数字经 `formatMetric` 语义，`last_updated_at` 经 `formatDateTime`），验证三种状态均正确呈现（无数据不显示为 0）
- [ ] 3.3 新增 `RecentContent` 组件，列表复用 `DataProvenance` 标注来源与采集时间，空态/失败态用 `StateMessage`，验证跳转详情可用
- [ ] 3.4 重写 `frontend/app/page.tsx`：用 `Promise.allSettled` 拉取 overview 并编排六个分区，验证 overview 失败时搜索入口与静态分区仍可用（局部降级）
- [ ] 3.5 分类 chips 保持跳转 `/search?q=<分类>`，验证点击进入对应搜索结果页

## 4. Frontend: 样式与响应式

- [ ] 4.1 在 `frontend/app/globals.css` 追加首页新区块样式（Hero、能力卡网格、统计条、最近更新双栏），复用现有 CSS 变量保持深色主题，验证与既有页面视觉一致
- [ ] 4.2 增加 `@media (max-width: 640px)` 响应式规则（统计条/能力卡/双栏在移动端堆叠），验证窄屏下无溢出与重叠

## 5. 集成验证

- [ ] 5.1 前端运行 `cd frontend && npm run test && npm run build`，验证测试与构建全部通过
- [ ] 5.2 后端运行 `cd backend && pytest -q`，验证全部通过
- [ ] 5.3 端到端验证：有数据时首页展示真实覆盖数值与最近更新；清空/模拟无数据时显示「暂无」；模拟 overview 失败时仅该区块降级、搜索仍可用

## Workflow follow-up

- 评审通过后归档本变更（`/opsx-archive`）。
- 归档后确认 `openspec/specs/web-app` 与 `openspec/specs/query-api` 已合并本变更的 delta。
