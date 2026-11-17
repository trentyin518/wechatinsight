import { AccountResultCard } from "@/components/console/AccountResultCard";
import { ArticleTable } from "@/components/console/ArticleTable";
import { ArticleToolbar } from "@/components/console/ArticleToolbar";
import { SearchFilters } from "@/components/console/SearchFilters";
import { Pagination } from "@/components/Pagination";
import { StateMessage } from "@/components/StateMessage";
import { ApiError, getServerSelection, searchAccountsWithFilters, searchArticles } from "@/lib/api";
import {
  consoleQueryToApiParams,
  consoleQueryToArticleApiParams,
  consoleQueryToSearchParams,
  parseConsoleQuery,
  type ConsoleQuery,
} from "@/lib/consoleFilters";

interface ConsolePageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

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

function hasCriteria(cq: ConsoleQuery): boolean {
  const nameMode = Boolean(
    cq.q ||
      cq.category ||
      cq.fans ||
      cq.read ||
      cq.price ||
      cq.ads ||
      cq.xigua ||
      cq.region ||
      cq.recent ||
      cq.original ||
      cq.service ||
      cq.video,
  );
  const articleMode = cq.attr !== "all" || cq.dedup || cq.time !== "0";
  return nameMode || articleMode;
}

export default async function ConsoleSearchPage({ searchParams }: ConsolePageProps) {
  const sp = await searchParams;
  const cq = parseConsoleQuery(sp);
  const selection = await getServerSelection();
  const selectedIds = new Set((selection?.items ?? []).map((item) => item.account.id));

  return (
    <>
      <SearchFilters initial={cq} />
      {!hasCriteria(cq) ? (
        <div className="console-hint">
          {cq.mode === "article"
            ? "输入文章标题或正文关键词，按文章内容检索已收录文章；也可按所属行业、文章属性筛选。"
            : "输入关键词，或直接按行业 / 活粉 / 阅读 / 报价 / 广告量 / 地区等条件筛选公众号。平台仅展示已收录账号，并标注数据来源与采集时间。"}
        </div>
      ) : cq.mode === "article" ? (
        <ArticleResultsSection cq={cq} />
      ) : (
        <AccountResults cq={cq} selectedIds={selectedIds} />
      )}
    </>
  );
}

function baseExtraQuery(cq: ConsoleQuery): Record<string, string> {
  return Object.fromEntries(consoleQueryToSearchParams({ ...cq, page: 1 }));
}

async function AccountResults({ cq, selectedIds }: { cq: ConsoleQuery; selectedIds: Set<number> }) {
  let data;
  try {
    data = await searchAccountsWithFilters(consoleQueryToApiParams(cq));
  } catch (error) {
    return <SearchError error={error} />;
  }

  if (data.items.length === 0) {
    return (
      <StateMessage
        title="没有符合条件的公众号"
        description="可尝试放宽筛选条件，或更换关键词。缺失指标的账号不会被对应的数值区间命中。"
      />
    );
  }

  return (
    <section className="console-results">
      <div className="result-bar">
        <span className="result-count">
          找到 <b>{data.total}</b> 个公众号
        </span>
        <div className="column-chips">
          {COLUMN_CHIPS.map((label) => (
            <span className="column-chip" key={label}>
              {label}
            </span>
          ))}
        </div>
      </div>

      <div className="acct-list">
        {data.items.map((account) => (
          <AccountResultCard
            key={account.id}
            account={account}
            initialSelected={selectedIds.has(account.id)}
          />
        ))}
      </div>

      <Pagination
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        basePath="/console"
        extraQuery={baseExtraQuery(cq)}
      />
    </section>
  );
}

async function ArticleResultsSection({ cq }: { cq: ConsoleQuery }) {
  let data;
  try {
    data = await searchArticles(consoleQueryToArticleApiParams(cq));
  } catch (error) {
    return <SearchError error={error} />;
  }

  if (data.items.length === 0) {
    return (
      <StateMessage
        title="没有符合条件的文章"
        description="可尝试更换关键词或放宽筛选条件；文章检索仅覆盖已收录文章。"
      />
    );
  }

  return (
    <section className="art-results">
      <ArticleToolbar initial={cq} total={data.total} />
      <ArticleTable items={data.items} />
      <Pagination
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        basePath="/console"
        extraQuery={baseExtraQuery(cq)}
      />
    </section>
  );
}

function SearchError({ error }: { error: unknown }) {
  const apiError = error as ApiError;
  const message =
    apiError.code === "DATA_SOURCE_BUSY"
      ? "数据源繁忙，请稍后重试。已收录的数据仍可访问。"
      : apiError.code === "DATA_SOURCE_UNAVAILABLE"
        ? "当前暂时无法从数据源更新数据，请稍后重试。已收录的数据仍可访问。"
        : apiError.message;
  return <StateMessage tone="error" title="搜索失败" description={message} />;
}
