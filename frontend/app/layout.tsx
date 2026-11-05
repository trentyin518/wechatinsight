import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "微信洞察 · 公众号数据分析",
  description:
    "面向内容创作者与运营者的微信公众号数据查询平台：搜索公众号、浏览历史文章与可获取的互动指标。",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="site-header">
          <div className="container header-inner">
            <Link className="brand" href="/">
              微信洞察<span className="brand-dot">·</span>
            </Link>
            <nav className="nav">
              <Link href="/">搜索</Link>
            </nav>
          </div>
        </header>
        <main className="container main">{children}</main>
        <footer className="site-footer">
          <div className="container">
            数据来源以第三方供应商实际提供为准，平台仅展示已收录账号并标注采集时间。
          </div>
        </footer>
      </body>
    </html>
  );
}
