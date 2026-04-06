const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const LS_TOKEN         = 'umr_token'
const LS_REFRESH_TOKEN = 'umr_refresh_token'

function getToken(): string | null {
  try { return localStorage.getItem(LS_TOKEN) } catch { return null }
}

function authHeaders(token?: string): Record<string, string> {
  const t = token ?? getToken()
  return t
    ? { 'Content-Type': 'application/json', Authorization: `Bearer ${t}` }
    : { 'Content-Type': 'application/json' }
}

async function tryRefresh(): Promise<string | null> {
  try {
    const stored = localStorage.getItem(LS_REFRESH_TOKEN)
    if (!stored) return null
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: stored }),
    })
    if (!res.ok) return null
    const data = await res.json()
    localStorage.setItem(LS_TOKEN, data.token)
    if (data.refresh_token) localStorage.setItem(LS_REFRESH_TOKEN, data.refresh_token)
    return data.token as string
  } catch {
    return null
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function handleResponse(res: Response, retry: () => Promise<Response>): Promise<any> {
  if (res.status === 401) {
    const newToken = await tryRefresh()
    if (newToken) {
      const retried = await retry()
      if (!retried.ok) throw new Error(await retried.text())
      return retried.json()
    }
    if (typeof window !== 'undefined') {
      localStorage.removeItem(LS_TOKEN)
      localStorage.removeItem(LS_REFRESH_TOKEN)
      window.location.href = '/auth/login'
    }
    throw new Error('Session expired. Please log in again.')
  }
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// Render free tier cold-starts can take up to 50s.
// Retry up to 3 times with increasing delays before giving up.
async function fetchWithRetry(input: string, init: RequestInit): Promise<Response> {
  const delays = [5000, 15000, 30000]
  let lastError: unknown
  for (let i = 0; i <= delays.length; i++) {
    try {
      return await fetch(input, init)
    } catch (err) {
      lastError = err
      if (i < delays.length) {
        await new Promise((r) => setTimeout(r, delays[i]))
      }
    }
  }
  throw lastError
}

/** Silently wake up the Render backend. Call on page mount so the server
 *  is warm by the time the user submits a form. */
export function pingBackend(): void {
  fetch(`${API_URL}/health`).catch(() => {/* silent */})
}

export async function apiPost(endpoint: string, body: unknown) {
  const res = await fetchWithRetry(`${API_URL}${endpoint}`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  })
  return handleResponse(res, async () => {
    const token = getToken()
    return fetchWithRetry(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers: authHeaders(token ?? undefined),
      body: JSON.stringify(body),
    })
  })
}

export async function apiGet(endpoint: string) {
  const res = await fetchWithRetry(`${API_URL}${endpoint}`, { headers: authHeaders() })
  return handleResponse(res, async () => {
    const token = getToken()
    return fetchWithRetry(`${API_URL}${endpoint}`, { headers: authHeaders(token ?? undefined) })
  })
}
