'use client'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export default function TopPredictionsChart({ scores }: { scores: Record<string, number> }) {
  if (!scores || Object.keys(scores).length === 0) return null

  const data = Object.keys(scores)
    .map(ticker => ({ ticker, score: scores[ticker] * 100 })) // Show as percentage
    .sort((a,b) => b.score - a.score)
    .slice(0, 8) // Top 8

  return (
    <div className="h-[300px] w-full">
      <h3 className="text-sm font-black uppercase tracking-widest text-gray-500 mb-6">Top ML Signals (%)</h3>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 0, right: 10, left: -20, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
          <XAxis 
            dataKey="ticker" 
            stroke="#525252" 
            fontSize={10} 
            tickLine={false} 
            axisLine={false}
            tick={{ fill: '#a3a3a3' }}
          />
          <YAxis 
            stroke="#525252" 
            fontSize={10} 
            tickLine={false} 
            axisLine={false}
            tickFormatter={(val) => `${val.toFixed(1)}%`}
          />
          <Tooltip 
            cursor={{ fill: 'rgba(59, 130, 246, 0.05)' }}
            contentStyle={{ backgroundColor: '#171717', borderColor: '#333', borderRadius: '12px' }}
            itemStyle={{ color: '#fff', fontSize: '13px' }}
            formatter={(val: any) => [`${val.toFixed(2)}%`, 'Prediction']}
          />
          <Bar dataKey="score" radius={[4, 4, 0, 0]} barSize={24}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.ticker.endsWith('.NS') ? '#10b981' : '#3b82f6'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
