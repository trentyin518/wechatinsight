import Link from "next/link";

import { DataProvenance } from "@/components/DataProvenance";
import { InsightSection } from "@/components/InsightSection";
import { ValueCards } from "@/components/ValueCards";
import { getServerOverview } from "@/lib/api";

const CATEGORIES = ["科技", "财经", "生活方式", "教育", "健康"];

export default async function HomePage() {
  const overview = await getServerOverview();
  const recents = overview?.recent_accounts ?? [];

  return (
    <>
      <section className="landing-hero">
        <div className="landing-badges">
          <span className="pill">微信公众号数据</span>
          <span className="pill">真实可溯源</span>
          <span className="pill">缺失不等于 0</span>
        </div>
        <h1>搜索公众号，查看真实可获取的数据</h1>
        <p className="landing-sub">
          查询公众号资料与历史文章，浏览数据源实际提供的阅读量、点赞量与在看数。平台只展示已收录账号，
          并明确标注数据来源与采集时间——缺失的指标不会显示为 0。
        </p>
        <div className="landing-cta">
          <Link className="btn btn-primary" href="/login">
            登录 / 注册
          </Link>
          <Link className="btn" href="#categories">
            按分类浏览
          </Link>
        </div>
        <p className="muted small" style={{ marginTop: 12 }}>
          搜索与数据功能需登录并通过信息登记审核后使用。
        </p>
      </section>

      <section className="section">
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
