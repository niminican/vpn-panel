import { Menu, LogOut, UserCircle } from 'lucide-react'
import { useAuthStore } from '../../stores/authStore'
import { useNavigate } from 'react-router-dom'

interface HeaderProps {
  onMenuToggle: () => void
}

export default function Header({ onMenuToggle }: HeaderProps) {
  const logout = useAuthStore((s) => s.logout)
  const admin = useAuthStore((s) => s.admin)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="flex h-14 sm:h-16 items-center justify-between border-b bg-white px-3 sm:px-6">
      <button
        onClick={onMenuToggle}
        className="rounded-lg p-2 hover:bg-gray-100"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="flex items-center gap-3">
        {admin && (
          <div className="flex items-center gap-1.5 text-sm text-gray-600">
            <UserCircle className="h-4 w-4" />
            <span className="font-medium">{admin.username}</span>
            <span className="hidden sm:inline text-xs text-gray-400">({admin.role === 'super_admin' ? 'Super Admin' : 'Admin'})</span>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-600 hover:bg-gray-100"
        >
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">Logout</span>
        </button>
      </div>
    </header>
  )
}
