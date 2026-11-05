import { formatMetric } from "@/lib/format";

export interface MetricValues {
  read_count: number | null;
  like_count: number | null;
  wow_count: number | null;
  comment_count: number | null;
  share_count: number | null;
}

const FIELDS: { key: keyof MetricValues; label: string }[] = [
  { key: "read_count", label: "阅读量" },
  { key: "like_count", label: "点赞量" },
  { key: "wow_count", label: "在看数" },
  { key: "comment_count", label: "评论数" },
  { key: "share_count", label: "分享数" },
];

export function MetricGrid({ metrics }: { metrics: MetricValues | null }) {
  return (
    <dl className="metric-grid">
      {FIELDS.map((field) => (
        <div className="metric" key={field.key}>
          <dt>{field.label}</dt>
          <dd>{formatMetric(metrics ? metrics[field.key] : null)}</dd>
        </div>
      ))}
    </dl>
  );
}
