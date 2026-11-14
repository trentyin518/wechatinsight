import Link from "next/link";
import type { CSSProperties } from "react";

import { formatMetric } from "@/lib/format";

interface InsightSectionProps {
  accountsCount?: number;
  articlesCount?: number;
  metricsCount?: number;
  providersCount?: number;
}

const CHECKS = ["掌握竞品投放动态", "降低投放对接成本", "投后数据复盘跟踪"];

const SATELLITES = [
  { label: "商品", top: "16%", left: "76%", color: "#f59e0b" },
  { label: "舆情监控", top: "32%", left: "18%", color: "#3b82f6" },
  { label: "子品牌", top: "34%", left: "86%", color: "#6366f1" },
  { label: "公众号", top: "66%", left: "16%", color: "#10b981" },
  { label: "原文链接", top: "66%", left: "84%", color: "#f97316" },
  { label: "广告文案", top: "90%", left: "44%", color: "#8b5cf6" },
];

function display(value?: number): string {
  return typeof value === "number" ? formatMetric(value) : "暂无";
}

// Each label pulses with its own duration/delay/amplitude so the scaling looks
// staggered ("random") instead of all moving in lockstep. Values are derived
// from the index (deterministic, so SSR and hydration stay in sync).
function pulseStyle(index: number, top: string, left: string): CSSProperties {
  const dur = 3 + (index % 3) * 0.7;
  const delay = ((index * 0.7) % 2.8).toFixed(2);
  const pulse = (1.05 + (index % 3) * 0.035).toFixed(3);
  const style: CSSProperties & Record<string, string | number> = {
    top,
    left,
    "--dur": `${dur}s`,
    "--delay": `${delay}s`,
    "--pulse": pulse,
  };
  return style;
}

export function InsightSection({
  accountsCount,
  articlesCount,
  metricsCount,
  providersCount,
}: InsightSectionProps) {
  const stats = [
    { value: display(accountsCount), label: "已收录公众号" },
    { value: display(articlesCount), label: "已收录文章" },
    { value: display(metricsCount), label: "指标快照" },
    { value: display(providersCount), label: "已接入数据源" },
  ];

  return (
    <section className="section">
      <div className="insight-head">
        <h2 className="insight-title">洞察品牌营销数据</h2>
        <p className="insight-sub">
          数据赋能品牌方精准营销，掌握竞品投放动态、降低投放成本、投后数据跟踪
        </p>
      </div>

      <div className="insight-body">
        <div className="insight-left">
          <div className="insight-stats">
            {stats.map((s) => (
              <div className="insight-stat" key={s.label}>
                <b>{s.value}</b>
                <span>{s.label}</span>
              </div>
            ))}
          </div>

          <div className="insight-panel card">
            <h3>数据赋能品牌方精准营销</h3>
            <ul className="check-list">
              {CHECKS.map((c) => (
                <li key={c}>
                  <span className="check-mark" aria-hidden>
                    ✓
                  </span>
                  {c}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="orbit">
          <div className="orbit-ring orbit-ring-1" />
          <div className="orbit-ring orbit-ring-2" />
          <div className="orbit-ring orbit-ring-3" />
          <Link className="orbit-center" href="/search?q=" aria-label="搜索公众号">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round">
              <path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9 6.8 19.1l1-5.8L3.5 9.2l5.9-.9L12 3Z" />
            </svg>
            <span>品牌</span>
          </Link>
          {SATELLITES.map((s, index) => (
            <Link
              className="orbit-chip"
              key={s.label}
              href={`/search?q=${encodeURIComponent(s.label)}`}
              style={pulseStyle(index, s.top, s.left)}
            >
              <i style={{ background: s.color }} />
              {s.label}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
