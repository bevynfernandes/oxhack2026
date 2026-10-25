export type SavedSearch = { query: string; watched: boolean };
const KEY = "signalshift.research-searches.v1";
/** Load only local filter values, never destinations or executable content. */
export function loadSavedSearches(): SavedSearch[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    if (!Array.isArray(value)) return [];
    return value.filter((row): row is SavedSearch =>
      Boolean(
        row &&
        typeof row === "object" &&
        typeof row.query === "string" &&
        row.query.length <= 200 &&
        typeof row.watched === "boolean" &&
        (row.query.trim() || row.watched),
      ),
    );
  } catch {
    return [];
  }
}
/** Persist search filters only; never launch research when saving or restoring them. */
export function storeSavedSearches(searches: SavedSearch[]) {
  localStorage.setItem(KEY, JSON.stringify(searches));
}
