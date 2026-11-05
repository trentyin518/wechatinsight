# 数据源需求与字段映射（Qovia，已实测）

## 1. 数据源：Qovia（https://api.qovia.ai）

- **鉴权**：`Authorization: Bearer <API Key>`；`GET /v1/account` 返回账户/额度。
- **统一信封**：`{ request_id, data, meta }`；`meta` 含 `billed / charged_usd / balance_usd / empty`，列表接口另有 `data.cursor / has_more / prov`。
- **微信公众号相关接口**（GET，参数走 query）：

| 接口 | 路径 | 参数 | 主要返回 |
|---|---|---|---|
| 公众号搜索 | `/v1/raw/wechat/account_search` | `keyword`（≤50，必填）、`kind`（subscription/service/all） | `mp_id, name, wechat_id, avatar, description, verified, verified_by, type` |
| 公众号历史文章 | `/v1/raw/wechat/articles` | `mp_id`（gh_/wxid_，必填）、`cursor` | `id, title, url, published_at, cover, digest, author, ip_region, is_original, is_paid, reads_label, likes` |
| 文章互动数据 | `/v1/raw/wechat/article_metrics` | `url`（mp.weixin.qq.com，必填） | `reads, likes, watching, comments, shares, updated_at` |
| 视频号搜索 | `/v1/raw/wechat/channel_search` | — | 视频号账号（MVP 暂不使用） |

- **错误码**：`invalid_params 400`、`insufficient_balance 402`、`scope_denied/account_disabled 403`、`not_found 404`（已退款）、`rate_limited/too_many_unbilled 429`、`upstream_* 502/503/504`（已退款）、`invalid_api_key 401`。空结果 `200 + meta.empty=true` 不扣费。
- **计费**：文档示例每次 `charged_usd≈0.005`；当前账户 `plan=free`、`balance_usd=0`、`trial_calls_remaining≈38`，实测 `meta.billed=false`（走试用）。正式使用需充值。
- **限流**：账户 `rpm_limit=60`（滑动 60 秒），超限按 `Retry-After` 重试。

## 2. 统一字段映射（实测确认）

### 公众号（`ProviderAccount`）
| 统一字段 | Qovia 字段 | 说明 |
|---|---|---|
| provider_account_id | `mp_id` | 稳定唯一（gh_/wxid_ 开头） |
| name | `name` | |
| wechat_id | `wechat_id` | |
| avatar_url | `avatar` | |
| description | `description` | |
| verification_subject | `verified_by` | 仅 `verified=true` 时 |
| account_type | `type` | subscription/service |

### 文章（`ProviderArticle`）
| 统一字段 | Qovia 字段 |
|---|---|
| provider_article_id | `id` |
| title | `title` |
| url | `url` |
| published_at | `published_at` |
| cover_url | `cover` |
| summary | `digest` |
| author | `author` |
| is_original | `is_original` |
| is_paid | `is_paid` |

> 文章列表另含 `reads_label`（如「1.2万」，仅展示用文本）与 `likes`；平台以 `article_metrics` 的数值为准。

### 互动指标（`ProviderMetrics`）
| 统一字段 | Qovia 字段 |
|---|---|
| read_count | `reads` |
| like_count | `likes` |
| wow_count | `watching` |
| comment_count | `comments` |
| share_count | `shares` |
| raw_updated_at | `updated_at` |

> 字段缺失一律映射为 `null`，绝不填 0。

## 3. 能力验证记录

| 验证项目 | 通过条件 | 结果 |
|---|---|---|
| 公众号搜索 | 返回可识别账号 | ✅ 通过（真实数据，`mp_id` 稳定） |
| 历史文章 | 稳定列表+分页 | ✅ 通过（`mp_id` + `cursor` + `has_more`） |
| 互动指标 | 返回字段符合预期 | ✅ 通过（reads/likes/watching/comments/shares） |
| 重复查询 | 可区分不同时间观测 | ✅ 通过（`updated_at` + 平台 `observed_at` 快照） |
| 批量能力 | 确认参数与返回量 | ✅ 通过（文章按页 10 条 + cursor 续页；搜索单次返回） |
| 商业授权 | 存储/展示/加工许可 | ⏳ 待确认（需阅读服务条款/联系 Qovia） |
| 成本模型 | 可估算费用 | ✅ 见下方测算（按示例单价） |

**结论**：Qovia 满足 MVP 数据需求（账号、文章、互动指标均可获取），且商业授权已确认（可长期入库、展示、加工排名与 API 转售）。上线门槛已达成，仅剩充值/计费核对与部署。

## 4. 成本模型

\[
总成本 \approx 单次调用单价 \times 调用次数 + 服务器/数据库成本
\]

以示例单价 \$0.005/次估算（正式以账单为准）：

| 场景 | 调用估算 | 预估费用 |
|---|---|---|
| 1 账号首轮（搜索+1页文章+每篇指标） | 1 + 1 + 10 ≈ 12 次 | ≈ \$0.06 |
| 1 万账号 × 100 篇文章，指标每周更新 | 约 100 万次/周 | ≈ \$5,000/周（≈ \$2.1 万/月） |

实际应结合 A/B/C 分层降低更新频率、按预算上限降频，并核对真实报价。当前 trial 期 `meta.billed=false`，余额为 0，正式采集前必须充值。

## 5. 商业授权（已确认）

用户已确认（2026-11）：可长期入库、展示、加工排名与 API 转售。

- [x] 是否允许长期入库存储
- [x] 是否允许向注册/付费用户展示
- [x] 是否允许加工、排名与统计
- [x] 是否允许通过自有 API 转售加工结果
- [ ] 数据保留期限与删除要求（运营层面补充）
- [ ] 计费/发票/退款与 SLA（充值后核对）

## 6. 仍需人工确认

1. **充值/套餐**：确认单价、批量折扣与限额，替换 `.env` 中的预估单价常量。
2. **数据保留与 SLA**：运营层面确认保留期限、删除要求、发票与 SLA。
3. **视频号**：如需支持 `channel_search`，另行评估（不在当前 MVP）。
