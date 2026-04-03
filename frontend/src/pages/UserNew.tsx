import { useState, useEffect, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Package as PackageIcon } from 'lucide-react'
import api from '../api/client'
import { formatBytes } from '../lib/utils'
import toast from 'react-hot-toast'

interface Destination {
  id: number
  name: string
  protocol: string
}

interface Pkg {
  id: number
  name: string
  description: string | null
  bandwidth_limit: number | null
  speed_limit: number | null
  duration_days: number
  max_connections: number
  price: number | null
  currency: string
  enabled: boolean
  destination_vpn_id: number | null
  destination_vpn_name: string | null
}

export default function UserNew() {
  const navigate = useNavigate()
  const [destinations, setDestinations] = useState<Destination[]>([])
  const [packages, setPackages] = useState<Pkg[]>([])
  const [selectedPkg, setSelectedPkg] = useState<number | null>(null)
  const [form, setForm] = useState({
    username: '',
    note: '',
    destination_vpn_id: '',
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

  useEffect(() => {
    api.get('/destinations').then((res) => setDestinations(res.data))
    api.get('/packages').then((res) => setPackages(res.data.filter((p: Pkg) => p.enabled)))
  }, [])

  const applyPackage = (pkgId: number | null) => {
    setSelectedPkg(pkgId)
    if (!pkgId) return

    const pkg = packages.find((p) => p.id === pkgId)
    if (!pkg) return

    // Determine best unit for bandwidth
    const bwBytes = pkg.bandwidth_limit
    let bwValue = ''
    let bwUnit: 'GB' | 'MB' = 'GB'
    if (bwBytes) {
      if (bwBytes < 1024 * 1024 * 1024) {
        bwValue = String(bwBytes / (1024 * 1024))
        bwUnit = 'MB'
      } else {
        bwValue = String(bwBytes / (1024 * 1024 * 1024))
        bwUnit = 'GB'
      }
    }

    // Convert speed from Kbps to Mbps
    const speedMbps = pkg.speed_limit ? String(pkg.speed_limit / 1000) : ''

    // Calculate expiry date from duration_days
    const expiry = new Date()
    expiry.setDate(expiry.getDate() + pkg.duration_days)
    const expiryStr = expiry.toISOString().slice(0, 16) // format for datetime-local

    setForm((prev) => ({
      ...prev,
      bandwidth_limit_down: bwValue,
      bandwidth_limit_up: bwValue,
      bandwidth_unit_down: bwUnit,
      bandwidth_unit_up: bwUnit,
      speed_limit_down: speedMbps,
      speed_limit_up: speedMbps,
      max_connections: String(pkg.max_connections),
      expiry_date: expiryStr,
      destination_vpn_id: pkg.destination_vpn_id ? String(pkg.destination_vpn_id) : prev.destination_vpn_id,
    }))

    toast.success(`Package "${pkg.name}" applied`)
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      const payload: Record<string, unknown> = {
        username: form.username,
        note: form.note || null,
        destination_vpn_id: form.destination_vpn_id ? Number(form.destination_vpn_id) : null,
        package_id: selectedPkg || null,
        max_connections: Number(form.max_connections),
        alert_enabled: form.alert_enabled,
        alert_threshold: Number(form.alert_threshold),
      }
      // Convert GB/MB to bytes for bandwidth limits
      if (form.bandwidth_limit_down) {
        const multiplier = form.bandwidth_unit_down === 'GB' ? 1024 * 1024 * 1024 : 1024 * 1024
        payload.bandwidth_limit_down = Number(form.bandwidth_limit_down) * multiplier
      }
      if (form.bandwidth_limit_up) {
        const multiplier = form.bandwidth_unit_up === 'GB' ? 1024 * 1024 * 1024 : 1024 * 1024
        payload.bandwidth_limit_up = Number(form.bandwidth_limit_up) * multiplier
      }
      // Convert Mbps to Kbps for speed limits
      if (form.speed_limit_down) payload.speed_limit_down = Number(form.speed_limit_down) * 1000
      if (form.speed_limit_up) payload.speed_limit_up = Number(form.speed_limit_up) * 1000
      if (form.expiry_date) payload.expiry_date = new Date(form.expiry_date).toISOString()

      const res = await api.post('/users', payload)
      toast.success('User created')
      navigate(`/users/${res.data.id}`)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create user')
    }
  }

  const update = (field: string, value: unknown) => setForm({ ...form, [field]: value })

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Create New User</h1>

      <form onSubmit={handleSubmit} className="space-y-6 bg-white rounded-xl p-6 shadow-sm border border-gray-100">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
          <input
            type="text"
            value={form.username}
            onChange={(e) => update('username', e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Note</label>
          <input
            type="text"
            value={form.note}
            onChange={(e) => update('note', e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Destination VPN</label>
          <select
            value={form.destination_vpn_id}
            onChange={(e) => update('destination_vpn_id', e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">-- None --</option>
            {destinations.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.protocol})
              </option>
            ))}
          </select>
        </div>

        {/* Package Selection */}
        {packages.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Apply Package</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {packages.map((pkg) => (
                <button
                  key={pkg.id}
                  type="button"
                  onClick={() => applyPackage(pkg.id)}
                  className={`relative rounded-lg border-2 p-3 text-left text-sm transition-all hover:shadow-md ${
                    selectedPkg === pkg.id
                      ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <PackageIcon className={`h-4 w-4 ${selectedPkg === pkg.id ? 'text-blue-600' : 'text-gray-400'}`} />
                    <span className="font-medium text-gray-900">{pkg.name}</span>
                  </div>
                  <div className="space-y-0.5 text-xs text-gray-500">
                    <div>Traffic: {pkg.bandwidth_limit ? formatBytes(pkg.bandwidth_limit) : 'Unlimited'}</div>
                    <div>Speed: {pkg.speed_limit ? `${pkg.speed_limit / 1000} Mbps` : 'Unlimited'}</div>
                    <div>{pkg.duration_days} days &middot; {pkg.max_connections} conn</div>
                    {pkg.price && (
                      <div className="font-medium text-gray-700">{pkg.price.toLocaleString()} {pkg.currency}</div>
                    )}
                  </div>
                  {selectedPkg === pkg.id && (
                    <div className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-blue-500" />
                  )}
                </button>
              ))}
            </div>
            {selectedPkg && (
              <button
                type="button"
                onClick={() => setSelectedPkg(null)}
                className="mt-2 text-xs text-gray-400 hover:text-gray-600"
              >
                Clear package selection (keep current values)
              </button>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Download Limit</label>
            <div className="flex gap-2">
              <input
                type="number"
                value={form.bandwidth_limit_down}
                onChange={(e) => update('bandwidth_limit_down', e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Unlimited"
                min="0"
                step="any"
              />
              <select
                value={form.bandwidth_unit_down}
                onChange={(e) => update('bandwidth_unit_down', e.target.value)}
                className="w-20 rounded-lg border border-gray-300 px-2 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="GB">GB</option>
                <option value="MB">MB</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Upload Limit</label>
            <div className="flex gap-2">
              <input
                type="number"
                value={form.bandwidth_limit_up}
                onChange={(e) => update('bandwidth_limit_up', e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Unlimited"
                min="0"
                step="any"
              />
              <select
                value={form.bandwidth_unit_up}
                onChange={(e) => update('bandwidth_unit_up', e.target.value)}
                className="w-20 rounded-lg border border-gray-300 px-2 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="GB">GB</option>
                <option value="MB">MB</option>
              </select>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Download Speed (Mbps)</label>
            <input
              type="number"
              value={form.speed_limit_down}
              onChange={(e) => update('speed_limit_down', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Unlimited"
              min="0"
              step="any"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Upload Speed (Mbps)</label>
            <input
              type="number"
              value={form.speed_limit_up}
              onChange={(e) => update('speed_limit_up', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Unlimited"
              min="0"
              step="any"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Connections</label>
            <input
              type="number"
              value={form.max_connections}
              onChange={(e) => update('max_connections', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              min="1"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Expiry Date</label>
            <input
              type="datetime-local"
              value={form.expiry_date}
              onChange={(e) => update('expiry_date', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="alert_enabled"
              checked={form.alert_enabled}
              onChange={(e) => update('alert_enabled', e.target.checked)}
              className="rounded border-gray-300"
            />
            <label htmlFor="alert_enabled" className="text-sm text-gray-700">Enable Alerts</label>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Alert Threshold (%)</label>
            <input
              type="number"
              value={form.alert_threshold}
              onChange={(e) => update('alert_threshold', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              min="1"
              max="100"
            />
          </div>
        </div>

        <div className="flex gap-3 pt-4">
          <button
            type="submit"
            className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            Create User
          </button>
          <button
            type="button"
            onClick={() => navigate('/users')}
            className="rounded-lg border border-gray-300 px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
