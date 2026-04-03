import { useEffect, useState } from 'react'
import { Bell, Check, CheckCheck } from 'lucide-react'
import api from '../api/client'
import { formatDate } from '../lib/utils'
import toast from 'react-hot-toast'

interface AlertItem {
  id: number
  user_id: number | null
  type: string
  message: string
  channel: string | null
  sent_at: string
  acknowledged: boolean
}

const TYPE_COLORS: Record<string, string> = {
  bandwidth_warning: 'bg-orange-100 text-orange-700',
  expiry_warning: 'bg-yellow-100 text-yellow-700',
  expired: 'bg-red-100 text-red-700',
  dest_vpn_down: 'bg-red-100 text-red-700',
}

export default function Alerts() {
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [unreadOnly, setUnreadOnly] = useState(false)

  const fetchAlerts = async () => {
    try {
      const res = await api.get('/alerts', { params: { limit: 100, unread_only: unreadOnly } })
      setAlerts(res.data)
    } catch { /* may not have permission */ }
  }

  useEffect(() => { fetchAlerts() }, [unreadOnly])

  const acknowledge = async (id: number) => {
    try {
      await api.post(`/alerts/${id}/acknowledge`)
      fetchAlerts()
    } catch { toast.error('Failed to acknowledge') }
  }

  const acknowledgeAll = async () => {
    try {
      await api.post('/alerts/acknowledge-all')
      toast.success('All alerts acknowledged')
      fetchAlerts()
    } catch { toast.error('Failed to acknowledge alerts') }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Alerts</h1>
        <div className="flex gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)}
              className="rounded border-gray-300" />
            Unread only
          </label>
          <button onClick={acknowledgeAll}
            className="flex items-center gap-1.5 rounded-lg bg-gray-50 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100">
            <CheckCheck className="h-4 w-4" /> Mark all read
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {alerts.length === 0 ? (
          <div className="rounded-xl bg-white p-12 shadow-sm border border-gray-100 text-center">
            <Bell className="h-12 w-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No alerts</p>
          </div>
        ) : alerts.map((alert) => (
          <div key={alert.id}
            className={`rounded-xl bg-white p-4 shadow-sm border ${alert.acknowledged ? 'border-gray-100 opacity-60' : 'border-gray-200'} flex items-start justify-between`}>
            <div className="flex items-start gap-3">
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[alert.type] || 'bg-gray-100 text-gray-600'}`}>
                {alert.type.replace(/_/g, ' ')}
              </span>
              <div>
                <p className="text-sm text-gray-900">{alert.message}</p>
                <p className="text-xs text-gray-400 mt-1">{formatDate(alert.sent_at)}</p>
              </div>
            </div>
            {!alert.acknowledged && (
              <button onClick={() => acknowledge(alert.id)}
                className="rounded p-1.5 text-gray-400 hover:bg-gray-100" title="Acknowledge">
                <Check className="h-4 w-4" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
