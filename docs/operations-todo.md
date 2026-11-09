# 上线后待办

> 里程碑 8（部署与验收）已于 2026-11-08 完成，验收记录见 `docs/deployment.md` 第 10、11 节。
> 本文件只跟踪**上线之后**的运营类事项，按优先级排列。

## 1. 域名备案（阻塞项，影响对外 80/443）

现状：`api.wechatinsight.com` 指向大陆 ECS 但未备案，阿里云拦截 80（提示页）与 443（RST），
当前靠 **8443** 临时端口对外服务。

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

现状：`DEFAULT_PROVIDER=mock`，验收用的是示例数据。

步骤：

1. 充值并拿到 API Key，写入 `backend/.env`（**不要用 `sed -i`**，改完 `chown wechat:wechat && chmod 600`）：

```
DEFAULT_PROVIDER=qovia
QOVIA_API_KEY=<真实 key>
QOVIA_BASE_URL=<供应商地址>
```

2. 重启并确认：

```bash
systemctl restart wechatinsight-api wechatinsight-worker
sleep 5
curl -sS -o /dev/null -w 'health = %{http_code}\n' https://api.wechatinsight.com:8443/health
```

3. 跑一轮真实搜索并检查成本记录：

```bash
cd /opt/wechat-insight && source backend/pgenv.sh
curl -sS "https://api.wechatinsight.com:8443/api/v1/accounts?q=科技" | head -c 400; echo
psql "$PGURL" -Atc "select provider, endpoint, success, returned_items, created_at
                    from api_usage_logs order by id desc limit 5"
```

4. 完整验收（真实数据下重跑）：

```bash
PATH=/usr/pgsql-18/bin:$PATH \
API_BASE=https://api.wechatinsight.com:8443 \
FRONTEND_ORIGIN=https://www.wechatinsight.com \
SEARCH_Q='科技' DATABASE_URL="$PGURL" \
bash deploy/acceptance.sh
```

5. 验收后把第 8 节清单的「数据源使用权限已确认」勾上，并在 11.2 中删除对应遗留项。

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
