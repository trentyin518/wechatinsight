# 自托管部署（迁移出 Vercel）

本项目由两个服务组成：

- **后端**：FastAPI（`backend/`），已用 systemd 跑在 `127.0.0.1:8000`（`wechatinsight-api`）。
- **前端**：Next.js 15（`frontend/`），浏览器访问的 UI，并把同源 `/api/*` 反代到后端。

迁移的核心就是**把 Next.js 从 Vercel 挪到自己的服务器**，后端无需变动。

---

## 1. 关键环境变量（前端）

| 变量 | 作用 | 示例 |
| --- | --- | --- |
| `API_PROXY_TARGET` | 同源 `/api/*` 反代目标 + 服务端组件直连后端地址。**构建时被烘焙进 rewrites**。 | `http://127.0.0.1:8000` |
| `NEXT_PUBLIC_API_BASE` | 服务端组件兜底地址（一般与上者一致） | `http://127.0.0.1:8000` |
| `NEXT_PUBLIC_AUTH_ENFORCED` | 前端登录门禁（与后端 `AUTH_ENFORCED` 配套） | `false` |
| `NEXT_PUBLIC_SESSION_COOKIE_NAME` | 会话 Cookie 名 | `wi_session` |

> ⚠️ `API_PROXY_TARGET` 在 `next.config.mjs` 的 `rewrites()` 里**构建期**求值，所以：
> **改了后端地址必须重新 `npm run build`（或重建镜像）。** 运行时再改只影响服务端组件，不影响 `/api/*` 反代。

浏览器只与**前端同源**通信（`/api/v1/...`），由 Next 服务端转发到后端——这样 HttpOnly 会话 Cookie 保持同源，无需 CORS。

---

## 2. 方案 A：Docker（推荐做隔离/可复现）

已提供 `frontend/Dockerfile`（多阶段；构建时自动加 `NEXT_OUTPUT=standalone` 产出最小 server bundle）。宿主机走 `next start` 时**不要**设 `NEXT_OUTPUT`，保持默认即可。

```bash
cd frontend

# 构建（API_PROXY_TARGET 作为构建参数烘焙进 rewrites）
docker build \
  --build-arg API_PROXY_TARGET=http://host.docker.internal:8000 \
  -t wechatinsight-web:latest .

# 运行（容器内访问宿主机的后端 :8000）
docker run -d --name wi-web -p 3000:3000 \
  --add-host=host.docker.internal:host-gateway \
  -e API_PROXY_TARGET=http://host.docker.internal:8000 \
  wechatinsight-web:latest
```

或使用 `deploy/docker-compose.web.yml`：

```bash
docker compose -f deploy/docker-compose.web.yml up -d --build
```

> macOS/Windows 的 Docker Desktop 自带 `host.docker.internal`；Linux 需上面的 `--add-host` 或 compose 里的 `extra_hosts`。
> 若后端也容器化在同一网络，直接写服务名（如 `http://backend:8000`）。

---

## 3. 方案 B：直接在宿主机跑（与后端 systemd 一致，最省事）

```bash
cd frontend
npm ci
API_PROXY_TARGET=http://127.0.0.1:8000 npm run build     # 构建期烘焙
```

安装 systemd 单元（已提供 `deploy/systemd/wechatinsight-web.service`，按需改路径/用户）：

```bash
sudo cp deploy/systemd/wechatinsight-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wechatinsight-web
sudo systemctl status wechatinsight-web
```

该单元用 `next start -p 3000` 启动，`API_PROXY_TARGET` 已指向本机后端。

---

## 4. 反向代理 + HTTPS（生产必备）

在前端前面放一层 nginx / Caddy，负责 TLS、域名、以及把 `/api/*` 直接打到后端。

### Caddy（最简，自带 HTTPS）
```caddyfile
example.com {
    # 后端 API 直接反代（可选：也可让 Next 的 /api 反代处理）
    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }
    # 其余交给 Next
    reverse_proxy 127.0.0.1:3000
}
```

### nginx
```nginx
server {
    listen 443 ssl;
    server_name example.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> 若用反向代理把 `/api/*` 直接指向后端，则 `API_PROXY_TARGET` 只影响「服务端组件直连后端」的路径，设成后端地址即可。

---

## 5. 后端 CORS / Cookie 注意

- 浏览器只访问**前端同源**，默认**不需要**放宽 CORS。
- 若前后端不同域，需在后端 `CORS_ORIGINS` 加上前端域名，并让会话 Cookie 走跨域 `SameSite=None; Secure`（一般不建议，优先用同域反代）。
- 后端 `FRONTEND_BASE_URL` 用于 OAuth 回跳等，改成你的公网前端域名。

---

## 6. 验收清单

```bash
# 前端起来了吗
curl -I http://127.0.0.1:3000/

# 同源反代是否打通（应返回后端 JSON，而不是 Next 的 404）
curl -s http://127.0.0.1:3000/api/v1/health || true

# 后端连通性（极媒优先、失败切 Qovia）
cd backend && .venv/bin/python -m scripts.check_provider "科技"
```

构建时出现 `API 代理目标仍是本机地址` 警告：若前后端**不在同一台机器**，说明 `API_PROXY_TARGET` 没设对，务必填真实后端地址后重新构建；若前后端**同机**（后端就在 `127.0.0.1:8000`），这个警告是误报，可忽略。
