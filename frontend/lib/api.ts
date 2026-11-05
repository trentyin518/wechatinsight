import type {
  AccountDetail,
  AccountSearchResponse,
  ArticleDetail,
  ArticleListResponse,
  MetricsHistoryResponse,
} from "./types";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
}

async function getJson<T>(path: string): Promise<T> {
  const url = `${apiBase()}${path}`;
  let response: Response;
  try {
    response = await fetch(url, { cache: "no-store" });
  } catch {
    throw new ApiError("无法连接到后端服务。", "NETWORK_ERROR", 0);
  }

  if (!response.ok) {
    let code = `HTTP_${response.status}`;
    let message = "请求失败，请稍后重试。";
    try {
      const body = await response.json();
      if (body?.error?.code) code = body.error.code;
      if (body?.error?.message) message = body.error.message;
    } catch {
      // keep defaults
    }
    throw new ApiError(message, code, response.status);
  }
  return (await response.json()) as T;
}

export function searchAccounts(
  q: string,
  page = 1,
  pageSize = 20,
): Promise<AccountSearchResponse> {
  const params = new URLSearchParams({ q, page: String(page), page_size: String(pageSize) });
  return getJson<AccountSearchResponse>(`/api/v1/accounts?${params.toString()}`);
}

export function getAccount(id: string | number): Promise<AccountDetail> {
  return getJson<AccountDetail>(`/api/v1/accounts/${id}`);
}

export function getAccountArticles(
  id: string | number,
  page = 1,
  pageSize = 20,
): Promise<ArticleListResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  return getJson<ArticleListResponse>(`/api/v1/accounts/${id}/articles?${params.toString()}`);
}

export function getArticle(id: string | number): Promise<ArticleDetail> {
  return getJson<ArticleDetail>(`/api/v1/articles/${id}`);
}

export function getArticleMetrics(id: string | number): Promise<MetricsHistoryResponse> {
  return getJson<MetricsHistoryResponse>(`/api/v1/articles/${id}/metrics`);
}
