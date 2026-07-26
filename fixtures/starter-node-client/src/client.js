/**
 * Fetch the first page from a cursor-based API.
 */
export async function fetchFirstPage(fetchPage, { signal } = {}) {
  return fetchPage({ cursor: null, signal });
}
