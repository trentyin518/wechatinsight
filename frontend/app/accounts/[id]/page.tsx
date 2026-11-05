import Link from "next/link";

import { DataProvenance } from "@/components/DataProvenance";
import { Pagination } from "@/components/Pagination";
import { StateMessage } from "@/components/StateMessage";
import { ApiError, getAccount, getAccountArticles } from "@/lib/api";
import { formatMetric } from "@/lib/format";

interface AccountPageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string }>;
}

export default async function AccountPage({ params, searchParams }: AccountPageProps) {
  const { id } = await params;
  const sp = await searchParams;
  const page = Math.max(1, Number.parseInt(sp.page ?? "1", 10) || 1);

  try {
    const [account, articles] = await Promise.all([
      getAccount(id),
      getAccountArticles(id, page),
    ]);

    return (
      <>
        <div className="breadcrumb">
          <Link href="/">首页</Link> / <Link href={`/search?q=${encodeURIComponent(account.name)}`}>搜索</Link> /{" "}
          {account.name}
        </div>

        <section className="profile-head">
          <div className="avatar" aria-hidden>
            {account.name.slice(0, 1)}
          </div>
          <div>
            <h1>{account.name}</h1>
            {account.wechat_id ? <p className="muted small">微信号：{account.wechat_id}</p> : null}
            {account.description ? <p className="muted">{account.description}</p> : null}
            <div className="meta-row">
              <DataProvenance provider={account.provider} observedAt={account.last_synced_at} label="最近同步" />
              {account.verification_subject ? <span>认证主体：{account.verification_subject}</span> : null}
              {account.account_type ? <span>账号类型：{account.account_type}</span> : null}
            </div>
          </div>
        </section>

        <section className="section">
          <h2 className="section-title">历史文章（平台已收录 {articles.total} 篇）</h2>
          {articles.items.length === 0 ? (
            <StateMessage
              title="暂无历史文章"
              description="该账号的文章尚未同步，等待 Worker 更新后再查看。"
            />
          ) : (
            <div className="list">
              {articles.items.map((article) => (
                <Link className="list-item" key={article.id} href={`/articles/${article.id}`}>
                  <h3>{article.title}</h3>
                  <div className="list-meta">
                    <span>阅读 {formatMetric(article.read_count)}</span>
                    <span>点赞 {formatMetric(article.like_count)}</span>
                    <span>在看 {formatMetric(article.wow_count)}</span>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <DataProvenance
                      provider={article.provider}
                      observedAt={article.metrics_observed_at}
                      label="指标采集"
                    />
                  </div>
                </Link>
              ))}
            </div>
          )}
          <Pagination
            page={articles.page}
            pageSize={articles.page_size}
            total={articles.total}
            basePath={`/accounts/${id}`}
          />
        </section>
      </>
    );
  } catch (error) {
    const apiError = error as ApiError;
    if (apiError.code === "NOT_FOUND") {
      return <StateMessage tone="error" title="公众号不存在" description="该公众号不在平台收录范围内。" />;
    }
    return (
      <StateMessage
        tone="error"
        title="加载失败"
        description={
          apiError.code === "DATA_SOURCE_UNAVAILABLE"
            ? "数据源暂时不可用，请稍后重试。"
            : apiError.message
        }
      />
    );
  }
}
