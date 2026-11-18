import { formatDateTime, providerLabel } from "@/lib/format";

interface DataProvenanceProps {
  provider: string;
  observedAt?: string | null;
  label?: string;
  /** A demand-driven collection job is queued/running for this account. */
  collecting?: boolean;
}

export function DataProvenance({ provider, observedAt, label, collecting }: DataProvenanceProps) {
  const pending = collecting && !observedAt;
  return (
    <span className="provenance" title="数据来源与采集时间">
      <span className="badge">{providerLabel(provider)}</span>
      <span className="provenance-text">
        {pending ? (
          <span className="provenance-collecting">采集中…</span>
        ) : (
          <>
            {label ? `${label}：` : "采集于 "}
            {formatDateTime(observedAt)}
          </>
        )}
      </span>
    </span>
  );
}
