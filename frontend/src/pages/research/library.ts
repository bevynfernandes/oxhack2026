import { useMemo, useSyncExternalStore } from "react";

export type ResearchEntry = {
  path: string;
  name: string;
  domain: string;
  kind: "report" | "saved" | "job";
  asOf: string | null;
  visitedAt: string;
  watched: boolean;
  notes: string;
  reviewOn: string;
};
const KEY = "signalshift.research-library.v1";
const EVENT = "signalshift-research-library";

/** Allow only application-owned report, saved dossier and job links. */
export function researchKind(path: string): ResearchEntry["kind"] | null {
  if (/^\/research\/(v2\/)?reports\/[\w-]+$/.test(path)) return "report";
  if (/^\/companies\/[\w-]+\/[\w-]+$/.test(path)) return "saved";
  if (/^\/research\/(v2\/)?jobs\/[\w-]+$/.test(path)) return "job";
  return null;
}

/** Treat browser storage as untrusted; never load arbitrary routes from it. */
export function parseLibrary(raw: string | null): ResearchEntry[] {
  try {
    const rows: unknown = JSON.parse(raw ?? "[]");
    if (!Array.isArray(rows)) return [];
    const seen = new Set<string>();
    return rows.filter((row): row is ResearchEntry => {
      if (!row || typeof row !== "object") return false;
      const r = row as ResearchEntry;
      const valid =
        typeof r.path === "string" &&
        Boolean(researchKind(r.path)) &&
        researchKind(r.path) === r.kind &&
        typeof r.name === "string" &&
        r.name.length <= 300 &&
        typeof r.domain === "string" &&
        r.domain.length <= 2048 &&
        (r.asOf === null || typeof r.asOf === "string") &&
        typeof r.visitedAt === "string" &&
        Number.isFinite(Date.parse(r.visitedAt)) &&
        typeof r.watched === "boolean" &&
        typeof r.notes === "string" &&
        r.notes.length <= 4000 &&
        typeof r.reviewOn === "string" &&
        /^(\d{4}-\d{2}-\d{2})?$/.test(r.reviewOn) &&
        !seen.has(r.path);
      if (valid) seen.add(r.path);
      return valid;
    });
  } catch {
    return [];
  }
}
function readRaw() {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(EVENT, callback);
  };
}
/** Reactive browser-local history, shared across tabs with no server writes. */
export function useResearchLibrary() {
  const raw = useSyncExternalStore(subscribe, readRaw, () => null);
  return useMemo(() => parseLibrary(raw), [raw]);
}
function write(rows: ResearchEntry[]) {
  localStorage.setItem(KEY, JSON.stringify(rows));
  window.dispatchEvent(new Event(EVENT));
}
/** Record an exact resource without replacing notes or claiming account persistence. */
export function rememberResearch(
  entry: Pick<ResearchEntry, "path" | "name" | "domain" | "asOf">,
) {
  const kind = researchKind(entry.path);
  if (!kind) return;
  const rows = parseLibrary(readRaw());
  const previous = rows.find((row) => row.path === entry.path);
  write([
    {
      ...previous,
      ...entry,
      asOf: entry.asOf ?? previous?.asOf ?? null,
      kind,
      visitedAt: new Date().toISOString(),
      watched: previous?.watched ?? false,
      notes: previous?.notes ?? "",
      reviewOn: previous?.reviewOn ?? "",
    },
    ...rows.filter((row) => row.path !== entry.path),
  ]);
}
/** Save only personal annotations; research facts and immutable reports stay unchanged. */
export function annotateResearch(
  path: string,
  patch: Pick<ResearchEntry, "watched" | "notes" | "reviewOn">,
) {
  if (
    patch.notes.length > 4000 ||
    !/^(\d{4}-\d{2}-\d{2})?$/.test(patch.reviewOn)
  )
    throw new Error("Invalid research note");
  write(
    parseLibrary(readRaw()).map((row) =>
      row.path === path ? { ...row, ...patch } : row,
    ),
  );
}
/** Forget a local link only; never delete the underlying report. */
export function forgetResearch(path: string) {
  write(parseLibrary(readRaw()).filter((row) => row.path !== path));
}
