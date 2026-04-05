import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  Globe,
  ScrollText,
  Package,
  Settings,
  Shield,
  Bell,
  UserCog,
  ClipboardList,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { useAuthStore } from '../../stores/authStore'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/destinations', icon: Globe, label: 'Destinations' },
  { to: '/users', icon: Users, label: 'Users' },
  { to: '/logs', icon: ScrollText, label: 'Logs' },
  { to: '/packages', icon: Package, label: 'Packages' },
  { to: '/alerts', icon: Bell, label: 'Alerts' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

const superAdminItems = [
  { to: '/admin-management', icon: UserCog, label: 'Admins' },
  { to: '/audit-log', icon: ClipboardList, label: 'Activity Log' },
]

interface SidebarProps {
  open: boolean
  isMobile: boolean
  onToggle: () => void
  onNavigate: () => void
}

export default function Sidebar({ open, isMobile, onNavigate }: SidebarProps) {
  const admin = useAuthStore(s => s.admin)
  const isSuperAdmin = admin?.role === 'super_admin'

  const allItems = isSuperAdmin ? [...navItems, ...superAdminItems] : navItems

  if (!open && isMobile) return null

  return (
    <aside
      className={cn(
        'flex flex-col bg-gray-900 text-white transition-all duration-300',
        isMobile
          ? 'fixed inset-y-0 left-0 z-40 w-56 shadow-2xl'
          : open ? 'w-64' : 'w-16'
      )}
    >
      <div className="flex h-16 items-center gap-3 px-4 border-b border-gray-700">
        <Shield className="h-8 w-8 text-blue-400 flex-shrink-0" />
        {(open || isMobile) && <span className="text-lg font-bold">VPN Panel</span>}
      </div>

      <nav className="flex-1 py-4 space-y-1 overflow-y-auto">
        {allItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-4 py-2 sm:py-2.5 text-xs sm:text-sm transition-colors',
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              )
            }
          >
            <item.icon className="h-5 w-5 flex-shrink-0" />
            {(open || isMobile) && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
