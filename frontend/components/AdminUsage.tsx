"use client";

import { useCallback, useEffect, useState } from "react";

import { getUsageOverview } from "@/lib/clientApi";
import { toApiError } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import type { UsageOverview } from "@/lib/types";

function money(value: number | null, digits = 3): string {
  if (value === null || value === undefined) return "—";
  return `$${value.toFixed(digits)}`;
}

export function AdminUsage() {
  const [data, setData] = useState<UsageOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getUsageOverview());
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const warns: string[] = [];
  if (data) {
    if (data.over_daily_budget) {
      warns.push(
        `今日消耗已达/超日预算（${money(data.daily_budget_usd, 2)}），付费调用已被自动暂停。`,
      );
    }
    if (data.over_monthly_budget) {
      warns.push(`本月消耗已达/超月预算（${money(data.monthly_budget_usd, 2)}）。`);
    }
    if (data.balance_usd !== null && data.balance_usd <= 1) {
      warns.push(`数据源余额偏低（${money(data.balance_usd)}），请及时充值以免冷启动搜索失败。`);
    }
  }

  return (
    <div className="admin-panel">
      <div className="toolbar">
        <h2 style={{ margin: 0 }}>平台用量与预算</h2>
        <button type="button" className="btn" onClick={() => void load()}>
          刷新
        </button>
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {loading && !data ? <p className="muted">加载中…</p> : null}

      {data ? (
        <>
          {warns.length > 0 ? (
            <div
              className="card"
              style={{ borderColor: "#d9534f", background: "#fdf3f3", marginBottom: 18 }}
            >
              <strong style={{ color: "#c9302c" }}>成本告警</strong>
              <ul className="muted small" style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                {warns.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="stat-band">
            <div className="stat">
              <div className="stat-value">
                {data.balance_usd === null ? "—" : money(data.balance_usd)}
              </div>
              <div className="stat-label">
                数据源余额{data.plan ? ` · ${data.plan}` : ""}
              </div>
            </div>
            <div className="stat">
              <div className="stat-value">{money(data.daily_cost_usd)}</div>
              <div className="stat-label">今日消耗 / 预算 {money(data.daily_budget_usd, 2)}</div>
            </div>
            <div className="stat">
              <div className="stat-value">{money(data.monthly_cost_usd)}</div>
              <div className="stat-label">
                本月消耗 / 预算 {money(data.monthly_budget_usd, 2)}
              </div>
            </div>
            <div className="stat">
              <div className="stat-value">{data.today_calls}</div>
              <div className="stat-label">今日调用次数</div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 18 }}>
            <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
              <span
                className={`status-pill ${data.collection_enabled ? "status-approved" : "status-rejected"}`}
              >
                后台采集：{data.collection_enabled ? "开" : "关"}
              </span>
              <span
                className={`status-pill ${data.search_retry_enabled ? "status-approved" : "status-rejected"}`}
              >
                搜索重试：{data.search_retry_enabled ? "开" : "关"}
              </span>
            </div>
            <p className="muted small" style={{ marginTop: 10 }}>
              默认关闭后台采集与重试。网站仅在用户搜索本地未命中时才调用数据源，并受预算上限保护，最大限度节省调用。
            </p>
          </div>

          <div className="card" style={{ marginTop: 18 }}>
            <h3 style={{ marginTop: 0 }}>最近调用</h3>
            {data.recent.length === 0 ? (
              <p className="muted">暂无调用记录。</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {data.recent.map((c, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 10,
                      fontSize: 13,
                      borderBottom: "1px solid var(--border)",
                      paddingBottom: 6,
                    }}
                  >
                    <span className="muted small" style={{ minWidth: 150 }}>
                      {formatDateTime(c.request_time)}
                    </span>
                    <span style={{ flex: 1, marginLeft: 8 }}>{c.endpoint}</span>
                    <span
                      className={`status-pill ${c.success ? "status-approved" : "status-rejected"}`}
                    >
                      {c.success ? "成功" : "失败"}
                    </span>
                    <span style={{ minWidth: 70, textAlign: "right" }}>
                      {money(c.estimated_cost)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
