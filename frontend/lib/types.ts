export interface AccountOut {
  id: number;
  name: string;
  wechat_id: string | null;
  description: string | null;
  avatar_url: string | null;
  verification_subject?: string | null;
  account_type?: string | null;
  provider: string;
  last_synced_at: string | null;
  category?: string | null;
  region?: string | null;
  estimated_fans?: number | null;
  avg_read?: number | null;
  avg_like?: number | null;
  avg_wow?: number | null;
  avg_share?: number | null;
  avg_comment?: number | null;
  article_count?: number | null;
  estimated_price?: number | null;
  ad_count_30d?: number | null;
  xigua_index?: number | null;
  is_original?: boolean | null;
  has_video?: boolean | null;
  collecting?: boolean;
  collection_state?: string | null;
  collection_error?: string | null;
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
  source?: "local" | "content";
}

export interface SimilarAccountsResponse {
  account: AccountOut;
  items: AccountOut[];
}

export interface ArticleListItem {
  id: number;
  title: string;
  article_url: string;
  provider: string;
  published_at: string | null;
  ip_region: string | null;
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

export interface ArticleSearchItem {
  id: number;
  title: string;
  article_url: string;
  provider: string;
  published_at: string | null;
  is_original: boolean | null;
  author: string | null;
  ip_region: string | null;
  summary: string | null;
  account_id: number;
  account_name: string;
  account_avatar_url: string | null;
  account_category: string | null;
  account_estimated_fans: number | null;
  read_count: number | null;
  like_count: number | null;
  share_count: number | null;
  wow_count: number | null;
  comment_count: number | null;
  metrics_observed_at: string | null;
  external?: boolean;
}

export interface ArticleSearchResponse {
  items: ArticleSearchItem[];
  page: number;
  page_size: number;
  total: number;
  source?: "local" | "live";
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
  ip_region: string | null;
  cover_url: string | null;
  published_at: string | null;
  is_original: boolean | null;
  is_paid: boolean | null;
  metrics: MetricPoint | null;
}

export type OnboardingStatus = "none" | "pending" | "approved" | "rejected";

export interface UserOut {
  id: number;
  phone: string | null;
  display_name: string | null;
  is_admin: boolean;
  onboarding_status: OnboardingStatus;
  created_at: string;
}

export interface MeResponse {
  user: UserOut;
}

export interface WechatAuthorizeResponse {
  authorize_url: string;
  configured: boolean;
  mock_enabled: boolean;
  appid?: string | null;
  redirect_uri?: string | null;
  scope?: string;
  state?: string | null;
}

export interface ProofUploadResponse {
  proof_id: number;
  mime_type: string;
  size_bytes: number;
  original_name: string | null;
}

export interface SubmissionSummary {
  id: number;
  status: OnboardingStatus;
  reject_reason: string | null;
  submitted_at: string;
  reviewed_at: string | null;
}

export interface OnboardingStatusResponse {
  status: OnboardingStatus;
  submission: SubmissionSummary | null;
  proof_required?: boolean;
}

export interface OnboardingSubmitInput {
  source_channel: string;
  source_other?: string;
  user_type: string;
  user_type_other?: string;
  company_name: string;
  contact_name: string;
  contact_phone: string;
  needs?: string;
  proof_id?: number;
}

export interface SubmissionOut {
  id: number;
  user_id: number;
  user_phone: string | null;
  user_display_name: string | null;
  status: OnboardingStatus;
  source_channel: string | null;
  source_other: string | null;
  user_type: string | null;
  user_type_other: string | null;
  company_name: string | null;
  contact_name: string | null;
  contact_phone: string | null;
  needs: string | null;
  proof_id: number | null;
  reject_reason: string | null;
  submitted_at: string;
  reviewed_at: string | null;
}

export interface SubmissionListResponse {
  items: SubmissionOut[];
  total: number;
}

export interface OverviewResponse {
  accounts_count: number;
  articles_count: number;
  metrics_count: number;
  providers_count: number;
  last_updated_at: string | null;
  recent_accounts: AccountOut[];
}

export interface SelectionItem {
  account: AccountOut;
  added_at: string;
}

export interface SelectionListResponse {
  items: SelectionItem[];
  total: number;
}

export interface SelectionState {
  account_id: number;
  selected: boolean;
  total: number;
}

export interface UsageLogItem {
  request_time: string;
  provider: string;
  endpoint: string;
  success: boolean;
  estimated_cost: number;
}

export interface UsageOverview {
  balance_usd: number | null;
  plan: string | null;
  daily_cost_usd: number;
  monthly_cost_usd: number;
  daily_budget_usd: number;
  monthly_budget_usd: number;
  today_calls: number;
  collection_enabled: boolean;
  search_retry_enabled: boolean;
  over_daily_budget: boolean;
  over_monthly_budget: boolean;
  recent: UsageLogItem[];
}

export interface SyncFailureReason {
  error_code: string | null;
  count: number;
}

export interface SyncFailedJob {
  id: number;
  job_type: string;
  target_type: string;
  target_id: number | null;
  error_code: string | null;
  error_message: string | null;
  updated_at: string;
}

export interface SyncHealth {
  status_counts: Record<string, number>;
  total_jobs: number;
  pending_count: number;
  pending_oldest_at: string | null;
  pending_oldest_age_seconds: number | null;
  metrics_pending: number;
  metrics_throttle_threshold: number;
  failed_reasons: SyncFailureReason[];
  recent_failed: SyncFailedJob[];
  by_type: JobTypeBreakdown[];
  success_24h: number;
  failed_24h: number;
  worker_hint: string | null;
}

export interface SyncDrainResult {
  scheduled: boolean;
  pending: number;
  metrics_pending: number;
  max_jobs: number;
  throttled: boolean;
  message: string;
}

export interface RecollectResult {
  queued: boolean;
  job_id: number | null;
  message: string;
}

export interface JobTypeBreakdown {
  job_type: string;
  total: number;
  status_counts: Record<string, number>;
}
