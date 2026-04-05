import { useEffect, useState } from 'react'
import {
  Users,
  Wifi,
  WifiOff,
  HardDrive,
  Cpu,
  MemoryStick,
  ArrowUpCircle,
  ArrowDownCircle,
  Globe,
} from 'lucide-react'
import api from '../api/client'
import { formatBytes } from '../lib/utils'

interface DashboardData {
  system: {
    cpu_percent: number
    memory_percent: number
    memory_used_gb: number
    memory_total_gb: number
    disk_percent: number
    disk_used_gb: number
    disk_total_gb: number
  }
  total_users: number
  active_users: number
  disabled_users: number
  expired_users: number
  online_users: number
  total_bandwidth_up: number
  total_bandwidth_down: number
  destination_vpns_up: number
  destination_vpns_total: number
  recent_alerts_count: number
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color = 'blue',
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string | number
  sub?: string
  color?: string
}) {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
    orange: 'bg-orange-50 text-orange-600',
  }

  return (
    <div className="rounded-xl bg-white p-3 sm:p-5 shadow-sm border border-gray-100">
      <div className="flex items-center gap-2 sm:gap-3">
        <div className={`rounded-lg p-2 sm:p-2.5 ${colorMap[color]}`}>
          <Icon className="h-4 w-4 sm:h-5 sm:w-5" />
        </div>
        <div className="min-w-0">
          <p className="text-xs sm:text-sm text-gray-500 truncate">{label}</p>
          <p className="text-lg sm:text-2xl font-bold text-gray-900">{value}</p>
          {sub && <p className="text-xs text-gray-400 mt-0.5 truncate">{sub}</p>}
        </div>
      </div>
    </div>
  )
}

function GaugeBar({ label, percent, used, total }: { label: string; percent: number; used: string; total: string }) {
  const color = percent > 90 ? 'bg-red-500' : percent > 70 ? 'bg-orange-500' : 'bg-blue-500'
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="font-medium text-gray-700">{label}</span>
        <span className="text-gray-500">{used} / {total}</span>
      </div>
      <div className="h-3 rounded-full bg-gray-200 overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${percent}%` }} />
      </div>
      <p className="text-xs text-gray-400 mt-0.5 text-right">{percent.toFixed(1)}%</p>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await api.get('/dashboard')
        setData(res.data)
      } catch {
        // handle error
      } finally {
        setLoading(false)
      }
    }
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <StatCard icon={Users} label="Total Users" value={data.total_users} sub={`${data.active_users} active`} />
        <StatCard icon={Wifi} label="Online Now" value={data.online_users} color="green" />
        <StatCard
          icon={Globe}
          label="Destinations"
          value={`${data.destination_vpns_up}/${data.destination_vpns_total}`}
          sub="up / total"
          color="purple"
        />
        <StatCard
          icon={data.recent_alerts_count > 0 ? WifiOff : Wifi}
          label="Alerts"
          value={data.recent_alerts_count}
          color={data.recent_alerts_count > 0 ? 'red' : 'green'}
        />
      </div>

      {/* Bandwidth Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100">
          <h3 className="text-sm font-medium text-gray-500 mb-3">Total Bandwidth Usage</h3>
          <div className="flex gap-6">
            <div className="flex items-center gap-2">
              <ArrowUpCircle className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-xs text-gray-400">Upload</p>
                <p className="text-lg font-bold">{formatBytes(data.total_bandwidth_up)}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <ArrowDownCircle className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-xs text-gray-400">Download</p>
                <p className="text-lg font-bold">{formatBytes(data.total_bandwidth_down)}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100">
          <h3 className="text-sm font-medium text-gray-500 mb-3">User Breakdown</h3>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <p className="text-lg font-bold text-green-600">{data.active_users}</p>
              <p className="text-xs text-gray-400">Active</p>
            </div>
            <div>
              <p className="text-lg font-bold text-gray-400">{data.disabled_users}</p>
              <p className="text-xs text-gray-400">Disabled</p>
            </div>
            <div>
              <p className="text-lg font-bold text-red-500">{data.expired_users}</p>
              <p className="text-xs text-gray-400">Expired</p>
            </div>
          </div>
        </div>
      </div>

      {/* System Resources */}
      <div className="rounded-xl bg-white p-5 shadow-sm border border-gray-100">
        <h3 className="text-sm font-medium text-gray-500 mb-4">Server Resources</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <GaugeBar
            label="CPU"
            percent={data.system.cpu_percent}
            used={`${data.system.cpu_percent.toFixed(1)}%`}
            total="100%"
          />
          <GaugeBar
            label="Memory"
            percent={data.system.memory_percent}
            used={`${data.system.memory_used_gb} GB`}
            total={`${data.system.memory_total_gb} GB`}
          />
          <GaugeBar
            label="Disk"
            percent={data.system.disk_percent}
            used={`${data.system.disk_used_gb} GB`}
            total={`${data.system.disk_total_gb} GB`}
          />
        </div>
      </div>
    </div>
  )
}
