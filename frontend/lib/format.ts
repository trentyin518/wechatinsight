export const UNAVAILABLE = "暂不可用";

/**
 * Render a metric value. Crucially, `null`/`undefined` mean "not available"
 * and MUST NOT be shown as 0. A real 0 is displayed as "0".
 */
export function formatMetric(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return UNAVAILABLE;
  }
  return new Intl.NumberFormat("zh-CN").format(value);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return UNAVAILABLE;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return UNAVAILABLE;
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatObservedChange(
  delta: number | null | undefined,
  rate: number | null | undefined,
): string {
  if (delta === null || delta === undefined) {
    return "样本不足，暂不计算变化";
  }
  const sign = delta > 0 ? "+" : "";
  if (rate === null || rate === undefined) {
    return `${sign}${new Intl.NumberFormat("zh-CN").format(delta)}（上次为 0 或缺失，不计算变化率）`;
  }
  return `${sign}${new Intl.NumberFormat("zh-CN").format(delta)}（${rate.toFixed(1)}%）`;
}

export function providerLabel(provider: string): string {
  const map: Record<string, string> = {
    mock: "示例数据",
    qovia: "Qovia",
    xmedi: "极媒数据",
  };
  return map[provider] ?? provider;
}

export function collectionErrorLabel(code: string | null | undefined): string {
  const map: Record<string, string> = {
    DATA_SOURCE_BILLING: "数据源余额/计费异常",
    DATA_SOURCE_AUTH: "数据源鉴权失败",
    DATA_SOURCE_SCOPE_DENIED: "数据源无权限",
    DATA_SOURCE_UNAVAILABLE: "数据源暂不可用",
    DATA_SOURCE_RATE_LIMITED: "数据源限流",
    DATA_SOURCE_BAD_REQUEST: "数据源拒绝请求",
    NOT_FOUND: "数据源无此数据",
    INTERNAL_ERROR: "内部错误",
  };
  return map[code ?? ""] ?? "采集失败";
}
