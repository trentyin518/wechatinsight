"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { recollectAccount } from "@/lib/clientApi";
import { toApiError } from "@/lib/errors";

export function RecollectButton({ accountId }: { accountId: number }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onClick() {
    if (busy) return;
    const ok = window.confirm(
      "将重新拉取该账号最新文章并抓取指标，可能产生数据源费用。确定继续吗？",
    );
    if (!ok) return;
    setBusy(true);
    setMessage(null);
    try {
      const res = await recollectAccount(accountId);
      setMessage(res.message);
      if (res.queued) {
        window.setTimeout(() => router.refresh(), 4000);
      }
    } catch (err) {
      setMessage(toApiError(err).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        className="acct-btn"
        onClick={onClick}
        disabled={busy}
        title="强制为该账号重新拉取最新文章并抓取指标"
      >
        {busy ? "提交中…" : "重新采集"}
      </button>
      {message ? (
        <p className="muted small" style={{ marginTop: 6 }}>
          {message}
        </p>
      ) : null}
    </div>
  );
}
