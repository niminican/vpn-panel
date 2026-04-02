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
} from 'lucide-react'
import { cn } from '../../lib/utils'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/destinations', icon: Globe, label: 'Destinations' },
  { to: '/users', icon: Users, label: 'Users' },
  { to: '/logs', icon: ScrollText, label: 'Logs' },
  { to: '/packages', icon: Package, label: 'Packages' },
  { to: '/alerts', icon: Bell, label: 'Alerts' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

interface SidebarProps {
  open: boolean
  onToggle: () => void
}

export default function Sidebar({ open }: SidebarProps) {
  return (
    <aside
      className={cn(
        'flex flex-col bg-gray-900 text-white transition-all duration-300',
        open ? 'w-64' : 'w-16'
      )}
    >
      <div className="flex h-16 items-center gap-3 px-4 border-b border-gray-700">
        <Shield className="h-8 w-8 text-blue-400 flex-shrink-0" />
        {open && <span className="text-lg font-bold">VPN Panel</span>}
      </div>

      <nav className="flex-1 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              )
            }
          >
            <item.icon className="h-5 w-5 flex-shrink-0" />
            {open && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
