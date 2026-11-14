import Link from "next/link";

import { DataProvenance } from "@/components/DataProvenance";
import { Pagination } from "@/components/Pagination";
import { SearchForm } from "@/components/SearchForm";
import { StateMessage } from "@/components/StateMessage";
import { ApiError, searchAccounts } from "@/lib/api";
import { requireApprovedOrRedirect } from "@/lib/guard";

interface SearchPageProps {
  searchParams: Promise<{ q?: string; page?: string }>;
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  await requireApprovedOrRedirect();
  const sp = await searchParams;
  const q = (sp.q ?? "").trim();
  const page = Math.max(1, Number.parseInt(sp.page ?? "1", 10) || 1);

  return (
    <>
      <div className="breadcrumb">
        <Link href="/">首页</Link> / 搜索
      </div>
      <div className="hero" style={{ paddingTop: 0 }}>
        <h1>搜索结果</h1>
        <SearchForm initialQuery={q} />
      </div>

      {!q ? (
        <StateMessage title="请输入关键词" description="输入公众号名称、微信号或简介开始搜索。" />
      ) : (
        <Results q={q} page={page} />
      )}
    </>
  );
}

async function Results({ q, page }: { q: string; page: number }) {
  let data;
  try {
    data = await searchAccounts(q, page);
  } catch (error) {
    const apiError = error as ApiError;
    const message =
      apiError.code === "DATA_SOURCE_UNAVAILABLE"
        ? "当前暂时无法从数据源更新数据，请稍后重试。已收录的数据仍可访问。"
        : apiError.message;
    return <StateMessage tone="error" title="搜索失败" description={message} />;
  }

  if (data.items.length === 0) {
    return (
      <StateMessage
        title={`未找到与「${q}」相关的公众号`}
        description="本地库暂无匹配结果，且当前未执行实时查询或实时查询无结果。"
      />
    );
  }

  return (
    <section className="section" style={{ marginTop: 20 }}>
      <p className="muted small">
        平台本地已收录 {data.total} 条与「{q}」相关的公众号（非全网总数）。
      </p>
      <div className="card-grid">
        {data.items.map((account) => (
          <Link className="card" key={account.id} href={`/accounts/${account.id}`}>
            <h3>{account.name}</h3>
            {account.wechat_id ? <p className="muted small">微信号：{account.wechat_id}</p> : null}
            {account.description ? <p className="muted small">{account.description}</p> : null}
            <DataProvenance provider={account.provider} observedAt={account.last_synced_at} />
          </Link>
        ))}
      </div>
      <Pagination
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        basePath="/search"
        extraQuery={{ q }}
      />
    </section>
  );
}
