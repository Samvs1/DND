// Fetches the manual text from the server (`/api/manual`). Failure throws; the view shows its plain message.
export async function fetchManual() {
  const response = await fetch('/api/manual', { headers: { Accept: 'text/markdown' } });
  if (!response.ok) throw new Error('manual unavailable');
  return response.text();
}
