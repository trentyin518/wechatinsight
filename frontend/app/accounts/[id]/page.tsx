import Link from "next/link";

import { DataProvenance } from "@/components/DataProvenance";
import { Pagination } from "@/components/Pagination";
import { CollectingAutoRefresh } from "@/components/console/CollectingAutoRefresh";
import { SelectionButton } from "@/components/console/SelectionButton";
import { RecollectButton } from "@/components/console/RecollectButton";
import { StateMessage } from "@/components/StateMessage";
import {
  ApiError,
  getAccount,
  getAccountArticles,
  getServerSelection,
  getServerSimilarAccounts,
} from "@/lib/api";
import { formatMetric } from "@/lib/format";
import { requireApprovedOrRedirect } from "@/lib/guard";

interface AccountPageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string }>;
}

function formatWan(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value >= 10000) {
    const wan = value / 10000;
    return `${Number.isInteger(wan) ? wan.toFixed(1) : wan.toFixed(2)}万`;
  }
  return value.toLocaleString("zh-CN");
}

export default async function AccountPage({ params, searchParams }: AccountPageProps) {
  await requireApprovedOrRedirect();
  const { id } = await params;
  const sp = await searchParams;
  const page = Math.max(1, Number.parseInt(sp.page ?? "1", 10) || 1);
  const accountIdNum = Number.parseInt(id, 10);

  try {
    const [account, articles, similar, selection] = await Promise.all([
      getAccount(id),
      getAccountArticles(id, page),
      Number.isFinite(accountIdNum) ? getServerSimilarAccounts(accountIdNum) : Promise.resolve(null),
      getServerSelection(),
    ]);

    const selectedIds = new Set((selection?.items ?? []).map((item) => item.account.id));
    const similarItems = similar?.items ?? [];

    const typeLabel =
      account.account_type === "subscription"
        ? "订阅号"
        : account.account_type === "service"
          ? "服务号"
          : account.account_type;

    const stats: { label: string; value: string }[] = [
      { label: "西瓜指数", value: account.xigua_index != null ? account.xigua_index.toFixed(1) : "—" },
      { label: "预估活跃粉丝", value: formatWan(account.estimated_fans) },
      { label: "发文篇数", value: formatMetric(account.article_count) },
      { label: "头条平均阅读", value: formatWan(account.avg_read) },
      { label: "头条平均点赞", value: formatMetric(account.avg_like) },
      { label: "头条平均转发", value: formatMetric(account.avg_share) },
      { label: "头条平均在看", value: formatMetric(account.avg_wow) },
      { label: "头条平均留言", value: formatMetric(account.avg_comment) },
    ];

    return (
      <>
        <CollectingAutoRefresh active={Boolean(account.collecting)} />
        <div className="breadcrumb">
          <Link href="/console">控制台</Link> /{" "}
          <Link href={`/console?q=${encodeURIComponent(account.name)}`}>搜索</Link> / {account.name}
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
              <DataProvenance provider={account.provider} observedAt={account.last_synced_at} label="最近同步" state={account.collection_state} error={account.collection_error} collecting={account.collecting} />
              {account.verification_subject ? <span>认证主体：{account.verification_subject}</span> : null}
              {typeLabel ? <span>账号类型：{typeLabel}</span> : null}
              {account.category ? <span>所属行业：{account.category}</span> : null}
              {account.region ? <span>运营地区：{account.region}</span> : null}
              {account.is_original ? <span className="tag tag-green">原创号</span> : null}
              {account.has_video ? <span className="tag tag-blue">视频号</span> : null}
            </div>
            <div className="profile-actions">
              <SelectionButton accountId={account.id} initialSelected={selectedIds.has(account.id)} />
              <RecollectButton accountId={account.id} />
              <Link className="btn" href={`/console/similar?account=${account.id}`}>
                查看相似号
              </Link>
              <Link className="btn" href={`/console?q=${encodeURIComponent(account.name)}`}>
                返回搜索
              </Link>
            </div>
          </div>
        </section>

        <section className="section">
          <div className="acct-stats acct-stats-wide">
            {stats.map((item) => (
              <div className="acct-stat" key={item.label}>
                <b>{item.value}</b>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
          {account.last_synced_at && !account.article_count ? (
            <p className="muted small" style={{ marginTop: 12 }}>
              该号已在数据源完成采集，但暂无可公开文章，故「发文篇数 / 头条平均*」指标不可用。
            </p>
          ) : null}
          {account.estimated_price != null ? (
            <p className="muted small" style={{ marginTop: 12 }}>
              预估广告报价：<b>¥{formatWan(account.estimated_price)} 起</b>
            </p>
          ) : null}
        </section>

        {similarItems.length > 0 ? (
          <section className="section">
            <div className="section-head">
              <h2 className="section-title">相似公众号（同行业 · 相近量级）</h2>
              <Link className="section-more" href={`/console/similar?account=${account.id}`}>
                查看更多
              </Link>
            </div>
            <div className="list">
              {similarItems.slice(0, 4).map((item) => (
                <Link className="list-item" key={item.id} href={`/accounts/${item.id}`}>
                  <h3>{item.name}</h3>
                  <div className="list-meta">
                    <span>{item.category || "—"}</span>
                    <span>预估活跃粉丝 {formatWan(item.estimated_fans)}</span>
                    <span>头条平均阅读 {formatWan(item.avg_read)}</span>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        ) : null}

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
