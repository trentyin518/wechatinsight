# Tasks

## 1. 数据源验证（阶段 0，编码前置）

- [x] 1.1 注册候选供应商账户并获取测试 API Key，验证可完成一次鉴权请求（成功返回示例响应即通过）
- [x] 1.2 测试四类能力：公众号搜索、历史文章、文章互动指标、重复查询，产出「验证项目 → 通过条件 → 结果」记录表
- [x] 1.3 确认批量查询能力、返回条数、限流与数据更新时间字段，记录真实请求参数与返回样例
- [x] 1.4 向供应商确认数据存储、商业展示与加工授权，形成数据授权确认清单
- [x] 1.5 估算 1 万公众号规模下的月调用量与费用，形成初步成本测算与首选供应商结论
- [x] 1.6 产出 `docs/requirements.md` 中的数据源字段映射文档，并验证其覆盖账号/文章/指标全部决策字段

## 2. 项目骨架与环境

- [x] 2.1 创建 monorepo 根结构与 `.gitignore`（忽略 `.env`、`node_modules`、`__pycache__`、构建产物），验证目录树与 `proposal.md` 影响列表一致
- [x] 2.2 初始化 `frontend/`（Next.js + TypeScript + App Router），验证 `npm run build` 成功
- [x] 2.3 初始化 `backend/`（FastAPI + Pydantic + SQLAlchemy + Alembic + httpx + APScheduler），验证 `uvicorn` 启动且 `GET /health` 返回 `{"status":"ok"}`
- [x] 2.4 创建 `worker/` 骨架并复用后端 providers/db 包，验证可导入后端模块且 `python -m worker.main` 能启动空循环
- [x] 2.5 配置环境变量模板 `.env.example`（`APP_ENV`、`DATABASE_URL`、供应商 Key、`CORS_ORIGINS`），验证 README 说明与实际变量一致，且无密钥写入前端 `NEXT_PUBLIC_`
- [x] 2.6 编写本地开发指南 `docs/development.md` 与部署说明 `docs/deployment.md`，验证按文档步骤可本地起全栈

## 3. 数据库模型与迁移

- [x] 3.1 定义 `wechat_accounts`、`wechat_articles`、`article_metrics` 模型（内部 ID 主键、指标快照字段含 `observed_at`/`raw_updated_at`），验证 Alembic 迁移可 `upgrade head` 并在空库建表成功
- [x] 3.2 定义 `provider_account_mappings`（`provider, provider_account_id` 唯一）与 `data_providers` 表，验证换源不改变内部账号主键的单元测试通过
- [x] 3.3 定义 `sync_jobs`（状态机字段、重试次数、错误码、调用次数、预估成本）与 `api_usage_logs`（供应商/接口/成功/条数/成本/币种/关联任务），验证迁移生成且字段完整
- [x] 3.4 添加文章去重唯一约束（规范化 URL + provider）与查询索引（如 `account_id, published_at DESC`），验证重复插入被约束拒绝的测试通过
- [x] 3.5 编写 `docs/database.md` 说明表结构与快照语义（`null ≠ 0`），验证文档与迁移 schema 一致

## 4. Provider 接口与首个适配器

- [x] 4.1 在 `backend/app/providers/base.py` 用 `Protocol` 定义四类操作与标准化返回结构，验证类型检查/导入通过
- [x] 4.2 实现首选供应商适配器（`qovia.py` 或 `xmedi.py`），把响应转换为统一结构并保留 `provider`，验证「缺失字段为 `null`」的单测通过
- [x] 4.3 在适配器内实现超时、重试、限流与错误封装（`DataSourceUnavailable`），验证模拟超时/额度耗尽时抛出标准化异常而非原始错误
- [x] 4.4 实现 `provider_registry` 与账号/文章 upsert + 映射写入 + URL 规范化去重，验证「同一账号重复搜索不新建」「同一 URL 不同形式合并」测试通过
- [x] 4.5 编写适配器样例测试脚本（少量真实账号），验证可抓取一页文章并写入数据库且生成指标快照

## 5. 后端查询 API

- [x] 5.1 搭建 `/api/v1` 路由与统一分页模型、统一错误信封异常处理器，验证 404/参数错误返回 `{ "error": { "code", "message" } }`
- [x] 5.2 实现公众号搜索与详情接口，结果本地优先且 `total` 为本地命中数，验证分页与本地 `total` 的接口测试通过
- [x] 5.3 实现历史文章列表与文章详情接口，返回最近一次保存指标（含 `metrics_observed_at`），验证不会在请求时调用第三方的测试通过
- [x] 5.4 实现文章指标历史接口（按时间排序）与观测阅读量变化计算，验证「上次为 0/缺失不算变化率」的测试通过
- [x] 5.5 实现受控冷启动查询（缓存 + 额度 + 限流）与数据源不可用降级，验证超限返回额度错误、第三方故障返回本地数据
- [x] 5.6 补充 API 合约测试与 OpenAPI 校验，验证 P0 端点响应结构稳定

## 6. 采集 Worker 与调度

- [x] 6.1 实现三类任务（账号资料更新、历史文章同步、文章指标更新）与状态机流转，验证状态转换单测覆盖 `PENDING/RUNNING/SUCCESS/RETRY/FAILED`
- [x] 6.2 实现幂等写入与分页游标保存/续传，验证「重复执行不产生重复数据」「中断后从游标继续」测试通过
- [x] 6.3 接入 APScheduler 定时调度与频率配置（A/B/C 分层），验证到期任务被入队、优先级调度测试通过
- [x] 6.4 实现每次第三方调用的 `api_usage_logs` 写入与每日/每月预算上限降频，验证接近预算时低优先级任务降频的测试通过
- [x] 6.5 实现失败重试上限与任务日志，验证超限转 `FAILED` 且保留错误码
- [x] 6.6 端到端验证：跑一轮调度后数据库新增文章与指标快照、用量日志有对应记录

## 7. 前端页面

- [x] 7.1 实现 `lib/api` 客户端与 `DataProvenance` 展示组件（来源 + `observed_at` + 缺失渲染为「暂不可用」），验证组件单测覆盖 `null` 指标
- [x] 7.2 实现首页搜索入口、分类入口与数据覆盖说明，验证提交关键词跳转结果页
- [x] 7.3 实现搜索结果页（分页、空状态）与公众号详情页（资料、最近更新时间、历史文章），验证空/错误状态正确渲染
- [x] 7.4 实现文章详情页（标题、链接、公众号、发布时间、指标、采集时间；单次指标不出趋势图），验证缺失指标不显示为 0
- [x] 7.5 实现统一错误边界与数据源不可用提示，验证后端返回 `DATA_SOURCE_UNAVAILABLE` 时页面友好降级且站点可用
- [x] 7.6 通读 `docs/development.md` 启动全栈，验证「首页搜索→公众号详情→文章详情」完整闭环可点通

## 8. 部署与验收

- [x] 8.1 部署前端到 Vercel、后端与 Worker 到云服务器、配置 PostgreSQL 与 CORS，验证线上 `GET /health` 与一次搜索可用（线上 health 200、搜索/详情/文章/指标全 PASS，见 `docs/deployment.md` 10、11）
- [x] 8.2 配置 HTTPS、连接池、日志轮转与每日备份并执行一次恢复测试，验证恢复后数据完整（四项判据 + 冻结写入后恢复演练一致，见 10.4）
- [ ] 8.3 执行上线验收清单（搜索/详情/历史文章/指标快照/去重/更新时间/成本记录/缺失不显示为 0/第三方故障不致整站不可用），验证全部通过（冒烟全 PASS，见 11.1；剩余：第三方故障注入、Qovia 真实数据验收）
- [x] 8.4 运行性能检查：正常负载下本地查询 API P95 < 500ms（工程目标，记录实测值），验证结果写入 `docs/deployment.md`

## Workflow follow-up

- 阶段 0 数据源验证未通过前，4.x 及之后任务阻塞，需先确认可用供应商、成本与授权。
- 所有实现完成并通过评审后，运行 `/opsx-archive` 归档本变更并同步主 specs。
