import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import MainLayout from './components/layout/MainLayout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Users from './pages/Users'
import UserNew from './pages/UserNew'
import UserDetail from './pages/UserDetail'
import Destinations from './pages/Destinations'
import Logs from './pages/Logs'
import Packages from './pages/Packages'
import Settings from './pages/Settings'
import Alerts from './pages/Alerts'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <MainLayout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/users" element={<Users />} />
                <Route path="/users/new" element={<UserNew />} />
                <Route path="/users/:id" element={<UserDetail />} />
                <Route path="/destinations" element={<Destinations />} />
                <Route path="/logs" element={<Logs />} />
                <Route path="/packages" element={<Packages />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/alerts" element={<Alerts />} />
              </Routes>
            </MainLayout>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}
