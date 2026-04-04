import { createClient, SupabaseClient } from '@supabase/supabase-js'

// Lazy singleton — NOT created at module load time.
// Module-level createClient() runs during Next.js SSG/SSR static analysis and
// throws "supabaseUrl is required" because env vars aren't available then.
// Instead, the client is created on first actual use (always inside an event
// handler or useEffect, never during prerendering).
let _client: SupabaseClient | null = null

export function getSupabase(): SupabaseClient {
  if (!_client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL  || ''
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
    _client = createClient(url, key)
  }
  return _client
}
