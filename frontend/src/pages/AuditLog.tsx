import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import api from '../api/client'
import { formatDate } from '../lib/utils'

interface AuditEntry {
  id: number
  admin_id: number
  admin_username: string
  action: string
  resource_type: string | null
  resource_id: number | null
  details: string | null
  ip_address: string | null
  user_agent: string | null
  device_info: string | null
  created_at: string
}

const ACTION_COLORS: Record<string, string> = {
  login: 'bg-blue-100 text-blue-700',
  create_user: 'bg-green-100 text-green-700',
  delete_user: 'bg-red-100 text-red-700',
  toggle_user: 'bg-yellow-100 text-yellow-700',
  create_admin: 'bg-purple-100 text-purple-700',
  delete_admin: 'bg-red-100 text-red-700',
  update_admin: 'bg-orange-100 text-orange-700',
  change_password: 'bg-gray-100 text-gray-700',
  update_config: 'bg-indigo-100 text-indigo-700',
}

export default function AuditLog() {
  const [logs, setLogs] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [filters, setFilters] = useState({ admin_username: '', action: '' })

  const fetchLogs = async () => {
    try {
      const params: Record<string, string | number> = { skip: page * 50, limit: 50 }
      if (filters.admin_username) params.admin_username = filters.admin_username
      if (filters.action) params.action = filters.action
      const res = await api.get('/admins/audit-logs', { params })
      setLogs(res.data.logs)
      setTotal(res.data.total)
    } catch {
      // May not have permission
    }
  }

  useEffect(() => { fetchLogs() }, [page, filters])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Activity Log ({total})</h1>

      <div className="flex gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input type="text" placeholder="Admin username..."
            value={filters.admin_username}
            onChange={e => setFilters({ ...filters, admin_username: e.target.value })}
            className="rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none" />
        </div>
        <select value={filters.action} onChange={e => setFilters({ ...filters, action: e.target.value })}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none">
          <option value="">All actions</option>
          <option value="login">Login</option>
          <option value="create_user">Create User</option>
          <option value="delete_user">Delete User</option>
          <option value="toggle_user">Toggle User</option>
          <option value="create_admin">Create Admin</option>
          <option value="update_admin">Update Admin</option>
          <option value="delete_admin">Delete Admin</option>
          <option value="change_password">Change Password</option>
          <option value="update_config">Update Config</option>
        </select>
      </div>

      <div className="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Admin</th>
              <th className="px-4 py-3">Action</th>
              <th className="px-4 py-3">Details</th>
              <th className="px-4 py-3">IP Address</th>
              <th className="px-4 py-3">Device</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">No activity logs yet.</td>
              </tr>
            ) : (
              logs.map(log => (
                <tr key={log.id} className="border-b last:border-b-0 hover:bg-gray-50">
                  <td className="px-4 py-2.5 text-xs text-gray-500">{formatDate(log.created_at)}</td>
                  <td className="px-4 py-2.5 font-medium">{log.admin_username}</td>
                  <td className="px-4 py-2.5">
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${ACTION_COLORS[log.action] || 'bg-gray-100 text-gray-600'}`}>
                      {log.action.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-500 max-w-[200px] truncate" title={log.details || ''}>
                    {log.details || '-'}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-gray-500">{log.ip_address || '-'}</td>
                  <td className="px-4 py-2.5 text-xs text-gray-500" title={log.user_agent || ''}>
                    {log.device_info || '-'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {total > 50 && (
          <div className="flex items-center justify-between border-t px-4 py-3">
            <span className="text-sm text-gray-500">
              Showing {page * 50 + 1}-{Math.min((page + 1) * 50, total)} of {total}
            </span>
            <div className="flex gap-2">
              <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}
                className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-gray-50">Previous</button>
              <button onClick={() => setPage(page + 1)} disabled={(page + 1) * 50 >= total}
                className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-gray-50">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
