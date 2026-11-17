import Link from "next/link";

import type { ArticleSearchItem } from "@/lib/types";

function formatWan(value: number | null | undefined): string {
  if (value === null || value === undefined) return "暂无数据";
  if (value >= 10000) {
    const wan = value / 10000;
    return `${Number.isInteger(wan) ? wan.toFixed(1) : wan.toFixed(2)}万`;
  }
  return value.toLocaleString("zh-CN");
}

function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined) return "暂无数据";
  return value.toLocaleString("zh-CN");
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  return iso.slice(0, 19).replace("T", " ");
}

export function ArticleTable({ items }: { items: ArticleSearchItem[] }) {
  return (
    <div className="art-table-wrap">
      <table className="art-table">
        <thead>
          <tr>
            <th className="art-col-info">文章信息</th>
            <th>预估活跃粉丝</th>
            <th>阅读数</th>
            <th>点赞数</th>
            <th>转发数</th>
            <th>在看数</th>
            <th>评论数</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const initial = (item.account_name || "号").trim().slice(0, 1) || "号";
            return (
              <tr key={item.id}>
                <td className="art-col-info">
                  <div className="art-tags">
                    {item.is_original ? (
                      <span className="tag tag-green">原创</span>
                    ) : (
                      <span className="tag tag-gray">非原创</span>
                    )}
                  </div>
                  <Link className="art-title" href={`/articles/${item.id}`}>
                    {item.title}
                  </Link>
                  <div className="art-sub">
                    <span className="art-avatar">{initial}</span>
                    <span className="art-account">{item.account_name}</span>
                    {item.account_category ? (
                      <span className="art-cat">{item.account_category}</span>
                    ) : null}
                    <span className="art-time">发布时间：{formatTime(item.published_at)}</span>
                    {item.ip_region ? <span className="art-time">IP属地：{item.ip_region}</span> : null}
                  </div>
                </td>
                <td>{formatWan(item.account_estimated_fans)}</td>
                <td>{formatInt(item.read_count)}</td>
                <td>{formatInt(item.like_count)}</td>
                <td>{formatInt(item.share_count)}</td>
                <td>{formatInt(item.wow_count)}</td>
                <td>{formatInt(item.comment_count)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
