"use client";

import { useState } from "react";

interface ValueItem {
  key: string;
  title: string;
  desc: string;
  icon: React.ReactNode;
}

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

const ITEMS: ValueItem[] = [
  {
    key: "data",
    title: "数据真实性",
    desc: "指标来自第三方源真实返回并标注采集时间，帮助你甄别异常波动与水号，避免被虚高数据误导。",
    icon: (
      <svg viewBox="0 0 24 24" width="20" height="20" {...stroke}>
        <path d="M6 19V10M12 19V5M18 19v-6" />
        <path d="M4 19h16" />
      </svg>
    ),
  },
  {
    key: "match",
    title: "精准匹配",
    desc: "按账号、分类与指标快速筛选，精准匹配你的投放目标与调研需求，减少无效检索。",
    icon: (
      <svg viewBox="0 0 24 24" width="20" height="20" {...stroke}>
        <circle cx="12" cy="12" r="7" />
        <circle cx="12" cy="12" r="2.5" />
        <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
      </svg>
    ),
  },
  {
    key: "kol",
    title: "KOL洞察",
    desc: "多维度呈现账号内容与互动指标历史，洞察 KOL 的真实影响力与增长趋势，选号更有依据。",
    icon: (
      <svg viewBox="0 0 24 24" width="20" height="20" {...stroke}>
        <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" />
        <circle cx="12" cy="12" r="2.5" />
      </svg>
    ),
  },
  {
    key: "competitor",
    title: "竞品追踪",
    desc: "多维度整理竞品/对标账号的社媒平台现状及内容策略，对比品牌营销路径，找准品牌发力点。",
    icon: (
      <svg viewBox="0 0 24 24" width="20" height="20" {...stroke}>
        <path d="M3 16l5-5 4 3 6-7" />
        <path d="M15 7h4v4" />
      </svg>
    ),
  },
  {
    key: "marketing",
    title: "营销投放",
    desc: "投放前后对比数据表现，复盘转化与效果，用真实数据优化下一次投放策略。",
    icon: (
      <svg viewBox="0 0 24 24" width="20" height="20" {...stroke}>
        <path d="M4 10v4l12 5V5L4 10Z" />
        <path d="M4 10H3v4h1" />
        <path d="M18 9a3 3 0 0 1 0 6" />
      </svg>
    ),
  },
];

export function ValueCards() {
  // Default the highlighted card to "KOL洞察" to match the reference design.
  const [active, setActive] = useState("kol");

  return (
    <div className="value-cards">
      {ITEMS.map((item) => {
        const isActive = active === item.key;
        return (
          <button
            type="button"
            key={item.key}
            className={`value-card${isActive ? " value-card-active" : ""}`}
            onMouseEnter={() => setActive(item.key)}
            onFocus={() => setActive(item.key)}
            onClick={() => setActive(item.key)}
            aria-pressed={isActive}
          >
            <span className="value-icon">{item.icon}</span>
            <span className="value-title">{item.title}</span>
            <span className="value-desc">{item.desc}</span>
          </button>
        );
      })}
    </div>
  );
}
