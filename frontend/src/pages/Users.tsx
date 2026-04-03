import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Plus,
  Search,
  MoreVertical,
  Power,
  Trash2,
  RotateCcw,
  Eye,
} from 'lucide-react'
import api from '../api/client'
import { formatBytes, formatDate } from '../lib/utils'
import toast from 'react-hot-toast'

interface User {
  id: number
  username: string
  enabled: boolean
  assigned_ip: string
  destination_vpn_name: string | null
  bandwidth_used_up: number
  bandwidth_used_down: number
  bandwidth_limit_up: number | null
  bandwidth_limit_down: number | null
  is_online: boolean
  expiry_date: string | null
  created_at: string
}

export default function Users() {
  const [users, setUsers] = useState<User[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [menuOpen, setMenuOpen] = useState<number | null>(null)
  const navigate = useNavigate()

  // Close menu on outside click
  useEffect(() => {
    const handleClick = () => setMenuOpen(null)
    if (menuOpen !== null) {
      document.addEventListener('click', handleClick)
      return () => document.removeEventListener('click', handleClick)
    }
  }, [menuOpen])

  const fetchUsers = async () => {
    try {
      const res = await api.get('/users', { params: { search, limit: 50 } })
      setUsers(res.data.users)
      setTotal(res.data.total)
    } catch {
      toast.error('Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [search])

  const toggleUser = async (id: number) => {
    await api.post(`/users/${id}/toggle`)
    fetchUsers()
    setMenuOpen(null)
  }

  const resetBandwidth = async (id: number) => {
    await api.post(`/users/${id}/reset-bandwidth`)
    toast.success('Bandwidth reset')
    fetchUsers()
    setMenuOpen(null)
  }

  const deleteUser = async (id: number) => {
    if (!confirm('Are you sure you want to delete this user?')) return
    await api.delete(`/users/${id}`)
    toast.success('User deleted')
    fetchUsers()
    setMenuOpen(null)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Users ({total})</h1>
        <Link
          to="/users/new"
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          Add User
        </Link>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Search users..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-gray-300 py-2.5 pl-10 pr-4 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      <div className="rounded-xl bg-white shadow-sm border border-gray-100 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">IP</th>
              <th className="px-4 py-3">Destination</th>
              <th className="px-4 py-3">Upload</th>
              <th className="px-4 py-3">Download</th>
              <th className="px-4 py-3">Expiry</th>
              <th className="px-4 py-3 w-10"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                  No users found
                </td>
              </tr>
            ) : (
              users.map((user, idx) => (
                <tr
                  key={user.id}
                  className="border-b last:border-b-0 hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/users/${user.id}`)}
                >
                  <td className="px-4 py-3 font-medium">{user.username}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`h-2 w-2 rounded-full ${
                          user.is_online
                            ? 'bg-green-500'
                            : user.enabled
                            ? 'bg-yellow-400'
                            : 'bg-gray-300'
                        }`}
                      />
                      <span className="text-xs">
                        {user.is_online ? 'Online' : user.enabled ? 'Offline' : 'Disabled'}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500 font-mono text-xs">{user.assigned_ip}</td>
                  <td className="px-4 py-3 text-gray-500">{user.destination_vpn_name || '-'}</td>
                  <td className="px-4 py-3">
                    <span className="text-gray-700">{formatBytes(user.bandwidth_used_up)}</span>
                    {user.bandwidth_limit_up && (
                      <span className="text-gray-400 text-xs"> / {formatBytes(user.bandwidth_limit_up)}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-gray-700">{formatBytes(user.bandwidth_used_down)}</span>
                    {user.bandwidth_limit_down && (
                      <span className="text-gray-400 text-xs"> / {formatBytes(user.bandwidth_limit_down)}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{formatDate(user.expiry_date)}</td>
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <div className="relative">
                      <button
                        onClick={() => setMenuOpen(menuOpen === user.id ? null : user.id)}
                        className="rounded p-1 hover:bg-gray-100"
                      >
                        <MoreVertical className="h-4 w-4 text-gray-400" />
                      </button>
                      {menuOpen === user.id && (
                        <div className={`absolute right-0 z-20 w-44 rounded-lg bg-white shadow-lg border py-1 ${idx >= users.length - 2 ? 'bottom-full mb-1' : 'mt-1'}`}>
                          <button
                            onClick={() => navigate(`/users/${user.id}`)}
                            className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50"
                          >
                            <Eye className="h-4 w-4" /> View Details
                          </button>
                          <button
                            onClick={() => toggleUser(user.id)}
                            className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50"
                          >
                            <Power className="h-4 w-4" /> {user.enabled ? 'Disable' : 'Enable'}
                          </button>
                          <button
                            onClick={() => resetBandwidth(user.id)}
                            className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50"
                          >
                            <RotateCcw className="h-4 w-4" /> Reset Bandwidth
                          </button>
                          <button
                            onClick={() => deleteUser(user.id)}
                            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                          >
                            <Trash2 className="h-4 w-4" /> Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
