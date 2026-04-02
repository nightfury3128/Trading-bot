'use client'

import { useState } from 'react'
import { ShoppingCart, Shield, Zap, Lock, MinusCircle, HelpCircle, ArrowUpRight, ArrowDownRight, Share2 } from 'lucide-react'

export default function TradeCards({ 
  trades,
  currency = 'USD',
  fxRate = 83.5
}: { 
  trades: any[];
  currency?: 'USD' | 'INR';
  fxRate?: number;
}) {
  const [filter, setFilter] = useState<'ALL' | 'BUY' | 'SELL'>('ALL')
  
  const symbol = currency === 'INR' ? '₹' : '$'
  const locale = currency === 'INR' ? 'en-IN' : 'en-US'

  const format = (v: number) => {
    return `${symbol}${Math.abs(v).toLocaleString(locale, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
  }

  const convert = (val: number, ticker: string) => {
    const tickerCurrency = ticker.endsWith('.NS') ? 'INR' : 'USD'
    if (currency === tickerCurrency) return val
    if (currency === 'INR' && tickerCurrency === 'USD') return val * fxRate
    if (currency === 'USD' && tickerCurrency === 'INR') return val / fxRate
    return val
  }

  const getActionInfo = (action: string) => {
    const a = action.toUpperCase()
    if (a === 'BUY') return { icon: ShoppingCart, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' }
    if (a.includes('STOP_LOSS')) return { icon: Shield, color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20' }
    if (a.includes('NEGATIVE_SIGNAL')) return { icon: Zap, color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' }
    if (a.includes('PROFIT_LOCK')) return { icon: Lock, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' }
    if (a.includes('RISK_REDUCTION')) return { icon: MinusCircle, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' }
    return { icon: HelpCircle, color: 'text-gray-400', bg: 'bg-gray-500/10', border: 'border-gray-500/20' }
  }
  
  if (!trades.length) return <div className="text-gray-500 p-8 font-black flex flex-col items-center justify-center h-full opacity-50 uppercase tracking-widest text-xs">No recent activity</div>

  const filteredTrades = trades.filter((t) => {
    if (filter === 'ALL') return true
    const isBuy = t.action.toUpperCase() === 'BUY'
    if (filter === 'BUY') return isBuy
    return !isBuy
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2 mb-4 sticky top-0 bg-[#0a0a0a]/80 backdrop-blur-md pb-4 z-10 border-b border-white/5">
        <button onClick={() => setFilter('ALL')} className={`px-4 py-2 text-[10px] font-black rounded-xl transition-all duration-300 tracking-widest ${filter === 'ALL' ? 'bg-white text-black shadow-lg shadow-white/10' : 'bg-white/5 text-gray-500 hover:text-white border border-white/5'}`}>ALL</button>
        <button onClick={() => setFilter('BUY')} className={`px-4 py-2 text-[10px] font-black rounded-xl transition-all duration-300 tracking-widest ${filter === 'BUY' ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20' : 'bg-emerald-500/5 text-emerald-500/50 hover:text-emerald-400 border border-emerald-500/10'}`}>BUYS</button>
        <button onClick={() => setFilter('SELL')} className={`px-4 py-2 text-[10px] font-black rounded-xl transition-all duration-300 tracking-widest ${filter === 'SELL' ? 'bg-rose-500 text-white shadow-lg shadow-rose-500/20' : 'bg-rose-500/5 text-rose-500/50 hover:text-rose-400 border border-rose-500/10'}`}>SELLS</button>
      </div>
      
      {filteredTrades.length === 0 && (
        <div className="text-gray-600 p-8 font-black flex items-center justify-center h-full uppercase tracking-widest text-[10px]">No matches found</div>
      )}

      <div className="grid gap-3">
        {filteredTrades.map((trade, i) => {
            const actionInfo = getActionInfo(trade.action)
            const ActionIcon = actionInfo.icon
            const isBuy = trade.action.toUpperCase() === 'BUY'
            const isPartial = (trade.remaining_shares ?? 0) > 0
            
            return (
              <div key={i} className="group relative overflow-hidden bg-[#111111]/80 backdrop-blur-xl border border-white/5 rounded-2xl p-5 hover:border-white/10 transition-all duration-500 shadow-xl">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                    {isBuy ? <ArrowUpRight className="w-12 h-12 text-emerald-500" /> : <ArrowDownRight className="w-12 h-12 text-rose-500" />}
                </div>
                
                <div className="flex items-start justify-between mb-4 relative z-10">
                    <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center border ${actionInfo.border} ${actionInfo.bg}`}>
                            <ActionIcon className={`w-5 h-5 ${actionInfo.color}`} />
                        </div>
                        <div className="flex flex-col">
                            <span className={`text-[10px] font-black uppercase tracking-[0.2em] ${actionInfo.color}`}>
                                {trade.action.replace('_', ' ')}
                            </span>
                            <span className="text-xs text-gray-500 font-mono mt-0.5">{trade.date}</span>
                        </div>
                    </div>
                    {isPartial && (
                        <div className="px-2 py-1 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                            <span className="text-[9px] font-black text-blue-400 uppercase tracking-widest">Partial</span>
                        </div>
                    )}
                </div>

                <div className="flex justify-between items-end relative z-10">
                    <div>
                        <h4 className="text-xl font-black text-white tracking-tighter group-hover:text-blue-400 transition-colors uppercase">
                            {trade.ticker}
                        </h4>
                        <div className="flex items-center gap-2 mt-1">
                            <Share2 className="w-3 h-3 text-gray-600" />
                            <span className="text-xs font-black text-gray-400 tracking-tight">
                                {Number(trade.shares).toFixed(isBuy ? 4 : 2)} SHARES
                            </span>
                            {isPartial && (
                                <span className="text-[10px] text-gray-600 font-bold tracking-tight">
                                    / {Number(trade.remaining_shares).toFixed(2)} LEFT
                                </span>
                            )}
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="text-lg font-black text-white tracking-tight">
                            {format(convert(Number(trade.price * trade.shares), trade.ticker))}
                        </div>
                        <div className="text-[10px] text-gray-600 font-black tracking-widest mt-0.5">
                            @ {format(convert(Number(trade.price), trade.ticker))}
                        </div>
                    </div>
                </div>
              </div>
            )
        })}
      </div>
    </div>
  )
}
