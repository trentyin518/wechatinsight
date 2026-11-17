"use client";

import { useEffect, useRef } from "react";

// Official WeChat "网站应用" QR SDK. It renders the real login QR inside a
// container element; once the user confirms on their phone, WeChat performs a
// top-level redirect to our callback (redirect_uri) which signs the session in.
const SCRIPT_SRC = "https://res.wx.qq.com/connect/zh_CN/htmledition/js/wxLogin.js";
const CONTAINER_ID = "wx_login_container";

type WxLoginOptions = {
  self_redirect: boolean;
  id: string;
  appid: string;
  scope: string;
  redirect_uri: string;
  state: string;
  style: "black" | "white";
  href?: string;
};

declare global {
  interface Window {
    WxLogin?: new (options: WxLoginOptions) => unknown;
  }
}

function loadSdk(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.WxLogin) return Promise.resolve();
  const existing = document.querySelector<HTMLScriptElement>(
    `script[src="${SCRIPT_SRC}"]`,
  );
  if (existing) {
    return new Promise((resolve) => {
      if (window.WxLogin) return resolve();
      existing.addEventListener("load", () => resolve(), { once: true });
    });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("无法加载微信登录组件"));
    document.body.appendChild(script);
  });
}

export interface WechatQrLoginProps {
  appid: string;
  redirectUri: string;
  state: string;
  scope?: string;
  onError?: (message: string) => void;
}

export function WechatQrLogin({
  appid,
  redirectUri,
  state,
  scope = "snsapi_login",
  onError,
}: WechatQrLoginProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  useEffect(() => {
    let cancelled = false;
    loadSdk()
      .then(() => {
        if (cancelled || !window.WxLogin) return;
        const host = containerRef.current;
        if (!host) return;
        host.innerHTML = "";
        new window.WxLogin({
          self_redirect: false,
          id: CONTAINER_ID,
          appid,
          scope,
          // WeChat requires an URL-encoded redirect_uri here.
          redirect_uri: encodeURIComponent(redirectUri),
          state,
          style: "black",
        });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          onErrorRef.current?.(err instanceof Error ? err.message : "二维码加载失败");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [appid, redirectUri, state, scope]);

  return <div ref={containerRef} id={CONTAINER_ID} className="wx-qr" />;
}
