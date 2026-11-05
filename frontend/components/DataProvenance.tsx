import { formatDateTime, providerLabel } from "@/lib/format";

interface DataProvenanceProps {
  provider: string;
  observedAt?: string | null;
  label?: string;
}

export function DataProvenance({ provider, observedAt, label }: DataProvenanceProps) {
  return (
    <span className="provenance" title="数据来源与采集时间">
      <span className="badge">{providerLabel(provider)}</span>
      <span className="provenance-text">
        {label ? `${label}：` : "采集于 "}
        {formatDateTime(observedAt)}
      </span>
    </span>
  );
}
