import { AccountResultCard } from "@/components/console/AccountResultCard";
import { Pagination } from "@/components/Pagination";
import type { AccountSearchResponse } from "@/lib/types";
import { consoleQueryToSearchParams, type ConsoleQuery } from "@/lib/consoleFilters";

const COLUMN_CHIPS = [
  "西瓜指数",
  "活跃粉丝",
  "头条平均阅读",
  "头条平均点赞",
  "头条平均转发",
  "头条平均在看",
  "头条平均留言",
  "周发文数",
  "关键词匹配",
];

export function AccountResultsView({
  cq,
  data,
  selectedIds,
}: {
  cq: ConsoleQuery;
  data: AccountSearchResponse;
  selectedIds: number[];
}) {
  const selectedSet = new Set(selectedIds);
  const extraQuery = Object.fromEntries(consoleQueryToSearchParams({ ...cq, page: 1 }));

  return (
    <section className="console-results">
      {data.source === "content" ? (
        <div className="console-hint">
          未找到名称匹配的公众号，以下为发布相关内容的公众号（由内容检索匹配，资料可能不完整）。
        </div>
      ) : null}
      <div className="result-bar">
        <span className="result-count">
          找到 <b>{data.total}</b> 个公众号
        </span>
        <div className="column-chips">
          {COLUMN_CHIPS.map((label) => (
            <span className="column-chip" key={label}>{label}</span>
          ))}
        </div>
      </div>
      <div className="acct-list">
        {data.items.map((account) => (
          <AccountResultCard
            key={account.id}
            account={account}
            initialSelected={selectedSet.has(account.id)}
          />
        ))}
      </div>
      <Pagination
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        basePath="/console"
        extraQuery={extraQuery}
      />
    </section>
  );
}
