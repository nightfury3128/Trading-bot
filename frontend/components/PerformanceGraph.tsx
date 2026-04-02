'use client'
import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

export default function PerformanceGraph({ 
  data, 
  currency = 'USD', 
  fxRate = 83.5,
  usBenchmarkData = [],
  inBenchmarkData = []
}: { 
  data: any[]; 
  currency?: 'USD' | 'INR';
  fxRate?: number;
  usBenchmarkData?: any[];
  inBenchmarkData?: any[];
}) {
  const [timeFilter, setTimeFilter] = useState<'1W' | '1M' | 'ALL'>('ALL')
  const [showBenchmarks, setShowBenchmarks] = useState(true)
  
  const symbol = currency === 'INR' ? '₹' : '$'
  const locale = currency === 'INR' ? 'en-IN' : 'en-US'

  if (!data || data.length === 0) return <div className="text-center text-gray-500 font-medium p-8 flex items-center justify-center h-full">No performance records found.</div>

  const filteredData = data.filter((d) => {
    if (timeFilter === 'ALL') return true;
    const date = new Date(d.date)
    const now = new Date()
    const diffTime = Math.abs(now.getTime() - date.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)); 
    
    if (timeFilter === '1W') return diffDays <= 7;
    if (timeFilter === '1M') return diffDays <= 30;
    return true;
  })

  // Fallback to plotting all data if filter returns nothing
  const targetPortfolio = filteredData.length > 0 ? filteredData : data

  // Normalization Bases
  const startVisibleDate = new Date(targetPortfolio[0]?.date || Date.now())
  const portfolioBase = Number(targetPortfolio[0]?.total_value || 1)

  const fUsBench = usBenchmarkData.filter(b => new Date(b.date) >= startVisibleDate)
  const fInBench = inBenchmarkData.filter(b => new Date(b.date) >= startVisibleDate)

  const usBenchBase = Number(fUsBench[0]?.value || 1)
  const inBenchBase = Number(fInBench[0]?.value || 1)

  const mergedData = targetPortfolio.map((d, i) => {
    let pValNative = Number(d.total_value)
    let pValDisplay = pValNative
    if (currency === 'INR') pValDisplay *= fxRate

    const dateKey = d.date.split('T')[0]
    
    const usQuote = fUsBench.find(b => b.date.split('T')[0] === dateKey) || fUsBench[i]
    let usValNorm = usQuote ? (Number(usQuote.value) / usBenchBase) * portfolioBase : null
    if (usValNorm && currency === 'INR') usValNorm *= fxRate

    const inQuote = fInBench.find(b => b.date.split('T')[0] === dateKey) || fInBench[i]
    let inValNorm = inQuote ? (Number(inQuote.value) / inBenchBase) * portfolioBase : null
    if (inValNorm && currency === 'INR') inValNorm *= fxRate

    return {
      date: dateKey,
      portfolio: pValDisplay,
      usMarket: usValNorm,
      inMarket: inValNorm,
    }
  })

  const minVal = Math.min(...mergedData.map(d => Math.min(d.portfolio, d.usMarket || d.portfolio, d.inMarket || d.portfolio))) * 0.98
  const maxVal = Math.max(...mergedData.map(d => Math.max(d.portfolio, d.usMarket || d.portfolio, d.inMarket || d.portfolio))) * 1.02

  return (
    <div className="flex flex-col h-full w-full">
      <div className="flex items-center justify-between mb-8 overflow-x-auto pb-2 gap-4">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-bold text-white tracking-tight whitespace-nowrap">Performance vs Benchmarks</h2>
          <button 
            onClick={() => setShowBenchmarks(!showBenchmarks)}
            className={`px-3 py-1 text-[10px] font-black uppercase rounded-lg border transition-all ${showBenchmarks ? 'bg-blue-500/10 border-blue-500 text-blue-400' : 'bg-gray-800 border-gray-700 text-gray-500'}`}
          >
            {showBenchmarks ? 'Hide Markets' : 'Show Markets'}
          </button>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setTimeFilter('1W')} className={`px-3 py-1 text-xs font-bold rounded-lg transition-all ${timeFilter === '1W' ? 'bg-blue-500 text-white shadow-md shadow-blue-500/30' : 'bg-transparent text-gray-400 hover:bg-[#202020]'}`}>1W</button>
          <button onClick={() => setTimeFilter('1M')} className={`px-3 py-1 text-xs font-bold rounded-lg transition-all ${timeFilter === '1M' ? 'bg-blue-500 text-white shadow-md shadow-blue-500/30' : 'bg-transparent text-gray-400 hover:bg-[#202020]'}`}>1M</button>
          <button onClick={() => setTimeFilter('ALL')} className={`px-3 py-1 text-xs font-bold rounded-lg transition-all ${timeFilter === 'ALL' ? 'bg-blue-500 text-white shadow-md shadow-blue-500/30' : 'bg-transparent text-gray-400 hover:bg-[#202020]'}`}>ALL</button>
        </div>
      </div>
      <div className="h-[350px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={mergedData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#262626" vertical={false} />
          <XAxis 
            dataKey="date" 
            stroke="#525252" 
            fontSize={11} 
            tickLine={false} 
            axisLine={false}
            dy={10}
          />
          <YAxis 
            stroke="#525252" 
            fontSize={11} 
            tickLine={false} 
            axisLine={false}
            tickFormatter={(val) => `${symbol}${val.toLocaleString(locale)}`}
            domain={[minVal, maxVal]}
          />
          <Tooltip 
            contentStyle={{ backgroundColor: '#171717', borderColor: '#262626', borderRadius: '12px', boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)' }}
            itemStyle={{ fontWeight: 600, fontSize: '12px' }}
            formatter={(value: any) => [`${symbol}${Number(value).toLocaleString(locale, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`]}
            labelStyle={{ color: '#a3a3a3', marginBottom: '8px', fontSize: '11px' }}
          />
          <Legend 
             verticalAlign="top" 
             align="right" 
             iconType="circle"
             wrapperStyle={{ paddingBottom: '20px', fontSize: '11px' }}
          />
          <Line 
            name="My Portfolio"
            type="monotone" 
            dataKey="portfolio" 
            stroke="#3b82f6" 
            strokeWidth={3} 
            dot={false}
            activeDot={{ r: 6, fill: '#3b82f6', stroke: '#0a0a0a', strokeWidth: 3 }}
            animationDuration={1500}
          />
          {showBenchmarks && (
            <>
              <Line 
                name="S&P 500 (US)"
                type="monotone" 
                dataKey="usMarket" 
                stroke="#ef4444" 
                strokeWidth={2} 
                strokeDasharray="4 4"
                dot={false}
                activeDot={{ r: 4, fill: '#ef4444', stroke: '#0a0a0a', strokeWidth: 2 }}
                animationDuration={1500}
              />
              <Line 
                name="NIFTY 50 (India)"
                type="monotone" 
                dataKey="inMarket" 
                stroke="#10b981" 
                strokeWidth={2} 
                strokeDasharray="4 4"
                dot={false}
                activeDot={{ r: 4, fill: '#10b981', stroke: '#0a0a0a', strokeWidth: 2 }}
                animationDuration={1500}
              />
            </>
          )}
        </LineChart>
      </ResponsiveContainer>
      </div>
    </div>
  )
}
