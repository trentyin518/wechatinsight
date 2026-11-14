"use client";

import { useCallback, useEffect, useState } from "react";

import { approveSubmission, listSubmissions, rejectSubmission } from "@/lib/clientApi";
import { toApiError } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import type { SubmissionOut } from "@/lib/types";

const SOURCE_LABELS: Record<string, string> = {
  search_engine: "搜索引擎",
  wechat_article: "公众号文章",
  friend_referral: "朋友推荐",
  media_site: "媒体平台/网站",
  other: "其他",
};

const TYPE_LABELS: Record<string, string> = {
  advertiser: "广告主",
  brand: "品牌方",
  agency: "广告媒介机构",
  public_opinion: "舆情机构",
  account_owner: "号主",
  agency4a: "4A公司",
  other: "其他",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "待审核",
  approved: "已通过",
  rejected: "已驳回",
  none: "未提交",
};

export function AdminReviews() {
  const [items, setItems] = useState<SubmissionOut[]>([]);
  const [filter, setFilter] = useState<string>("pending");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listSubmissions(filter === "all" ? undefined : filter);
      setItems(res.items);
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onApprove(id: number) {
    setBusyId(id);
    try {
      await approveSubmission(id);
      await load();
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setBusyId(null);
    }
  }

  async function onReject(id: number) {
    if (!rejectReason.trim()) {
      setError("请填写驳回原因。");
      return;
    }
    setBusyId(id);
    try {
      await rejectSubmission(id, rejectReason.trim());
      setRejectingId(null);
      setRejectReason("");
      await load();
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="admin-panel">
      <div className="toolbar">
        <div className="tabs">
          <button
            type="button"
            className={`tab ${filter === "pending" ? "tab-active" : ""}`}
            onClick={() => setFilter("pending")}
          >
            待审核
          </button>
          <button
            type="button"
            className={`tab ${filter === "all" ? "tab-active" : ""}`}
            onClick={() => setFilter("all")}
          >
            全部
          </button>
        </div>
        <button type="button" className="btn" onClick={() => void load()}>
          刷新
        </button>
      </div>

      {error ? <p className="form-error">{error}</p> : null}
      {loading ? <p className="muted">加载中…</p> : null}

      {!loading && items.length === 0 ? <p className="muted">暂无登记记录。</p> : null}

      <div className="review-list">
        {items.map((item) => (
          <div className="review-card card" key={item.id}>
            <div className="review-head">
              <div>
                <strong>{item.company_name || "（未填公司）"}</strong>
                <span className={`status-pill status-${item.status}`}>
                  {STATUS_LABELS[item.status] || item.status}
                </span>
              </div>
              <span className="muted small">{formatDateTime(item.submitted_at)}</span>
            </div>
            <div className="review-meta">
              <span>申请人：{item.contact_name || "-"}</span>
              <span>电话：{item.contact_phone || "-"}</span>
              <span>账号：{item.user_phone || item.user_display_name || item.user_id}</span>
              <span>途径：{item.source_channel ? SOURCE_LABELS[item.source_channel] || item.source_channel : "-"}{item.source_other ? `（${item.source_other}）` : ""}</span>
              <span>类型：{item.user_type ? TYPE_LABELS[item.user_type] || item.user_type : "-"}{item.user_type_other ? `（${item.user_type_other}）` : ""}</span>
            </div>
            {item.needs ? <p className="muted small">需求：{item.needs}</p> : null}
            {item.reject_reason ? <p className="muted small">驳回原因：{item.reject_reason}</p> : null}

            <div className="review-actions">
              {item.proof_id ? (
                <a
                  className="btn"
                  href={`/api/v1/onboarding/submissions/${item.id}/proof`}
                  target="_blank"
                  rel="noreferrer"
                >
                  查看证明
                </a>
              ) : null}
              {item.status === "pending" ? (
                <>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={busyId === item.id}
                    onClick={() => onApprove(item.id)}
                  >
                    通过
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={busyId === item.id}
                    onClick={() => {
                      setRejectingId(rejectingId === item.id ? null : item.id);
                      setRejectReason("");
                    }}
                  >
                    驳回
                  </button>
                </>
              ) : null}
            </div>

            {rejectingId === item.id ? (
              <div className="reject-box">
                <input
                  className="search-input"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="请填写驳回原因"
                />
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busyId === item.id}
                  onClick={() => onReject(item.id)}
                >
                  确认驳回
                </button>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
