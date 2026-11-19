"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

/**
 * While any visible account is still being collected ("采集中…"), softly
 * re-fetch the server components every few seconds so metrics/averages appear
 * incrementally instead of only after the whole batch finishes. Stops after
 * `maxTicks` refreshes or as soon as collection ends.
 */
export function CollectingAutoRefresh({
  active,
  intervalMs = 3000,
  maxTicks = 20,
}: {
  active: boolean;
  intervalMs?: number;
  maxTicks?: number;
}) {
  const router = useRouter();
  const ticks = useRef(0);

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
      ticks.current += 1;
      router.refresh();
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [active, intervalMs, maxTicks, router]);

  return null;
}
