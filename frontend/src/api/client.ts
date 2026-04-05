import axios from 'axios'
import toast from 'react-hot-toast'

const BASE = import.meta.env.BASE_URL?.replace(/\/+$/, '') || ''

const api = axios.create({
  baseURL: `${BASE}/api`,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status

    // Handle rate limiting
    if (status === 429) {
      const detail = error.response?.data?.detail || 'Too many requests. Please wait.'
      toast.error(detail)
      return Promise.reject(error)
    }

    // Handle permission denied
    if (status === 403) {
      toast.error('Permission denied')
      return Promise.reject(error)
    }

    // Handle auth errors
    if (status === 401 && !error.config.url?.includes('/auth/login')) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken && !error.config._retry) {
        error.config._retry = true
        try {
          const res = await axios.post(`${BASE}/api/auth/refresh`, {
            refresh_token: refreshToken,
          })
          localStorage.setItem('access_token', res.data.access_token)
          localStorage.setItem('refresh_token', res.data.refresh_token)
          error.config.headers.Authorization = `Bearer ${res.data.access_token}`
          return api(error.config)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = `${BASE}/login`
        }
      } else {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = `${BASE}/login`
      }
    }
    return Promise.reject(error)
  }
)

export default api
