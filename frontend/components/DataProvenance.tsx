import { collectionErrorLabel, formatDateTime, providerLabel } from "@/lib/format";

type CollectionState = "idle" | "collecting" | "failed" | "empty" | "collected";

interface DataProvenanceProps {
  provider: string;
  observedAt?: string | null;
  label?: string;
  /** Richer enrichment status from the backend; drives an explicit label. */
  state?: CollectionState | string | null;
  /** Raw error code, shown as a friendly reason when state === "failed". */
  error?: string | null;
  /** Legacy boolean; only used to derive state when `state` is absent. */
  collecting?: boolean;
}

export function DataProvenance({
  provider,
  observedAt,
  label,
  state,
  error,
  collecting,
}: DataProvenanceProps) {
  const resolved: CollectionState =
    (state as CollectionState) ??
    (collecting && !observedAt ? "collecting" : observedAt ? "collected" : "idle");

  let body: React.ReactNode;
  if (resolved === "collecting") {
    body = <span className="provenance-collecting">采集中…</span>;
  } else if (resolved === "failed") {
    body = <span className="provenance-failed">采集失败：{collectionErrorLabel(error)}</span>;
  } else if (resolved === "empty") {
    body = <span className="provenance-empty">数据源无公开文章</span>;
  } else if (resolved === "idle") {
    body = (
      <>
        {label ? `${label}：` : "采集于 "}
        {formatDateTime(observedAt)}
      </>
    );
  } else {
    body = (
      <>
        {label ? `${label}：` : "采集于 "}
        {formatDateTime(observedAt)}
      </>
    );
  }

  return (
    <span className="provenance" title="数据来源与采集时间">
      <span className="badge">{providerLabel(provider)}</span>
      <span className="provenance-text">{body}</span>
    </span>
  );
}
