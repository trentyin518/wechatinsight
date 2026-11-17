import Link from "next/link";

import { AccountResultCard } from "@/components/console/AccountResultCard";
import { StateMessage } from "@/components/StateMessage";
import { getServerSelection, getServerSimilarAccounts } from "@/lib/api";

interface SimilarPageProps {
  searchParams: Promise<{ account?: string }>;
}

function formatWan(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value >= 10000) {
    const wan = value / 10000;
    return `${Number.isInteger(wan) ? wan.toFixed(1) : wan.toFixed(2)}万`;
  }
  return value.toLocaleString("zh-CN");
}

export default async function SimilarAccountsPage({ searchParams }: SimilarPageProps) {
  const sp = await searchParams;
  const accountId = Number.parseInt(sp.account ?? "", 10);

  if (!Number.isFinite(accountId) || accountId <= 0) {
    return (
      <StateMessage
        title="缺少公众号参数"
        description="请从搜索结果或选号清单中点击「查看相似号」进入。"
      />
    );
  }

  const data = await getServerSimilarAccounts(accountId);
  if (data === null) {
    return (
      <StateMessage
        tone="error"
        title="相似号加载失败"
        description="暂时无法获取相似公众号，请稍后重试。"
      />
    );
  }

  const selection = await getServerSelection();
  const selectedIds = new Set((selection?.items ?? []).map((item) => item.account.id));

  const target = data.account;
  const items = data.items;

  return (
    <section className="console-results">
      <div className="result-bar">
        <span className="result-count">
          与「{target.name}」相似的公众号 · 共 <b>{items.length}</b> 个
        </span>
        <Link className="similar-back" href="/console">
          返回搜索
        </Link>
      </div>

      <p className="similar-hint">
        推荐依据：所属行业（{target.category || "—"}）优先，结合预估活跃粉丝量级（
        {formatWan(target.estimated_fans)}）与运营地区匹配。
      </p>

      {items.length === 0 ? (
        <StateMessage
          title="暂无相似账号"
          description="该账号目前没有同行业或量级相近的可比账号，发现更多账号后会自动匹配。"
        />
      ) : (
        <div className="acct-list">
          {items.map((account) => (
            <AccountResultCard
              key={account.id}
              account={account}
              initialSelected={selectedIds.has(account.id)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
