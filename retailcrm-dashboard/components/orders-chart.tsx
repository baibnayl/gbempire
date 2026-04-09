'use client'

import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
} from 'recharts'

export type ChartPoint = {
  date: string
  orders: number
  revenue: number
}

export function OrdersChart({ data }: { data: ChartPoint[] }) {
  if (!data.length) {
    return <div className="empty">Нет данных для графика.</div>
  }

  return (
    <div style={{ width: '100%', height: 360 }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid stroke="rgba(99,102,241,0.16)" vertical={false} />
          <XAxis dataKey="date" stroke="#a5b4fc" tickLine={false} axisLine={false} />
          <YAxis stroke="#a5b4fc" tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip />
          <Line type="monotone" dataKey="orders" stroke="#818cf8" strokeWidth={3} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function RevenueChart({ data }: { data: ChartPoint[] }) {
  if (!data.length) {
    return <div className="empty">Нет данных по выручке.</div>
  }

  return (
    <div style={{ width: '100%', height: 260 }}>
      <ResponsiveContainer>
        <BarChart data={data}>
          <CartesianGrid stroke="rgba(99,102,241,0.16)" vertical={false} />
          <XAxis dataKey="date" stroke="#a5b4fc" tickLine={false} axisLine={false} hide />
          <YAxis stroke="#a5b4fc" tickLine={false} axisLine={false} />
          <Tooltip />
          <Bar dataKey="revenue" fill="#4f46e5" radius={[8, 8, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
