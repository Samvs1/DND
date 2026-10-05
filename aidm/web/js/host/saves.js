// The list of saved campaigns for the host's Load control (GET /api/saves). A failure is shown as friendly text.

export async function fetchSaves(fetchFn = fetch) {
  try {
    const response = await fetchFn('/api/saves');
    if (!response.ok) return null;
    const rows = await response.json();
    return Array.isArray(rows) ? rows : null;
  } catch {
    return null;
  }
}
