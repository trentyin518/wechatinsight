import Link from "next/link";
import type { ReactNode } from "react";

import { ConsoleSidebar } from "@/components/console/ConsoleSidebar";
import { getServerSelection } from "@/lib/api";
import { requireApprovedOrRedirect } from "@/lib/guard";

export default async function ConsoleLayout({ children }: { children: ReactNode }) {
  await requireApprovedOrRedirect();

  const selection = await getServerSelection();
  const count = selection?.total ?? 0;

  return (
    <div className="console-wrap">
      <ConsoleSidebar />
      <div className="console-main">
        <div className="console-tabs">
          <span className="console-tab console-tab-active">公众号版</span>
          <span className="console-tab">视频号版</span>
          <Link className="console-selection-link" href="/console/selection">
            选号清单{count > 0 ? ` · ${count}` : ""}
          </Link>
        </div>
        {children}
      </div>
    </div>
  );
}
