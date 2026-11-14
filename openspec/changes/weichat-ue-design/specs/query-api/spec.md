# Spec Delta

## ADDED Requirements

### Requirement: 覆盖概览统计端点

系统 MUST 提供只读端点 `GET /api/v1/overview`，返回平台本地数据的聚合覆盖信息：已收录公众号数、已收录文章数、接入数据源数与最近数据更新时间，并可返回少量「最近更新账号」条目（含账号基础字段与同步时间）供首页内容区块使用。该端点 MUST 只读本地库，MUST NOT 触发第三方调用，并 MUST 复用统一错误信封。

#### Scenario: 返回真实聚合数据
- **WHEN** 调用 `GET /api/v1/overview` 且本地已有数据
- **THEN** 返回真实计数与最近更新时间，数值与本地库一致

#### Scenario: 本地无数据
- **WHEN** 调用 `GET /api/v1/overview` 但本地尚无数据
- **THEN** 计数返回 0 且 `last_updated_at` 返回 `null`、最近更新列表为空，以表达「尚无数据」

#### Scenario: 端点异常
- **WHEN** 聚合查询失败
- **THEN** 返回统一错误信封 `{ "error": { "code", "message" } }` 与合适的 HTTP 状态码，前端可据此局部降级
