import Link from "next/link";

import { DataProvenance } from "@/components/DataProvenance";
import { SelectionButton } from "@/components/console/SelectionButton";
import type { AccountOut } from "@/lib/types";

function formatWan(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value >= 10000) {
    const wan = value / 10000;
    return `${Number.isInteger(wan) ? wan.toFixed(1) : wan.toFixed(2)}万`;
  }
  return value.toLocaleString("zh-CN");
}

function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString("zh-CN");
}

function formatOne(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(1);
}

export function AccountResultCard({
  account,
  initialSelected = false,
}: {
  account: AccountOut;
  initialSelected?: boolean;
}) {
  const initial = account.name.trim().slice(0, 1) || "号";
  const typeLabel =
    account.account_type === "subscription"
      ? "订阅号"
      : account.account_type === "service"
        ? "服务号"
        : account.account_type;

  const stats: { label: string; value: string }[] = [
    { label: "西瓜指数", value: formatOne(account.xigua_index) },
    { label: "预估活跃粉丝", value: formatWan(account.estimated_fans) },
    { label: "发文篇数", value: formatInt(account.article_count) },
    { label: "头条平均阅读", value: formatWan(account.avg_read) },
    { label: "头条平均点赞", value: formatInt(account.avg_like) },
    { label: "头条平均转发", value: formatInt(account.avg_share) },
    { label: "头条平均在看", value: formatInt(account.avg_wow) },
    { label: "头条平均留言", value: formatInt(account.avg_comment) },
  ];

  return (
    <article className="acct-card">
      <div className="acct-main">
        <div className="acct-head">
          <div className="acct-avatar">
            {account.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={account.avatar_url} alt="" />
            ) : (
              <span>{initial}</span>
            )}
          </div>
          <div className="acct-headinfo">
            <div className="acct-name-row">
              <h3 className="acct-name">{account.name}</h3>
              {account.wechat_id ? <span className="acct-id">{account.wechat_id}</span> : null}
            </div>
            <div className="acct-tags">
              {typeLabel ? <span className="tag tag-green">{typeLabel}</span> : null}
              {account.is_original ? <span className="tag tag-green">原创号</span> : null}
              {account.has_video ? <span className="tag tag-blue">视频号</span> : null}
              <span className="tag tag-blue">数据源 · {account.provider}</span>
            </div>
          </div>
        </div>

        <div className="acct-meta">
          <span>账号主体：{account.verification_subject || "—"}</span>
          <span className="acct-meta-sep">·</span>
          <span>所属行业：{account.category || "—"}</span>
          <span className="acct-meta-sep">·</span>
          <span>运营地区：{account.region || "—"}</span>
        </div>
        <p className="acct-desc">简介：{account.description || "暂无简介"}</p>

        <div className="acct-stats">
          {stats.map((item) => (
            <div className="acct-stat" key={item.label}>
              <b>{item.value}</b>
              <span>{item.label}</span>
            </div>
          ))}
        </div>

        <div className="acct-provenance">
          <DataProvenance provider={account.provider} observedAt={account.last_synced_at} />
        </div>
      </div>

      <aside className="acct-aside">
        <div className="acct-quote">
          <strong>预估广告报价</strong>
          {account.estimated_price != null ? (
            <span className="acct-quote-price">¥{formatWan(account.estimated_price)} 起</span>
          ) : (
            <span className="acct-quote-lock">限专业版及以上会员查看</span>
          )}
        </div>
        <Link className="acct-btn acct-btn-primary" href={`/accounts/${account.id}`}>
          查看详情
        </Link>
        <Link className="acct-btn" href={`/console/similar?account=${account.id}`}>
          查看相似号
        </Link>
        <SelectionButton accountId={account.id} initialSelected={initialSelected} />
      </aside>
    </article>
  );
}
