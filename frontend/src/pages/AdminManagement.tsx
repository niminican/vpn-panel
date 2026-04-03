import { useEffect, useState } from 'react'
import { Plus, Trash2, Edit2, X, Check, Shield } from 'lucide-react'
import api from '../api/client'
import toast from 'react-hot-toast'

interface AdminData {
  id: number
  username: string
  role: string
  permissions: string[]
  created_at: string
}

const ALL_PERMISSIONS = [
  { key: 'users.view', label: 'View Users' },
  { key: 'users.create', label: 'Create Users' },
  { key: 'users.edit', label: 'Edit Users' },
  { key: 'users.delete', label: 'Delete Users' },
  { key: 'destinations.view', label: 'View Destinations' },
  { key: 'destinations.manage', label: 'Manage Destinations' },
  { key: 'logs.view', label: 'View Logs' },
  { key: 'packages.manage', label: 'Manage Packages' },
  { key: 'settings.manage', label: 'Manage Settings' },
  { key: 'alerts.view', label: 'View Alerts' },
]

export default function AdminManagement() {
  const [admins, setAdmins] = useState<AdminData[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState({ username: '', password: '', role: 'admin', permissions: [] as string[] })

  useEffect(() => { fetchAdmins() }, [])

  const fetchAdmins = async () => {
    try {
      const res = await api.get('/admins')
      setAdmins(res.data)
    } catch {
      toast.error('Failed to load admins')
    }
  }

  const createAdmin = async () => {
    if (!form.username || !form.password) { toast.error('Username and password required'); return }
    try {
      await api.post('/admins', form)
      toast.success('Admin created')
      setShowCreate(false)
      setForm({ username: '', password: '', role: 'admin', permissions: [] })
      fetchAdmins()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create admin')
    }
  }

  const updateAdmin = async (adminId: number) => {
    try {
      const payload: any = { permissions: form.permissions, role: form.role }
      if (form.password) payload.password = form.password
      if (form.username) payload.username = form.username
      await api.put(`/admins/${adminId}`, payload)
      toast.success('Admin updated')
      setEditingId(null)
      fetchAdmins()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update admin')
    }
  }

  const deleteAdmin = async (adminId: number, username: string) => {
    if (!confirm(`Delete admin "${username}"?`)) return
    try {
      await api.delete(`/admins/${adminId}`)
      toast.success('Admin deleted')
      fetchAdmins()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to delete admin')
    }
  }

  const togglePermission = (perm: string) => {
    setForm(f => ({
      ...f,
      permissions: f.permissions.includes(perm)
        ? f.permissions.filter(p => p !== perm)
        : [...f.permissions, perm]
    }))
  }

  const startEdit = (admin: AdminData) => {
    setEditingId(admin.id)
    setForm({ username: admin.username, password: '', role: admin.role, permissions: [...admin.permissions] })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Admin Management</h1>
        <button onClick={() => { setShowCreate(true); setForm({ username: '', password: '', role: 'admin', permissions: [] }) }}
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          <Plus className="h-4 w-4" /> New Admin
        </button>
      </div>

      {/* Create Admin Form */}
      {showCreate && (
        <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100 space-y-4">
          <h3 className="text-sm font-medium text-gray-700">Create New Admin</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input type="text" placeholder="Username" value={form.username}
              onChange={e => setForm({ ...form, username: e.target.value })}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
            <input type="password" placeholder="Password" value={form.password}
              onChange={e => setForm({ ...form, password: e.target.value })}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
            <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none">
              <option value="admin">Admin (Limited)</option>
              <option value="super_admin">Super Admin</option>
            </select>
          </div>
          {form.role === 'admin' && (
            <div>
              <p className="text-xs text-gray-500 mb-2">Permissions:</p>
              <div className="flex flex-wrap gap-2">
                {ALL_PERMISSIONS.map(p => (
                  <button key={p.key} onClick={() => togglePermission(p.key)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium border transition-colors ${
                      form.permissions.includes(p.key)
                        ? 'bg-blue-50 border-blue-300 text-blue-700'
                        : 'bg-white border-gray-200 text-gray-500 hover:border-gray-300'
                    }`}>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="flex gap-2">
            <button onClick={createAdmin}
              className="flex items-center gap-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
              <Check className="h-4 w-4" /> Create
            </button>
            <button onClick={() => setShowCreate(false)}
              className="rounded-lg border px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Admin List */}
      <div className="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
              <th className="px-4 py-3">Username</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Permissions</th>
              <th className="px-4 py-3 w-24">Actions</th>
            </tr>
          </thead>
          <tbody>
            {admins.map(a => (
              <tr key={a.id} className="border-b last:border-b-0 hover:bg-gray-50">
                {editingId === a.id ? (
                  <>
                    <td className="px-4 py-2.5">
                      <input type="text" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })}
                        className="w-full rounded border border-gray-300 px-2 py-1 text-sm" />
                      <input type="password" placeholder="New password (optional)" value={form.password}
                        onChange={e => setForm({ ...form, password: e.target.value })}
                        className="w-full rounded border border-gray-300 px-2 py-1 text-sm mt-1" />
                    </td>
                    <td className="px-4 py-2.5">
                      <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}
                        className="rounded border border-gray-300 px-2 py-1 text-sm">
                        <option value="admin">Admin</option>
                        <option value="super_admin">Super Admin</option>
                      </select>
                    </td>
                    <td className="px-4 py-2.5">
                      {form.role === 'admin' && (
                        <div className="flex flex-wrap gap-1">
                          {ALL_PERMISSIONS.map(p => (
                            <button key={p.key} onClick={() => togglePermission(p.key)}
                              className={`rounded px-2 py-0.5 text-xs border ${
                                form.permissions.includes(p.key)
                                  ? 'bg-blue-50 border-blue-300 text-blue-700'
                                  : 'bg-white border-gray-200 text-gray-400'
                              }`}>
                              {p.label}
                            </button>
                          ))}
                        </div>
                      )}
                      {form.role === 'super_admin' && <span className="text-xs text-gray-400">All permissions</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1">
                        <button onClick={() => updateAdmin(a.id)} className="rounded p-1 text-green-600 hover:bg-green-50">
                          <Check className="h-4 w-4" />
                        </button>
                        <button onClick={() => setEditingId(null)} className="rounded p-1 text-gray-400 hover:bg-gray-100">
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="px-4 py-2.5 font-medium">
                      <div className="flex items-center gap-2">
                        {a.username}
                        {a.role === 'super_admin' && <Shield className="h-4 w-4 text-blue-500" />}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        a.role === 'super_admin' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
                      }`}>
                        {a.role === 'super_admin' ? 'Super Admin' : 'Admin'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      {a.role === 'super_admin' ? (
                        <span className="text-xs text-gray-400">All permissions</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {a.permissions.length === 0 ? (
                            <span className="text-xs text-gray-400">No permissions</span>
                          ) : (
                            a.permissions.map(p => (
                              <span key={p} className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">
                                {ALL_PERMISSIONS.find(ap => ap.key === p)?.label || p}
                              </span>
                            ))
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1">
                        <button onClick={() => startEdit(a)} className="rounded p-1 text-gray-400 hover:bg-gray-100">
                          <Edit2 className="h-4 w-4" />
                        </button>
                        <button onClick={() => deleteAdmin(a.id, a.username)} className="rounded p-1 text-red-400 hover:bg-red-50">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
