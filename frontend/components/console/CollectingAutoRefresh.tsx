"use client";

import { useEffect, useRef, useTransition } from "react";
import { useRouter } from "next/navigation";

/**
 * While any visible account is still being collected ("采集中…"), softly
 * re-fetch the server components so metrics/averages appear incrementally.
 *
 * Self-pacing: a tick is skipped while the previous refresh is still resolving,
 * so slow refreshes never pile up into a refresh storm (which made
 * switching/searching feel frozen). Stops after `maxTicks` or once idle.
 */
export function CollectingAutoRefresh({
  active,
  intervalMs = 4000,
  maxTicks = 15,
}: {
  active: boolean;
  intervalMs?: number;
  maxTicks?: number;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const ticks = useRef(0);
  const pendingRef = useRef(false);
  pendingRef.current = isPending;

  useEffect(() => {
    if (!active) {
      ticks.current = 0;
      return;
    }
    const id = window.setInterval(() => {
      if (ticks.current >= maxTicks) {
        window.clearInterval(id);
        return;
      }
      if (pendingRef.current) return; // previous refresh still in flight — skip
      ticks.current += 1;
      startTransition(() => router.refresh());
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [active, intervalMs, maxTicks, router]);

  return null;
}
