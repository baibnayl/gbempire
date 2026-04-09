import { getDashboardData } from '@/lib/dashboard-data'
import { OrdersChart, RevenueChart } from '@/components/orders-chart'

export const dynamic = 'force-dynamic'

function money(value: number) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'KZT',
    maximumFractionDigits: 0,
  }).format(value)
}

function dt(value: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export default async function Page() {
  const data = await getDashboardData()

  return (
    <main className="page">
      <div className="header">
        <div>
          <h1 className="title">RetailCRM Orders Dashboard</h1>
          <p className="subtitle">
            Данные берутся из Supabase. На странице показаны последние заказы,
            динамика по дням и базовые метрики.
          </p>
        </div>
        <div className="badge">Last sync: {dt(data.metrics.lastSyncAt)}</div>
      </div>

      <section className="grid">
        <div className="card metric">
          <div className="metric-label">Всего заказов</div>
          <div className="metric-value">{data.metrics.totalOrders}</div>
          <div className="metric-sub">в выборке из Supabase</div>
        </div>

        <div className="card metric">
          <div className="metric-label">Общая сумма</div>
          <div className="metric-value">{money(data.metrics.totalRevenue)}</div>
          <div className="metric-sub">сумма по полю total_sum</div>
        </div>

        <div className="card metric">
          <div className="metric-label">Средний чек</div>
          <div className="metric-value">{money(data.metrics.avgCheck)}</div>
          <div className="metric-sub">общая сумма / число заказов</div>
        </div>

        <div className="card metric">
          <div className="metric-label">Статусов</div>
          <div className="metric-value">{data.statuses.length}</div>
          <div className="metric-sub">топ статусов справа</div>
        </div>

        <div className="card chart">
          <h2 className="section-title">Заказы по дням</h2>
          <OrdersChart data={data.chart} />
        </div>

        <div className="card side">
          <h2 className="section-title">Топ статусов</h2>
          <div className="kv-list">
            {data.statuses.length ? (
              data.statuses.map((item) => (
                <div key={item.status} className="kv">
                  <span className="kv-key">{item.status}</span>
                  <span className="kv-value">{item.count}</span>
                </div>
              ))
            ) : (
              <div className="empty">Статусы пока не найдены.</div>
            )}
          </div>

          <div className="footer-note">Выручка за те же даты:</div>
          <RevenueChart data={data.chart} />
        </div>

        <div className="card table-card">
          <h2 className="section-title">Последние заказы</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Номер</th>
                  <th>Клиент</th>
                  <th>Город</th>
                  <th>Статус</th>
                  <th>Сумма</th>
                  <th>Дата</th>
                </tr>
              </thead>
              <tbody>
                {data.recentOrders.length ? (
                  data.recentOrders.map((order) => (
                    <tr key={order.retailcrm_order_id ?? order.order_number ?? Math.random()}>
                      <td>{order.retailcrm_order_id ?? '—'}</td>
                      <td>{order.order_number ?? '—'}</td>
                      <td>{[order.first_name, order.last_name].filter(Boolean).join(' ') || '—'}</td>
                      <td>{order.city ?? '—'}</td>
                      <td>{order.status ?? '—'}</td>
                      <td>{money(Number(order.total_sum ?? 0))}</td>
                      <td>{dt(order.order_created_at)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7}>
                      <div className="empty">В таблице пока нет заказов.</div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </main>
  )
}
