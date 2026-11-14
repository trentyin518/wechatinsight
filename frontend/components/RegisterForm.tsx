"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { registerAccount } from "@/lib/clientApi";
import { toApiError } from "@/lib/errors";

export function RegisterForm() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("两次输入的密码不一致。");
      return;
    }
    setLoading(true);
    try {
      await registerAccount(phone.trim(), password, displayName.trim() || undefined);
      router.push("/onboarding");
      router.refresh();
    } catch (err) {
      setError(toApiError(err).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-card">
      {error ? <p className="form-error">{error}</p> : null}
      <form className="form-stack" onSubmit={onSubmit}>
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
          <span>昵称（可选）</span>
          <input
            className="search-input"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="请输入昵称"
          />
        </label>
        <label className="field">
          <span>密码</span>
          <input
            className="search-input"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="8-64 位密码"
            required
          />
        </label>
        <label className="field">
          <span>确认密码</span>
          <input
            className="search-input"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="请再次输入密码"
            required
          />
        </label>
        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? "注册中…" : "注册并继续"}
        </button>
        <p className="muted small">
          已有账号？<Link href="/login">去登录</Link>
        </p>
      </form>
    </div>
  );
}
