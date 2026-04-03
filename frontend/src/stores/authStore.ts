import { create } from 'zustand'
import api from '../api/client'

interface AdminInfo {
  id: number
  username: string
  role: string
  permissions: string[]
}

interface AuthState {
  isAuthenticated: boolean
  loading: boolean
  admin: AdminInfo | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => void
  fetchAdmin: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: !!localStorage.getItem('access_token'),
  loading: false,
  admin: null,

  login: async (username: string, password: string) => {
    set({ loading: true })
    try {
      const res = await api.post('/auth/login', { username, password })
      localStorage.setItem('access_token', res.data.access_token)
      localStorage.setItem('refresh_token', res.data.refresh_token)
      set({ isAuthenticated: true, loading: false })
      // Fetch admin info after login
      try {
        const me = await api.get('/admins/me')
        set({ admin: me.data })
      } catch { /* ignore */ }
    } catch (err) {
      set({ loading: false })
      throw err
    }
  },

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ isAuthenticated: false, admin: null })
  },

  checkAuth: () => {
    set({ isAuthenticated: !!localStorage.getItem('access_token') })
  },

  fetchAdmin: async () => {
    try {
      const me = await api.get('/admins/me')
      set({ admin: me.data })
    } catch { /* ignore */ }
  },
}))
