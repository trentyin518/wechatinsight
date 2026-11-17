"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import {
  ADS_OPTIONS,
  CATEGORY_OPTIONS,
  FANS_OPTIONS,
  PRICE_OPTIONS,
  READ_OPTIONS,
  RECENT_OPTIONS,
  REGION_OPTIONS,
  XIGUA_OPTIONS,
  consoleQueryToHref,
  type ConsoleQuery,
  type Option,
} from "@/lib/consoleFilters";

const NAME_SCOPES = ["公众号名称", "公众号简介", "公众号发文主题", "公众号主体"];
const ARTICLE_SCOPES: Option[] = [
  { key: "title", label: "文章标题" },
  { key: "title_content", label: "文章标题+内容" },
  { key: "topic", label: "文章话题" },
  { key: "comment", label: "留言搜索" },
];
const ATTR_OPTIONS: Option[] = [
  { key: "all", label: "不限" },
  { key: "original", label: "原创号" },
  { key: "nonoriginal", label: "非原创" },
];
const DEDUP_OPTIONS: Option[] = [
  { key: "0", label: "不去重" },
  { key: "1", label: "去重" },
];

function ChipRow({
  label,
  options,
  value,
  onSelect,
}: {
  label: string;
  options: Option[];
  value: string;
  onSelect: (key: string) => void;
}) {
  return (
    <div className="filter-row">
      <span className="filter-label">{label}：</span>
      <div className="filter-opts">
        {options.map((option) => {
          if (option.key === "__more__") {
            return (
              <span className="filter-opt-more" key="__more__">
                {option.label}
              </span>
            );
          }
          return (
            <button
              type="button"
              key={option.key || "any"}
              className={`filter-opt-btn${value === option.key ? " active" : ""}`}
              onClick={() => onSelect(option.key)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SelectRow({
  options,
  value,
  onSelect,
}: {
  options: Option[];
  value: string;
  onSelect: (key: string) => void;
}) {
  return (
    <select className="filter-native" value={value} onChange={(e) => onSelect(e.target.value)}>
      {options.map((option) => (
        <option key={option.key || "any"} value={option.key}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

export function SearchFilters({ initial }: { initial: ConsoleQuery }) {
  const router = useRouter();
  const [scope, setScope] = useState(NAME_SCOPES[0]);
  const [keyword, setKeyword] = useState(initial.q);

  useEffect(() => {
    setKeyword(initial.q);
  }, [initial.q]);

  function push(next: ConsoleQuery) {
    router.push(consoleQueryToHref({ ...next, page: 1 }));
  }

  function itemOnSelect(patch: Partial<ConsoleQuery>) {
    router.push(consoleQueryToHref({ ...initial, ...patch, q: keyword.trim(), page: 1 }));
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    router.push(consoleQueryToHref({ ...initial, q: keyword.trim(), page: 1 }));
  }

  const isArticle = initial.mode === "article";

  return (
    <div className="filters-card">
      <div className="filter-searchtabs">
        <button
          type="button"
          className={`filter-searchtab${!isArticle ? " active" : ""}`}
          onClick={() => push({ ...initial, mode: "name" })}
        >
          按关键词搜索
        </button>
        <button
          type="button"
          className={`filter-searchtab${isArticle ? " active" : ""}`}
          onClick={() => push({ ...initial, mode: "article" })}
        >
          按文章内容搜索
        </button>
      </div>

      {isArticle ? (
        <div className="filter-row filter-row-top">
          <span className="filter-label">搜索范围：</span>
          <div className="filter-opts">
            {ARTICLE_SCOPES.map((option) => (
              <label className="filter-radio" key={option.key}>
                <input
                  type="radio"
                  name="article-scope"
                  checked={initial.scope === option.key}
                  onChange={() => itemOnSelect({ scope: option.key })}
                />
                {option.label}
              </label>
            ))}
          </div>
        </div>
      ) : (
        <div className="filter-row filter-row-top">
          <span className="filter-label">搜索范围：</span>
          <div className="filter-opts">
            {NAME_SCOPES.map((option) => (
              <label className="filter-radio" key={option}>
                <input
                  type="radio"
                  name="scope"
                  checked={scope === option}
                  onChange={() => setScope(option)}
                />
                {option}
              </label>
            ))}
          </div>
        </div>
      )}

      <form className="filter-search" onSubmit={onSubmit}>
        <input
          className="filter-input"
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder={
            isArticle
              ? "请输入文章标题或正文内容关键词"
              : "请输入公众号名称、公众号ID、公众号发文地址"
          }
        />
        <button type="submit" className="filter-search-btn">
          搜索
        </button>
        {isArticle ? (
          <button type="button" className="filter-adv-btn" title="更多维度以数据源实际提供为准">
            高级搜索
          </button>
        ) : null}
        <span className="filter-search-hint">公众号收录 / 号主认证</span>
        <span className="filter-search-hint filter-search-hint-link">如何快速找到优质号</span>
      </form>

      <ChipRow
        label="所属行业"
        options={CATEGORY_OPTIONS}
        value={initial.category}
        onSelect={(key) => itemOnSelect({ category: key })}
      />

      {isArticle ? (
        <>
          <ChipRow
            label="文章属性"
            options={ATTR_OPTIONS}
            value={initial.attr}
            onSelect={(key) => itemOnSelect({ attr: key })}
          />
          <ChipRow
            label="账号去重"
            options={DEDUP_OPTIONS}
            value={initial.dedup ? "1" : "0"}
            onSelect={(key) => itemOnSelect({ dedup: key === "1" })}
          />
          <p className="filter-note">
            按文章内容检索已收录文章，命中后展示对应公众号与文章指标；「文章话题 / 留言」维度数据源未提供时按「标题+内容」近似检索。
          </p>
        </>
      ) : (
        <>
          <ChipRow
            label="预估活粉"
            options={FANS_OPTIONS}
            value={initial.fans}
            onSelect={(key) => itemOnSelect({ fans: key })}
          />
          <ChipRow
            label="平均阅读"
            options={READ_OPTIONS}
            value={initial.read}
            onSelect={(key) => itemOnSelect({ read: key })}
          />
          <ChipRow
            label="预估报价"
            options={PRICE_OPTIONS}
            value={initial.price}
            onSelect={(key) => itemOnSelect({ price: key })}
          />
          <ChipRow
            label="30天广告"
            options={ADS_OPTIONS}
            value={initial.ads}
            onSelect={(key) => itemOnSelect({ ads: key })}
          />

          <div className="filter-row">
            <span className="filter-label">更多筛选：</span>
            <div className="filter-opts">
              <SelectRow
                options={XIGUA_OPTIONS}
                value={initial.xigua}
                onSelect={(key) => itemOnSelect({ xigua: key })}
              />
              <SelectRow
                options={REGION_OPTIONS}
                value={initial.region}
                onSelect={(key) => itemOnSelect({ region: key })}
              />
              <SelectRow
                options={RECENT_OPTIONS}
                value={initial.recent}
                onSelect={(key) => itemOnSelect({ recent: key })}
              />
            </div>
          </div>

          <div className="filter-row filter-row-checks">
            <span className="filter-label" />
            <div className="filter-opts">
              <label className="filter-check">
                <input
                  type="checkbox"
                  checked={initial.original}
                  onChange={(e) => itemOnSelect({ original: e.target.checked })}
                />
                原创号
              </label>
              <label className="filter-check">
                <input
                  type="checkbox"
                  checked={initial.service}
                  onChange={(e) => itemOnSelect({ service: e.target.checked })}
                />
                服务号
              </label>
              <label className="filter-check">
                <input
                  type="checkbox"
                  checked={initial.video}
                  onChange={(e) => itemOnSelect({ video: e.target.checked })}
                />
                带视频内容
              </label>
            </div>
          </div>

          <p className="filter-note">
            可按关键词、所属行业、活粉 / 阅读 / 报价区间、30天广告量与地区筛选；缺失指标的账号不会被对应区间命中（缺失不显示为 0）。
          </p>
        </>
      )}
    </div>
  );
}
