"use client";

import { useRouter } from "next/navigation";

import { consoleQueryToHref, type ConsoleQuery } from "@/lib/consoleFilters";

const SORTS = [
  { key: "default", label: "默认排序" },
  { key: "read", label: "阅读最多" },
  { key: "like", label: "点赞最多" },
  { key: "share", label: "转发最多" },
  { key: "wow", label: "在看最多" },
  { key: "comment", label: "评论最多" },
  { key: "latest", label: "最新发布" },
];

const TIMES = [
  { key: "0", label: "全部时间" },
  { key: "1", label: "近24小时" },
  { key: "7", label: "近7天" },
  { key: "30", label: "近30天" },
];

export function ArticleToolbar({ initial, total }: { initial: ConsoleQuery; total: number }) {
  const router = useRouter();

  function go(patch: Partial<ConsoleQuery>) {
    router.push(consoleQueryToHref({ ...initial, ...patch, page: 1 }));
  }

  return (
    <div className="art-toolbar">
      <div className="art-info-bar">
        <span>
          共搜索到 <b>{total}</b> 个结果
        </span>
        <span className="art-info-links">
          点击搜索相关广告文案，若找不到公众号可手动添加收录或联系在线客服
        </span>
      </div>
      <div className="art-controls">
        <div className="art-sort">
          {SORTS.map((option) => (
            <button
              type="button"
              key={option.key}
              className={`art-sort-btn${initial.sort === option.key ? " active" : ""}`}
              onClick={() => go({ sort: option.key })}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="art-time">
          <span className="art-time-label">快捷时间</span>
          <select
            className="filter-native"
            value={initial.time}
            onChange={(e) => go({ time: e.target.value })}
          >
            {TIMES.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
