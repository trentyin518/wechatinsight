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

- [x] 可搜索公众号、查询详情、历史文章与可用互动指标
- [x] 指标以快照形式保存，缺失不显示为 0
- [ ] 能识别重复账号与重复文章（文章去重已 PASS；账号去重查询脚本待修，见 11.2）
- [x] 展示数据来源与更新时间
- [x] 能记录数据源与调用成本
- [x] 首页可搜索，结果支持分页，详情页正常
- [ ] 第三方 API 故障不会导致整站不可用（未做故障注入验证）
- [ ] 采集任务自动运行，失败可重试，重复任务不产生重复数据（worker 运行中，重试路径未验证）
- [x] 可查看任务状态与 API 调用量/预估费用
- [x] 前后端已部署，HTTPS 正常，数据库不暴露，密钥未泄漏（公网端口暂用 8443，见 10.5）
- [ ] 数据源使用权限已确认（待 Qovia 账号与授权）

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

## 10. 生产部署记录（2026-11-08）

### 10.1 环境实况

| 项 | 值 |
|---|---|
| 服务器 | 阿里云 ECS（2C / 1.8 GB 内存，已加 3 GB swap） |
| 代码目录 | `/opt/wechat-insight`（运行用户 `wechat`，`--system` 无登录 shell） |
| 环境变量 | `/opt/wechat-insight/backend/.env`（`chmod 600`，`chown wechat`） |
| Python | 3.11.18（uv 托管，已复制到 `/opt/python/cpython-3.11.18-linux-x86_64-gnu`，避免服务用户穿越 `/root`） |
| venv | `/opt/wechat-insight/backend/.venv`（由 `wechat` 创建，`readlink -f .venv/bin/python` 必须落在 `/opt/python` 或 `/usr/bin`） |
| 数据库 | Neon Postgres **18.6**（pooler 主机 + `sslmode=require`） |
| PG 客户端 | `/usr/pgsql-18/bin/{pg_dump,psql,pg_restore}`（阿里云 PGDG 镜像 repo，`/etc/yum.repos.d/pgdg18.repo`） |
| 反向代理 | Nginx + certbot，`api.wechatinsight.com` → `127.0.0.1:8000` |
| 服务 | `wechatinsight-api`（uvicorn 2 workers）、`wechatinsight-worker`（APScheduler） |

### 10.2 Neon 连接要点（踩坑记录）

1. **pooler 主机名必须带 endpoint 参数**（旧 libpq 不支持 SNI）：
   `...?sslmode=require&options=endpoint%3D<endpoint-id>`，即 `DIRECT_DATABASE_URL` 的形态。
   `pg_dump` / `psql` 一律用 direct 串，不要用裸 pooler 串，否则报
   `ERROR: Endpoint ID is not specified`。
2. **`pg_dump` 主版本必须 ≥ 服务器主版本**（Neon 已 PG 18，用 13 会
   `aborting because of server version mismatch`）。
3. **`DATABASE_URL` 必须用 `postgresql+psycopg://`**（psycopg3）。写成 `+psycopg2`
   会 `ModuleNotFoundError: No module named 'psycopg2'`（requirements 未装 psycopg2）。
4. 阿里云到 `download.postgresql.org` 不可达；改用
   `https://mirrors.aliyun.com/postgresql/repos/yum/18/redhat/rhel-8-x86_64`。
5. 1.8 GB 内存实例上 `dnf` 易被 OOM kill（`Killed`）；安装时先停服务并加大 swap。

### 10.3 运维辅助脚本

| 脚本 | 说明 |
|---|---|
| `backend/pgenv.sh` | 逐行解析 `.env`（不 `source`，避免 DSN 里的 `&` 被 shell 解释），导出 `PGURL`（优先 `DIRECT_DATABASE_URL`，并规整 `+psycopg2`→裸 `postgresql`） |
| `backend/backup.sh` | 用 `/usr/pgsql-18/bin/pg_dump` 逻辑备份到 `/var/backups/wechatinsight`，`pg_restore --list` 自检 + sha256 + 14 天保留；cron `15 3 * * *` |

### 10.4 8.2 验收记录（2026-11-08）

| 验收项 | 判据 | 结果 |
|---|---|---|
| HTTPS | `https://api.wechatinsight.com/health` 200；HTTP 301；`certbot renew --dry-run` 通过 | ✅ 通过（ECDSA 证书，到期 2027-02-05；Nginx 80→443 跳转 + `/.well-known` webroot 续期） |
| 连接池 | `engine.pool` 为 `QueuePool`，`pool_pre_ping=True`；50 次请求后 `checkedout()==0` | ✅ 通过（size=5 / overflow=10，每 worker） |
| 日志轮转 | `/etc/logrotate.d/wechatinsight` 生效，`logrotate -f` 生成 `api.log.1`，timer active | ✅ 通过（daily / rotate 14 / compress / copytruncate） |
| 每日备份 | `backup.sh` 产出非空 dump，`pg_restore --list` 可列出对象，crontab 含 `15 3 * * *` | ✅ 通过（dump + `.sha256`，产物见 `/var/backups/wechatinsight/`） |
| 恢复演练 | 恢复到 `wechatinsight_restore` 后四表行数与源库一致，`alembic_version` 一致 | ✅ 通过（`1 / 5 / 16 / 18`，`alembic_version=0001`） |

复核脚本：`backend/verify-82.sh`，输出留档到 `/var/log/wechatinsight/8.2-YYYYMMDD.txt`。

> 演练必须先冻结写入进程，否则源库行数会继续增长、与 dump 产生漂移，出现「dst < src」的假失败：
>
> ```bash
> systemctl stop wechatinsight-worker wechatinsight-api
> backend/backup.sh
> # 恢复 + 比对
> systemctl start wechatinsight-api wechatinsight-worker
> ```
>
> 2026-11-08 首轮未冻结：`wechat_accounts 1 / wechat_articles 5` 一致，`article_metrics 6→1`、`api_usage_logs 8→2`
> 不一致（备份后 worker 又写入 5 条指标快照与若干调用记录，属漂移非缺陷）；冻结写入后复测四表完全一致。

### 10.5 域名备案与端口方案（重要）

`api.wechatinsight.com` 指向大陆 ECS 但**尚未完成 ICP 备案**，阿里云会拦截：

- 80 端口：返回 `Non-compliance ICP Filing` 提示页（不是我们的 301）
- 443 端口：TCP 可连、TLS 握手可完成，但 HTTP 请求被 RST（`curl: (35) Connection reset by peer`）

因此备案通过前，`https://api.wechatinsight.com` 对外不可用。当前采用**临时端口方案**：

- Nginx 同一 server 块额外监听 **8443**（备案拦截只针对 80/443）
- 安全组 / firewalld 放行 8443
- 前端 `NEXT_PUBLIC_API_BASE=https://api.wechatinsight.com:8443`
- 证书对端口无关，8443 复用同一张证书

备案通过后：去掉 8443 监听、前端改回 443 并 Redeploy。可选替代：部署到香港/海外节点（无需备案）。

### 10.6 服务管理
```bash
systemctl status wechatinsight-api wechatinsight-worker
journalctl -u wechatinsight-api -n 100 --no-pager
# 日志同时写入 /var/log/wechatinsight/{api,worker}.log
systemctl reset-failed wechatinsight-api && systemctl restart wechatinsight-api
```

## 11. 8.3 验收记录（2026-11-08）

### 11.1 冒烟结果

命令（服务器执行，走公网 8443）：

```bash
PATH=/usr/pgsql-18/bin:$PATH \
API_BASE=https://api.wechatinsight.com:8443 \
FRONTEND_ORIGIN=https://www.wechatinsight.com \
SEARCH_Q='示例' DATABASE_URL="$PGURL" \
bash deploy/acceptance.sh
```

| 检查 | 结果 |
|---|---|
| `GET /health` | PASS 200 `{status: ok}` |
| 搜索（`page_size` 上限生效） | PASS total=1 items=1 |
| 公众号详情 | PASS id=1 |
| 文章列表 | PASS total=5 |
| 文章详情 + 指标非 0 | PASS id=5 metrics null=False |
| 指标历史 | PASS points=10（worker 每轮追加快照） |
| 404 错误信封 | PASS `{error:{code,message}}` |
| CORS（`https://www.wechatinsight.com`） | PASS |
| 文章去重 | PASS 无重复 |
| `api_usage_logs` 成本记录 | PASS 53 行 |
| 账号去重查询 | WARN 查询语句报错（见 11.2） |

补充：同一套脚本在 `API_BASE=http://127.0.0.1:8000` 下也全 PASS，排除 Nginx 干扰。

### 11.2 遗留项

1. **账号去重查询 WARN**：`acceptance.sh` 的账号去重 SQL 需与真实唯一键 `(provider, provider_account_id)` 对齐；定位命令：
   `psql "$PGURL" -Atc 'select count(*) from (select provider, provider_account_id from wechat_accounts group by 1,2 having count(*)>1) x'`
2. **备案**：8443 为临时方案，备案通过后切回 443（见 10.5）。
3. **Qovia 真实数据**：`DEFAULT_PROVIDER=mock`，充值后改 `qovia` 再跑一轮验收（成本/真实数据项）。
4. **故障注入**：未验证第三方 API 故障时的降级行为。

