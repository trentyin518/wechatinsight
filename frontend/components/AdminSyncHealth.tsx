"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getSyncHealth, triggerSyncDrain } from "@/lib/clientApi";
import { toApiError } from "@/lib/errors";
import { collectionErrorLabel, formatDateTime } from "@/lib/format";
import type { SyncHealth } from "@/lib/types";

const STATUS_ORDER = ["PENDING", "RUNNING", "RETRY", "SUCCESS", "FAILED"] as const;
const STATUS_LABEL: Record<string, string> = {
  PENDING: "排队",
  RUNNING: "运行中",
  RETRY: "重试中",
  SUCCESS: "成功",
  FAILED: "失败",
};

function ageLabel(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds} 秒`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时`;
  return `${Math.floor(seconds / 86400)} 天`;
}

function terminalCount(d: SyncHealth): number {
  return (d.status_counts.SUCCESS ?? 0) + (d.status_counts.FAILED ?? 0);
}

interface DrainProgress {
  baseline: number; // terminal (SUCCESS+FAILED) count when the drain started
  target: number; // how many jobs this drain will process at most
}

export function AdminSyncHealth() {
  const [data, setData] = useState<SyncHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [progress, setProgress] = useState<DrainProgress | null>(null);
  const [polling, setPolling] = useState(false);
  const progressRef = useRef<DrainProgress | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getSyncHealth());
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Live polling while a drain is running: refresh health every 2.5s and stop
  // once the drain's target is reached (or the queue empties).
  useEffect(() => {
    if (!polling) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const d = await getSyncHealth();
        if (cancelled) return;
        setData(d);
        const p = progressRef.current;
        if (p) {
          const done = Math.max(0, terminalCount(d) - p.baseline);
          if (done >= p.target || d.pending_count === 0) {
            setPolling(false);
          }
        }
      } catch {
        // Keep polling through transient errors; a later tick will recover.
      }
    };
    void tick();
    const id = window.setInterval(tick, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [polling]);

  const drain = useCallback(async () => {
    if (!data || data.pending_count <= 0) return;
    const cap = Math.min(200, data.pending_count);
    const ok = window.confirm(
      `将消费最多 ${cap} 个排队任务，每个数据源调用约 $0.005，可能产生费用。\n` +
        `可在「用量」页查看消耗。确定开始消费吗？`,
    );
    if (!ok) return;
    setSubmitting(true);
    setNotice(null);
    const baseline = terminalCount(data);
    try {
      const res = await triggerSyncDrain(200);
      setNotice(res.message);
      if (res.scheduled) {
        progressRef.current = { baseline, target: res.max_jobs };
        setProgress({ baseline, target: res.max_jobs });
        setPolling(true);
      }
    } catch (err) {
      setNotice(toApiError(err).message);
    } finally {
      setSubmitting(false);
    }
  }, [data]);

  const processed =
    data && progress ? Math.max(0, terminalCount(data) - progress.baseline) : 0;
  const pct =
    progress && progress.target > 0
      ? Math.min(100, Math.round((processed / progress.target) * 100))
      : 0;

  return (
    <div className="admin-panel">
      <div className="toolbar">
        <h2 style={{ margin: 0 }}>同步任务健康度</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="btn"
            onClick={() => void drain()}
            disabled={submitting || !data || data.pending_count <= 0}
            title={
              data && data.pending_count > 0
                ? `后台消费最多 ${Math.min(200, data.pending_count)} 个排队任务`
                : "没有排队任务"
            }
          >
            {submitting
              ? "提交中…"
              : `消费积压${data && data.pending_count > 0 ? `（${data.pending_count}）` : ""}`}
          </button>
          <button type="button" className="btn" onClick={() => void load()}>
            刷新
          </button>
        </div>
      </div>

      {notice ? (
        <p className="muted small" style={{ marginTop: 8 }}>
          {notice}
        </p>
      ) : null}
      {error ? <p className="form-error">{error}</p> : null}
      {loading && !data ? <p className="muted">加载中…</p> : null}

      {data ? (
        <>
          {progress ? (
            <div className="card" style={{ marginBottom: 18 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  marginBottom: 8,
                  gap: 10,
                }}
              >
                <strong>
                  {polling ? "后台消费中…" : "本次消费"}
                  {processed >= progress.target ? "（已完成）" : ""}
                </strong>
                <span className="muted small">
                  已处理 ~{Math.min(processed, progress.target)} / {progress.target}
                  {data.pending_count ? ` · 剩余排队 ${data.pending_count}` : ""}
                </span>
              </div>
              <div
                style={{
                  height: 10,
                  borderRadius: 999,
                  background: "var(--border)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${pct}%`,
                    background: "#2e7d32",
                    transition: "width .4s ease",
                  }}
                />
              </div>
            </div>
          ) : null}

          {data.worker_hint ? (
            <div
              className="card"
              style={{ borderColor: "#d9a74f", background: "#fdf8ed", marginBottom: 18 }}
            >
              <strong style={{ color: "#a4720c" }}>可能卡住了</strong>
              <p className="muted small" style={{ margin: "8px 0 0" }}>
                {data.worker_hint}
              </p>
            </div>
          ) : null}

          <div className="stat-band">
            {STATUS_ORDER.map((status) => (
              <div className="stat" key={status}>
                <div className="stat-value">{data.status_counts[status] ?? 0}</div>
                <div className="stat-label">{STATUS_LABEL[status]}</div>
              </div>
            ))}
          </div>

          <div className="stat-band" style={{ marginTop: 12 }}>
            <div className="stat">
              <div className="stat-value">{data.total_jobs}</div>
              <div className="stat-label">任务总数</div>
            </div>
            <div className="stat">
              <div className="stat-value">{ageLabel(data.pending_oldest_age_seconds)}</div>
              <div className="stat-label">最久排队时长</div>
            </div>
            <div className="stat">
              <div className="stat-value" style={{ color: "#2e7d32" }}>
                {data.success_24h}
              </div>
              <div className="stat-label">24h 成功</div>
            </div>
            <div className="stat">
              <div className="stat-value" style={{ color: "#c9302c" }}>
                {data.failed_24h}
              </div>
              <div className="stat-label">24h 失败</div>
            </div>
          </div>

          <div className="card" style={{ marginTop: 18 }}>
            <h3 style={{ marginTop: 0 }}>失败原因 Top</h3>
            {data.failed_reasons.length === 0 ? (
              <p className="muted">没有失败任务。</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {data.failed_reasons.map((r, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 10,
                      fontSize: 13,
                      borderBottom: "1px solid var(--border)",
                      paddingBottom: 6,
                    }}
                  >
                    <span>{collectionErrorLabel(r.error_code)}</span>
                    <span className="muted small">{r.error_code ?? "—"}</span>
                    <span style={{ minWidth: 60, textAlign: "right" }}>{r.count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card" style={{ marginTop: 18 }}>
            <h3 style={{ marginTop: 0 }}>最近失败任务</h3>
            {data.recent_failed.length === 0 ? (
              <p className="muted">暂无失败记录。</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {data.recent_failed.map((j) => (
                  <div
                    key={j.id}
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 8,
                      fontSize: 13,
                      borderBottom: "1px solid var(--border)",
                      paddingBottom: 6,
                    }}
                  >
                    <span className="muted small" style={{ minWidth: 150 }}>
                      {formatDateTime(j.updated_at)}
                    </span>
                    <span style={{ minWidth: 120 }}>
                      {j.job_type} · {j.target_type}
                      {j.target_id !== null ? `#${j.target_id}` : ""}
                    </span>
                    <span className="status-pill status-rejected">
                      {collectionErrorLabel(j.error_code)}
                    </span>
                    {j.error_message ? (
                      <span className="muted small" style={{ flexBasis: "100%" }}>
                        {j.error_message}
                      </span>
                    ) : null}
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
