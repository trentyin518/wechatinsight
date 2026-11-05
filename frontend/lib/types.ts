export interface AccountOut {
  id: number;
  name: string;
  wechat_id: string | null;
  description: string | null;
  avatar_url: string | null;
  provider: string;
  last_synced_at: string | null;
}

export interface AccountDetail extends AccountOut {
  verification_subject: string | null;
  account_type: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccountSearchResponse {
  items: AccountOut[];
  page: number;
  page_size: number;
  total: number;
}

export interface ArticleListItem {
  id: number;
  title: string;
  article_url: string;
  provider: string;
  published_at: string | null;
  read_count: number | null;
  like_count: number | null;
  wow_count: number | null;
  comment_count: number | null;
  share_count: number | null;
  metrics_observed_at: string | null;
}

export interface ArticleListResponse {
  items: ArticleListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface MetricPoint {
  read_count: number | null;
  like_count: number | null;
  wow_count: number | null;
  comment_count: number | null;
  share_count: number | null;
  observed_at: string;
  raw_updated_at: string | null;
  provider: string;
}

export interface ObservedChange {
  delta: number | null;
  rate: number | null;
}

export interface MetricsHistoryResponse {
  article_id: number;
  points: MetricPoint[];
  observed_read_change: ObservedChange;
}

export interface ArticleDetail {
  id: number;
  account_id: number;
  title: string;
  article_url: string;
  provider: string;
  summary: string | null;
  author: string | null;
  cover_url: string | null;
  published_at: string | null;
  is_original: boolean | null;
  is_paid: boolean | null;
  metrics: MetricPoint | null;
}
