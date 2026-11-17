"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  label: string;
  href: string;
}

interface NavGroup {
  title: string;
  tone: "green" | "orange";
  items: NavItem[];
}

const GROUPS: NavGroup[] = [
  {
    title: "公众号",
    tone: "green",
    items: [
      { label: "公众号搜索", href: "/console" },
      { label: "行业排行榜", href: "/console/rank/industry" },
      { label: "同主体排行", href: "/console/rank/subject" },
    ],
  },
  {
    title: "广告与商品",
    tone: "orange",
    items: [
      { label: "广告找号", href: "/console/ads/find" },
      { label: "广告分类", href: "/console/ads/category" },
      { label: "广告热词", href: "/console/ads/hotwords" },
    ],
  },
];

export function ConsoleSidebar() {
  const pathname = usePathname();

  return (
    <aside className="console-sidebar">
      {GROUPS.map((group) => (
        <div className="side-group" key={group.title}>
          <div className="side-group-title">
            <span className={`side-dot side-dot-${group.tone}`} />
            {group.title}
          </div>
          <div className="side-sub">
            {group.items.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`side-link${active ? " side-link-active" : ""}`}
                  aria-current={active ? "page" : undefined}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </aside>
  );
}
