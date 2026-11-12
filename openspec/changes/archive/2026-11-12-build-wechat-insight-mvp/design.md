# Design

## Context

项目为纯新仓库（仅有 `openspec/` 脚手架），可从零确定技术栈与目录结构。设计文档已确定：Next.js + TypeScript 前端（Vercel）、Python + FastAPI 后端、独立 Python Worker 采集、PostgreSQL 存储、MVP 阶段暂不引入 Redis。动因与范围见 `proposal.md`，行为契约见各能力 `specs/<capability>/spec.md`。核心约束：数据真实性优先、第三方密钥只存服务端、成本需可控、`null` 不等于 `0`、指标必须留存历史快照。

## Goals / Non-Goals

**Goals:**
- 一套代码库（monorepo）同时容纳 `frontend/`、`backend/`、`worker/`，共享 OpenSpec 规划。
- 以统一 Provider 抽象隔离供应商，使更换/新增数据源无需改动业务层。
- 以「快照追加」模型保存指标，支撑后续趋势与排行榜。
- 后端 API 统一分页与错误信封；数据溯源（来源、采集时间、缺失）贯穿前后端。
- 可在单台云服务器 + Vercel 上运行，成本与复杂度可控。

**Non-Goals:**
- 不实现排行榜、趋势、对比、推广识别、会员支付、用户系统（后续变更）。
- 不引入 Redis/Celery、多 Worker 分布式调度、多数据源并行。
- 不实现真实粉丝数、粉丝画像、广告收入估算。
- 不在本阶段做全量历史回补或全行业覆盖。

## Decisions

### 1. Monorepo：`frontend/` + `backend/` + `worker/` + `docs/`
同一 Git 仓库管理三段，共享 `openspec/` 规划与根级文档。**替代方案**：多仓库拆分——被否决，MVP 阶段团队小，跨段联调频繁，单仓库更易保持数据契约同步。后端与 Worker 共享 Python 包（如 `backend/app/providers` 被 Worker 复用），避免适配器重复实现。

### 2. Provider 抽象：`Protocol` + 适配器注册表
在 `backend/app/providers/base.py` 用 `typing.Protocol` 定义 `search_accounts / get_account / get_articles / get_article_metrics`；每家供应商一个 `qovia.py`/`xmedi.py` 实现；`provider_registry` 按 `provider` 名解析实例。业务层仅依赖接口。**替代方案**：直接在各 service 里写供应商调用——被否决，会锁死供应商、难以限流与测试。适配器内部统一处理：超时、重试、限流、原始错误封装，对外只抛出标准化异常（如 `DataSourceUnavailable`）。

### 3. 数据模型：内部 ID + 供应商映射 + 快照
- `wechat_accounts` 用平台内部 `id` 主键；`provider_account_mappings(provider, provider_account_id) UNIQUE` 关联供应商 ID，支持换源不换主键。
- `wechat_articles` 以规范化 `article_url` + `provider` 唯一约束去重，辅以供应商标识。
- `article_metrics` **只追加**，每行含 `observed_at` 与可选的 `raw_updated_at`，绝不覆盖。
- `api_usage_logs` 记录每次第三方调用与预估成本；`sync_jobs` 记录任务状态机；`data_providers` 记录供应商配置与启用状态。
**替代方案**：在 `wechat_articles` 上直接存当前阅读量——被否决，会丢失历史，无法做趋势。所有结构变更走 Alembic。

### 4. 调度：数据库任务表 + APScheduler（MVP）
`sync_jobs` 表作为单一任务事实源，Worker 内 APScheduler 按频率轮询/入队，单进程处理。任务状态机 `PENDING→RUNNING→SUCCESS|RETRY|FAILED`，重试有上限，写入幂等（基于唯一约束 upsert），长任务保存分页游标。**替代方案**：一开始上 Redis + Celery——被否决，MVP 任务量小，过早引入增加部署与运维成本；设计为可在触发阈值（多机、积压）后平滑迁移到队列。

### 5. API：`/api/v1` + 统一错误信封 + 本地优先
FastAPI 路由按资源组织；Pydantic 响应模型保证字段稳定；异常处理器把领域异常映射为 `{ "error": { "code", "message" } }` 与合适 HTTP 状态码。查询优先读本地库；未命中时按受控策略（缓存 + 额度 + 限流）决定是否实时调用供应商。`GET /health` 轻量返回；依赖检查单独受保护。
**替代方案**：前端直连供应商——被否决，密钥暴露、无法统一格式与控费。

### 6. 前端：Next.js App Router + 数据溯源组件
`app/` 下按 `accounts/[id]`、`articles/[id]` 路由；统一 `lib/api` 封装调用后端；统一 `DataProvenance` 组件展示来源与 `observed_at`；`null` 指标渲染为「暂不可用」。缺失数据模块隐藏或标注，不画假曲线。服务端组件优先用于首屏与 SEO，交互分页用客户端组件。

### 7. 部署：Vercel（前端）+ 云服务器（FastAPI + Worker + PostgreSQL）
前后端不同子域（如 `www` 与 `api`）；CORS 白名单；第三方密钥仅后端环境变量；`.env` 不入库；生产启用 TLS、连接池、日志轮转、每日备份。

## Risks / Trade-offs

- **数据源验证未完成即开发** → 阶段 0 作为硬前置：至少一个数据源通过能力/成本/授权验证后才实现适配器，否则变更阻塞。
- **供应商覆盖/指标不稳定** → 适配器标准化 + `null` 语义 + 数据溯源展示，避免误导用户。
- **成本失控（文章指标调用量大）** → 分层调度（A/B/C）+ 每日/每月预算上限 + 低优先级降频 + 用量日志核对。
- **免费开源事件循环套 APScheduler 单点** → 任务状态落库、可恢复游标，预留迁移 Celery 的边界。
- **Vercel 未命中冷启动实时查询放大费用** → 本地优先 + 缓存 + 额度 + 限流；默认关闭无限制实时查询。
- **文章 URL 归一化不完善导致重复** → 规范化规则 + 供应商标识 + 唯一约束；异常进入人工核验而非按标题合并。

## Migration Plan

1. 初始化 monorepo 与 `.gitignore`，创建 `frontend/`、`backend/`、`worker/` 骨架。
2. 建库并落地 Alembic 初始迁移（核心表 + 扩展表）。
3. 实现 Provider 接口与首个适配器，本地跑通「搜索→文章→指标→入库」。
4. 起 FastAPI（`/health` + P0 接口）与 Worker（三类任务），联调。
5. 起 Next.js 页面并对接 API，部署前端到 Vercel、后端/Worker 到云服务器。
6. 回滚策略：迁移与代码均可按版本回退；数据快照模型保证回滚不丢历史；部署前做数据库备份。

## Open Questions

- 首个适配器锁定哪家供应商及其真实批量与计费规则，需由阶段 0 验证结果决定（不改变本设计结构）。
- 指标更新频率的具体初值（近 7 天 1～4 次/天等）需依据供应商限额与预算微调。
