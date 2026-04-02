import { useState, useEffect, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'
import toast from 'react-hot-toast'

interface Destination {
  id: number
  name: string
  protocol: string
}

export default function UserNew() {
  const navigate = useNavigate()
  const [destinations, setDestinations] = useState<Destination[]>([])
  const [form, setForm] = useState({
    username: '',
    note: '',
    destination_vpn_id: '',
    bandwidth_limit_down: '',
    bandwidth_limit_up: '',
    speed_limit_down: '',
    speed_limit_up: '',
    max_connections: '1',
    expiry_date: '',
    alert_enabled: true,
    alert_threshold: '80',
  })

  useEffect(() => {
    api.get('/destinations').then((res) => setDestinations(res.data))
  }, [])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      const payload: Record<string, unknown> = {
        username: form.username,
        note: form.note || null,
        destination_vpn_id: form.destination_vpn_id ? Number(form.destination_vpn_id) : null,
        max_connections: Number(form.max_connections),
        alert_enabled: form.alert_enabled,
        alert_threshold: Number(form.alert_threshold),
      }
      // Convert GB to bytes for bandwidth limits
      if (form.bandwidth_limit_down) payload.bandwidth_limit_down = Number(form.bandwidth_limit_down) * 1024 * 1024 * 1024
      if (form.bandwidth_limit_up) payload.bandwidth_limit_up = Number(form.bandwidth_limit_up) * 1024 * 1024 * 1024
      if (form.speed_limit_down) payload.speed_limit_down = Number(form.speed_limit_down)
      if (form.speed_limit_up) payload.speed_limit_up = Number(form.speed_limit_up)
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

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Download Limit (GB)</label>
            <input
              type="number"
              value={form.bandwidth_limit_down}
              onChange={(e) => update('bandwidth_limit_down', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Unlimited"
              min="0"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Upload Limit (GB)</label>
            <input
              type="number"
              value={form.bandwidth_limit_up}
              onChange={(e) => update('bandwidth_limit_up', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Unlimited"
              min="0"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Download Speed (Kbps)</label>
            <input
              type="number"
              value={form.speed_limit_down}
              onChange={(e) => update('speed_limit_down', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Unlimited"
              min="0"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Upload Speed (Kbps)</label>
            <input
              type="number"
              value={form.speed_limit_up}
              onChange={(e) => update('speed_limit_up', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Unlimited"
              min="0"
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
