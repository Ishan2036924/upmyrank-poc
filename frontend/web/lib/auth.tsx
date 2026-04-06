'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'
import { useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const LS_TOKEN         = 'umr_token'
const LS_REFRESH_TOKEN = 'umr_refresh_token'
const LS_STUDENT_ID    = 'umr_student_id'
const LS_NAME          = 'umr_name'

interface AuthState {
  token:        string | null
  studentId:    string | null
  name:         string | null
  isLoading:    boolean
  login:         (token: string, studentId: string, name: string, refreshToken?: string) => void
  logout:        () => void
  refreshToken:  () => Promise<string | null>
}

const AuthContext = createContext<AuthState>({
  token:        null,
  studentId:    null,
  name:         null,
  isLoading:    true,
  login:        () => {},
  logout:       () => {},
  refreshToken: async () => null,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [token,     setToken]     = useState<string | null>(null)
  const [studentId, setStudentId] = useState<string | null>(null)
  const [name,      setName]      = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // ── Load from localStorage on mount and validate ──────────────────────────
  useEffect(() => {
    const stored = {
      token:     localStorage.getItem(LS_TOKEN),
      studentId: localStorage.getItem(LS_STUDENT_ID),
      name:      localStorage.getItem(LS_NAME),
    }

    if (!stored.token || !stored.studentId) {
      setIsLoading(false)
      return
    }

    // Validate token is still good
    fetch(`${API_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${stored.token}` },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(() => {
        setToken(stored.token)
        setStudentId(stored.studentId)
        setName(stored.name)
      })
      .catch(() => {
        // Token expired — clear storage
        localStorage.removeItem(LS_TOKEN)
        localStorage.removeItem(LS_STUDENT_ID)
        localStorage.removeItem(LS_NAME)
      })
      .finally(() => setIsLoading(false))
  }, [])

  const login = useCallback(
    (newToken: string, newStudentId: string, newName: string, newRefreshToken?: string) => {
      localStorage.setItem(LS_TOKEN,      newToken)
      localStorage.setItem(LS_STUDENT_ID, newStudentId)
      localStorage.setItem(LS_NAME,       newName)
      if (newRefreshToken) localStorage.setItem(LS_REFRESH_TOKEN, newRefreshToken)
      setToken(newToken)
      setStudentId(newStudentId)
      setName(newName)
    },
    [],
  )

  const logout = useCallback(() => {
    localStorage.removeItem(LS_TOKEN)
    localStorage.removeItem(LS_REFRESH_TOKEN)
    localStorage.removeItem(LS_STUDENT_ID)
    localStorage.removeItem(LS_NAME)
    setToken(null)
    setStudentId(null)
    setName(null)
    router.push('/auth/login')
  }, [router])

  const refreshToken = useCallback(async (): Promise<string | null> => {
    const stored = localStorage.getItem(LS_REFRESH_TOKEN)
    if (!stored) return null
    try {
      const res = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: stored }),
      })
      if (!res.ok) throw new Error('refresh failed')
      const data = await res.json()
      localStorage.setItem(LS_TOKEN, data.token)
      if (data.refresh_token) localStorage.setItem(LS_REFRESH_TOKEN, data.refresh_token)
      setToken(data.token)
      return data.token as string
    } catch {
      // Refresh failed — log out
      localStorage.removeItem(LS_TOKEN)
      localStorage.removeItem(LS_REFRESH_TOKEN)
      localStorage.removeItem(LS_STUDENT_ID)
      localStorage.removeItem(LS_NAME)
      setToken(null)
      setStudentId(null)
      setName(null)
      return null
    }
  }, [])

  return (
    <AuthContext.Provider value={{ token, studentId, name, isLoading, login, logout, refreshToken }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
