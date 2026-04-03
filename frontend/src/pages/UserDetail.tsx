import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Copy,
  Download,
  Power,
  RotateCcw,
  Trash2,
  QrCode,
  Plus,
  X,
  Save,
  Edit3,
} from 'lucide-react'
import api from '../api/client'
import { formatBytes, formatDate, percentUsed } from '../lib/utils'
import toast from 'react-hot-toast'

interface UserData {
  id: number
  username: string
  note: string | null
  enabled: boolean
  destination_vpn_id: number | null
  destination_vpn_name: string | null
  assigned_ip: string
  bandwidth_limit_up: number | null
  bandwidth_limit_down: number | null
  bandwidth_used_up: number
  bandwidth_used_down: number
  speed_limit_up: number | null
  speed_limit_down: number | null
  max_connections: number
  expiry_date: string | null
  alert_enabled: boolean
  alert_threshold: number
  telegram_username: string | null
  telegram_link_code: string | null
  is_online: boolean
  active_sessions_count: number
  created_at: string
  updated_at: string
}

interface ConfigData {
  config_text: string; qr_code_base64: string
  dns: string; allowed_ips: string; endpoint: string; mtu: number | null; persistent_keepalive: number
}
interface WhitelistEntry { id: number; user_id: number; address: string; port: number | null; protocol: string; description: string | null }
interface ScheduleEntry { id: number; user_id: number; day_of_week: number; start_time: string; end_time: string; enabled: boolean }
interface SessionEntry {
  id: number
  user_id: number
  endpoint: string | null
  client_ip: string | null
  connected_at: string
  disconnected_at: string | null
  bytes_sent: number
  bytes_received: number
  duration_seconds: number | null
}

const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  const rm = m % 60
  if (h < 24) return `${h}h ${rm}m`
  const d = Math.floor(h / 24)
  const rh = h % 24
  return `${d}d ${rh}h`
}

export default function UserDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [user, setUser] = useState<UserData | null>(null)
  const [config, setConfig] = useState<ConfigData | null>(null)
  const [showQR, setShowQR] = useState(false)
  const [tab, setTab] = useState<'overview' | 'config' | 'sessions' | 'whitelist' | 'schedule'>('overview')

  // Whitelist state
  const [whitelist, setWhitelist] = useState<WhitelistEntry[]>([])
  const [wlForm, setWlForm] = useState({ address: '', port: '', protocol: 'any', description: '' })

  // Sessions state
  const [sessions, setSessions] = useState<SessionEntry[]>([])
  const [sessionsTotal, setSessionsTotal] = useState(0)
  const [sessionsPage, setSessionsPage] = useState(0)

  // Schedule state
  const [schedules, setSchedules] = useState<ScheduleEntry[]>([])
  const [schedForm, setSchedForm] = useState({ day_of_week: '0', start_time: '00:00', end_time: '23:59' })

  // Config edit state
  const [editingConfig, setEditingConfig] = useState(false)
  const [configForm, setConfigForm] = useState({ dns: '', allowed_ips: '', endpoint: '', mtu: '', persistent_keepalive: '' })

  useEffect(() => { fetchUser() }, [id])

  const fetchUser = async () => {
    try {
      const res = await api.get(`/users/${id}`)
      setUser(res.data)
    } catch { toast.error('Failed to load user') }
  }

  const fetchConfig = async () => {
    try {
      const res = await api.get(`/users/${id}/config`)
      setConfig(res.data)
      setConfigForm({
        dns: res.data.dns || '',
        allowed_ips: res.data.allowed_ips || '',
        endpoint: res.data.endpoint || '',
        mtu: res.data.mtu ? String(res.data.mtu) : '',
        persistent_keepalive: res.data.persistent_keepalive != null ? String(res.data.persistent_keepalive) : '25',
      })
    } catch { toast.error('Failed to load config') }
  }

  const saveConfig = async () => {
    try {
      const payload: Record<string, string | number | null> = {
        dns: configForm.dns || null,
        allowed_ips: configForm.allowed_ips || null,
        endpoint: configForm.endpoint || null,
        mtu: configForm.mtu ? Number(configForm.mtu) : null,
        persistent_keepalive: configForm.persistent_keepalive ? Number(configForm.persistent_keepalive) : null,
      }
      const res = await api.put(`/users/${id}/config`, payload)
      setConfig(res.data)
      setEditingConfig(false)
      toast.success('Config saved')
    } catch { toast.error('Failed to save config') }
  }

  const fetchSessions = async (page = 0) => {
    try {
      const res = await api.get(`/users/${id}/sessions`, { params: { skip: page * 50, limit: 50 } })
      setSessions(res.data.sessions)
      setSessionsTotal(res.data.total)
    } catch { toast.error('Failed to load sessions') }
  }

  const fetchWhitelist = async () => {
    try {
      const res = await api.get(`/users/${id}/whitelist`)
      setWhitelist(res.data)
    } catch { toast.error('Failed to load whitelist') }
  }

  const fetchSchedules = async () => {
    try {
      const res = await api.get(`/users/${id}/schedules`)
      setSchedules(res.data)
    } catch { toast.error('Failed to load schedules') }
  }

  const toggleUser = async () => {
    try {
      await api.post(`/users/${id}/toggle`)
      fetchUser()
      toast.success(user?.enabled ? 'User disabled' : 'User enabled')
    } catch { toast.error('Failed to toggle user') }
  }

  const resetBandwidth = async () => {
    try {
      await api.post(`/users/${id}/reset-bandwidth`)
      fetchUser()
      toast.success('Bandwidth reset')
    } catch { toast.error('Failed to reset bandwidth') }
  }

  const deleteUser = async () => {
    if (!confirm('Are you sure?')) return
    try {
      await api.delete(`/users/${id}`)
      toast.success('User deleted')
      navigate('/users')
    } catch { toast.error('Failed to delete user') }
  }

  const copyConfig = () => {
    if (config) { navigator.clipboard.writeText(config.config_text); toast.success('Copied') }
  }

  const downloadConfig = () => {
    if (!config || !user) return
    const blob = new Blob([config.config_text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `${user.username}.conf`; a.click()
    URL.revokeObjectURL(url)
  }

  // Whitelist
  const addWhitelistEntry = async () => {
    if (!wlForm.address) return
    try {
      await api.post(`/users/${id}/whitelist`, {
        address: wlForm.address,
        port: wlForm.port ? Number(wlForm.port) : null,
        protocol: wlForm.protocol,
        description: wlForm.description || null,
      })
      setWlForm({ address: '', port: '', protocol: 'any', description: '' })
      fetchWhitelist()
      toast.success('Whitelist entry added')
    } catch { toast.error('Failed') }
  }

  const deleteWhitelistEntry = async (entryId: number) => {
    try {
      await api.delete(`/users/${id}/whitelist/${entryId}`)
      fetchWhitelist()
      toast.success('Entry removed')
    } catch { toast.error('Failed to remove entry') }
  }

  // Schedule
  const addSchedule = async () => {
    try {
      await api.post(`/users/${id}/schedules`, {
        day_of_week: Number(schedForm.day_of_week),
        start_time: schedForm.start_time,
        end_time: schedForm.end_time,
      })
      fetchSchedules()
      toast.success('Schedule added')
    } catch { toast.error('Failed') }
  }

  const deleteSchedule = async (schedId: number) => {
    try {
      await api.delete(`/users/${id}/schedules/${schedId}`)
      fetchSchedules()
      toast.success('Schedule removed')
    } catch { toast.error('Failed to remove schedule') }
  }

  if (!user) {
    return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>
  }

  const upPercent = percentUsed(user.bandwidth_used_up, user.bandwidth_limit_up)
  const downPercent = percentUsed(user.bandwidth_used_down, user.bandwidth_limit_down)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/users')} className="rounded-lg p-2 hover:bg-gray-100">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-gray-900">{user.username}</h1>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                user.is_online ? 'bg-green-100 text-green-700' : user.enabled ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
              }`}>
                {user.is_online ? 'Online' : user.enabled ? 'Offline' : 'Disabled'}
              </span>
            </div>
            <p className="text-sm text-gray-500">{user.assigned_ip} | Created {formatDate(user.created_at)}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={toggleUser} className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium ${
            user.enabled ? 'bg-orange-50 text-orange-600 hover:bg-orange-100' : 'bg-green-50 text-green-600 hover:bg-green-100'
          }`}>
            <Power className="h-4 w-4" /> {user.enabled ? 'Disable' : 'Enable'}
          </button>
          <button onClick={resetBandwidth} className="flex items-center gap-1.5 rounded-lg bg-gray-50 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100">
            <RotateCcw className="h-4 w-4" /> Reset BW
          </button>
          <button onClick={deleteUser} className="flex items-center gap-1.5 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-100">
            <Trash2 className="h-4 w-4" /> Delete
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <div className="flex gap-6">
          {(['overview', 'config', 'sessions', 'whitelist', 'schedule'] as const).map((t) => (
            <button key={t} onClick={() => {
              setTab(t)
              if (t === 'config' && !config) fetchConfig()
              if (t === 'sessions' && sessions.length === 0) fetchSessions()
              if (t === 'whitelist' && whitelist.length === 0) fetchWhitelist()
              if (t === 'schedule' && schedules.length === 0) fetchSchedules()
            }}
              className={`border-b-2 px-1 pb-3 text-sm font-medium capitalize transition-colors ${
                tab === t ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >{t}</button>
          ))}
        </div>
      </div>

      {/* Overview Tab */}
      {tab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100">
            <h3 className="text-sm font-medium text-gray-500 mb-4">Bandwidth Usage</h3>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Download</span>
                  <span>{formatBytes(user.bandwidth_used_down)}{user.bandwidth_limit_down && ` / ${formatBytes(user.bandwidth_limit_down)}`}</span>
                </div>
                <div className="h-3 rounded-full bg-gray-200 overflow-hidden">
                  <div className={`h-full rounded-full transition-all ${downPercent > 90 ? 'bg-red-500' : 'bg-blue-500'}`}
                    style={{ width: `${user.bandwidth_limit_down ? downPercent : 0}%` }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Upload</span>
                  <span>{formatBytes(user.bandwidth_used_up)}{user.bandwidth_limit_up && ` / ${formatBytes(user.bandwidth_limit_up)}`}</span>
                </div>
                <div className="h-3 rounded-full bg-gray-200 overflow-hidden">
                  <div className={`h-full rounded-full transition-all ${upPercent > 90 ? 'bg-red-500' : 'bg-green-500'}`}
                    style={{ width: `${user.bandwidth_limit_up ? upPercent : 0}%` }} />
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100">
            <h3 className="text-sm font-medium text-gray-500 mb-4">Details</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-gray-500">Destination VPN</dt><dd className="font-medium">{user.destination_vpn_name || 'None'}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Speed (Down/Up)</dt><dd className="font-medium">{user.speed_limit_down ? `${user.speed_limit_down / 1000} Mbps` : 'Unlimited'} / {user.speed_limit_up ? `${user.speed_limit_up / 1000} Mbps` : 'Unlimited'}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Max Connections</dt><dd className="font-medium">{user.max_connections}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Expiry</dt><dd className="font-medium">{formatDate(user.expiry_date)}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Alert</dt><dd className="font-medium">{user.alert_enabled ? `${user.alert_threshold}%` : 'Disabled'}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Telegram</dt><dd className="font-medium">{user.telegram_username || 'Not linked'}</dd></div>
              {user.telegram_link_code && !user.telegram_username && (
                <div className="flex justify-between"><dt className="text-gray-500">Link Code</dt><dd className="font-mono text-xs bg-gray-100 px-2 py-1 rounded">{user.telegram_link_code}</dd></div>
              )}
              {user.note && <div className="flex justify-between"><dt className="text-gray-500">Note</dt><dd>{user.note}</dd></div>}
            </dl>
          </div>
        </div>
      )}

      {/* Config Tab */}
      {tab === 'config' && (
        <div className="space-y-4">
          <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100">
            {config ? (
              <div className="space-y-4">
                <div className="flex gap-2">
                  <button onClick={copyConfig} className="flex items-center gap-1.5 rounded-lg bg-gray-50 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100">
                    <Copy className="h-4 w-4" /> Copy
                  </button>
                  <button onClick={downloadConfig} className="flex items-center gap-1.5 rounded-lg bg-gray-50 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100">
                    <Download className="h-4 w-4" /> Download .conf
                  </button>
                  <button onClick={() => setShowQR(!showQR)} className="flex items-center gap-1.5 rounded-lg bg-gray-50 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100">
                    <QrCode className="h-4 w-4" /> {showQR ? 'Hide' : 'Show'} QR
                  </button>
                  <button onClick={() => setEditingConfig(!editingConfig)} className="flex items-center gap-1.5 rounded-lg bg-blue-50 px-3 py-2 text-sm font-medium text-blue-600 hover:bg-blue-100">
                    <Edit3 className="h-4 w-4" /> {editingConfig ? 'Cancel Edit' : 'Edit Config'}
                  </button>
                </div>
                <pre className="rounded-lg bg-gray-900 text-green-400 p-4 text-sm font-mono overflow-x-auto whitespace-pre-wrap">{config.config_text}</pre>
                {showQR && (
                  <div className="flex justify-center p-4">
                    <img src={`data:image/png;base64,${config.qr_code_base64}`} alt="QR Code" className="w-64 h-64" />
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-32"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>
            )}
          </div>

          {/* Config Edit Form */}
          {editingConfig && config && (
            <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100">
              <h3 className="text-sm font-medium text-gray-500 mb-4">Edit Config</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">DNS Servers</label>
                  <input type="text" value={configForm.dns} onChange={(e) => setConfigForm({ ...configForm, dns: e.target.value })}
                    placeholder="1.1.1.1,8.8.8.8"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Endpoint</label>
                  <input type="text" value={configForm.endpoint} onChange={(e) => setConfigForm({ ...configForm, endpoint: e.target.value })}
                    placeholder="server-ip:51820"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Allowed IPs</label>
                  <input type="text" value={configForm.allowed_ips} onChange={(e) => setConfigForm({ ...configForm, allowed_ips: e.target.value })}
                    placeholder="0.0.0.0/0, ::/0"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
                </div>
                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="block text-xs text-gray-500 mb-1">MTU</label>
                    <input type="number" value={configForm.mtu} onChange={(e) => setConfigForm({ ...configForm, mtu: e.target.value })}
                      placeholder="Auto"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
                  </div>
                  <div className="flex-1">
                    <label className="block text-xs text-gray-500 mb-1">Keepalive (s)</label>
                    <input type="number" value={configForm.persistent_keepalive} onChange={(e) => setConfigForm({ ...configForm, persistent_keepalive: e.target.value })}
                      placeholder="25"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
                  </div>
                </div>
              </div>
              <div className="mt-4 flex justify-end">
                <button onClick={saveConfig}
                  className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                  <Save className="h-4 w-4" /> Save Config
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Sessions Tab */}
      {tab === 'sessions' && (
        <div className="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                <th className="px-4 py-3">Connected</th>
                <th className="px-4 py-3">Disconnected</th>
                <th className="px-4 py-3">Duration</th>
                <th className="px-4 py-3">Download</th>
                <th className="px-4 py-3">Upload</th>
                <th className="px-4 py-3">Client IP</th>
                <th className="px-4 py-3">Endpoint</th>
              </tr>
            </thead>
            <tbody>
              {sessions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-400">No sessions recorded yet.</td>
                </tr>
              ) : (
                sessions.map((s) => (
                  <tr key={s.id} className="border-b last:border-b-0 hover:bg-gray-50">
                    <td className="px-4 py-2.5 text-xs text-gray-600">{formatDate(s.connected_at)}</td>
                    <td className="px-4 py-2.5 text-xs text-gray-600">
                      {s.disconnected_at ? formatDate(s.disconnected_at) : (
                        <span className="inline-flex items-center gap-1 text-green-600 font-medium">
                          <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" /> Connected
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs font-medium">
                      {s.duration_seconds != null ? formatDuration(s.duration_seconds) : (
                        <span className="text-green-600">Active</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs">{formatBytes(s.bytes_sent)}</td>
                    <td className="px-4 py-2.5 text-xs">{formatBytes(s.bytes_received)}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-500">{s.client_ip || '-'}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-500">{s.endpoint || '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {sessionsTotal > 50 && (
            <div className="flex items-center justify-between border-t px-4 py-3">
              <span className="text-sm text-gray-500">
                Showing {sessionsPage * 50 + 1}-{Math.min((sessionsPage + 1) * 50, sessionsTotal)} of {sessionsTotal}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => { setSessionsPage(Math.max(0, sessionsPage - 1)); fetchSessions(Math.max(0, sessionsPage - 1)) }}
                  disabled={sessionsPage === 0}
                  className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-gray-50"
                >Previous</button>
                <button
                  onClick={() => { setSessionsPage(sessionsPage + 1); fetchSessions(sessionsPage + 1) }}
                  disabled={(sessionsPage + 1) * 50 >= sessionsTotal}
                  className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-gray-50"
                >Next</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Whitelist Tab */}
      {tab === 'whitelist' && (
        <div className="space-y-4">
          <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Add Whitelist Entry</h3>
            <p className="text-xs text-gray-400 mb-3">When entries exist, the user can ONLY access these destinations. Leave empty for unrestricted access.</p>
            <div className="flex gap-2 flex-wrap">
              <input type="text" placeholder="IP, CIDR or domain" value={wlForm.address}
                onChange={(e) => setWlForm({ ...wlForm, address: e.target.value })}
                className="flex-1 min-w-[200px] rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
              <input type="number" placeholder="Port" value={wlForm.port}
                onChange={(e) => setWlForm({ ...wlForm, port: e.target.value })}
                className="w-24 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
              <select value={wlForm.protocol} onChange={(e) => setWlForm({ ...wlForm, protocol: e.target.value })}
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none">
                <option value="any">Any</option>
                <option value="tcp">TCP</option>
                <option value="udp">UDP</option>
              </select>
              <input type="text" placeholder="Description" value={wlForm.description}
                onChange={(e) => setWlForm({ ...wlForm, description: e.target.value })}
                className="flex-1 min-w-[150px] rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
              <button onClick={addWhitelistEntry}
                className="flex items-center gap-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                <Plus className="h-4 w-4" /> Add
              </button>
            </div>
          </div>

          {whitelist.length > 0 && (
            <div className="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                    <th className="px-4 py-3">Address</th>
                    <th className="px-4 py-3">Port</th>
                    <th className="px-4 py-3">Protocol</th>
                    <th className="px-4 py-3">Description</th>
                    <th className="px-4 py-3 w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {whitelist.map((entry) => (
                    <tr key={entry.id} className="border-b last:border-b-0">
                      <td className="px-4 py-2.5 font-mono text-xs">{entry.address}</td>
                      <td className="px-4 py-2.5">{entry.port || 'All'}</td>
                      <td className="px-4 py-2.5 uppercase text-xs">{entry.protocol}</td>
                      <td className="px-4 py-2.5 text-gray-500">{entry.description || '-'}</td>
                      <td className="px-4 py-2.5">
                        <button onClick={() => deleteWhitelistEntry(entry.id)} className="rounded p-1 text-red-400 hover:bg-red-50">
                          <X className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {whitelist.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">No whitelist entries. User has unrestricted access.</p>
          )}
        </div>
      )}

      {/* Schedule Tab */}
      {tab === 'schedule' && (
        <div className="space-y-4">
          <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Add Access Schedule</h3>
            <p className="text-xs text-gray-400 mb-3">Define when this user can access the VPN. Without schedules, access is 24/7.</p>
            <div className="flex gap-2 flex-wrap items-end">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Day</label>
                <select value={schedForm.day_of_week} onChange={(e) => setSchedForm({ ...schedForm, day_of_week: e.target.value })}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none">
                  {DAY_NAMES.map((day, i) => <option key={i} value={i}>{day}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">From</label>
                <input type="time" value={schedForm.start_time} onChange={(e) => setSchedForm({ ...schedForm, start_time: e.target.value })}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">To</label>
                <input type="time" value={schedForm.end_time} onChange={(e) => setSchedForm({ ...schedForm, end_time: e.target.value })}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
              </div>
              <button onClick={addSchedule}
                className="flex items-center gap-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                <Plus className="h-4 w-4" /> Add
              </button>
            </div>
          </div>

          {schedules.length > 0 && (
            <div className="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                    <th className="px-4 py-3">Day</th>
                    <th className="px-4 py-3">From</th>
                    <th className="px-4 py-3">To</th>
                    <th className="px-4 py-3 w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((s) => (
                    <tr key={s.id} className="border-b last:border-b-0">
                      <td className="px-4 py-2.5 font-medium">{DAY_NAMES[s.day_of_week]}</td>
                      <td className="px-4 py-2.5">{s.start_time}</td>
                      <td className="px-4 py-2.5">{s.end_time}</td>
                      <td className="px-4 py-2.5">
                        <button onClick={() => deleteSchedule(s.id)} className="rounded p-1 text-red-400 hover:bg-red-50">
                          <X className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {schedules.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">No schedules. User has 24/7 access.</p>
          )}
        </div>
      )}
    </div>
  )
}
