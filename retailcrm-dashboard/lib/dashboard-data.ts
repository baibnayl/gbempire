import { getSupabaseServerClient } from './supabase'

export type OrderRow = {
  retailcrm_order_id: number | null
  order_number: string | null
  status: string | null
  first_name: string | null
  last_name: string | null
  city: string | null
  total_sum: number | null
  order_created_at: string | null
}

export type DashboardData = {
  metrics: {
    totalOrders: number
    totalRevenue: number
    avgCheck: number
    lastSyncAt: string | null
  }
  chart: Array<{ date: string; orders: number; revenue: number }>
  recentOrders: OrderRow[]
  statuses: Array<{ status: string; count: number }>
}

function formatDay(dateValue: string | null): string {
  if (!dateValue) return 'Unknown'
  const date = new Date(dateValue)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return date.toISOString().slice(0, 10)
}

export async function getDashboardData(): Promise<DashboardData> {
  const supabase = getSupabaseServerClient()

  const [ordersRes, syncRes] = await Promise.all([
    supabase
      .from('retailcrm_orders')
      .select('retailcrm_order_id, order_number, status, first_name, last_name, city, total_sum, order_created_at')
      .order('order_created_at', { ascending: false, nullsFirst: false })
      .limit(2000),
    supabase
      .from('sync_state')
      .select('last_sync_at')
      .eq('source', 'retailcrm_orders')
      .single(),
  ])

  if (ordersRes.error) {
    throw new Error(`Supabase orders query failed: ${ordersRes.error.message}`)
  }

  const orders = (ordersRes.data ?? []) as OrderRow[]
  const lastSyncAt = syncRes.data?.last_sync_at ?? null

  const totalOrders = orders.length
  const totalRevenue = orders.reduce((sum, row) => sum + Number(row.total_sum ?? 0), 0)
  const avgCheck = totalOrders ? totalRevenue / totalOrders : 0

  const chartMap = new Map<string, { date: string; orders: number; revenue: number }>()
  const statusMap = new Map<string, number>()

  for (const row of orders) {
    const date = formatDay(row.order_created_at)
    const existing = chartMap.get(date) ?? { date, orders: 0, revenue: 0 }
    existing.orders += 1
    existing.revenue += Number(row.total_sum ?? 0)
    chartMap.set(date, existing)

    const status = row.status || 'unknown'
    statusMap.set(status, (statusMap.get(status) ?? 0) + 1)
  }

  const chart = Array.from(chartMap.values())
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-30)

  const statuses = Array.from(statusMap.entries())
    .map(([status, count]) => ({ status, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)

  return {
    metrics: {
      totalOrders,
      totalRevenue,
      avgCheck,
      lastSyncAt,
    },
    chart,
    recentOrders: orders.slice(0, 12),
    statuses,
  }
}
