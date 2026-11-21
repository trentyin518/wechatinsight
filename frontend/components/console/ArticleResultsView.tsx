import { ArticleTable } from "@/components/console/ArticleTable";
import { ArticleToolbar } from "@/components/console/ArticleToolbar";
import { Pagination } from "@/components/Pagination";
import type { ArticleSearchResponse } from "@/lib/types";
import { consoleQueryToSearchParams, type ConsoleQuery } from "@/lib/consoleFilters";

export function ArticleResultsView({
  cq,
  data,
}: {
  cq: ConsoleQuery;
  data: ArticleSearchResponse;
}) {
  const extraQuery = Object.fromEntries(consoleQueryToSearchParams({ ...cq, page: 1 }));

  return (
    <section className="art-results">
      <ArticleToolbar initial={cq} total={data.total} />
      {data.source === "live" ? (
        <div className="console-hint">
          本地暂未收录该关键词的文章，以下为实时内容检索结果（未收录，点击标题查看原文）。
        </div>
      ) : null}
      <ArticleTable items={data.items} />
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
