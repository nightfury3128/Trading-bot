'use client'

import { useState } from 'react'

export default function TradeCards({ trades }: { trades: any[] }) {
  const [filter, setFilter] = useState<'ALL' | 'BUY' | 'SELL'>('ALL')
  
  if (!trades.length) return <div className="text-gray-500 p-4 font-medium flex items-center justify-center h-full">No recent trades.</div>

  const filteredTrades = trades.filter((t) => {
    if (filter === 'ALL') return true
    const isBuy = t.action.toUpperCase() === 'BUY'
    if (filter === 'BUY') return isBuy
    return !isBuy
  })

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2 mb-2 sticky top-0 bg-[#171717] pb-2 z-10 border-b border-gray-800">
        <button onClick={() => setFilter('ALL')} className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${filter === 'ALL' ? 'bg-gray-100 text-black shadow-md' : 'bg-gray-800/50 text-gray-400 hover:text-gray-200'}`}>ALL</button>
        <button onClick={() => setFilter('BUY')} className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${filter === 'BUY' ? 'bg-emerald-500 text-white shadow-md shadow-emerald-500/20' : 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border border-emerald-500/10'}`}>BUYS</button>
        <button onClick={() => setFilter('SELL')} className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${filter === 'SELL' ? 'bg-rose-500 text-white shadow-md shadow-rose-500/20' : 'bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border border-rose-500/10'}`}>SELLS</button>
      </div>
      
      {filteredTrades.length === 0 && (
        <div className="text-gray-500 p-4 font-medium flex items-center justify-center h-full">No trades match this filter.</div>
      )}

      {filteredTrades.map((trade, i) => {
        const action = trade.action.toUpperCase()
        const isBuy = action === 'BUY'
        const isSell = action === 'SELL' || action === 'STOP_LOSS' || action === 'TAKE_PROFIT'
        
        return (
          <div key={i} className="bg-[#171717] border border-gray-800/80 rounded-xl p-4 flex gap-4 hover:border-gray-700/80 transition-all shadow-md hover:bg-[#1a1a1a] group">
            <div className={`w-1.5 rounded-full ${
              isBuy ? 'bg-emerald-500' : isSell ? 'bg-rose-500' : 'bg-blue-500'
            }`} />
            <div className="flex-1">
              <div className="flex justify-between items-start mb-2">
                <span className={`px-2.5 py-1 text-xs font-bold rounded-md tracking-wide ${
                  isBuy ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 
                  isSell ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 
                  'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                }`}>
                  {trade.action}
                </span>
                <span className="text-xs text-gray-500 font-mono bg-gray-900 px-2 py-0.5 rounded">{trade.date}</span>
              </div>
              <div className="flex justify-between mt-2 items-end">
                <div>
                  <h4 className="text-lg font-bold text-gray-100 flex items-center gap-2">
                    {trade.ticker}
                  </h4>
                  <p className="text-sm text-gray-400 mt-0.5">Shares: <span className="font-mono text-gray-300">{Number(trade.shares).toFixed(4)}</span></p>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-gray-100 tracking-tight">${Number(trade.price * trade.shares).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
                  <p className="text-xs text-gray-500 mt-1 font-mono">@ ${Number(trade.price).toFixed(2)}</p>
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
