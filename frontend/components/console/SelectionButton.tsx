"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { addSelection, removeSelection } from "@/lib/clientApi";

export function SelectionButton({
  accountId,
  initialSelected,
}: {
  accountId: number;
  initialSelected: boolean;
}) {
  const router = useRouter();
  const [selected, setSelected] = useState(initialSelected);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSelected(initialSelected);
  }, [initialSelected]);

  async function toggle() {
    if (busy) return;
    setBusy(true);
    try {
      if (selected) {
        await removeSelection(accountId);
      } else {
        await addSelection(accountId);
      }
      setSelected(!selected);
      router.refresh();
    } catch {
      // keep current state on failure
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      className={`acct-btn${selected ? " acct-btn-active" : ""}`}
      onClick={toggle}
      disabled={busy}
    >
      {selected ? "已加入选号清单" : "加入选号清单"}
    </button>
  );
}
