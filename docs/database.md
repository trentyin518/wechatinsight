# 数据库设计

所有表结构变更通过 Alembic 管理（`backend/migrations`），生产环境禁止手工改表。

## 核心原则

- **内部 ID 主键**：`wechat_accounts.id`、`wechat_articles.id` 是平台自己的 ID；供应商 ID 存于映射表，换源不换主键。
- **指标快照只追加**：`article_metrics` 每行代表某时刻的观测，**从不覆盖**历史，用于计算观测变化与趋势。
- **`null ≠ 0`**：任何字段为 `null` 表示「数据源未提供或尚未采集」，不代表 0。计算与展示都必须区分二者。
- **时间带时区**：所有时间列均为 `TIMESTAMPTZ`；`observed_at` 是平台采集时间，`raw_updated_at` 是供应商声明的更新时间。

## 数据表

### wechat_accounts
公众号基础信息。

| 列 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | 平台内部 ID |
| name | TEXT NOT NULL | 名称 |
| wechat_id | TEXT | 微信号 |
| avatar_url | TEXT | 头像 |
| description | TEXT | 简介 |
| verification_subject | TEXT | 认证主体 |
| account_type | TEXT | 账号类型 |
| primary_provider | VARCHAR(64) NOT NULL | 主数据源 |
| priority | VARCHAR(1) NOT NULL DEFAULT 'B' | 分层 A/B/C，用于调度 |
| created_at / updated_at | TIMESTAMPTZ | |
| last_synced_at | TIMESTAMPTZ | 最近同步时间 |

索引：`idx_wechat_accounts_name`、`idx_wechat_accounts_wechat_id`。

### provider_account_mappings
供应商账号到内部账号的映射。

| 列 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| account_id | BIGINT FK | 指向 wechat_accounts |
| provider | VARCHAR(64) | 供应商标识 |
| provider_account_id | VARCHAR(255) | 供应商账号 ID |

唯一约束：`uq_provider_account (provider, provider_account_id)`。同一供应商账号重复出现时复用内部 ID。

### wechat_articles
文章基础信息。

| 列 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| account_id | BIGINT FK | 所属公众号 |
| provider | VARCHAR(64) | 数据源 |
| provider_article_id | VARCHAR(255) | 供应商文章 ID |
| title | TEXT NOT NULL | 标题 |
| article_url | TEXT NOT NULL | 原始链接 |
| normalized_url | TEXT NOT NULL | 规范化链接（去重键） |
| summary / author / cover_url | TEXT | 可选 |
| published_at | TIMESTAMPTZ | 发布时间 |
| is_original / is_paid | BOOLEAN | 可空 |
| created_at / updated_at | TIMESTAMPTZ | |

唯一约束：`uq_article_provider_url (provider, normalized_url)`。索引：`idx_articles_account_published (account_id, published_at)`。
去重规则：规范化 URL（去除 `utm_*`、`from`、`scene`、fragment、默认端口等）后比较，**不按标题去重**。

### article_metrics
文章互动指标历史快照（只追加）。

| 列 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL PK | |
| article_id | BIGINT FK | |
| provider | VARCHAR(64) | |
| read_count / like_count / wow_count / comment_count / share_count | BIGINT NULL | 未知为 null |
| observed_at | TIMESTAMPTZ | 平台采集时间 |
| raw_updated_at | TIMESTAMPTZ NULL | 供应商更新时间 |
| created_at | TIMESTAMPTZ | |

索引：`idx_article_metrics_article_time (article_id, observed_at)`。

### data_providers
数据源配置与状态（名称、是否启用、配置 JSON）。

### sync_jobs
采集任务与状态机。

| 列 | 说明 |
|---|---|
| job_type | SYNC_ACCOUNT / SYNC_ARTICLES / SYNC_METRICS |
| target_type / target_id | account / article 及目标 ID |
| provider / priority | 数据源与分层 |
| status | PENDING / RUNNING / SUCCESS / RETRY / FAILED |
| retry_count / max_retries | 重试控制 |
| cursor | 分页游标，支持断点续传 |
| error_code / error_message | 失败信息 |
| api_calls / estimated_cost | 该任务的调用量与预估成本 |
| created_at / started_at / finished_at / updated_at | 时间戳 |

索引：`idx_sync_jobs_status_priority`、`idx_sync_jobs_type_target`。

### api_usage_logs
第三方调用记录与成本。

| 列 | 说明 |
|---|---|
| provider / endpoint | 供应商与接口 |
| request_time | 请求时间 |
| success / returned_items / request_units | 结果与用量 |
| estimated_cost / currency | 预估成本与币种 |
| job_id | 关联任务（可空） |

索引：`idx_api_usage_provider_time (provider, request_time)`。

## 迁移命令

```bash
cd backend
alembic upgrade head      # 应用迁移
alembic revision --autogenerate -m "message"   # 生成新迁移
alembic downgrade -1      # 回退一步
```

本地无 PostgreSQL 时，`DATABASE_URL=sqlite+pysqlite:///./dev.db` 可直接运行；生产必须使用 PostgreSQL。
