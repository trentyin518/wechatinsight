export interface Option {
  key: string;
  label: string;
}

export interface Range {
  min?: number;
  max?: number;
}

export const CATEGORY_OPTIONS: Option[] = [
  { key: "", label: "不限" },
  { key: "资讯", label: "资讯" },
  { key: "财经", label: "财经" },
  { key: "教育", label: "教育" },
  { key: "娱乐", label: "娱乐" },
  { key: "科技", label: "科技" },
  { key: "生活", label: "生活" },
  { key: "体育", label: "体育" },
  { key: "游戏动漫", label: "游戏动漫" },
  { key: "文化", label: "文化" },
  { key: "旅游", label: "旅游" },
  { key: "美食", label: "美食" },
  { key: "情感", label: "情感" },
  { key: "文摘", label: "文摘" },
  { key: "汽车", label: "汽车" },
  { key: "时尚", label: "时尚" },
  { key: "美妆护肤", label: "美妆护肤" },
  { key: "房产", label: "房产" },
  { key: "健康", label: "健康" },
  { key: "__more__", label: "更多" },
];

export const FANS_OPTIONS: Option[] = [
  { key: "", label: "不限" },
  { key: "lt5", label: "5万以下" },
  { key: "5-10", label: "5万-10万" },
  { key: "10-20", label: "10万-20万" },
  { key: "20-50", label: "20万-50万" },
  { key: "50-100", label: "50万-100万" },
  { key: "gt100", label: "100万以上" },
];

export const READ_OPTIONS: Option[] = [
  { key: "", label: "不限" },
  { key: "lt2000", label: "2000以下" },
  { key: "2000-5000", label: "2000-5000" },
  { key: "5000-10000", label: "5000-1万" },
  { key: "10000-50000", label: "1万-5万" },
  { key: "50000-100000", label: "5万-10万" },
  { key: "gt100000", label: "10万以上" },
];

export const PRICE_OPTIONS: Option[] = [
  { key: "", label: "不限" },
  { key: "lt5000", label: "5000以下" },
  { key: "5000-10000", label: "5000-1万" },
  { key: "10000-30000", label: "1万-3万" },
  { key: "30000-50000", label: "3万-5万" },
  { key: "50000-100000", label: "5万-10万" },
  { key: "gt100000", label: "10万以上" },
];

export const ADS_OPTIONS: Option[] = [
  { key: "", label: "不限" },
  { key: "eq0", label: "0篇" },
  { key: "1-4", label: "1-4篇" },
  { key: "5-14", label: "5-14篇" },
  { key: "15-30", label: "15-30篇" },
  { key: "gt30", label: "30篇以上" },
];

export const XIGUA_OPTIONS: Option[] = [
  { key: "", label: "西瓜指数 · 不限" },
  { key: "1000", label: "1000 以上" },
  { key: "1500", label: "1500 以上" },
  { key: "2000", label: "2000 以上" },
];

export const REGION_OPTIONS: Option[] = [
  { key: "", label: "所在地区 · 不限" },
  { key: "北京", label: "北京" },
  { key: "上海", label: "上海" },
  { key: "广州", label: "广州" },
  { key: "深圳", label: "深圳" },
  { key: "杭州", label: "杭州" },
  { key: "成都", label: "成都" },
];

export const RECENT_OPTIONS: Option[] = [
  { key: "", label: "近期发文 · 不限" },
  { key: "7", label: "7天内" },
  { key: "15", label: "15天内" },
  { key: "30", label: "30天内" },
];

const FANS_RANGE: Record<string, Range> = {
  "": {},
  lt5: { max: 50000 },
  "5-10": { min: 50001, max: 100000 },
  "10-20": { min: 100001, max: 200000 },
  "20-50": { min: 200001, max: 500000 },
  "50-100": { min: 500001, max: 1000000 },
  gt100: { min: 1000001 },
};

const READ_RANGE: Record<string, Range> = {
  "": {},
  lt2000: { max: 2000 },
  "2000-5000": { min: 2001, max: 5000 },
  "5000-10000": { min: 5001, max: 10000 },
  "10000-50000": { min: 10001, max: 50000 },
  "50000-100000": { min: 50001, max: 100000 },
  gt100000: { min: 100001 },
};

const PRICE_RANGE: Record<string, Range> = {
  "": {},
  lt5000: { max: 5000 },
  "5000-10000": { min: 5001, max: 10000 },
  "10000-30000": { min: 10001, max: 30000 },
  "30000-50000": { min: 30001, max: 50000 },
  "50000-100000": { min: 50001, max: 100000 },
  gt100000: { min: 100001 },
};

const ADS_RANGE: Record<string, Range> = {
  "": {},
  eq0: { min: 0, max: 0 },
  "1-4": { min: 1, max: 4 },
  "5-14": { min: 5, max: 14 },
  "15-30": { min: 15, max: 30 },
  gt30: { min: 31 },
};

export interface ConsoleQuery {
  q: string;
  page: number;
  mode: "name" | "article";
  category: string;
  fans: string;
  read: string;
  price: string;
  ads: string;
  xigua: string;
  region: string;
  recent: string;
  original: boolean;
  service: boolean;
  video: boolean;
  // article-mode only
  scope: string;
  attr: string;
  dedup: boolean;
  sort: string;
  time: string;
}

type RawParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

export function parseConsoleQuery(sp: RawParams): ConsoleQuery {
  return {
    q: first(sp.q).trim(),
    page: Math.max(1, Number.parseInt(first(sp.page) || "1", 10) || 1),
    mode: first(sp.mode) === "article" ? "article" : "name",
    category: first(sp.category),
    fans: first(sp.fans),
    read: first(sp.read),
    price: first(sp.price),
    ads: first(sp.ads),
    xigua: first(sp.xigua),
    region: first(sp.region),
    recent: first(sp.recent),
    original: first(sp.original) === "1",
    service: first(sp.service) === "1",
    video: first(sp.video) === "1",
    scope: first(sp.scope) || "title",
    attr: first(sp.attr) || "all",
    dedup: first(sp.dedup) === "1",
    sort: first(sp.sort) || "default",
    time: first(sp.time) || "0",
  };
}

export function consoleQueryToSearchParams(cq: ConsoleQuery): URLSearchParams {
  const params = new URLSearchParams();
  if (cq.q) params.set("q", cq.q);
  if (cq.page > 1) params.set("page", String(cq.page));
  if (cq.mode === "article") params.set("mode", "article");
  if (cq.category) params.set("category", cq.category);
  if (cq.fans) params.set("fans", cq.fans);
  if (cq.read) params.set("read", cq.read);
  if (cq.price) params.set("price", cq.price);
  if (cq.ads) params.set("ads", cq.ads);
  if (cq.xigua) params.set("xigua", cq.xigua);
  if (cq.region) params.set("region", cq.region);
  if (cq.recent) params.set("recent", cq.recent);
  if (cq.original) params.set("original", "1");
  if (cq.service) params.set("service", "1");
  if (cq.video) params.set("video", "1");
  if (cq.mode === "article") {
    if (cq.scope && cq.scope !== "title") params.set("scope", cq.scope);
    if (cq.attr && cq.attr !== "all") params.set("attr", cq.attr);
    if (cq.dedup) params.set("dedup", "1");
    if (cq.sort && cq.sort !== "default") params.set("sort", cq.sort);
    if (cq.time && cq.time !== "0") params.set("time", cq.time);
  }
  return params;
}

export function consoleQueryToHref(cq: ConsoleQuery): string {
  const qs = consoleQueryToSearchParams(cq).toString();
  return qs ? `/console?${qs}` : "/console";
}

/** Map validated UI state to backend query params (ranges expanded). */
export function consoleQueryToApiParams(cq: ConsoleQuery): Record<string, string> {
  const params: Record<string, string> = { q: cq.q, page: String(cq.page) };
  if (cq.mode === "article") params.mode = "article";
  if (cq.category) params.category = cq.category;
  if (cq.region) params.region = cq.region;

  const fans = FANS_RANGE[cq.fans] ?? {};
  const read = READ_RANGE[cq.read] ?? {};
  const price = PRICE_RANGE[cq.price] ?? {};
  const ads = ADS_RANGE[cq.ads] ?? {};

  if (fans.min !== undefined) params.fans_min = String(fans.min);
  if (fans.max !== undefined) params.fans_max = String(fans.max);
  if (read.min !== undefined) params.read_min = String(read.min);
  if (read.max !== undefined) params.read_max = String(read.max);
  if (price.min !== undefined) params.price_min = String(price.min);
  if (price.max !== undefined) params.price_max = String(price.max);
  if (ads.min !== undefined) params.ad_min = String(ads.min);
  if (ads.max !== undefined) params.ad_max = String(ads.max);
  if (cq.xigua) params.xigua_min = cq.xigua;
  if (cq.recent) params.recent_days = cq.recent;
  if (cq.original) params.is_original = "true";
  if (cq.service) params.service_only = "true";
  if (cq.video) params.has_video = "true";

  return params;
}

/** Map article-mode UI state to the article-search endpoint params. */
export function consoleQueryToArticleApiParams(cq: ConsoleQuery): Record<string, string> {
  const params: Record<string, string> = { q: cq.q, page: String(cq.page) };
  if (cq.scope) params.scope = cq.scope;
  if (cq.category) params.category = cq.category;
  if (cq.attr === "original") params.original = "true";
  else if (cq.attr === "nonoriginal") params.original = "false";
  if (cq.dedup) params.dedup = "true";
  params.sort = cq.sort || "default";
  if (cq.time && cq.time !== "0") params.time_days = cq.time;
  return params;
}
