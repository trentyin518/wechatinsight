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
  proof_id: number;
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
