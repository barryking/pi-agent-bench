/**
 * Fetch the first page from a cursor-based API.
 */
export async function fetchFirstPage(fetchPage, { signal } = {}) {
  return fetchPage({ cursor: null, signal });
}

/**
 * Fetch all cursor pages while detecting loops and respecting cancellation.
 */
export async function fetchAllPages(fetchPage, options = {}) {
  const { signal, maxPages = 100 } = options;
  if (!Number.isInteger(maxPages) || maxPages < 1) {
    throw new RangeError("maxPages must be a positive integer");
  }
  const items = [];
  const seen = new Set();
  let cursor = null;
  for (let pageNumber = 0; pageNumber < maxPages; pageNumber += 1) {
    const page = await fetchPage({ cursor, signal });
    items.push(...page.items);
    if (page.nextCursor === null) return items;
    if (seen.has(page.nextCursor)) throw new Error("repeated cursor");
    seen.add(page.nextCursor);
    cursor = page.nextCursor;
  }
  throw new Error("maxPages exceeded");
}
