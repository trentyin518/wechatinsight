# 上线后待办

> 里程碑 8（部署与验收）已于 2026-11-08 完成，验收记录见 `docs/deployment.md` 第 10、11 节。
> 本文件只跟踪**上线之后**的运营类事项，按优先级排列。

## 1. 后端迁移到境外节点（阻塞项）

现状：`api.wechatinsight.com` 在大陆 ECS 且未备案，阿里云对跨境访问做拦截
（Vercel 美国节点 SSR fetch 被 RST → 前端「无法连接到后端服务」）。
8443 临时端口同样被拦，端口不是变量。

决定：**API + Worker 迁到香港/新加坡节点，数据库保持 Neon**。迁移后直接走 443，
备案与 8443 都不再需要。完整步骤见 `docs/migrate-backend-offshore.md`。

迁移完成后本文件第 1 节的备案流程改为「可选/不再需要」。

步骤：

1. 阿里云控制台 → 备案 → 提交主体与域名信息（个人/企业材料、服务器实例）
2. 备案通过后修改 Nginx，去掉 8443 监听：

```bash
# /etc/nginx/conf.d/wechat-api.conf 中删除这两行
#     listen 8443 ssl;
#     listen [::]:8443 ssl;
nginx -t && systemctl reload nginx
```

3. 前端环境变量改回标准端口并 Redeploy：

```
NEXT_PUBLIC_API_BASE = https://api.wechatinsight.com
```

4. 验证：

```bash
curl -sI https://api.wechatinsight.com/health          # 本地执行，期望 200
curl -sI http://api.wechatinsight.com/health           # 期望 301
certbot renew --dry-run
```

5. 关闭安全组 8443 入方向规则（可选）

## 2. Vercel 前端指向确认

现状：后端公网地址是 `https://api.wechatinsight.com:8443`，需确认 Vercel 已同步。

> **2026-11-09 事故记录：Vercel 全部部署 2 秒、域名返回平台 404**
>
> 根因：项目 Settings → Build & Development 里把 **Build Command / Install Command 的 Override 打开**了。
> 打开后 Vercel 的 framework cross-check 会退回 `@vercel/static` 构建器（`detectedFramework: skipped`），
> 产物只是源码目录的一份静态拷贝，`/` 自然 404；日志特征是 `Build Completed [52ms]` +
> `Skipping cache upload because no files were prepared`。
>
> 修复：
>
> ```bash
> # 1) 清掉三个覆盖项（API，也可在 dashboard 关掉 Override 开关）
> #    buildCommand / installCommand / outputDirectory → null
> #    nodeVersion 26.x → 22.x
> # 2) 本地真实构建（~48s，产出 static/_next + functions/*.func）
> cd frontend
> npx vercel link --yes --project wechatinsight
> npx vercel pull --yes --environment=production
> npx vercel build --prod
> ls .vercel/output/static .vercel/output/functions
> # 3) 上传产物并确认域名
> npx vercel deploy --prebuilt --prod
> curl -sSI https://www.wechatinsight.com/
> ```
>
> 之后 `rootDirectory=frontend` 保持不变，Git 集成构建即恢复正常。
> 判断构建是否真的跑了：`vercel ls` 的 Duration 必须是 30s 以上，日志必须有 `Detected Next.js`。

步骤：

1. Vercel → 项目 → Settings → Environment Variables：`NEXT_PUBLIC_API_BASE=https://api.wechatinsight.com:8443`
2. **Redeploy**（环境变量变更不会自动生效）
3. 浏览器验收：
   - 首页搜索「示例」→ 出现「示例科技观察」
   - 进入公众号 → 5 篇文章
   - 进入文章详情 → 指标有值
   - DevTools → Network：请求域名带 `:8443`，无 CORS 报错

## 3. Qovia 真实数据验收

> **2026-11-15 本地验收（充值后）**
>
> - `DEFAULT_PROVIDER=qovia` 已切换；`python -m scripts.check_provider 科技` → OK。
> - Neon 库已补齐迁移 `0003`–`0006`（此前停在 `0002`，缺 `category` 等列）。
> - 五个分类样例已入库并写入指标：夕小瑶科技说 / 财经杂志 / 合肥市教育局发布 / 健康中国 / 生活方式；
>   账号级 `article_count`、`avg_*` 由本地文章指标聚合，行业由搜索关键词提示写入。
> - 本地 API overview：`accounts≈40` `articles≈926` `metrics≈7380` `providers=2`。
>
> **线上仍待**：生产 API（`api.topsaypan.com`）仍是旧镜像（无 `/overview`、无筛选字段），
> 需把 `DEFAULT_PROVIDER=qovia` 写入服务器 `.env`、跑迁移、重启 api/worker 并 Redeploy。

> **2026-11-16 充值核对与聚合修复**
>
> - 真实数据管线存在缺失函数：`accounts_repo.refresh_derived_attributes` /
>   `apply_category_hint` 被 worker 与脚本调用却从未实现，`sync_articles`/`sync_metrics`
>   一进聚合就 `AttributeError`。已补齐（发文数、平均阅读/点赞/在看/转发/留言、是否原创、
>   运营地区由真实文章+最新指标聚合；关键词→行业提示），`pytest` 78 passed。
> - 新增 `scripts/seed_real.py`：按分类有界、幂等地播种/补全真实数据（搜索+文章页+指标，
>   单账号与总量双重预算上限），并规整行业标签到前端口径。
> - **计费现状（阻塞）**：本地 `.env` 的 `QOVIA_API_KEY`（账号 `tentyin518@gmail.com`、
>   key 名 `wechat-insight`）当前 `balance_usd=0.000000`、`plan=payg`、`trial_calls_remaining=0`；
>   `/v1/account` 正常，但 `account_search` 与 `article_metrics` 均返回 **402 余额不足**。
>   充值未体现在该 Key 上 → 冷启动搜索、文章同步、指标补全都无法进行。
> - 已清理生产 worker 的重试风暴：88 个 `RETRY` 任务因 402 反复打接口，已置为 `FAILED`
>   （避免充值到位后瞬间被刷余额）。当前队列 `PENDING/RETRY=0`。
> - 待办：在 Qovia 后台确认充值账户与本地 Key 一致（或把已充值 Key 写入 `.env`），
>   余额到位后执行
>   `python -m scripts.seed_real --categories 科技,财经,教育,健康,生活,美食,汽车,娱乐`。
>
> **2026-11-16 续：充值到账，已按“每类最小量”补齐真实数据**
>
> - `/v1/account` → `balance_usd=10.0`（payg），采集约花 \$0.9，余 \$9.1。
> - 用 `seed_real` 为 科技/财经/教育/健康/生活/美食/汽车/娱乐 各收录 3+ 真实公众号并同步文章，
>   每类至少 1 个账号有真实平均阅读（如 财经杂志 16672、娱乐爆姐 16680、健康中国 11592…）。
> - 修复搜索返回的 HTML 高亮污染：`qovia` provider 对 name/description/title 统一去标签。
> - 站点（前端 :3000 / 后端 :8000）端到端验证各分类页均以真实数据渲染，`pytest` 78 passed。

> **2026-11-11 额度事故记录**
>
> 现象：所有冷启动搜索返回 429 QUOTA_EXCEEDED，前端表现为「额度已用尽」。
> 根因：`next_pending` 会把 RETRY 任务在同一循环内立刻重捡，调度器又在失败后每周期重建 job，
> 5 篇文章 × 3 次重试 × 每分钟一轮 → 42,254 次失败调用；而 `log_usage` 对失败调用同样按
> $0.005 记账 → 假账单 $211，超过月度预算 $100 与日预算 $5。
>
> 修复：失败调用与 mock 调用成本置 0；RETRY 改为指数退避（30s→30m）；目标失败后 6 小时熔断
> 不再入队（提交 9d3a553，50 tests passed）。历史假账单已清零，恢复后 today=$0.16 month=$1.18。

步骤（生产）：

1. 写入服务器 `.env`（**不要用 `sed -i`**，改完 `chown wechat:wechat && chmod 600`）：

```
DEFAULT_PROVIDER=qovia
QOVIA_API_KEY=<真实 key>
QOVIA_BASE_URL=https://api.qovia.ai
```

2. 部署含 overview / 账号筛选字段的后端，并跑迁移到 `0006`：

```bash
cd /opt/wechat-insight && source backend/pgenv.sh
alembic upgrade head   # 若 0003/0005 表已存在，先 stamp 再 upgrade 缺列
systemctl restart wechatinsight-api wechatinsight-worker
```

3. 验收：

```bash
curl -sS "https://api.topsaypan.com/api/v1/overview" | head -c 400; echo
curl -sS "https://api.topsaypan.com/api/v1/accounts?q=科技&page_size=2" | head -c 400; echo
bash deploy/acceptance.sh
```

## 4. Worker 失败重试的线上观察（可选）

现状：`tests/test_worker.py` 已覆盖重试逻辑，线上未做显式观察。

做法（择一）：

- 短暂断开数据库：把 Neon 分支设为不可用/暂停 5 分钟，观察 `journalctl -u wechatinsight-worker`
  出现 `RETRY` 状态与退避重试，恢复后任务转为 `SUCCESS`
- 或临时把 `QOVIA_BASE_URL` 指向不可达地址（用 systemd drop-in，不碰 `.env`），观察任务重试与失败上限

关注点：

```bash
journalctl -u wechatinsight-worker -n 100 --no-pager
psql "$PGURL" -Atc "select status, count(*) from jobs group by 1"
```

## 5. 顺手可做的增强

- Nginx 5xx 返回 JSON：`proxy_intercept_errors on;` + `error_page 502 503 504 = @json_error;`
  避免 uvicorn 不可用时前端拿到 HTML（见 `docs/deployment.md` 11.2）
- 备份异地化：在 `.env` 配置 `AWS_S3_BUCKET`，`deploy/backup/pgdump-backup.sh` 会自动上传
- 恢复演练纳入季度例检：`deploy/backup/restore-test.sh`（记得先冻结写入进程）
