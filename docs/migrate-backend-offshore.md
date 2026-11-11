# 后端迁移到香港/新加坡（脱离 ICP 备案与跨境拦截）

> 背景：`api.wechatinsight.com` 部署在大陆 ECS 且未备案，阿里云对**跨境访问**做拦截
> （Vercel 在美国 iad1，SSR fetch 直接被 RST → 前端显示「无法连接到后端服务」）。
> 大陆 ECS 上即使换 8443 端口也绕不过：拦截按 TLS 指纹/SNI 判定，与端口无关。
>
> 目标：把 API + Worker 迁到境外节点（推荐阿里云香港轻量应用服务器），数据库仍用 Neon。
> 迁完后 `api.wechatinsight.com` 直接走 443，**不再需要备案、不再需要 8443**。

## 0. 前置条件

- 一台境外节点（2C2G 足够，Alibaba Cloud HK 轻量 / 腾讯云 HK 均可），系统 Alibaba Cloud Linux 3 或 Ubuntu 22.04
- 域名解析控制台可改 `api` 的 A 记录
- 现有 `backend/.env`（Neon `DATABASE_URL`、CORS、budget 等），**数据库不用迁移**

## 1. 基础环境

```bash
# 系统依赖（AL3 用 dnf，Ubuntu 用 apt）
dnf install -y nginx git python3.11 python3.11-devel gcc
python3.11 -m venv /opt/wechat-insight/backend/.venv 2>/dev/null || true

# certbot
dnf install -y certbot python3-certbot-nginx

# 用户
useradd -r -s /sbin/nologin wechat 2>/dev/null || true
```

## 2. 拉代码与依赖

```bash
mkdir -p /opt && cd /opt
git clone https://github.com/trentyin518/wechatinsight.git
cd wechat-insight
git checkout main

cd backend
python3.11 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt      # 若仓库用 uv，则 uv sync

mkdir -p /var/log/wechatinsight /var/backups/wechatinsight
chown -R wechat:wechat /opt/wechat-insight /var/log/wechatinsight /var/backups/wechatinsight
```

## 3. 配置 .env

从旧机器拷贝（**不要手敲，也不要 `sed -i` 改，会破坏属主**）：

```bash
# 旧机器
scp /opt/wechat-insight/backend/.env root@<HK_IP>:/opt/wechat-insight/backend/.env
```

新机器上确认关键项：

```bash
chown wechat:wechat /opt/wechat-insight/backend/.env
chmod 600 /opt/wechat-insight/backend/.env
grep -E '^(APP_ENV|DEFAULT_PROVIDER|CORS_ORIGINS)=' backend/.env
```

`DATABASE_URL` 指向 Neon，境外访问比大陆更快，无需改。

## 4. 数据库迁移与 systemd

```bash
cd /opt/wechat-insight/backend
sudo -u wechat .venv/bin/alembic upgrade head     # 幂等

mkdir -p /etc/systemd/system/wechatinsight-api.service.d
cp /opt/wechat-insight/deploy/systemd/wechatinsight-api.service /etc/systemd/system/
cp /opt/wechat-insight/deploy/systemd/wechatinsight-worker.service /etc/systemd/system/
cp /opt/wechat-insight/deploy/systemd/wechatinsight-api.service.d/restart.conf \
   /etc/systemd/system/wechatinsight-api.service.d/

systemctl daemon-reload
systemctl enable --now wechatinsight-api wechatinsight-worker
systemctl is-active wechatinsight-api wechatinsight-worker
curl -sS -o /dev/null -w 'local health=%{http_code}\n' http://127.0.0.1:8000/health
```

## 5. Nginx + 证书（境外节点无备案，HTTP-01 可用）

先把 DNS 的 `api` A 记录**改到新节点**（旧节点保持运行，随时可切回）：

```bash
dig +short api.wechatinsight.com      # 应返回新节点 IP
```

然后：

```bash
mkdir -p /var/www/certbot
cp /opt/wechat-insight/deploy/nginx/wechat-api-https.conf /etc/nginx/conf.d/wechat-api.conf

# 证书：webroot 方式（80 端口此时已放行，境外无 ICP 拦截）
certbot certonly --webroot -w /var/www/certbot -d api.wechatinsight.com \
  --non-interactive --agree-tos -m <your-email>

nginx -t && systemctl enable --now nginx && systemctl reload nginx
ss -ltnp | grep -E ':(80|443)'
```

验证：

```bash
curl -sS -o /dev/null -w 'https=%{http_code}\n' https://api.wechatinsight.com/health
curl -sS -o /dev/null -w 'http=%{http_code}\n'  http://api.wechatinsight.com/health   # 期望 301
certbot renew --dry-run
```

## 6. 定时任务

```bash
crontab -e
# 备份（Neon 逻辑备份）
15 3 * * * /opt/wechat-insight/backend/backup.sh >> /var/log/wechatinsight/backup.log 2>&1
```

## 7. 切换前端

Vercel → Settings → Environment Variables：

```
NEXT_PUBLIC_API_BASE = https://api.wechatinsight.com
```

（**去掉 `:8443`**）→ Redeploy（或 `cd frontend && npx vercel build --prod && npx vercel deploy --prebuilt --prod`）。

## 8. 验收

```bash
# 服务器
cd /opt/wechat-insight && source backend/pgenv.sh
PATH=/usr/pgsql-18/bin:$PATH \
API_BASE=https://api.wechatinsight.com \
FRONTEND_ORIGIN=https://www.wechatinsight.com \
SEARCH_Q='示例' DATABASE_URL="$PGURL" \
bash deploy/acceptance.sh
```

浏览器：

- https://www.wechatinsight.com/ 搜索「示例」→ 出结果
- 搜索「汽车之家」（冷启动，走上游）→ 不再报网络错误
- 文章详情 → 指标有值

## 9. 下线旧节点

确认 48 小时稳定后：

```bash
# 旧大陆 ECS
systemctl disable --now wechatinsight-api wechatinsight-worker nginx
```

安全组关闭 8443/80/443（或保留仅作备用）。

## 回滚

DNS 改回大陆 ECS IP + Vercel 环境变量改回 `https://api.wechatinsight.com:8443` + Redeploy。
旧节点服务先别停，至少保留一周。

## 迁移后可以删掉的东西

- 大陆节点上 nginx 的 8443 监听
- `docs/deployment.md` 10.5 的临时端口方案（改为历史记录）
- 安全组 8443 规则
