'use client'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, Legend } from 'recharts'

const COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f43f5e', '#facc15', '#10b981', '#14b8a6', '#0ea5e9']

export default function IndustryPieChart({ 
  portfolio, 
  livePrices, 
  sectors,
  currency = 'USD',
  fxRate = 83.5
}: { 
  portfolio: any[], 
  livePrices: Record<string, number>, 
  sectors: Record<string, string>,
  currency?: 'USD' | 'INR',
  fxRate?: number
}) {
  const dataMap: Record<string, number> = {}
  
  const symbol = currency === 'INR' ? '₹' : '$'
  const locale = currency === 'INR' ? 'en-IN' : 'en-US'

  portfolio.forEach(p => {
    const sector = sectors[p.ticker] || 'Unknown'
    const tickerCurrency = p.ticker.endsWith('.NS') ? 'INR' : 'USD'
    let val = Number(p.shares) * (livePrices[p.ticker] || p.buy_price)
    
    // Normalization to display currency
    if (currency === 'INR' && tickerCurrency === 'USD') val *= fxRate
    else if (currency === 'USD' && tickerCurrency === 'INR') val /= fxRate

    dataMap[sector] = (dataMap[sector] || 0) + val
  })

  let data = Object.keys(dataMap).map(key => ({ name: key, value: dataMap[key] }))
  data.sort((a,b) => b.value - a.value)
  
  if (data.length === 0) return <div className="text-center text-gray-500 p-8 flex items-center justify-center font-medium h-full">No allocation data.</div>

  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={65}
            outerRadius={85}
            paddingAngle={6}
            dataKey="value"
            stroke="none"
            cornerRadius={4}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <RechartsTooltip 
            formatter={(value: any) => [`${symbol}${Number(value).toLocaleString(locale, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`, 'Value']}
            contentStyle={{ backgroundColor: '#171717', borderColor: '#262626', borderRadius: '12px', color: '#fff', boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)' }}
            itemStyle={{ color: '#fff', fontWeight: 500 }}
          />
          <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '12px', color: '#a3a3a3', fontWeight: 500 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
