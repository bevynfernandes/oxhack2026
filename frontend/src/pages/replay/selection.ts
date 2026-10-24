import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { DTO } from "../../api/client";

export type Receipt = { id: string; informed: boolean; result: DTO<"Reveal"> };
type Saved = { selected: string[]; revealed: boolean; receipts: Receipt[] };

/** Restore only selection IDs from a batch-specific URL or browser store. */
export function initialSelection(
  batchId: string,
  eligible: readonly string[],
  fallback: readonly string[],
): Saved {
  const allowed = new Set(eligible);
  let saved: Saved = { selected: [...fallback], revealed: false, receipts: [] };
  try {
    const raw: unknown = JSON.parse(
      localStorage.getItem(`signalshift:${batchId}`) ?? "null",
    );
    if (
      raw &&
      typeof raw === "object" &&
      "selected" in raw &&
      Array.isArray(raw.selected)
    ) {
      saved = {
        selected: raw.selected.filter(
          (value): value is string => typeof value === "string",
        ),
        revealed: "revealed" in raw && raw.revealed === true,
        receipts: [],
      };
    }
  } catch {
    /* Browser storage is optional; never replace API data. */
  }
  const params = new URLSearchParams(location.search);
  if (params.has("selection"))
    saved.selected = params.getAll("selection").filter(Boolean);
  saved.selected = [...new Set(saved.selected)]
    .filter((id) => allowed.has(id))
    .slice(0, 5);
  return saved;
}

/** Keep immutable score receipts in-session and persist selection/awareness per batch. */
export function useSelection(
  batchId: string,
  eligible: readonly string[],
  fallback: readonly string[],
) {
  const cache = useQueryClient();
  const [saved, setSaved] = useState(
    () =>
      cache.getQueryData<Saved>(["selection", batchId]) ??
      initialSelection(batchId, eligible, fallback),
  );
  const [storageWarning, setStorageWarning] = useState(false);
  function persist(next: Saved) {
    setSaved(next);
    cache.setQueryData(["selection", batchId], next);
    try {
      localStorage.setItem(
        `signalshift:${batchId}`,
        JSON.stringify({ selected: next.selected, revealed: next.revealed }),
      );
    } catch {
      setStorageWarning(true);
    }
  }
  function select(ids: string[]) {
    persist({ ...saved, selected: ids });
    const url = new URL(location.href);
    url.searchParams.delete("selection");
    (ids.length ? ids : [""]).forEach((id) =>
      url.searchParams.append("selection", id),
    );
    history.replaceState(history.state, "", url);
  }
  function record(result: DTO<"Reveal">) {
    persist({
      ...saved,
      revealed: true,
      receipts: [
        ...saved.receipts,
        { id: crypto.randomUUID(), informed: saved.revealed, result },
      ],
    });
  }
  return { ...saved, select, record, storageWarning };
}
