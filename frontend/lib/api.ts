import { cookies } from "next/headers";

import { ApiError } from "./errors";
import type {
  AccountDetail,
  AccountSearchResponse,
  ArticleDetail,
  ArticleListResponse,
  MeResponse,
  MetricsHistoryResponse,
  OnboardingStatusResponse,
  OverviewResponse,
  UserOut,
} from "./types";

export { ApiError } from "./errors";

function apiBase(): string {
  return (
    process.env.API_PROXY_TARGET ||
    process.env.NEXT_PUBLIC_API_BASE ||
    "http://localhost:8000"
  );
}

function sessionCookieName(): string {
  return process.env.NEXT_PUBLIC_SESSION_COOKIE_NAME || "wi_session";
}

async function sessionCookieHeader(): Promise<string | undefined> {
  const store = await cookies();
  const token = store.get(sessionCookieName())?.value;
  return token ? `${sessionCookieName()}=${token}` : undefined;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${apiBase()}${path}`;
  const headers: Record<string, string> = {
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  const cookie = await sessionCookieHeader();
  if (cookie) headers["cookie"] = cookie;

  let response: Response;
  try {
    response = await fetch(url, { cache: "no-store", ...init, headers });
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

function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path);
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

export async function getServerCurrentUser(): Promise<UserOut | null> {
  try {
    const data = await getJson<MeResponse>("/api/v1/auth/me");
    return data.user;
  } catch {
    return null;
  }
}

export async function getServerOnboardingStatus(): Promise<OnboardingStatusResponse | null> {
  try {
    return await getJson<OnboardingStatusResponse>("/api/v1/onboarding/status");
  } catch {
    return null;
  }
}

export async function getServerOverview(): Promise<OverviewResponse | null> {
  try {
    return await getJson<OverviewResponse>("/api/v1/overview");
  } catch {
    return null;
  }
}
