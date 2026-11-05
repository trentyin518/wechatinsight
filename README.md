# 微信洞察 · 微信公众号数据分析平台（MVP）

面向内容创作者、自媒体运营者和营销机构的微信公众号数据查询平台。第一版聚焦一条**可验证的最小数据闭环**：

> 搜索公众号 → 查看详情 → 浏览历史文章 → 查看数据源实际提供的互动指标 → Worker 定时更新并累积指标快照。

**核心原则：数据真实性优先。** 平台明确区分「第三方原始数据 / 平台计算指标 / 缺失数据」，缺失字段显示为「暂不可用」而不是 0，并标注数据来源与采集时间。

## 技术栈

- 前端：Next.js 15 + TypeScript（App Router），部署 Vercel
- 后端：Python + FastAPI + SQLAlchemy 2 + Alembic
- 采集：独立 Python Worker + APScheduler
- 数据库：PostgreSQL（本地可用 SQLite 零配置）

## 目录

```
backend/   FastAPI API、数据模型、Provider 适配器、测试
worker/    采集任务、状态机调度（复用 backend 包）
frontend/  Next.js 页面与组件
docs/      需求/数据库/开发/部署文档
openspec/  规划与规格（proposal/specs/design/tasks）
```

## 快速开始

```bash
cp .env.example .env

# 后端
cd backend && python3 -m venv .venv && ./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/alembic upgrade head
./.venv/bin/uvicorn app.main:app --reload --port 8000

# Worker（仓库根目录，本地默认 mock 数据源）
backend/.venv/bin/python -m worker.main --once

# 前端
cd frontend && npm install && npm run dev   # http://localhost:3000
```

测试：`cd backend && ./.venv/bin/python -m pytest -q`；`cd frontend && npm run test && npm run build`。

详见 `docs/development.md`。

## 已实现（MVP）

- 统一 `WeChatProvider` 接口 + `mock`/`qovia`/`xmedi` 适配器，字段映射集中、错误不外泄
- 数据模型：公众号、文章、指标快照（只追加）、供应商映射、数据源、采集任务、调用成本日志
- P0 查询 API：搜索、详情、历史文章、文章详情、指标历史，统一分页与错误信封
- Worker：三类同步任务、状态机、幂等、游标续传、分层调度、预算降级与用量记录
- 前端：首页搜索、结果页、公众号详情、文章详情，数据溯源与缺失状态处理

## 未包含（后续变更）

排行榜、趋势分析、账号对比、推广识别、用户登录/收藏/监控、会员与支付、多数据源并行、Redis/Celery。

## 数据源验证（已完成）

Qovia 已真实联调通过（`https://api.qovia.ai`，Bearer 鉴权）：

- `GET /v1/raw/wechat/account_search` — 公众号搜索（`mp_id` 稳定）
- `GET /v1/raw/wechat/articles` — 历史文章（`mp_id` + `cursor` 分页）
- `GET /v1/raw/wechat/article_metrics` — 互动数据（reads/likes/watching/comments/shares）

实测已跑通「账号 → 文章 → 指标快照」真实闭环。字段映射见 `docs/requirements.md` 与 `backend/app/providers/qovia.py`。
**商业授权已确认**（可长期入库、展示、加工排名与 API 转售）。上线前仍需充值（当前 `balance=0`，靠 trial，`meta.billed=false`；示例单价约 `$0.005/次`）。

## 规划

本仓库使用 OpenSpec 管理变更，当前变更见 `openspec/changes/build-wechat-insight-mvp/`。
