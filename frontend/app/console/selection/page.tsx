import { AccountResultCard } from "@/components/console/AccountResultCard";
import { StateMessage } from "@/components/StateMessage";
import { getServerSelection } from "@/lib/api";

export default async function SelectionPage() {
  const data = await getServerSelection();
  const items = data?.items ?? [];

  if (items.length === 0) {
    return (
      <StateMessage
        title="选号清单为空"
        description="在搜索结果中点击「加入选号清单」即可收藏公众号，方便后续对比与投放评估。"
      />
    );
  }

  return (
    <section className="console-results">
      <div className="result-bar">
        <span className="result-count">
          选号清单 · 共 <b>{items.length}</b> 个公众号
        </span>
      </div>
      <div className="acct-list">
        {items.map((item) => (
          <AccountResultCard key={item.account.id} account={item.account} initialSelected />
        ))}
      </div>
    </section>
  );
}
