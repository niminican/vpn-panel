import { create } from 'zustand'
import api from '../api/client'

interface AuthState {
  isAuthenticated: boolean
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: !!localStorage.getItem('access_token'),
  loading: false,

  login: async (username: string, password: string) => {
    set({ loading: true })
    try {
      const res = await api.post('/auth/login', { username, password })
      localStorage.setItem('access_token', res.data.access_token)
      localStorage.setItem('refresh_token', res.data.refresh_token)
      set({ isAuthenticated: true, loading: false })
    } catch {
      set({ loading: false })
      throw new Error('Invalid credentials')
    }
  },

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ isAuthenticated: false })
  },

  checkAuth: () => {
    set({ isAuthenticated: !!localStorage.getItem('access_token') })
  },
}))
