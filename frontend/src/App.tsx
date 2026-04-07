import { useEffect, Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import MainLayout from './components/layout/MainLayout'
import ErrorBoundary from './components/ErrorBoundary'

// Code splitting: lazy load all pages
const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Users = lazy(() => import('./pages/Users'))
const UserNew = lazy(() => import('./pages/UserNew'))
const UserDetail = lazy(() => import('./pages/UserDetail'))
const Destinations = lazy(() => import('./pages/Destinations'))
const Inbounds = lazy(() => import('./pages/Inbounds'))
const Logs = lazy(() => import('./pages/Logs'))
const Packages = lazy(() => import('./pages/Packages'))
const Settings = lazy(() => import('./pages/Settings'))
const Alerts = lazy(() => import('./pages/Alerts'))
const AdminManagement = lazy(() => import('./pages/AdminManagement'))
const AuditLog = lazy(() => import('./pages/AuditLog'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
    </div>
  )
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, admin, fetchAdmin } = useAuthStore()

  useEffect(() => {
    if (isAuthenticated && !admin) {
      fetchAdmin()
    }
  }, [isAuthenticated])

  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <MainLayout>
                  <Suspense fallback={<PageLoader />}>
                    <Routes>
                      <Route path="/" element={<Dashboard />} />
                      <Route path="/users" element={<Users />} />
                      <Route path="/users/new" element={<UserNew />} />
                      <Route path="/users/:id" element={<UserDetail />} />
                      <Route path="/destinations" element={<Destinations />} />
                      <Route path="/inbounds" element={<Inbounds />} />
                      <Route path="/logs" element={<Logs />} />
                      <Route path="/packages" element={<Packages />} />
                      <Route path="/settings" element={<Settings />} />
                      <Route path="/alerts" element={<Alerts />} />
                      <Route path="/admin-management" element={<AdminManagement />} />
                      <Route path="/audit-log" element={<AuditLog />} />
                    </Routes>
                  </Suspense>
                </MainLayout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
