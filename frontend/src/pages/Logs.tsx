import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import api from '../api/client'
import { formatDate } from '../lib/utils'

interface LogEntry {
  id: number
  user_id: number | null
  username: string | null
  source_ip: string
  dest_ip: string
  dest_hostname: string | null
  dest_port: number | null
  protocol: string | null
  bytes_sent: number
  bytes_received: number
  started_at: string
  dest_country: string | null
  dest_country_code: string | null
  dest_city: string | null
  dest_isp: string | null
}

function getFlagEmoji(countryCode: string): string {
  const codePoints = countryCode
    .toUpperCase()
    .split('')
    .map((c) => 0x1f1e6 + c.charCodeAt(0) - 65)
  return String.fromCodePoint(...codePoints)
}

export default function Logs() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    dest_ip: '',
    dest_hostname: '',
    protocol: '',
    username: '',
  })
  const [page, setPage] = useState(0)

  const fetchLogs = async () => {
    try {
      const params: Record<string, string | number> = { skip: page * 50, limit: 50 }
      if (filters.dest_ip) params.dest_ip = filters.dest_ip
      if (filters.dest_hostname) params.dest_hostname = filters.dest_hostname
      if (filters.protocol) params.protocol = filters.protocol
      if (filters.username) params.username = filters.username
      const res = await api.get('/logs', { params })
      setLogs(res.data.logs)
      setTotal(res.data.total)
    } catch {
      // handle error
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [page, filters])

  return (
    <div className="space-y-3 sm:space-y-6">
      <h1 className="text-lg sm:text-2xl font-bold text-gray-900">Connection Logs ({total})</h1>

      {/* Filters */}
      <div className="flex gap-2 sm:gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Username..."
            value={filters.username}
            onChange={(e) => { setFilters({ ...filters, username: e.target.value }); setPage(0) }}
            className="rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Destination IP..."
            value={filters.dest_ip}
            onChange={(e) => { setFilters({ ...filters, dest_ip: e.target.value }); setPage(0) }}
            className="rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Hostname..."
            value={filters.dest_hostname}
            onChange={(e) => { setFilters({ ...filters, dest_hostname: e.target.value }); setPage(0) }}
            className="rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
        <select
          value={filters.protocol}
          onChange={(e) => { setFilters({ ...filters, protocol: e.target.value }); setPage(0) }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">All protocols</option>
          <option value="tcp">TCP</option>
          <option value="udp">UDP</option>
          <option value="icmp">ICMP</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                <th className="px-2 sm:px-4 py-3">Time</th>
                <th className="px-2 sm:px-4 py-3">User</th>
                <th className="px-2 sm:px-4 py-3 hidden sm:table-cell">Source</th>
                <th className="px-2 sm:px-4 py-3">Destination</th>
                <th className="px-2 sm:px-4 py-3 hidden md:table-cell">Location</th>
                <th className="px-2 sm:px-4 py-3 hidden lg:table-cell">Hostname</th>
                <th className="px-2 sm:px-4 py-3 hidden sm:table-cell">Port</th>
                <th className="px-2 sm:px-4 py-3 hidden sm:table-cell">Proto</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-gray-400">Loading...</td>
                </tr>
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                    No connection logs yet. Logs appear when users connect and browse.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="border-b last:border-b-0 hover:bg-gray-50">
                    <td className="px-2 sm:px-4 py-2.5 text-xs text-gray-500 whitespace-nowrap">{formatDate(log.started_at)}</td>
                    <td className="px-2 sm:px-4 py-2.5 font-medium">{log.username || '-'}</td>
                    <td className="px-2 sm:px-4 py-2.5 font-mono text-xs text-gray-500 hidden sm:table-cell">{log.source_ip}</td>
                    <td className="px-2 sm:px-4 py-2.5 font-mono text-xs">{log.dest_ip}</td>
                    <td className="px-2 sm:px-4 py-2.5 text-xs text-gray-600 whitespace-nowrap hidden md:table-cell">
                      {log.dest_country_code ? (
                        <span title={[log.dest_city, log.dest_country, log.dest_isp].filter(Boolean).join(' · ')}>
                          <span className="mr-1">{getFlagEmoji(log.dest_country_code)}</span>
                          {log.dest_city || log.dest_country || ''}
                        </span>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                    <td className="px-2 sm:px-4 py-2.5 text-xs text-gray-600 max-w-[180px] truncate hidden lg:table-cell" title={log.dest_hostname || ''}>
                      {log.dest_hostname || <span className="text-gray-300">-</span>}
                    </td>
                    <td className="px-2 sm:px-4 py-2.5 font-mono text-xs text-gray-500 hidden sm:table-cell">{log.dest_port || '-'}</td>
                    <td className="px-2 sm:px-4 py-2.5 hidden sm:table-cell">
                      <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium uppercase">
                        {log.protocol || '-'}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 50 && (
          <div className="flex items-center justify-between border-t px-4 py-3">
            <span className="text-sm text-gray-500">
              Showing {page * 50 + 1}-{Math.min((page + 1) * 50, total)} of {total}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(Math.max(0, page - 1))}
                disabled={page === 0}
                className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-gray-50"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(page + 1)}
                disabled={(page + 1) * 50 >= total}
                className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-gray-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
