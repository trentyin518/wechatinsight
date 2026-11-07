# 部署说明

> 部署到 Vercel / 云服务器需要人工持有账号与服务器资源，以下为可执行步骤清单。

## 1. 组件与位置

| 组件 | 位置 |
|---|---|
| Next.js 前端 | Vercel |
| FastAPI 后端 | 云服务器（如阿里云 ECS） |
| Python Worker | 同上，独立后台进程 |
| PostgreSQL | 托管数据库或独立云服务器 |

示例域名：`www.example.com` → 前端；`api.example.com` → 后端。

## 2. 环境变量（后端 / Worker）

```
APP_ENV=production
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/wechat_insight
QOVIA_API_KEY=...            # 仅服务端
CORS_ORIGINS=https://www.example.com
DAILY_BUDGET_USD=5
MONTHLY_BUDGET_USD=100
```

前端（Vercel）只需 `NEXT_PUBLIC_API_BASE=https://api.example.com`（非密钥）。

## 3. 后端部署

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

配合 systemd / supervisor 做进程守护与自动重启；前置 Nginx/HTTPS 反向代理；配置数据库连接池、请求超时与日志轮转。

## 4. Worker 部署

```bash
backend/.venv/bin/python -m worker.main --interval 300
```

作为独立后台服务运行，不依赖用户访问触发。可用 systemd 管理。

## 5. 安全

- HTTPS/TLS 必须启用，数据库不暴露公网。
- 第三方密钥仅存后端环境变量，日志中不得输出密钥。
- `.env` 不入库；生产使用强密码与网络访问控制。

## 6. 备份与恢复

- 每日数据库备份，定期执行恢复演练。
- 记录迁移版本；重要配置单独备份。
- 恢复测试：从备份恢复后校验账号/文章/指标记录数与主键一致。

## 7. 健康检查与性能

- 线上 `GET /health` → `{"status":"ok"}`。
- 性能目标：正常负载下本地查询 API **P95 < 500ms**（工程目标，非保证值）。
  实测记录（本地基准，2026-11-02）：SQLite + TestClient，`GET /api/v1/accounts/1/articles` 200 次请求，
  P50 ≈ 1.5ms、P95 ≈ 1.9ms、P99 ≈ 2.0ms（远低于目标；生产以 PostgreSQL 与真实网络为准，需复测）。

## 8. 上线验收清单（对应设计文档第十八节）

- [ ] 可搜索公众号、查询详情、历史文章与可用互动指标
- [ ] 指标以快照形式保存，缺失不显示为 0
- [ ] 能识别重复账号与重复文章
- [ ] 展示数据来源与更新时间
- [ ] 能记录数据源与调用成本
- [ ] 首页可搜索，结果支持分页，详情页正常
- [ ] 第三方 API 故障不会导致整站不可用
- [ ] 采集任务自动运行，失败可重试，重复任务不产生重复数据
- [ ] 可查看任务状态与 API 调用量/预估费用
- [ ] 前后端已部署，HTTPS 正常，数据库不暴露，密钥未泄漏
- [ ] 数据源使用权限已确认

## 9. 可执行部署资产（`deploy/`）

| 文件 | 用途 |
|---|---|
| `deploy/systemd/wechatinsight-api.service` | 后端进程守护（含启动前 `alembic upgrade head`） |
| `deploy/systemd/wechatinsight-worker.service` | Worker 常驻调度进程 |
| `deploy/nginx/api.wechatinsight.com.conf` | HTTPS 反向代理（80 跳 443，`/health` 不缓存） |
| `deploy/logrotate/wechatinsight` | `/var/log/wechatinsight/*.log` 每日轮转保留 14 天 |
| `deploy/backup/pgdump-backup.sh` | 每日 `pg_dump` 逻辑备份 + 校验 + 可选 S3 异地 + 保留策略 |
| `deploy/backup/restore-test.sh` | 恢复到临时库并比对行数与迁移版本（8.2 演练） |
| `deploy/acceptance.sh` | 8.3 验收冒烟测试（HTTP + 可选数据库去重/成本校验） |

路径约定：代码 `/opt/wechat-insight`，环境变量 `/opt/wechat-insight/backend/.env`，运行用户 `wechat`，venv `backend/.venv`，日志 `/var/log/wechatinsight`。

注意：`backend/migrations/env.py` 在 Postgres 上优先使用 `DIRECT_DATABASE_URL`（Neon direct，绕过 PgBouncer），否则回退 `DATABASE_URL`；DSN 里的 `+psycopg2` scheme 会自动规整为已安装的 psycopg3，无需 `psycopg2-binary`。
