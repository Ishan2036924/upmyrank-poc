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
    // v0.20.12 — surface the silent-logout transition. When the refresh
    // token is also expired we must redirect to /auth/login, but users who
    // experienced "I was logged in yesterday, why am I logged out?" need
    // the WHY. The login page reads `?reason=session_expired` and shows
    // a clarifying toast.
    if (typeof window !== 'undefined') {
      localStorage.removeItem(LS_TOKEN)
      localStorage.removeItem(LS_REFRESH_TOKEN)
      window.location.href = '/auth/login?reason=session_expired'
    }
    throw new Error('Session expired. Please log in again.')
  }
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// v0.20.12 — earlier + more specific cold-start toast. Was 8s + generic;
// now 3s + sets the right expectation ("up to 60 sec on free tier"). When
// Render Starter is provisioned this toast effectively never fires (warm
// requests return in <2 s); on free tier it converts the "is it broken?"
// reflex into a "ah, just waking up" reaction.
let _coldStartToastShown = false
async function _showColdStartToast() {
  if (_coldStartToastShown) return
  _coldStartToastShown = true
  setTimeout(() => { _coldStartToastShown = false }, 60_000)  // re-arm after 1 min
  try {
    const { toast } = await import('sonner')
    toast.info('Waking up the server — this can take up to a minute on first load.', {
      description: 'Subsequent requests will be fast. Sit tight!',
      duration: 8000,
    })
  } catch {
    // sonner may not be available — fail silent.
  }
}

// Render free tier cold-starts can take up to 50s.
// Retry up to 3 times with increasing delays before giving up.
async function fetchWithRetry(input: string, init: RequestInit): Promise<Response> {
  const delays = [5000, 15000, 30000]
  let lastError: unknown
  for (let i = 0; i <= delays.length; i++) {
    // v0.20.12 — toast at 3 s (was 8 s) so we beat the user's "is this
    // broken?" instinct. Only fires on the FIRST attempt; retries don't spam.
    let toastTimer: ReturnType<typeof setTimeout> | null = null
    if (i === 0 && typeof window !== 'undefined') {
      toastTimer = setTimeout(_showColdStartToast, 3000)
    }
    try {
      const res = await fetch(input, init)
      if (toastTimer) clearTimeout(toastTimer)
      return res
    } catch (err) {
      if (toastTimer) clearTimeout(toastTimer)
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

// v0.20.2 — used by /settings PATCH /student/{id}
export async function apiPatch(endpoint: string, body: unknown) {
  const res = await fetchWithRetry(`${API_URL}${endpoint}`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(body),
  })
  return handleResponse(res, async () => {
    const token = getToken()
    return fetchWithRetry(`${API_URL}${endpoint}`, {
      method: 'PATCH',
      headers: authHeaders(token ?? undefined),
      body: JSON.stringify(body),
    })
  })
}
