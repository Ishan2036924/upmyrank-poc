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

const LS_TOKEN      = 'umr_token'
const LS_STUDENT_ID = 'umr_student_id'
const LS_NAME       = 'umr_name'

interface AuthState {
  token:      string | null
  studentId:  string | null
  name:       string | null
  isLoading:  boolean
  login:  (token: string, studentId: string, name: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthState>({
  token:     null,
  studentId: null,
  name:      null,
  isLoading: true,
  login:  () => {},
  logout: () => {},
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
    (newToken: string, newStudentId: string, newName: string) => {
      localStorage.setItem(LS_TOKEN,      newToken)
      localStorage.setItem(LS_STUDENT_ID, newStudentId)
      localStorage.setItem(LS_NAME,       newName)
      setToken(newToken)
      setStudentId(newStudentId)
      setName(newName)
    },
    [],
  )

  const logout = useCallback(() => {
    localStorage.removeItem(LS_TOKEN)
    localStorage.removeItem(LS_STUDENT_ID)
    localStorage.removeItem(LS_NAME)
    setToken(null)
    setStudentId(null)
    setName(null)
    router.push('/auth/login')
  }, [router])

  return (
    <AuthContext.Provider value={{ token, studentId, name, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
