import { useEffect, useState, FormEvent } from 'react'
import {
  Plus,
  Globe,
  Play,
  Square,
  Trash2,
  Upload,
  Edit2,
  Users,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronDown,
  ChevronUp,
  X,
} from 'lucide-react'
import api from '../api/client'
import { formatDate, formatBytes } from '../lib/utils'
import toast from 'react-hot-toast'

interface Destination {
  id: number
  name: string
  protocol: string
  interface_name: string
  config_text: string | null
  enabled: boolean
  is_running: boolean
  start_mode: string
  user_count: number
  total_upload: number
  total_download: number
  created_at: string
}

interface DestUserStats {
  id: number
  username: string
  is_online: boolean
  bandwidth_used_up: number
  bandwidth_used_down: number
}

export default function Destinations() {
  const [destinations, setDestinations] = useState<Destination[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [form, setForm] = useState({
    name: '',
    protocol: 'auto',
    interface_name: '',
    config_text: '',
    start_mode: 'manual',
  })
  const [inputMode, setInputMode] = useState<'paste' | 'upload'>('paste')

  // User stats panel
  const [expandedDest, setExpandedDest] = useState<number | null>(null)
  const [destUsers, setDestUsers] = useState<DestUserStats[]>([])
  const [loadingUsers, setLoadingUsers] = useState(false)
  const [userSort, setUserSort] = useState<'download' | 'upload'>('download')

  const fetchDestinations = async () => {
    const res = await api.get('/destinations')
    setDestinations(res.data)
  }

  useEffect(() => {
    fetchDestinations()
  }, [])

  const fetchDestUsers = async (destId: number, sort: string) => {
    setLoadingUsers(true)
    try {
      const res = await api.get(`/destinations/${destId}/users`, { params: { sort_by: sort } })
      setDestUsers(res.data)
    } catch {
      toast.error('Failed to load users')
    } finally {
      setLoadingUsers(false)
    }
  }

  const toggleUserPanel = (destId: number) => {
    if (expandedDest === destId) {
      setExpandedDest(null)
    } else {
      setExpandedDest(destId)
      fetchDestUsers(destId, userSort)
    }
  }

  const changeSortAndFetch = (sort: 'download' | 'upload') => {
    setUserSort(sort)
    if (expandedDest) {
      fetchDestUsers(expandedDest, sort)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      if (editId) {
        await api.put(`/destinations/${editId}`, form)
        toast.success('Destination updated')
      } else {
        await api.post('/destinations', form)
        toast.success('Destination created')
      }
      setShowForm(false)
      setEditId(null)
      setForm({ name: '', protocol: 'auto', interface_name: '', config_text: '', start_mode: 'manual' })
      fetchDestinations()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed')
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const text = await file.text()
    setForm({ ...form, config_text: text })
    toast.success('Config file loaded')
  }

  const startDest = async (id: number) => {
    try {
      await api.post(`/destinations/${id}/start`)
      toast.success('VPN started successfully')
      fetchDestinations()
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to start VPN'
      toast.error(msg, { duration: 6000 })
    }
  }

  const stopDest = async (id: number) => {
    try {
      await api.post(`/destinations/${id}/stop`)
      toast.success('VPN stopped')
      fetchDestinations()
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to stop VPN'
      toast.error(msg, { duration: 6000 })
    }
  }

  const changeStartMode = async (id: number, mode: string) => {
    try {
      await api.put(`/destinations/${id}`, { start_mode: mode })
      toast.success(`Start mode changed to ${mode === 'manual' ? 'Manual' : mode === 'on_demand' ? 'On-Demand' : 'Auto-Restart'}`)
      fetchDestinations()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update')
    }
  }

  const startModeLabel = (mode: string) => {
    if (mode === 'on_demand') return 'On-Demand'
    if (mode === 'auto_restart') return 'Auto-Restart'
    return 'Manual'
  }

  const startModeColor = (mode: string) => {
    if (mode === 'on_demand') return 'text-blue-600 bg-blue-50 border-blue-200'
    if (mode === 'auto_restart') return 'text-purple-600 bg-purple-50 border-purple-200'
    return 'text-gray-600 bg-gray-50 border-gray-200'
  }

  const deleteDest = async (id: number) => {
    if (!confirm('Delete this destination?')) return
    await api.delete(`/destinations/${id}`)
    toast.success('Deleted')
    fetchDestinations()
  }

  const editDest = (dest: Destination) => {
    setForm({
      name: dest.name,
      protocol: dest.protocol,
      interface_name: dest.interface_name,
      config_text: dest.config_text || '',
      start_mode: dest.start_mode || 'manual',
    })
    setEditId(dest.id)
    setShowForm(true)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Destination VPNs</h1>
        <button
          onClick={() => {
            setShowForm(!showForm)
            setEditId(null)
            setForm({ name: '', protocol: 'auto', interface_name: '', config_text: '', start_mode: 'manual' })
          }}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-3 sm:px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 whitespace-nowrap"
        >
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">Add Destination</span>
          <span className="sm:hidden">Add</span>
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="rounded-xl bg-white p-6 shadow-sm border border-gray-100 space-y-4"
        >
          <h3 className="text-lg font-medium">
            {editId ? 'Edit Destination' : 'New Destination'}
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="e.g. Germany Server"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Protocol</label>
              <select
                value={form.protocol}
                onChange={(e) => setForm({ ...form, protocol: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="auto">Auto-detect</option>
                <option value="wireguard">WireGuard</option>
                <option value="openvpn">OpenVPN</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Interface Name *</label>
              <input
                type="text"
                value={form.interface_name}
                onChange={(e) => setForm({ ...form, interface_name: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="e.g. wg1 or tun0"
                required
              />
            </div>
          </div>

          {/* Config input mode toggle */}
          <div>
            <div className="flex gap-2 mb-2">
              <button
                type="button"
                onClick={() => setInputMode('paste')}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm ${
                  inputMode === 'paste'
                    ? 'bg-blue-50 text-blue-600 font-medium'
                    : 'bg-gray-50 text-gray-600'
                }`}
              >
                <Edit2 className="h-3.5 w-3.5" /> Paste Config
              </button>
              <button
                type="button"
                onClick={() => setInputMode('upload')}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm ${
                  inputMode === 'upload'
                    ? 'bg-blue-50 text-blue-600 font-medium'
                    : 'bg-gray-50 text-gray-600'
                }`}
              >
                <Upload className="h-3.5 w-3.5" /> Upload File
              </button>
            </div>

            {inputMode === 'paste' ? (
              <textarea
                value={form.config_text}
                onChange={(e) => setForm({ ...form, config_text: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                rows={10}
                placeholder="Paste your WireGuard (.conf) or OpenVPN (.ovpn) config here..."
              />
            ) : (
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                <input
                  type="file"
                  accept=".conf,.ovpn"
                  onChange={handleFileUpload}
                  className="hidden"
                  id="config-upload"
                />
                <label
                  htmlFor="config-upload"
                  className="cursor-pointer flex flex-col items-center gap-2"
                >
                  <Upload className="h-8 w-8 text-gray-400" />
                  <span className="text-sm text-gray-500">
                    Click to upload .conf or .ovpn file
                  </span>
                </label>
                {form.config_text && (
                  <p className="mt-2 text-xs text-green-600">Config file loaded ({form.config_text.length} chars)</p>
                )}
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Start Mode</label>
            <select value={form.start_mode} onChange={(e) => setForm({ ...form, start_mode: e.target.value })}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
              <option value="manual">Manual</option>
              <option value="on_demand">On-Demand (auto start/stop with users)</option>
              <option value="auto_restart">Auto-Restart (restart if stopped unexpectedly)</option>
            </select>
            <p className="mt-1 text-xs text-gray-400">
              {form.start_mode === 'on_demand' && 'Starts when a user connects, stops after 2 min idle.'}
              {form.start_mode === 'auto_restart' && 'Automatically restarts if it goes down (not manually stopped).'}
              {form.start_mode === 'manual' && 'You control start/stop manually.'}
            </p>
          </div>

          <div className="flex gap-3">
            <button
              type="submit"
              className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              {editId ? 'Update' : 'Create'}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false)
                setEditId(null)
              }}
              className="rounded-lg border border-gray-300 px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Destination Cards */}
      <div className="space-y-4">
        {destinations.length === 0 ? (
          <div className="rounded-xl bg-white p-12 shadow-sm border border-gray-100 text-center">
            <Globe className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No destination VPNs configured yet.</p>
            <p className="text-sm text-gray-400 mt-1">Add your first destination VPN to get started.</p>
          </div>
        ) : (
          destinations.map((dest) => (
            <div
              key={dest.id}
              className="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden"
            >
              <div className="p-3 sm:p-5">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Globe className="h-5 w-5 text-blue-500" />
                    <h3 className="font-medium text-gray-900">{dest.name}</h3>
                    {/* Status badge with mode info */}
                    {dest.is_running ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-green-100 text-green-700">
                        <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                        Running
                        <span className="text-green-500 font-normal">
                          · {startModeLabel(dest.start_mode)}
                        </span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-gray-100 text-gray-500">
                        <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />
                        Stopped
                        <span className="text-gray-400 font-normal">
                          · Mode: {startModeLabel(dest.start_mode)}
                        </span>
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 sm:gap-1.5 flex-wrap">
                    {/* Inline Start Mode Selector */}
                    <select
                      value={dest.start_mode}
                      onChange={(e) => changeStartMode(dest.id, e.target.value)}
                      className={`rounded-lg border px-2 py-1.5 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-blue-400 cursor-pointer ${startModeColor(dest.start_mode)}`}
                      title="Start Mode"
                    >
                      <option value="manual">Manual</option>
                      <option value="on_demand">On-Demand</option>
                      <option value="auto_restart">Auto-Restart</option>
                    </select>

                    <div className="w-px h-6 bg-gray-200 mx-0.5 hidden sm:block" />

                    {dest.is_running ? (
                      <button
                        onClick={() => stopDest(dest.id)}
                        className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-red-600 bg-red-50 hover:bg-red-100 border border-red-200"
                        title="Stop"
                      >
                        <Square className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">Stop</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => startDest(dest.id)}
                        className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-green-600 bg-green-50 hover:bg-green-100 border border-green-200"
                        title="Start"
                      >
                        <Play className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">Start</span>
                      </button>
                    )}
                    <button
                      onClick={() => editDest(dest)}
                      className="rounded p-1.5 text-gray-400 hover:bg-gray-50"
                      title="Edit"
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => deleteDest(dest.id)}
                      className="rounded p-1.5 text-red-400 hover:bg-red-50"
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                {/* Start mode description */}
                {dest.start_mode !== 'manual' && (
                  <p className="text-xs text-gray-400 mt-1 ml-7">
                    {dest.start_mode === 'on_demand'
                      ? 'Starts automatically when a user connects. Stops after 2 min with no active users.'
                      : 'Restarts automatically if it goes down unexpectedly. Will not restart if manually stopped.'}
                  </p>
                )}

                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 sm:gap-4 text-sm">
                  <div>
                    <p className="text-gray-400 text-xs">Protocol</p>
                    <p className="font-medium capitalize">{dest.protocol}</p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-xs">Interface</p>
                    <p className="font-mono">{dest.interface_name}</p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-xs">Upload</p>
                    <p className="flex items-center gap-1 text-blue-600 font-medium">
                      <ArrowUp className="h-3.5 w-3.5" />
                      {formatBytes(dest.total_upload)}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-xs">Download</p>
                    <p className="flex items-center gap-1 text-green-600 font-medium">
                      <ArrowDown className="h-3.5 w-3.5" />
                      {formatBytes(dest.total_download)}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-xs">Users</p>
                    <button
                      onClick={() => toggleUserPanel(dest.id)}
                      className="flex items-center gap-1 text-blue-600 hover:text-blue-800 font-medium"
                    >
                      <Users className="h-3.5 w-3.5" />
                      {dest.user_count}
                      {expandedDest === dest.id ? (
                        <ChevronUp className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </div>

                <p className="text-xs text-gray-400 mt-3">Created {formatDate(dest.created_at)}</p>
              </div>

              {/* Expanded Users Panel */}
              {expandedDest === dest.id && (
                <div className="border-t bg-gray-50 p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-medium text-gray-700">Users on {dest.name}</h4>
                    <div className="flex items-center gap-2">
                      <ArrowUpDown className="h-3.5 w-3.5 text-gray-400" />
                      <select
                        value={userSort}
                        onChange={(e) => changeSortAndFetch(e.target.value as 'download' | 'upload')}
                        className="text-xs rounded border border-gray-300 px-2 py-1 focus:outline-none"
                      >
                        <option value="download">Sort by Download</option>
                        <option value="upload">Sort by Upload</option>
                      </select>
                      <button
                        onClick={() => setExpandedDest(null)}
                        className="rounded p-1 text-gray-400 hover:bg-gray-200"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  {loadingUsers ? (
                    <div className="flex justify-center py-4">
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600" />
                    </div>
                  ) : destUsers.length === 0 ? (
                    <p className="text-sm text-gray-400 text-center py-4">No users assigned to this destination</p>
                  ) : (
                    <div className="rounded-lg bg-white border overflow-hidden">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                            <th className="px-4 py-2">User</th>
                            <th className="px-4 py-2">Status</th>
                            <th className="px-4 py-2 text-right">Upload</th>
                            <th className="px-4 py-2 text-right">Download</th>
                            <th className="px-4 py-2 text-right">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {destUsers.map((u) => (
                            <tr key={u.id} className="border-b last:border-b-0 hover:bg-gray-50">
                              <td className="px-4 py-2.5 font-medium">{u.username}</td>
                              <td className="px-4 py-2.5">
                                <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                                  u.is_online ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                                }`}>
                                  <span className={`h-1.5 w-1.5 rounded-full ${u.is_online ? 'bg-green-500' : 'bg-gray-400'}`} />
                                  {u.is_online ? 'Online' : 'Offline'}
                                </span>
                              </td>
                              <td className="px-4 py-2.5 text-right font-mono text-xs text-blue-600">
                                {formatBytes(u.bandwidth_used_up)}
                              </td>
                              <td className="px-4 py-2.5 text-right font-mono text-xs text-green-600">
                                {formatBytes(u.bandwidth_used_down)}
                              </td>
                              <td className="px-4 py-2.5 text-right font-mono text-xs font-medium">
                                {formatBytes(u.bandwidth_used_up + u.bandwidth_used_down)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
