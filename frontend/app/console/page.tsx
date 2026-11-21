import { SearchFilters } from "@/components/console/SearchFilters";
import { LiveFillAccounts, LiveFillArticles } from "@/components/console/LiveFill";
import { getServerSelection } from "@/lib/api";
import { parseConsoleQuery, type ConsoleQuery } from "@/lib/consoleFilters";

interface ConsolePageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

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
  const selectedIds = (selection?.items ?? []).map((item) => item.account.id);

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
        // Article list is fully client-filled: SSR never runs an article query,
        // so navigating/searching is never blocked by the (slow) data source.
        <LiveFillArticles cq={cq} />
      ) : (
        // Account list is fully client-filled too.
        <LiveFillAccounts cq={cq} selectedIds={selectedIds} />
      )}
    </>
  );
}
