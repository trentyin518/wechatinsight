"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { toApiError } from "@/lib/errors";
import {
  getWechatAuthorize,
  loginWithPassword,
  wechatMockLogin,
} from "@/lib/clientApi";
import type { WechatAuthorizeResponse } from "@/lib/types";

import { WechatQrLogin } from "./WechatQrLogin";

const MOCK_IDENTITY_KEY = "wi_mock_identity";

// The mock WeChat login maps an identity to a user (openid = "mock:<identity>").
// Persist a per-browser identity so repeated "模拟微信登录" returns to the SAME
// account (so a once-approved tester stays logged in as that approved user)
// instead of creating a brand-new, un-onboarded user on every login.
function getMockIdentity(): string {
  try {
    const existing = window.localStorage.getItem(MOCK_IDENTITY_KEY);
    if (existing) return existing;
    const id = `demo-${Math.random().toString(36).slice(2, 10)}`;
    window.localStorage.setItem(MOCK_IDENTITY_KEY, id);
    return id;
  } catch {
    return "demo";
  }
}

export function LoginForm() {
  const router = useRouter();
  const [tab, setTab] = useState<"password" | "wechat">("password");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [wechat, setWechat] = useState<WechatAuthorizeResponse | null>(null);

  useEffect(() => {
    if (tab !== "wechat" || wechat) return;
    getWechatAuthorize()
      .then(setWechat)
      .catch(() => setWechat(null));
  }, [tab, wechat]);

  function go() {
    // Always enter the onboarding flow after login; that page then redirects
    // approved users to the app and pending/rejected users to the right page.
    router.push("/onboarding");
    router.refresh();
  }

  async function onPasswordLogin(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginWithPassword(phone.trim(), password);
      go();
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setLoading(false);
    }
  }

  async function onMockLogin() {
    setError(null);
    setLoading(true);
    try {
      await wechatMockLogin(getMockIdentity());
      go();
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-card">
      <div className="tabs">
        <button
          type="button"
          className={`tab ${tab === "password" ? "tab-active" : ""}`}
          onClick={() => setTab("password")}
        >
          账号登录
        </button>
        <button
          type="button"
          className={`tab ${tab === "wechat" ? "tab-active" : ""}`}
          onClick={() => setTab("wechat")}
        >
          微信扫码
        </button>
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      {tab === "password" ? (
        <form className="form-stack" onSubmit={onPasswordLogin}>
          <label className="field">
            <span>手机号</span>
            <input
              className="search-input"
              inputMode="numeric"
              autoComplete="username"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="请输入 11 位手机号"
              required
            />
          </label>
          <label className="field">
            <span>密码</span>
            <input
              className="search-input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              required
            />
          </label>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? "登录中…" : "登录"}
          </button>
          <p className="muted small">
            还没有账号？<Link href="/register">立即注册</Link>
          </p>
        </form>
      ) : (
        <div className="form-stack">
          {!wechat ? (
            <p className="muted small">正在加载微信登录…</p>
          ) : wechat.configured &&
            wechat.appid &&
            wechat.redirect_uri &&
            wechat.state ? (
            <>
              <WechatQrLogin
                appid={wechat.appid}
                redirectUri={wechat.redirect_uri}
                state={wechat.state}
                scope={wechat.scope}
                onError={(message) => setError(message)}
              />
              <p className="muted small wechat-hint">
                请使用微信「扫一扫」扫描上方二维码登录。
              </p>
              <a className="muted small" href={wechat.authorize_url} target="_blank" rel="noreferrer">
                二维码未显示？在新窗口打开
              </a>
            </>
          ) : wechat.mock_enabled ? (
            <>
              <p className="muted small">
                当前未配置微信开放平台凭据，开发环境可模拟扫码登录；同一浏览器多次模拟登录会复用同一体验账号。生产环境将自动切换为真实扫码。
              </p>
              <button className="btn btn-primary" type="button" onClick={onMockLogin} disabled={loading}>
                {loading ? "登录中…" : "模拟微信登录"}
              </button>
            </>
          ) : (
            <p className="muted small">微信登录暂不可用，请使用账号登录。</p>
          )}
        </div>
      )}
    </div>
  );
}
