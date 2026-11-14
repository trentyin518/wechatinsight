"use client";

import { ApiError } from "./errors";
import type {
  MeResponse,
  OnboardingStatusResponse,
  OnboardingSubmitInput,
  ProofUploadResponse,
  SubmissionListResponse,
  SubmissionOut,
  UserOut,
  WechatAuthorizeResponse,
} from "./types";

async function parseError(response: Response): Promise<ApiError> {
  let code = `HTTP_${response.status}`;
  let message = "请求失败，请稍后重试。";
  try {
    const body = await response.json();
    if (body?.error?.code) code = body.error.code;
    if (body?.error?.message) message = body.error.message;
  } catch {
    // keep defaults
  }
  return new ApiError(message, code, response.status);
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { credentials: "include", ...init });
  } catch {
    throw new ApiError("无法连接到服务，请检查网络。", "NETWORK_ERROR", 0);
  }
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function loginWithPassword(phone: string, password: string): Promise<MeResponse> {
  return requestJson<MeResponse>("/api/v1/auth/login", jsonInit("POST", { phone, password }));
}

export function registerAccount(
  phone: string,
  password: string,
  displayName?: string,
): Promise<MeResponse> {
  return requestJson<MeResponse>(
    "/api/v1/auth/register",
    jsonInit("POST", { phone, password, display_name: displayName }),
  );
}

export async function logoutSession(): Promise<void> {
  await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" });
}

export function getWechatAuthorize(): Promise<WechatAuthorizeResponse> {
  return requestJson<WechatAuthorizeResponse>("/api/v1/auth/wechat/authorize");
}

export function wechatMockLogin(identity?: string, displayName?: string): Promise<MeResponse> {
  return requestJson<MeResponse>(
    "/api/v1/auth/wechat/mock",
    jsonInit("POST", { identity, display_name: displayName }),
  );
}

export async function fetchMe(): Promise<UserOut> {
  const data = await requestJson<MeResponse>("/api/v1/auth/me");
  return data.user;
}

export async function uploadProof(file: File): Promise<ProofUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  let response: Response;
  try {
    response = await fetch("/api/v1/onboarding/proof", {
      method: "POST",
      body: form,
      credentials: "include",
    });
  } catch {
    throw new ApiError("上传失败，请检查网络。", "NETWORK_ERROR", 0);
  }
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as ProofUploadResponse;
}

export function submitOnboarding(
  payload: OnboardingSubmitInput,
): Promise<OnboardingStatusResponse> {
  return requestJson<OnboardingStatusResponse>(
    "/api/v1/onboarding/submit",
    jsonInit("POST", payload),
  );
}

export function getOnboardingStatus(): Promise<OnboardingStatusResponse> {
  return requestJson<OnboardingStatusResponse>("/api/v1/onboarding/status");
}

export function listSubmissions(status?: string): Promise<SubmissionListResponse> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return requestJson<SubmissionListResponse>(`/api/v1/onboarding/submissions${query}`);
}

export function approveSubmission(id: number): Promise<SubmissionOut> {
  return requestJson<SubmissionOut>(`/api/v1/onboarding/submissions/${id}/approve`, {
    method: "POST",
    credentials: "include",
  });
}

export function rejectSubmission(id: number, reason: string): Promise<SubmissionOut> {
  return requestJson<SubmissionOut>(
    `/api/v1/onboarding/submissions/${id}/reject`,
    jsonInit("POST", { reason }),
  );
}
