import { useEffect, useState, FormEvent } from 'react'
import { Save, Lock, Eye, EyeOff } from 'lucide-react'
import api from '../api/client'
import toast from 'react-hot-toast'

interface SettingItem {
  key: string
  value: string
}

const LABELS: Record<string, { label: string; type: string; description: string }> = {
  global_alerts_enabled: { label: 'Global Alerts', type: 'toggle', description: 'Enable/disable all alerts system-wide' },
  alert_email_enabled: { label: 'Email Alerts', type: 'toggle', description: 'Send alerts via email (requires SMTP config)' },
  alert_telegram_enabled: { label: 'Telegram Alerts', type: 'toggle', description: 'Send alerts via Telegram bot' },
  bandwidth_poll_interval: { label: 'Bandwidth Poll Interval', type: 'number', description: 'Seconds between bandwidth polling (default: 60)' },
  connection_logging_enabled: { label: 'Connection Logging', type: 'toggle', description: 'Log all user connections (addresses and ports)' },
  panel_language: { label: 'Language', type: 'select', description: 'Panel display language' },
}

export default function Settings() {
  const [settings, setSettings] = useState<SettingItem[]>([])
  const [loading, setLoading] = useState(true)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrentPw, setShowCurrentPw] = useState(false)
  const [showNewPw, setShowNewPw] = useState(false)
  const [changingPw, setChangingPw] = useState(false)

  useEffect(() => {
    api.get('/settings').then((res) => {
      setSettings(res.data)
    }).catch(() => {
      // Settings may fail but page should still render
    }).finally(() => {
      setLoading(false)
    })
  }, [])

  const updateValue = (key: string, value: string) => {
    setSettings(settings.map((s) => (s.key === key ? { ...s, value } : s)))
  }

  const handleSave = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api.put('/settings', settings.map((s) => ({ key: s.key, value: s.value })))
      toast.success('Settings saved')
    } catch {
      toast.error('Failed to save')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      <form onSubmit={handleSave} className="space-y-1">
        <div className="rounded-xl bg-white shadow-sm border border-gray-100 divide-y">
          {settings.map((setting) => {
            const meta = LABELS[setting.key]
            if (!meta) return null

            return (
              <div key={setting.key} className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">{meta.label}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{meta.description}</p>
                </div>
                <div>
                  {meta.type === 'toggle' ? (
                    <button
                      type="button"
                      onClick={() => updateValue(setting.key, setting.value === 'true' ? 'false' : 'true')}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        setting.value === 'true' ? 'bg-blue-600' : 'bg-gray-300'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          setting.value === 'true' ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  ) : meta.type === 'number' ? (
                    <input
                      type="number"
                      value={setting.value}
                      onChange={(e) => updateValue(setting.key, e.target.value)}
                      className="w-24 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-right focus:border-blue-500 focus:outline-none"
                    />
                  ) : meta.type === 'select' ? (
                    <select
                      value={setting.value}
                      onChange={(e) => updateValue(setting.key, e.target.value)}
                      className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
                    >
                      <option value="en">English</option>
                      <option value="fa">Persian</option>
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={setting.value}
                      onChange={(e) => updateValue(setting.key, e.target.value)}
                      className="w-48 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
                    />
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <div className="pt-4">
          <button
            type="submit"
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Save className="h-4 w-4" /> Save Settings
          </button>
        </div>
      </form>

      {/* Change Password */}
      <div className="rounded-xl bg-white p-6 shadow-sm border border-gray-100">
        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Lock className="h-5 w-5 text-gray-500" />
          Change Admin Password
        </h3>
        <form
          onSubmit={async (e: FormEvent) => {
            e.preventDefault()
            if (newPassword !== confirmPassword) {
              toast.error('Passwords do not match')
              return
            }
            if (newPassword.length < 6) {
              toast.error('Password must be at least 6 characters')
              return
            }
            setChangingPw(true)
            try {
              await api.post('/auth/change-password', {
                current_password: currentPassword,
                new_password: newPassword,
              })
              toast.success('Password changed successfully')
              setCurrentPassword('')
              setNewPassword('')
              setConfirmPassword('')
            } catch (err: any) {
              toast.error(err.response?.data?.detail || 'Failed to change password')
            } finally {
              setChangingPw(false)
            }
          }}
          className="space-y-4 max-w-md"
        >
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Current Password</label>
            <div className="relative">
              <input
                type={showCurrentPw ? 'text' : 'password'}
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 pr-10"
                required
              />
              <button
                type="button"
                onClick={() => setShowCurrentPw(!showCurrentPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showCurrentPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
            <div className="relative">
              <input
                type={showNewPw ? 'text' : 'password'}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 pr-10"
                required
                minLength={6}
              />
              <button
                type="button"
                onClick={() => setShowNewPw(!showNewPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showNewPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm New Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className={`w-full rounded-lg border px-4 py-2.5 text-sm focus:outline-none focus:ring-1 ${
                confirmPassword && confirmPassword !== newPassword
                  ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
              }`}
              required
              minLength={6}
            />
            {confirmPassword && confirmPassword !== newPassword && (
              <p className="text-xs text-red-500 mt-1">Passwords do not match</p>
            )}
          </div>
          <button
            type="submit"
            disabled={changingPw}
            className="flex items-center gap-2 rounded-lg bg-red-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            <Lock className="h-4 w-4" />
            {changingPw ? 'Changing...' : 'Change Password'}
          </button>
        </form>
      </div>

      {/* Environment Info */}
      <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100">
        <h3 className="text-sm font-medium text-gray-500 mb-3">Environment Configuration</h3>
        <p className="text-xs text-gray-400 mb-2">
          These settings are configured via .env file and require a restart to take effect.
        </p>
        <div className="space-y-1 text-sm font-mono">
          <p className="text-gray-500">WG_INTERFACE, WG_PORT, WG_SUBNET, WG_DNS</p>
          <p className="text-gray-500">SMTP_HOST, SMTP_PORT, SMTP_USERNAME</p>
          <p className="text-gray-500">TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL</p>
          <p className="text-gray-500">SECRET_KEY, ENCRYPTION_KEY</p>
        </div>
      </div>
    </div>
  )
}
