"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchMe, logoutSession } from "@/lib/clientApi";
import type { UserOut } from "@/lib/types";

export function HeaderAuth() {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loaded, setLoaded] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    let active = true;
    // Re-check on every navigation so the header reflects login/logout that
    // happen client-side (the layout does not remount between routes).
    fetchMe()
      .then((u) => {
        if (active) setUser(u);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoaded(true);
      });
    return () => {
      active = false;
    };
  }, [pathname]);

  async function onLogout() {
    await logoutSession();
    setUser(null);
    router.push("/login");
    router.refresh();
  }

  return (
    <nav className="nav nav-inline">
      <Link href="/search">搜索</Link>
      {!loaded ? null : user ? (
        <>
          {user.is_admin ? <Link href="/admin/reviews">审核</Link> : null}
          <span className="nav-user">{user.display_name || user.phone || "我的账户"}</span>
          <button type="button" className="link-button" onClick={onLogout}>
            退出
          </button>
        </>
      ) : (
        <>
          <Link href="/login">登录</Link>
          <Link href="/register">注册</Link>
        </>
      )}
    </nav>
  );
}
