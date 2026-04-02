import { Menu, LogOut } from 'lucide-react'
import { useAuthStore } from '../../stores/authStore'
import { useNavigate } from 'react-router-dom'

interface HeaderProps {
  onMenuToggle: () => void
}

export default function Header({ onMenuToggle }: HeaderProps) {
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="flex h-16 items-center justify-between border-b bg-white px-6">
      <button
        onClick={onMenuToggle}
        className="rounded-lg p-2 hover:bg-gray-100"
      >
        <Menu className="h-5 w-5" />
      </button>

      <button
        onClick={handleLogout}
        className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-600 hover:bg-gray-100"
      >
        <LogOut className="h-4 w-4" />
        Logout
      </button>
    </header>
  )
}
