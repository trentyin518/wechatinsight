import Link from "next/link";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  basePath: string;
  extraQuery?: Record<string, string>;
}

function href(basePath: string, page: number, extraQuery?: Record<string, string>): string {
  const params = new URLSearchParams(extraQuery ?? {});
  params.set("page", String(page));
  return `${basePath}?${params.toString()}`;
}

export function Pagination({ page, pageSize, total, basePath, extraQuery }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  return (
    <nav className="pagination" aria-label="分页">
      {page > 1 ? (
        <Link className="btn" href={href(basePath, page - 1, extraQuery)}>
          上一页
        </Link>
      ) : (
        <span className="btn btn-disabled">上一页</span>
      )}
      <span className="page-indicator">
        第 {page} / {totalPages} 页 · 共 {total} 条
      </span>
      {page < totalPages ? (
        <Link className="btn" href={href(basePath, page + 1, extraQuery)}>
          下一页
        </Link>
      ) : (
        <span className="btn btn-disabled">下一页</span>
      )}
    </nav>
  );
}
