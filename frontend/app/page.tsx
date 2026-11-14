import Link from "next/link";

import { DataProvenance } from "@/components/DataProvenance";
import { InsightSection } from "@/components/InsightSection";
import { ValueCards } from "@/components/ValueCards";
import { getServerCurrentUser, getServerOverview } from "@/lib/api";

const CATEGORIES = ["科技", "财经", "生活方式", "教育", "健康"];

export default async function HomePage() {
  const [overview, user] = await Promise.all([getServerOverview(), getServerCurrentUser()]);
  const recents = overview?.recent_accounts ?? [];

  return (
    <>
      <section className="hero-dark">
        <div className="hero-dark-inner">
          <h1>新媒体广告投放及品牌营销服务</h1>
          <p className="hero-dark-sub">
            海量KOL资源对接，数据赋能品牌方精准营销，让广告投放更高效
          </p>
          {user ? (
            <a className="btn-use" href="#ad-value">
              立即使用
            </a>
          ) : (
            <Link className="btn-use" href="/login">
              立即使用
            </Link>
          )}
        </div>
        <div className="hero-tabs">
          <a className="hero-tab" href="#ad-value">
            <span className="hero-tab-icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round">
                <rect x="4" y="4" width="16" height="16" rx="4" />
                <path d="M12 8l1.3 2.6 2.9.4-2.1 2 .5 2.9L12 14.7 9.4 15.9l.5-2.9-2.1-2 2.9-.4L12 8Z" />
              </svg>
            </span>
            <span>投放评估</span>
          </a>
          <a className="hero-tab" href="#insight">
            <span className="hero-tab-icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round">
                <rect x="3" y="4" width="18" height="13" rx="2" />
                <path d="M7 13l3-3 2.5 2 3.5-4" />
                <path d="M9 21h6M12 17v4" />
              </svg>
            </span>
            <span>洞察营销</span>
          </a>
          <span className="hero-tab hero-tab-disabled" aria-disabled="true">
            <span className="hero-tab-icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round">
                <circle cx="12" cy="12" r="7" />
                <circle cx="12" cy="12" r="2" />
                <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
              </svg>
            </span>
            <span>行业聚焦</span>
          </span>
        </div>
      </section>

      <section className="section" id="ad-value">
        <div className="value-head">
          <h2 className="value-title-h">社媒账号广告投放价值评估</h2>
          <p className="value-sub">
            提供阅读、点赞量分钟级监测报告、为你快速甄别水号、避免投放踩坑
          </p>
        </div>
        <ValueCards />
      </section>

      <InsightSection
        accountsCount={overview?.accounts_count}
        articlesCount={overview?.articles_count}
        metricsCount={overview?.metrics_count}
        providersCount={overview?.providers_count}
      />

      <section className="section" id="categories">
        <h2 className="section-title">按分类浏览</h2>
        <div className="chip-row">
          {CATEGORIES.map((category) => (
            <Link className="chip" key={category} href={`/search?q=${encodeURIComponent(category)}`}>
              {category}
            </Link>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <h2 className="section-title">最近更新账号</h2>
        </div>
        {recents.length === 0 ? (
          <div className="notice">暂无可展示的账号，登录后可搜索并查看已收录账号。</div>
        ) : (
          <div className="card-grid">
            {recents.map((account) => (
              <Link className="card" key={account.id} href={`/accounts/${account.id}`}>
                <h3>{account.name}</h3>
                {account.wechat_id ? (
                  <p className="muted small">微信号：{account.wechat_id}</p>
                ) : null}
                {account.description ? (
                  <p className="muted small">{account.description}</p>
                ) : null}
                <DataProvenance provider={account.provider} observedAt={account.last_synced_at} />
              </Link>
            ))}
          </div>
        )}
      </section>

      <div className="notice">
        <strong>数据说明：</strong>
        本平台搜索与账号数据来自本地已收录账号，未命中时进行一次受控的第三方查询；所有指标以第三方数据源实际返回为准，
        缺失即标注，绝不虚构。部分数据功能需登录并通过信息登记审核后使用。
      </div>
    </>
  );
}
