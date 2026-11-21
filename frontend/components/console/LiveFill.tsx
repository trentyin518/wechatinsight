"use client";

import { useEffect, useMemo, useState } from "react";

import { searchAccountsClient, searchArticlesClient } from "@/lib/clientApi";
import {
  consoleQueryToApiParams,
  consoleQueryToArticleApiParams,
  type ConsoleQuery,
} from "@/lib/consoleFilters";
import type { AccountSearchResponse, ArticleSearchResponse } from "@/lib/types";
import { AccountResultsView } from "./AccountResultsView";
import { ArticleResultsView } from "./ArticleResultsView";
import { ResultsPending } from "./ResultsPending";
import { StateMessage } from "@/components/StateMessage";

const MAX_PENDING_ATTEMPTS = 8; // ~12s of "pending" polling before giving up
const PENDING_INTERVAL_MS = 1500;
const COLLECT_INTERVAL_MS = 4000;
const MAX_COLLECT_TICKS = 20; // ~80s of progressive "采集中" refresh

function useLiveFill<T>(
  cq: ConsoleQuery,
  fetch: () => Promise<T>,
): T | "loading" | "empty" | { error: string } {
  const key = useMemo(() => JSON.stringify(cq), [cq]);
  const [state, setState] = useState<T | "loading" | "empty" | { error: string }>("loading");
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    setState("loading");

    const load = () => {
      fetch()
        .then((data) => {
          if (cancelled) return;
          const result = data as T & { items?: unknown[]; source?: string };
          if (result.source === "pending") {
            attempts += 1;
            if (attempts < MAX_PENDING_ATTEMPTS) {
              timer = setTimeout(load, PENDING_INTERVAL_MS);
              setState("loading");
            } else {
              setState("empty");
            }
            return;
          }
          const has = Array.isArray(result.items) ? result.items.length > 0 : true;
          setState(has ? (data as T) : "empty");
        })
        .catch((err) => {
          if (!cancelled) setState({ error: err?.message ?? "搜索失败" });
        });
    };

    load();
    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}

type AccountState =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "error"; message: string }
  | { kind: "ok"; data: AccountSearchResponse };

export function LiveFillAccounts({ cq, selectedIds }: { cq: ConsoleQuery; selectedIds: number[] }) {
  const key = useMemo(() => JSON.stringify(cq), [cq]);
  const [state, setState] = useState<AccountState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let pendingAttempts = 0;
    let collectTicks = 0;
    setState({ kind: "loading" });

    const load = () => {
      searchAccountsClient(consoleQueryToApiParams(cq))
        .then((data) => {
          if (cancelled) return;
          // Cache cold on the backend: it primed in the background — poll again.
          if (data.source === "pending" && data.items.length === 0) {
            pendingAttempts += 1;
            if (pendingAttempts < MAX_PENDING_ATTEMPTS) {
              setState({ kind: "loading" });
              timer = setTimeout(load, PENDING_INTERVAL_MS);
            } else {
              setState({ kind: "empty" });
            }
            return;
          }
          if (data.items.length === 0) {
            setState({ kind: "empty" });
            return;
          }
          setState({ kind: "ok", data });
          // While accounts are still being collected, softly re-fetch so their
          // metrics appear incrementally (replaces the old router.refresh loop).
          if (data.items.some((a) => a.collecting) && collectTicks < MAX_COLLECT_TICKS) {
            collectTicks += 1;
            timer = setTimeout(load, COLLECT_INTERVAL_MS);
          }
        })
        .catch((err) => {
          if (!cancelled) setState({ kind: "error", message: err?.message ?? "搜索失败" });
        });
    };

    load();
    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (state.kind === "loading") return <ResultsPending mode="name" />;
  if (state.kind === "empty")
    return (
      <StateMessage
        title="没有符合条件的公众号"
        description="可尝试放宽筛选条件，或更换关键词。缺失指标的账号不会被对应的数值区间命中。"
      />
    );
  if (state.kind === "error")
    return <StateMessage tone="error" title="搜索失败" description={state.message} />;
  return <AccountResultsView cq={cq} data={state.data} selectedIds={selectedIds} />;
}

export function LiveFillArticles({ cq }: { cq: ConsoleQuery }) {
  const state = useLiveFill<ArticleSearchResponse>(
    cq,
    () => searchArticlesClient(consoleQueryToArticleApiParams(cq)),
  );
  if (state === "loading") return <ResultsPending mode="article" />;
  if (state === "empty")
    return (
      <StateMessage
        title="没有符合条件的文章"
        description="可尝试更换关键词或放宽筛选条件；文章检索仅覆盖已收录文章。"
      />
    );
  if ("error" in state)
    return <StateMessage tone="error" title="搜索失败" description={state.error} />;
  return <ArticleResultsView cq={cq} data={state} />;
}
