# query-api Specification

## Purpose

定义对外查询 API 的统一契约，包括版本化路由、分页、稳定错误结构、健康检查，以及数据缺失、数据源不可用、限流与额度超限等降级行为，使前端只依赖自有服务而不直连第三方接口。

## Requirements

### Requirement: 版本化路由与分页

所有查询相关 API MUST 位于 `/api/v1` 下；列表接口 MUST 采用统一分页参数并返回统一的页数据结构；响应字段命名 MUST 在版本内保持稳定。

#### Scenario: 分页查询
- **WHEN** 调用列表接口并传入页码与每页数量
- **THEN** 返回包含 `items`、`page`、`page_size`（及适用时的 `total`）的统一结构

#### Scenario: 稳定路由
- **WHEN** 前端调用公众号或文章接口
- **THEN** 请求命中 `/api/v1` 下的稳定路径

### Requirement: 稳定错误结构

API MUST 使用 HTTP 状态码表达结果类别，并提供稳定的错误信封 `{ "error": { "code", "message" } }`；MUST NOT 向前端返回第三方原始错误、密钥或内部服务器信息。

#### Scenario: 记录不存在
- **WHEN** 请求不存在的资源
- **THEN** 返回 404 与对应错误码

#### Scenario: 数据源不可用
- **WHEN** 依赖的第三方数据源暂时不可用
- **THEN** 返回明确的 `DATA_SOURCE_UNAVAILABLE` 错误码与友好提示

### Requirement: 健康检查

系统 MUST 提供 `GET /health` 返回 `{ "status": "ok" }`；生产环境的依赖健康检查 MUST NOT 向未授权用户暴露敏感内部信息。

#### Scenario: 基础健康检查
- **WHEN** 请求 `/health`
- **THEN** 返回 `status: ok`

### Requirement: 降级与限流

当数据源故障时 API MUST 仍能返回本地已缓存数据而不是整体不可用；系统 MUST 支持对查询进行频率限制与额度控制，超限时返回明确错误。

#### Scenario: 第三方故障但有本地数据
- **WHEN** 第三方接口不可用但本地已有缓存结果
- **THEN** API 返回本地数据并标注数据新鲜度

#### Scenario: 超过查询额度
- **WHEN** 调用超过配置的查询额度
- **THEN** 返回额度超限错误，而不是继续产生第三方费用
