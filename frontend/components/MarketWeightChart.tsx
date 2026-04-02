'use client'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#6366f1']

export default function MarketWeightChart({ 
  portfolio, 
  cash_usd, 
  cash_inr, 
  fxRate 
}: { 
  portfolio: any[], 
  cash_usd: number, 
  cash_inr: number, 
  fxRate: number 
}) {
  let usStocksValue = 0
  let indiaStocksValue = 0
  
  portfolio.forEach(p => {
    const val = Number(p.shares) * (p.currentPrice || p.buy_price) // using fallbacks if livePrices not passed directly
    if (p.ticker.endsWith('.NS')) {
      indiaStocksValue += val / fxRate // normalize to USD for comparison
    } else {
      usStocksValue += val
    }
  })

  const total_usd = usStocksValue + indiaStocksValue + cash_usd + (cash_inr / fxRate)
  
  if (total_usd === 0) return null

  const data = [
    { name: 'US Stocks', value: usStocksValue },
    { name: 'India Stocks', value: indiaStocksValue },
    { name: 'Cash (USD)', value: cash_usd },
    { name: 'Cash (INR)', value: cash_inr / fxRate }
  ].filter(d => d.value > 0)

  return (
    <div className="h-[250px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={80}
            paddingAngle={5}
            dataKey="value"
            stroke="none"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip 
            formatter={(val: any) => [`$${val.toLocaleString(undefined, {maximumFractionDigits: 0})}`, 'Value (USD Eq.)']}
            contentStyle={{ backgroundColor: '#171717', borderColor: '#333', borderRadius: '12px' }}
          />
          <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '11px', color: '#94a3b8' }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
