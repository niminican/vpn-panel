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
  Pencil,
} from 'lucide-react'
import api from '../api/client'
import { formatBytes, formatDate, percentUsed } from '../lib/utils'
import toast from 'react-hot-toast'

interface Destination { id: number; name: string; protocol: string }
interface Pkg { id: number; name: string; bandwidth_limit: number | null; speed_limit: number | null; duration_days: number; max_connections: number; enabled: boolean }

interface UserData {
  id: number
  username: string
  note: string | null
  enabled: boolean
  destination_vpn_id: number | null
  destination_vpn_name: string | null
  package_id: number | null
  package_name: string | null
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
  country: string | null
  country_code: string | null
  city: string | null
  isp: string | null
  asn: number | null
  os_hint: string | null
  ttl: number | null
}

const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

function getFlagEmoji(countryCode: string): string {
  const codePoints = countryCode
    .toUpperCase()
    .split('')
    .map(c => 0x1F1E6 + c.charCodeAt(0) - 65)
  return String.fromCodePoint(...codePoints)
}

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
  const [tab, setTab] = useState<'overview' | 'config' | 'sessions' | 'proxy' | 'whitelist' | 'blacklist' | 'schedule'>('overview')

  // Proxy accounts state
  const [proxyAccounts, setProxyAccounts] = useState<any[]>([])
  const [proxyLoaded, setProxyLoaded] = useState(false)
  const [inbounds, setInbounds] = useState<any[]>([])
  const [showAddProxy, setShowAddProxy] = useState(false)
  const [selectedInbound, setSelectedInbound] = useState('')

  // Whitelist state
  const [whitelist, setWhitelist] = useState<WhitelistEntry[]>([])
  const [wlForm, setWlForm] = useState({ address: '', port: '', protocol: 'any', description: '' })

  // Blacklist state
  const [blacklist, setBlacklist] = useState<WhitelistEntry[]>([])
  const [blForm, setBlForm] = useState({ address: '', port: '', protocol: 'any', description: '' })

  // Blocked requests state
  const [blockedRequests, setBlockedRequests] = useState<{ id: number; dest_ip: string; dest_hostname: string | null; dest_port: number | null; protocol: string | null; count: number; first_seen: string; last_seen: string }[]>([])
  const [blockedTotal, setBlockedTotal] = useState(0)
  const [blockedLoaded, setBlockedLoaded] = useState(false)

  // Visited destinations state
  const [visitedDests, setVisitedDests] = useState<{ dest_ip: string; dest_hostname: string | null; count: number; last_seen: string }[]>([])
  const [visitedLoaded, setVisitedLoaded] = useState(false)

  // Sessions state
  const [sessions, setSessions] = useState<SessionEntry[]>([])
  const [sessionsTotal, setSessionsTotal] = useState(0)
  const [sessionsPage, setSessionsPage] = useState(0)

  // Session detail (visited/blocked per session)
  const [expandedSession, setExpandedSession] = useState<number | null>(null)
  const [sessionVisited, setSessionVisited] = useState<{ dest_ip: string; dest_hostname: string | null; count: number; last_seen: string }[]>([])
  const [sessionBlocked, setSessionBlocked] = useState<{ id: number; dest_ip: string; dest_hostname: string | null; dest_port: number | null; protocol: string | null; count: number; first_seen: string; last_seen: string }[]>([])
  const [sessionDetailLoading, setSessionDetailLoading] = useState(false)

  // Schedule state
  const [schedules, setSchedules] = useState<ScheduleEntry[]>([])
  const [schedForm, setSchedForm] = useState({ day_of_week: '0', start_time: '00:00', end_time: '23:59' })

  // Config edit state
  const [editingConfig, setEditingConfig] = useState(false)
  const [configForm, setConfigForm] = useState({ dns: '', allowed_ips: '', endpoint: '', mtu: '', persistent_keepalive: '' })

  // User edit state
  const [editingUser, setEditingUser] = useState(false)
  const [destinations, setDestinations] = useState<Destination[]>([])
  const [packages, setPackages] = useState<Pkg[]>([])
  const [userForm, setUserForm] = useState({
    note: '',
    destination_vpn_id: '',
    package_id: '',
    bandwidth_limit_down: '',
    bandwidth_limit_up: '',
    bandwidth_unit_down: 'GB' as 'GB' | 'MB',
    bandwidth_unit_up: 'GB' as 'GB' | 'MB',
    speed_limit_down: '',
    speed_limit_up: '',
    max_connections: '1',
    expiry_date: '',
    alert_enabled: true,
    alert_threshold: '80',
  })

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

  const toggleSessionDetail = async (sessionId: number) => {
    if (expandedSession === sessionId) {
      setExpandedSession(null)
      setSessionVisited([])
      setSessionBlocked([])
      return
    }
    setExpandedSession(sessionId)
    setSessionDetailLoading(true)
    try {
      const [visitedRes, blockedRes] = await Promise.all([
        api.get(`/users/${id}/sessions/${sessionId}/visited`),
        api.get(`/users/${id}/sessions/${sessionId}/blocked`),
      ])
      setSessionVisited(visitedRes.data.visited)
      setSessionBlocked(blockedRes.data.blocked)
    } catch { toast.error('Failed to load session details') }
    setSessionDetailLoading(false)
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

  const fetchProxyAccounts = async () => {
    try {
      const [proxyRes, inbRes] = await Promise.all([
        api.get(`/users/${id}/proxy`),
        api.get('/inbounds'),
      ])
      setProxyAccounts(proxyRes.data)
      setInbounds(inbRes.data)
      setProxyLoaded(true)
    } catch { toast.error('Failed to load proxy accounts') }
  }

  const addProxyAccount = async () => {
    if (!selectedInbound) return
    try {
      await api.post(`/users/${id}/proxy`, { inbound_id: parseInt(selectedInbound) })
      toast.success('Proxy account created')
      setShowAddProxy(false)
      setSelectedInbound('')
      fetchProxyAccounts()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create proxy account')
    }
  }

  const deleteProxyAccount = async (proxyId: number) => {
    if (!confirm('Delete this proxy account?')) return
    try {
      await api.delete(`/users/${id}/proxy/${proxyId}`)
      toast.success('Proxy account deleted')
      fetchProxyAccounts()
    } catch { toast.error('Failed to delete') }
  }

  const copyShareLink = async (proxyId: number) => {
    try {
      const res = await api.get(`/users/${id}/proxy/${proxyId}/config`)
      await navigator.clipboard.writeText(res.data.share_link)
      toast.success('Share link copied!')
    } catch { toast.error('Failed to get config') }
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

  const startEditUser = async () => {
    if (!user) return
    // Load destinations and packages
    try {
      const [destRes, pkgRes] = await Promise.all([
        api.get('/destinations'),
        api.get('/packages'),
      ])
      setDestinations(destRes.data)
      setPackages(pkgRes.data.filter((p: Pkg) => p.enabled))
    } catch {}

    // Convert bytes to best unit
    const toBwUnit = (bytes: number | null): { value: string; unit: 'GB' | 'MB' } => {
      if (!bytes) return { value: '', unit: 'GB' }
      if (bytes < 1024 * 1024 * 1024) return { value: String(bytes / (1024 * 1024)), unit: 'MB' }
      return { value: String(bytes / (1024 * 1024 * 1024)), unit: 'GB' }
    }
    const down = toBwUnit(user.bandwidth_limit_down)
    const up = toBwUnit(user.bandwidth_limit_up)

    setUserForm({
      note: user.note || '',
      destination_vpn_id: user.destination_vpn_id ? String(user.destination_vpn_id) : '',
      package_id: user.package_id ? String(user.package_id) : '',
      bandwidth_limit_down: down.value,
      bandwidth_limit_up: up.value,
      bandwidth_unit_down: down.unit,
      bandwidth_unit_up: up.unit,
      speed_limit_down: user.speed_limit_down ? String(user.speed_limit_down / 1000) : '',
      speed_limit_up: user.speed_limit_up ? String(user.speed_limit_up / 1000) : '',
      max_connections: String(user.max_connections),
      expiry_date: user.expiry_date ? new Date(user.expiry_date).toISOString().slice(0, 16) : '',
      alert_enabled: user.alert_enabled,
      alert_threshold: String(user.alert_threshold),
    })
    setEditingUser(true)
  }

  const applyPackageToForm = (pkgId: string) => {
    setUserForm((prev) => ({ ...prev, package_id: pkgId }))
    const pkg = packages.find((p) => p.id === Number(pkgId))
    if (!pkg) return
    const bw = pkg.bandwidth_limit
    let bwValue = '', bwUnit: 'GB' | 'MB' = 'GB'
    if (bw) {
      if (bw < 1024 * 1024 * 1024) { bwValue = String(bw / (1024 * 1024)); bwUnit = 'MB' }
      else { bwValue = String(bw / (1024 * 1024 * 1024)); bwUnit = 'GB' }
    }
    const speedMbps = pkg.speed_limit ? String(pkg.speed_limit / 1000) : ''
    const expiry = new Date()
    expiry.setDate(expiry.getDate() + pkg.duration_days)
    setUserForm((prev) => ({
      ...prev,
      bandwidth_limit_down: bwValue, bandwidth_limit_up: bwValue,
      bandwidth_unit_down: bwUnit, bandwidth_unit_up: bwUnit,
      speed_limit_down: speedMbps, speed_limit_up: speedMbps,
      max_connections: String(pkg.max_connections),
      expiry_date: expiry.toISOString().slice(0, 16),
    }))
  }

  const saveUser = async () => {
    try {
      const payload: Record<string, unknown> = {
        note: userForm.note || null,
        destination_vpn_id: userForm.destination_vpn_id ? Number(userForm.destination_vpn_id) : null,
        package_id: userForm.package_id ? Number(userForm.package_id) : null,
        max_connections: Number(userForm.max_connections),
        alert_enabled: userForm.alert_enabled,
        alert_threshold: Number(userForm.alert_threshold),
        expiry_date: userForm.expiry_date ? new Date(userForm.expiry_date).toISOString() : null,
      }
      if (userForm.bandwidth_limit_down) {
        const m = userForm.bandwidth_unit_down === 'GB' ? 1024 * 1024 * 1024 : 1024 * 1024
        payload.bandwidth_limit_down = Number(userForm.bandwidth_limit_down) * m
      } else { payload.bandwidth_limit_down = null }
      if (userForm.bandwidth_limit_up) {
        const m = userForm.bandwidth_unit_up === 'GB' ? 1024 * 1024 * 1024 : 1024 * 1024
        payload.bandwidth_limit_up = Number(userForm.bandwidth_limit_up) * m
      } else { payload.bandwidth_limit_up = null }
      payload.speed_limit_down = userForm.speed_limit_down ? Number(userForm.speed_limit_down) * 1000 : null
      payload.speed_limit_up = userForm.speed_limit_up ? Number(userForm.speed_limit_up) * 1000 : null

      await api.put(`/users/${id}`, payload)
      await fetchUser()
      setEditingUser(false)
      toast.success('User updated')
    } catch { toast.error('Failed to update user') }
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
    if (!window.confirm('Are you sure you want to remove this whitelist entry?')) return
    try {
      await api.delete(`/users/${id}/whitelist/${entryId}`)
      fetchWhitelist()
      toast.success('Entry removed')
    } catch { toast.error('Failed to remove entry') }
  }

  const clearWhitelist = async () => {
    if (!window.confirm('Remove all whitelist entries? User will have unrestricted access.')) return
    try {
      await api.delete(`/users/${id}/whitelist/all`)
      setWhitelist([])
      toast.success('Whitelist cleared')
    } catch { toast.error('Failed to clear whitelist') }
  }

  // Visited destinations
  const fetchVisitedDests = async () => {
    try {
      const res = await api.get(`/users/${id}/whitelist/visited`, { params: { limit: 200 } })
      setVisitedDests(res.data.visited)
      setVisitedLoaded(true)
    } catch { /* ignore */ }
  }

  const clearVisitedDests = async () => {
    if (!window.confirm('Clear all visited destination logs for this user?')) return
    try {
      await api.delete(`/users/${id}/whitelist/visited`)
      setVisitedDests([])
      toast.success('Visited logs cleared')
    } catch { toast.error('Failed') }
  }

  const addVisitedToWhitelist = async (ip: string, hostname: string | null) => {
    const addr = hostname || ip
    if (!window.confirm(`Add "${addr}" to whitelist?`)) return
    setAddingBlocked(addr)
    try {
      await api.post(`/users/${id}/whitelist`, {
        address: addr,
        protocol: 'any',
        description: `Added from visited destinations (${ip})`,
      })
      fetchWhitelist()
      toast.success(`Added ${addr} to whitelist`)
    } catch { toast.error('Failed to add to whitelist') }
    finally { setAddingBlocked(null) }
  }

  const addVisitedToBlacklist = async (ip: string, hostname: string | null) => {
    const addr = hostname || ip
    if (!window.confirm(`Add "${addr}" to blacklist?`)) return
    setAddingBlocked(addr)
    try {
      await api.post(`/users/${id}/blacklist`, {
        address: addr,
        protocol: 'any',
        description: `Added from visited destinations (${ip})`,
      })
      fetchBlacklist()
      toast.success(`Added ${addr} to blacklist`)
    } catch { toast.error('Failed to add to blacklist') }
    finally { setAddingBlocked(null) }
  }

  // Blacklist
  const fetchBlacklist = async () => {
    try {
      const res = await api.get(`/users/${id}/blacklist`)
      setBlacklist(res.data)
    } catch { toast.error('Failed to load blacklist') }
  }

  const addBlacklistEntry = async () => {
    if (!blForm.address) return
    try {
      await api.post(`/users/${id}/blacklist`, {
        address: blForm.address,
        port: blForm.port ? Number(blForm.port) : null,
        protocol: blForm.protocol,
        description: blForm.description || null,
      })
      setBlForm({ address: '', port: '', protocol: 'any', description: '' })
      fetchBlacklist()
      toast.success('Blacklist entry added')
    } catch { toast.error('Failed') }
  }

  const deleteBlacklistEntry = async (entryId: number) => {
    if (!window.confirm('Are you sure you want to remove this blacklist entry?')) return
    try {
      await api.delete(`/users/${id}/blacklist/${entryId}`)
      fetchBlacklist()
      toast.success('Entry removed')
    } catch { toast.error('Failed to remove entry') }
  }

  // Blocked requests
  const [addingBlocked, setAddingBlocked] = useState<string | null>(null) // tracks which entry is being added

  const fetchBlockedRequests = async () => {
    try {
      const res = await api.get(`/users/${id}/blacklist/blocked`, { params: { limit: 200 } })
      setBlockedRequests(res.data.blocked)
      setBlockedTotal(res.data.total)
      setBlockedLoaded(true)
    } catch { /* ignore */ }
  }

  // Deduplicate blocked requests: merge rows with same (dest_ip OR dest_hostname)
  const deduplicatedBlocked = (() => {
    const map = new Map<string, typeof blockedRequests[0]>()
    for (const b of blockedRequests) {
      const key = b.dest_hostname || b.dest_ip
      const existing = map.get(key)
      if (existing) {
        existing.count += b.count
        if (new Date(b.last_seen) > new Date(existing.last_seen)) {
          existing.last_seen = b.last_seen
          if (b.dest_port && !existing.dest_port) existing.dest_port = b.dest_port
          if (b.protocol && !existing.protocol) existing.protocol = b.protocol
        }
      } else {
        map.set(key, { ...b })
      }
    }
    return Array.from(map.values()).sort((a, b) => b.count - a.count)
  })()

  const addBlockedToWhitelist = async (ip: string, hostname: string | null) => {
    const addr = hostname || ip
    if (!window.confirm(`Add "${addr}" to whitelist?`)) return
    setAddingBlocked(addr)
    try {
      await api.post(`/users/${id}/whitelist`, {
        address: addr,
        protocol: 'any',
        description: `Added from blocked requests (${ip})`,
      })
      fetchWhitelist()
      toast.success(`Added ${addr} to whitelist`)
    } catch { toast.error('Failed to add to whitelist') }
    finally { setAddingBlocked(null) }
  }

  const addBlockedToBlacklist = async (ip: string, hostname: string | null) => {
    const addr = hostname || ip
    if (!window.confirm(`Add "${addr}" to blacklist?`)) return
    setAddingBlocked(addr)
    try {
      await api.post(`/users/${id}/blacklist`, {
        address: addr,
        protocol: 'any',
        description: `Added from blocked requests (${ip})`,
      })
      fetchBlacklist()
      toast.success(`Added ${addr} to blacklist`)
    } catch { toast.error('Failed to add to blacklist') }
    finally { setAddingBlocked(null) }
  }

  const clearBlockedRequests = async () => {
    if (!window.confirm('Clear all blocked request logs?')) return
    try {
      await api.delete(`/users/${id}/blacklist/blocked`)
      setBlockedRequests([])
      setBlockedTotal(0)
      toast.success('Blocked requests cleared')
    } catch { toast.error('Failed') }
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
    <div className="space-y-3 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/users')} className="rounded-lg p-2 hover:bg-gray-100">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg sm:text-2xl font-bold text-gray-900">{user.username}</h1>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                user.is_online ? 'bg-green-100 text-green-700' : user.enabled ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
              }`}>
                {user.is_online ? 'Online' : user.enabled ? 'Offline' : 'Disabled'}
              </span>
            </div>
            <p className="text-sm text-gray-500">{user.assigned_ip} | Created {formatDate(user.created_at)}</p>
          </div>
        </div>
        <div className="flex gap-1.5 sm:gap-2 flex-wrap ml-10 sm:ml-0">
          <button onClick={startEditUser} className="flex items-center gap-1 sm:gap-1.5 rounded-lg bg-blue-50 px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-blue-600 hover:bg-blue-100">
            <Pencil className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> Edit
          </button>
          <button onClick={toggleUser} className={`flex items-center gap-1 sm:gap-1.5 rounded-lg px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium ${
            user.enabled ? 'bg-orange-50 text-orange-600 hover:bg-orange-100' : 'bg-green-50 text-green-600 hover:bg-green-100'
          }`}>
            <Power className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> {user.enabled ? 'Disable' : 'Enable'}
          </button>
          <button onClick={resetBandwidth} className="flex items-center gap-1 sm:gap-1.5 rounded-lg bg-gray-50 px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-gray-600 hover:bg-gray-100">
            <RotateCcw className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> <span className="hidden sm:inline">Reset BW</span><span className="sm:hidden">Reset</span>
          </button>
          <button onClick={deleteUser} className="flex items-center gap-1 sm:gap-1.5 rounded-lg bg-red-50 px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-red-600 hover:bg-red-100">
            <Trash2 className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> Delete
          </button>
        </div>
      </div>

      {/* Edit User Panel */}
      {editingUser && (
        <div className="rounded-xl bg-white p-3 sm:p-6 shadow-sm border border-blue-200 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-gray-900">Edit User</h3>
            <button onClick={() => setEditingUser(false)} className="rounded p-1 text-gray-400 hover:bg-gray-100"><X className="h-5 w-5" /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Destination VPN</label>
              <select value={userForm.destination_vpn_id} onChange={(e) => setUserForm({ ...userForm, destination_vpn_id: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
                <option value="">-- None --</option>
                {destinations.map((d) => <option key={d.id} value={d.id}>{d.name} ({d.protocol})</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Package</label>
              <select value={userForm.package_id} onChange={(e) => { if (e.target.value) applyPackageToForm(e.target.value); else setUserForm({ ...userForm, package_id: '' }) }}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
                <option value="">-- Custom --</option>
                {packages.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Download Limit</label>
              <div className="flex gap-2">
                <input type="number" value={userForm.bandwidth_limit_down} onChange={(e) => setUserForm({ ...userForm, bandwidth_limit_down: e.target.value })}
                  className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="Unlimited" min="0" step="any" />
                <select value={userForm.bandwidth_unit_down} onChange={(e) => setUserForm({ ...userForm, bandwidth_unit_down: e.target.value as 'GB' | 'MB' })}
                  className="w-20 rounded-lg border border-gray-300 px-2 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
                  <option value="GB">GB</option><option value="MB">MB</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Upload Limit</label>
              <div className="flex gap-2">
                <input type="number" value={userForm.bandwidth_limit_up} onChange={(e) => setUserForm({ ...userForm, bandwidth_limit_up: e.target.value })}
                  className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="Unlimited" min="0" step="any" />
                <select value={userForm.bandwidth_unit_up} onChange={(e) => setUserForm({ ...userForm, bandwidth_unit_up: e.target.value as 'GB' | 'MB' })}
                  className="w-20 rounded-lg border border-gray-300 px-2 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
                  <option value="GB">GB</option><option value="MB">MB</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Download Speed (Mbps)</label>
              <input type="number" value={userForm.speed_limit_down} onChange={(e) => setUserForm({ ...userForm, speed_limit_down: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="Unlimited" min="0" step="any" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Upload Speed (Mbps)</label>
              <input type="number" value={userForm.speed_limit_up} onChange={(e) => setUserForm({ ...userForm, speed_limit_up: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" placeholder="Unlimited" min="0" step="any" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max Connections</label>
              <input type="number" value={userForm.max_connections} onChange={(e) => setUserForm({ ...userForm, max_connections: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" min="1" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Expiry Date</label>
              <input type="datetime-local" value={userForm.expiry_date} onChange={(e) => setUserForm({ ...userForm, expiry_date: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Note</label>
              <input type="text" value={userForm.note} onChange={(e) => setUserForm({ ...userForm, note: e.target.value })}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div className="flex items-end gap-4">
              <div className="flex items-center gap-2">
                <input type="checkbox" id="edit_alert" checked={userForm.alert_enabled} onChange={(e) => setUserForm({ ...userForm, alert_enabled: e.target.checked })}
                  className="rounded border-gray-300" />
                <label htmlFor="edit_alert" className="text-sm text-gray-700">Alert</label>
              </div>
              {userForm.alert_enabled && (
                <div className="flex-1">
                  <input type="number" value={userForm.alert_threshold} onChange={(e) => setUserForm({ ...userForm, alert_threshold: e.target.value })}
                    className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    min="1" max="100" placeholder="Threshold %" />
                </div>
              )}
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button onClick={saveUser} className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700">Save Changes</button>
            <button onClick={() => setEditingUser(false)} className="rounded-lg border border-gray-300 px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50">Cancel</button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 overflow-x-auto">
        <div className="flex gap-4 sm:gap-6 min-w-max">
          {(['overview', 'config', 'sessions', 'proxy', 'whitelist', 'blacklist', 'schedule'] as const).map((t) => (
            <button key={t} onClick={() => {
              setTab(t)
              if (t === 'config' && !config) fetchConfig()
              if (t === 'sessions' && sessions.length === 0) fetchSessions()
              if (t === 'proxy' && !proxyLoaded) fetchProxyAccounts()
              if (t === 'whitelist' && whitelist.length === 0) fetchWhitelist()
              if (t === 'whitelist' && !visitedLoaded) fetchVisitedDests()
              if (t === 'blacklist' && blacklist.length === 0) fetchBlacklist()
              if (t === 'blacklist' && !blockedLoaded) fetchBlockedRequests()
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
              <div className="flex justify-between"><dt className="text-gray-500">Package</dt><dd className="font-medium">{user.package_name ? <span className="inline-flex items-center rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-700">{user.package_name}</span> : <span className="text-gray-400">Custom</span>}</dd></div>
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
                <div className="flex gap-1.5 sm:gap-2 flex-wrap">
                  <button onClick={copyConfig} className="flex items-center gap-1 sm:gap-1.5 rounded-lg bg-gray-50 px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-gray-600 hover:bg-gray-100">
                    <Copy className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> Copy
                  </button>
                  <button onClick={downloadConfig} className="flex items-center gap-1 sm:gap-1.5 rounded-lg bg-gray-50 px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-gray-600 hover:bg-gray-100">
                    <Download className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> <span className="hidden sm:inline">Download .conf</span><span className="sm:hidden">Download</span>
                  </button>
                  <button onClick={() => setShowQR(!showQR)} className="flex items-center gap-1 sm:gap-1.5 rounded-lg bg-gray-50 px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-gray-600 hover:bg-gray-100">
                    <QrCode className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> {showQR ? 'Hide' : 'Show'} QR
                  </button>
                  <button onClick={() => setEditingConfig(!editingConfig)} className="flex items-center gap-1 sm:gap-1.5 rounded-lg bg-blue-50 px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-blue-600 hover:bg-blue-100">
                    <Edit3 className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> {editingConfig ? 'Cancel' : 'Edit'}
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
        <div className="space-y-3">
          {sessions.length === 0 ? (
            <div className="rounded-xl bg-white p-8 shadow-sm border border-gray-100 text-center text-gray-400">
              No sessions recorded yet.
            </div>
          ) : (
            sessions.map((s) => (
              <div key={s.id} className="rounded-xl bg-white shadow-sm border border-gray-100 p-4">
                {/* Session header: status + time */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    {!s.disconnected_at ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 text-green-700 px-2.5 py-0.5 text-xs font-medium">
                        <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" /> Active
                      </span>
                    ) : (
                      <span className="rounded-full bg-gray-100 text-gray-500 px-2.5 py-0.5 text-xs font-medium">
                        {s.duration_seconds != null ? formatDuration(s.duration_seconds) : 'Ended'}
                      </span>
                    )}
                    {s.os_hint && (
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        s.os_hint.includes('Windows') ? 'bg-blue-100 text-blue-700' :
                        s.os_hint.includes('Linux') || s.os_hint.includes('Android') ? 'bg-green-100 text-green-700' :
                        'bg-purple-100 text-purple-700'
                      }`}>
                        {s.os_hint === 'Linux/Android/macOS' ? 'Linux/Android/Mac' : s.os_hint}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">{formatDate(s.connected_at)}</span>
                </div>

                {/* Info grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-x-4 gap-y-2 text-sm">
                  {(s.country || s.city) && (
                    <div>
                      <p className="text-xs text-gray-400">Location</p>
                      <p className="font-medium text-gray-700">
                        {s.country_code && <span className="mr-1">{getFlagEmoji(s.country_code)}</span>}
                        {[s.city, s.country].filter(Boolean).join(', ')}
                      </p>
                    </div>
                  )}
                  {s.isp && (
                    <div>
                      <p className="text-xs text-gray-400">ISP</p>
                      <p className="font-medium text-gray-700 truncate" title={s.isp}>{s.isp}</p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs text-gray-400">Client IP</p>
                    <p className="font-mono text-xs text-gray-600">{s.client_ip || '-'}</p>
                  </div>
                  <div className="hidden sm:block">
                    <p className="text-xs text-gray-400">Endpoint</p>
                    <p className="font-mono text-xs text-gray-600 truncate" title={s.endpoint || ''}>{s.endpoint || '-'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400">Download</p>
                    <p className="font-medium text-green-600">{formatBytes(s.bytes_sent)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400">Upload</p>
                    <p className="font-medium text-blue-600">{formatBytes(s.bytes_received)}</p>
                  </div>
                  {s.ttl != null && (
                    <div className="hidden sm:block">
                      <p className="text-xs text-gray-400">TTL</p>
                      <p className="font-mono text-xs text-gray-600">{s.ttl}</p>
                    </div>
                  )}
                  {s.disconnected_at && (
                    <div>
                      <p className="text-xs text-gray-400">Disconnected</p>
                      <p className="text-xs text-gray-600">{formatDate(s.disconnected_at)}</p>
                    </div>
                  )}
                </div>

                {/* View Details button */}
                <div className="mt-3 pt-3 border-t border-gray-100">
                  <button
                    onClick={() => toggleSessionDetail(s.id)}
                    className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                      expandedSession === s.id
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
                    }`}
                  >
                    {expandedSession === s.id ? 'Hide Details' : 'View Visited / Blocked'}
                  </button>
                </div>

                {/* Session Detail: Visited & Blocked */}
                {expandedSession === s.id && (
                  <div className="mt-3 space-y-3">
                    {sessionDetailLoading ? (
                      <p className="text-sm text-gray-400 text-center py-4">Loading...</p>
                    ) : (
                      <>
                        {/* Visited in this session */}
                        <div className="rounded-lg bg-green-50 p-3">
                          <h4 className="text-xs font-medium text-green-700 mb-2">
                            Visited Destinations ({sessionVisited.length})
                          </h4>
                          {sessionVisited.length > 0 ? (
                            <div className="overflow-x-auto">
                              <table className="w-full text-xs">
                                <thead>
                                  <tr className="border-b border-green-200 text-left text-green-600">
                                    <th className="px-2 py-1">IP</th>
                                    <th className="px-2 py-1">Hostname</th>
                                    <th className="px-2 py-1">Count</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {sessionVisited.map((v) => (
                                    <tr key={v.dest_hostname || v.dest_ip} className="border-b border-green-100 last:border-0">
                                      <td className="px-2 py-1 font-mono">{v.dest_ip}</td>
                                      <td className="px-2 py-1 text-gray-600 truncate max-w-[120px]" title={v.dest_hostname || ''}>{v.dest_hostname || '-'}</td>
                                      <td className="px-2 py-1 font-medium text-green-700">{v.count}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="text-xs text-green-600/60">No visited destinations in this session.</p>
                          )}
                        </div>

                        {/* Blocked in this session */}
                        <div className="rounded-lg bg-orange-50 p-3">
                          <h4 className="text-xs font-medium text-orange-700 mb-2">
                            Blocked Requests ({sessionBlocked.length})
                          </h4>
                          {sessionBlocked.length > 0 ? (
                            <div className="overflow-x-auto">
                              <table className="w-full text-xs">
                                <thead>
                                  <tr className="border-b border-orange-200 text-left text-orange-600">
                                    <th className="px-2 py-1">IP</th>
                                    <th className="px-2 py-1">Hostname</th>
                                    <th className="px-2 py-1">Count</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {sessionBlocked.map((b) => (
                                    <tr key={b.dest_hostname || b.dest_ip} className="border-b border-orange-100 last:border-0">
                                      <td className="px-2 py-1 font-mono">{b.dest_ip}</td>
                                      <td className="px-2 py-1 text-gray-600 truncate max-w-[120px]" title={b.dest_hostname || ''}>{b.dest_hostname || '-'}</td>
                                      <td className="px-2 py-1 font-medium text-orange-700">{b.count}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="text-xs text-orange-600/60">No blocked requests in this session.</p>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))
          )}

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

      {/* Proxy Tab */}
      {tab === 'proxy' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Proxy Accounts</h3>
            <button onClick={() => { setShowAddProxy(true); if (!proxyLoaded) fetchProxyAccounts() }} className="flex items-center gap-1 bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-blue-700">+ Add</button>
          </div>

          {showAddProxy && (
            <div className="bg-gray-50 rounded-lg p-4 flex items-end gap-3">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1">Inbound</label>
                <select value={selectedInbound} onChange={e => setSelectedInbound(e.target.value)} className="w-full border rounded-lg px-3 py-2 text-sm">
                  <option value="">Select inbound...</option>
                  {inbounds.filter((i: any) => i.enabled).map((i: any) => (
                    <option key={i.id} value={i.id}>{i.tag} ({i.protocol.toUpperCase()} :{i.port})</option>
                  ))}
                </select>
              </div>
              <button onClick={addProxyAccount} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">Create</button>
              <button onClick={() => setShowAddProxy(false)} className="text-gray-500 px-3 py-2 text-sm">Cancel</button>
            </div>
          )}

          {proxyAccounts.length === 0 && !showAddProxy && (
            <p className="text-gray-400 text-center py-8">No proxy accounts</p>
          )}

          <div className="space-y-3">
            {proxyAccounts.map((pa: any) => (
              <div key={pa.id} className="bg-white rounded-lg border p-4 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      pa.inbound_protocol === 'vless' ? 'bg-blue-100 text-blue-700' :
                      pa.inbound_protocol === 'trojan' ? 'bg-purple-100 text-purple-700' :
                      pa.inbound_protocol === 'shadowsocks' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>{(pa.inbound_protocol || '').toUpperCase()}</span>
                    <span className="text-sm font-medium">{pa.inbound_tag}</span>
                    <span className="text-xs text-gray-400">:{pa.inbound_port}</span>
                    <span className={`px-1.5 py-0.5 rounded text-xs ${pa.enabled ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                      {pa.enabled ? 'Active' : 'Disabled'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1 font-mono">{pa.uuid || pa.email}</p>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => copyShareLink(pa.id)} title="Copy share link" className="p-2 rounded hover:bg-gray-100 text-blue-600">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" /></svg>
                  </button>
                  <button onClick={() => deleteProxyAccount(pa.id)} title="Delete" className="p-2 rounded hover:bg-red-50 text-red-500">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" /></svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
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
                className="flex-1 min-w-0 sm:min-w-[200px] rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
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
                className="flex-1 min-w-0 sm:min-w-[150px] rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none" />
              <button onClick={addWhitelistEntry}
                className="flex items-center gap-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                <Plus className="h-4 w-4" /> Add
              </button>
            </div>
          </div>

          {whitelist.length > 0 && (
            <div className="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b">
                <span className="text-xs font-medium text-gray-500 uppercase">{whitelist.length} entries</span>
                <button onClick={clearWhitelist} className="text-xs text-red-500 hover:text-red-700">Clear All</button>
              </div>
              <div className="overflow-x-auto">
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
            </div>
          )}

          {whitelist.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">No whitelist entries. User has unrestricted access.</p>
          )}

          {/* Visited Destinations - sites user accessed */}
          <div className="rounded-xl bg-white p-5 shadow-sm border border-green-100 mt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-green-600">
                Visited Destinations ({visitedDests.length})
              </h3>
              <div className="flex gap-3">
                <button onClick={fetchVisitedDests} className="text-xs text-blue-500 hover:text-blue-700">Refresh</button>
                <button onClick={clearVisitedDests} className="text-xs text-red-500 hover:text-red-700">Clear All</button>
              </div>
            </div>
            <p className="text-xs text-gray-400 mb-3">
              Sites this user has visited.
            </p>
            {visitedDests.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-green-50 text-left text-xs font-medium uppercase text-gray-500">
                      <th className="px-2 sm:px-3 py-2">IP</th>
                      <th className="px-2 sm:px-3 py-2">Hostname</th>
                      <th className="px-2 sm:px-3 py-2">Count</th>
                      <th className="px-2 sm:px-3 py-2 hidden sm:table-cell">Last Seen</th>
                      <th className="px-2 sm:px-3 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {visitedDests.map((v) => {
                      const addr = v.dest_hostname || v.dest_ip
                      const isAdding = addingBlocked === addr
                      return (
                        <tr key={addr} className="border-b last:border-b-0 hover:bg-green-50/50">
                          <td className="px-2 sm:px-3 py-2 font-mono text-xs">
                            {v.dest_ip}
                          </td>
                          <td className="px-2 sm:px-3 py-2 text-xs text-gray-600 max-w-[150px] truncate" title={v.dest_hostname || ''}>
                            {v.dest_hostname || <span className="text-gray-300">-</span>}
                          </td>
                          <td className="px-2 sm:px-3 py-2 text-xs font-medium text-green-600">{v.count}</td>
                          <td className="px-2 sm:px-3 py-2 text-xs text-gray-500 whitespace-nowrap hidden sm:table-cell">{formatDate(v.last_seen)}</td>
                          <td className="px-2 sm:px-3 py-2">
                            <div className="flex gap-1">
                              <button
                                onClick={() => addVisitedToWhitelist(v.dest_ip, v.dest_hostname)}
                                disabled={isAdding}
                                className={`rounded px-1.5 sm:px-2 py-1 text-xs font-medium ${isAdding ? 'bg-gray-100 text-gray-400 cursor-wait' : 'bg-green-50 text-green-600 hover:bg-green-100'}`}
                                title="Add to whitelist"
                              >
                                {isAdding ? '...' : '+ WL'}
                              </button>
                              <button
                                onClick={() => addVisitedToBlacklist(v.dest_ip, v.dest_hostname)}
                                disabled={isAdding}
                                className={`rounded px-1.5 sm:px-2 py-1 text-xs font-medium ${isAdding ? 'bg-gray-100 text-gray-400 cursor-wait' : 'bg-red-50 text-red-600 hover:bg-red-100'}`}
                                title="Add to blacklist"
                              >
                                {isAdding ? '...' : '+ BL'}
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-gray-400 text-center py-4">No visited destinations yet. Click Refresh to check for new data.</p>
            )}
          </div>
        </div>
      )}

      {/* Blacklist Tab */}
      {tab === 'blacklist' && (
        <div className="space-y-4">
          <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100">
            <h3 className="text-sm font-medium text-gray-500 mb-3">Add Blacklist Entry</h3>
            <p className="text-xs text-gray-400 mb-3">
              Block specific addresses. Use <code className="bg-gray-100 px-1 rounded">*</code> to block ALL traffic except whitelist entries.
            </p>
            <div className="flex flex-wrap gap-3 items-end">
              <div className="flex-1 min-w-0 sm:min-w-[200px]">
                <label className="block text-xs text-gray-500 mb-1">Address (IP / CIDR / Domain / *)</label>
                <input type="text" value={blForm.address} onChange={(e) => setBlForm({ ...blForm, address: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="e.g. 1.2.3.4 or * for all" />
              </div>
              <div className="w-24">
                <label className="block text-xs text-gray-500 mb-1">Port</label>
                <input type="number" value={blForm.port} onChange={(e) => setBlForm({ ...blForm, port: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="All" />
              </div>
              <div className="w-28">
                <label className="block text-xs text-gray-500 mb-1">Protocol</label>
                <select value={blForm.protocol} onChange={(e) => setBlForm({ ...blForm, protocol: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm">
                  <option value="any">Any</option>
                  <option value="tcp">TCP</option>
                  <option value="udp">UDP</option>
                </select>
              </div>
              <div className="flex-1 min-w-0 sm:min-w-[150px]">
                <label className="block text-xs text-gray-500 mb-1">Description</label>
                <input type="text" value={blForm.description} onChange={(e) => setBlForm({ ...blForm, description: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="Optional" />
              </div>
              <button onClick={addBlacklistEntry}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 flex items-center gap-1">
                <Plus className="h-4 w-4" /> Block
              </button>
            </div>
          </div>

          {blacklist.length > 0 && (
            <div className="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
              <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-red-50 text-left text-xs font-medium uppercase text-red-600">
                    <th className="px-4 py-3">Address</th>
                    <th className="px-4 py-3">Port</th>
                    <th className="px-4 py-3">Protocol</th>
                    <th className="px-4 py-3">Description</th>
                    <th className="px-4 py-3 w-10"></th>
                  </tr>
                </thead>
                <tbody>
                  {blacklist.map((entry) => (
                    <tr key={entry.id} className="border-b last:border-b-0">
                      <td className="px-4 py-2.5 font-mono text-xs">{entry.address === '*' ? <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">* BLOCK ALL</span> : entry.address}</td>
                      <td className="px-4 py-2.5">{entry.port || 'All'}</td>
                      <td className="px-4 py-2.5 uppercase text-xs">{entry.protocol}</td>
                      <td className="px-4 py-2.5 text-gray-500">{entry.description || '-'}</td>
                      <td className="px-4 py-2.5">
                        <button onClick={() => deleteBlacklistEntry(entry.id)} className="rounded p-1 text-red-400 hover:bg-red-50">
                          <X className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          )}

          {blacklist.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">No blacklist entries. Nothing is blocked.</p>
          )}

          {/* Blocked Requests Section */}
          <div className="rounded-xl bg-white p-5 shadow-sm border border-orange-100 mt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-orange-600">
                Blocked Requests ({deduplicatedBlocked.length})
              </h3>
              <div className="flex gap-3">
                <button onClick={fetchBlockedRequests}
                  className="text-xs text-blue-500 hover:text-blue-700">
                  Refresh
                </button>
                <button onClick={clearBlockedRequests}
                  className="text-xs text-red-500 hover:text-red-700">
                  Clear All
                </button>
              </div>
            </div>
            <p className="text-xs text-gray-400 mb-3">
              Destinations this user tried to access but were blocked.
            </p>
            {deduplicatedBlocked.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-orange-50 text-left text-xs font-medium uppercase text-gray-500">
                      <th className="px-2 sm:px-3 py-2">IP</th>
                      <th className="px-2 sm:px-3 py-2">Hostname</th>
                      <th className="px-2 sm:px-3 py-2">Count</th>
                      <th className="px-2 sm:px-3 py-2 hidden sm:table-cell">Last Seen</th>
                      <th className="px-2 sm:px-3 py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {deduplicatedBlocked.map((b) => {
                      const addr = b.dest_hostname || b.dest_ip
                      const isAdding = addingBlocked === addr
                      return (
                        <tr key={addr} className="border-b last:border-b-0 hover:bg-orange-50/50">
                          <td className="px-2 sm:px-3 py-2 font-mono text-xs">
                            {b.dest_ip}
                          </td>
                          <td className="px-2 sm:px-3 py-2 text-xs text-gray-600 max-w-[150px] truncate" title={b.dest_hostname || ''}>
                            {b.dest_hostname || <span className="text-gray-300">-</span>}
                          </td>
                          <td className="px-2 sm:px-3 py-2 text-xs font-medium text-orange-600">{b.count}</td>
                          <td className="px-2 sm:px-3 py-2 text-xs text-gray-500 whitespace-nowrap hidden sm:table-cell">{formatDate(b.last_seen)}</td>
                          <td className="px-2 sm:px-3 py-2">
                            <div className="flex gap-1">
                              <button
                                onClick={() => addBlockedToWhitelist(b.dest_ip, b.dest_hostname)}
                                disabled={isAdding}
                                className={`rounded px-1.5 sm:px-2 py-1 text-xs font-medium ${isAdding ? 'bg-gray-100 text-gray-400 cursor-wait' : 'bg-green-50 text-green-600 hover:bg-green-100'}`}
                                title="Add to whitelist"
                              >
                                {isAdding ? '...' : '+ WL'}
                              </button>
                              <button
                                onClick={() => addBlockedToBlacklist(b.dest_ip, b.dest_hostname)}
                                disabled={isAdding}
                                className={`rounded px-1.5 sm:px-2 py-1 text-xs font-medium ${isAdding ? 'bg-gray-100 text-gray-400 cursor-wait' : 'bg-red-50 text-red-600 hover:bg-red-100'}`}
                                title="Add to blacklist"
                              >
                                {isAdding ? '...' : '+ BL'}
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-gray-400 text-center py-4">No blocked requests yet. Click Refresh to check for new data.</p>
            )}
          </div>
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
              <div className="overflow-x-auto">
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
