'use client'

import React from 'react'
import { 
  TrendingUp, 
  TrendingDown, 
  Target, 
  Award, 
  ShieldAlert, 
  BarChart3, 
  Clock, 
  ArrowRightLeft, 
  Shield, 
  Zap, 
  Lock, 
  MinusCircle,
  HelpCircle
} from 'lucide-react'

interface Trade {
  ticker: string
  action: string
  date: string
  price: number
  shares: number
  realized_pnl: number
  pnl_pct: number
  buy_price?: number
  buy_date?: string
  holding_days?: number
  market_return?: number
  alpha?: number
  currency: string
  remaining_shares?: number
}

interface TradeAnalysisProps {
  trades: Trade[]
  currency: 'USD' | 'INR'
  fxRate: number
}

export default function TradeAnalysis({ trades, currency, fxRate }: TradeAnalysisProps) {
  const sellTrades = trades.filter(t => 
    ['SELL', 'STOP_LOSS', 'TAKE_PROFIT', 'MODEL_SELL', 'NEGATIVE_SIGNAL', 'PROFIT_LOCK', 'RISK_REDUCTION'].includes(t.action.toUpperCase())
  )

  if (sellTrades.length === 0) {
    return (
      <div className="bg-[#111111]/50 backdrop-blur-md border border-white/5 rounded-[2rem] p-12 text-center shadow-2xl">
        <div className="w-16 h-16 bg-gray-800/30 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-gray-700/50">
            <BarChart3 className="w-8 h-8 text-gray-500" />
        </div>
        <p className="text-gray-400 font-medium tracking-tight">No closed trades found for performance analysis.</p>
      </div>
    )
  }

  // Aggregated Metrics
  const winRate = (sellTrades.filter(t => t.realized_pnl > 0).length / sellTrades.length) * 100
  const avgReturn = sellTrades.reduce((acc, t) => acc + (t.pnl_pct || 0), 0) / sellTrades.length
  const avgAlpha = sellTrades.reduce((acc, t) => acc + (t.alpha || 0), 0) / sellTrades.length
  const bestTrade = [...sellTrades].sort((a, b) => (b.pnl_pct || 0) - (a.pnl_pct || 0))[0]
  const worstTrade = [...sellTrades].sort((a, b) => (a.pnl_pct || 0) - (b.pnl_pct || 0))[0]

  const formatCurrency = (val: number, ticker: string) => {
    const isIndian = ticker.endsWith('.NS')
    let displayVal = val
    let displaySym = isIndian ? '₹' : '$'

    if (currency === 'INR' && !isIndian) {
      displayVal *= fxRate
      displaySym = '₹'
    } else if (currency === 'USD' && isIndian) {
      displayVal /= fxRate
      displaySym = '$'
    }

    return `${displaySym}${displayVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  const formatPercent = (val: number | undefined) => {
    if (val === undefined) return 'N/A'
    return `${val > 0 ? '+' : ''}${val.toFixed(2)}%`
  }

  const getReasonIcon = (action: string) => {
    const a = action.toUpperCase()
    if (a.includes('STOP_LOSS')) return { icon: Shield, color: 'text-rose-400', bg: 'bg-rose-500/10' }
    if (a.includes('NEGATIVE_SIGNAL')) return { icon: Zap, color: 'text-amber-400', bg: 'bg-amber-500/10' }
    if (a.includes('PROFIT_LOCK')) return { icon: Lock, color: 'text-emerald-400', bg: 'bg-emerald-500/10' }
    if (a.includes('RISK_REDUCTION')) return { icon: MinusCircle, color: 'text-blue-400', bg: 'bg-blue-500/10' }
    if (a.includes('TAKE_PROFIT')) return { icon: Target, color: 'text-emerald-400', bg: 'bg-emerald-500/10' }
    return { icon: HelpCircle, color: 'text-gray-400', bg: 'bg-gray-500/10' }
  }

  return (
    <div className="space-y-10">
      {/* Premium Aggregated Metrics Panel */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-6">
        {[
          { label: 'Win Rate', value: `${winRate.toFixed(1)}%`, icon: Target, shadow: 'shadow-blue-500/10', gradient: 'from-blue-500/20 to-transparent' },
          { label: 'Avg Return', value: formatPercent(avgReturn), icon: BarChart3, shadow: avgReturn >= 0 ? 'shadow-emerald-500/10' : 'shadow-rose-500/10', gradient: avgReturn >= 0 ? 'from-emerald-500/20 to-transparent' : 'from-rose-500/20 to-transparent' },
          { label: 'Avg Alpha', value: formatPercent(avgAlpha), icon: Award, shadow: 'shadow-indigo-500/10', gradient: 'from-indigo-500/20 to-transparent' },
          { label: 'Best Pick', value: formatPercent(bestTrade.pnl_pct), icon: TrendingUp, shadow: 'shadow-emerald-500/10', gradient: 'from-emerald-500/20 to-transparent' },
          { label: 'Worst Pick', value: formatPercent(worstTrade.pnl_pct), icon: TrendingDown, shadow: 'shadow-rose-500/10', gradient: 'from-rose-500/20 to-transparent' },
        ].map((metric, i) => (
          <div key={i} className={`relative overflow-hidden bg-[#111111]/80 backdrop-blur-xl border border-white/5 p-6 rounded-[1.5rem] flex flex-col items-center text-center group hover:border-white/10 transition-all duration-500 ${metric.shadow}`}>
            <div className={`absolute inset-0 bg-gradient-to-br ${metric.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500`} />
            <div className="relative z-10">
                <div className="w-10 h-10 bg-white/5 rounded-xl flex items-center justify-center mb-3 group-hover:scale-110 transition-transform duration-500 border border-white/5">
                    <metric.icon className="w-5 h-5 text-white/70" />
                </div>
                <span className="text-[10px] text-gray-500 uppercase tracking-[0.2em] font-black">{metric.label}</span>
                <div className="text-2xl font-black text-white mt-2 tracking-tight">{metric.value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Modern Trade History Table */}
      <div className="bg-[#111111]/60 backdrop-blur-2xl border border-white/5 rounded-[2.5rem] overflow-hidden shadow-2xl relative">
        <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none" />
        
        <div className="p-8 border-b border-white/5 flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
            <div>
                <h2 className="text-2xl font-black text-white tracking-tighter">Trade Intelligence</h2>
                <p className="text-gray-500 text-sm mt-1 font-medium">Historical performance and alpha breakdown</p>
            </div>
            <div className="flex gap-3">
                <div className="flex flex-col items-end gap-1 px-4 py-2 bg-emerald-500/5 rounded-2xl border border-emerald-500/10">
                    <span className="text-[9px] font-black text-emerald-500/50 uppercase tracking-widest leading-none">Portfolio Win Rate</span>
                    <span className="text-emerald-400 font-black tracking-tighter">{winRate.toFixed(1)}%</span>
                </div>
                <div className="flex flex-col items-end gap-1 px-4 py-2 bg-blue-500/5 rounded-2xl border border-blue-500/10">
                    <span className="text-[9px] font-black text-blue-500/50 uppercase tracking-widest leading-none">Market Alpha</span>
                    <span className="text-blue-400 font-black tracking-tighter">{formatPercent(avgAlpha)}</span>
                </div>
            </div>
        </div>

        <div className="overflow-x-auto relative z-10">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white/[0.01] text-gray-500 text-[10px] uppercase tracking-[0.15em] font-black border-b border-white/5">
                <th className="px-8 py-5">Asset Intelligence</th>
                <th className="px-8 py-5">Timing</th>
                <th className="px-4 py-5 text-right">Execution</th>
                <th className="px-8 py-5 text-right">Net Result</th>
                <th className="px-8 py-5 text-center">Alpha Benchmarking</th>
                <th className="px-8 py-5 text-right">Decision Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {sellTrades.map((trade, i) => {
                const reason = getReasonIcon(trade.action)
                const ReasonIcon = reason.icon
                
                return (
                  <tr key={i} className="hover:bg-white/[0.03] transition-all duration-300 group">
                    <td className="px-8 py-6">
                      <div className="flex flex-col">
                        <span className="text-white font-black text-lg tracking-tighter group-hover:text-blue-400 transition-colors uppercase">{trade.ticker}</span>
                        <span className="text-[10px] text-gray-500 font-bold tracking-wide mt-0.5">
                          {trade.ticker.endsWith('.NS') ? 'INDIA • NIFTY 50' : 'US • S&P 500'}
                        </span>
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex flex-col gap-1.5">
                        <div className="flex items-center gap-2 text-gray-300">
                          <Clock className="w-3.5 h-3.5 text-gray-600" />
                          <span className="text-xs font-black tracking-tight">{trade.holding_days ?? '?'} DAYS</span>
                        </div>
                        <span className="text-[10px] text-gray-600 font-medium tracking-tight uppercase">{trade.date.split(' ')[0]}</span>
                      </div>
                    </td>
                    <td className="px-4 py-6 text-right">
                      <div className="flex flex-col gap-1">
                        <span className="text-[10px] font-black text-gray-600 uppercase">IN @ {formatCurrency(trade.buy_price || 0, trade.ticker)}</span>
                        <span className="text-sm font-black text-white tracking-tight">OUT @ {formatCurrency(trade.price, trade.ticker)}</span>
                      </div>
                    </td>
                    <td className="px-8 py-6 text-right">
                      <div className="flex flex-col items-end">
                        <span className={`text-lg font-black tracking-tighter ${trade.pnl_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {formatPercent(trade.pnl_pct)}
                        </span>
                        <span className="text-[11px] text-gray-500 font-bold">{formatCurrency(trade.realized_pnl, trade.ticker)}</span>
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex flex-col items-center">
                         <div className="flex items-center gap-5">
                            <div className="text-center group-hover:scale-105 transition-transform">
                              <div className="text-[9px] font-black text-gray-600 uppercase mb-1">STRATEGY</div>
                              <div className={`text-xs font-black ${trade.pnl_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{formatPercent(trade.pnl_pct)}</div>
                            </div>
                            <div className="p-1.5 bg-white/5 rounded-lg border border-white/5">
                                <ArrowRightLeft className="w-3 h-3 text-gray-500" />
                            </div>
                            <div className="text-center group-hover:scale-105 transition-transform">
                              <div className="text-[9px] font-black text-gray-600 uppercase mb-1">BENCHMARK</div>
                              <div className="text-xs font-black text-blue-400">{formatPercent(trade.market_return)}</div>
                            </div>
                         </div>
                         {trade.alpha !== undefined && (
                           <div className={`mt-3 text-[10px] font-black px-3 py-1 rounded-full border bg-opacity-10 backdrop-blur-sm ${trade.alpha >= 0 ? 'bg-emerald-500 border-emerald-500/20 text-emerald-400' : 'bg-rose-500 border-rose-500/20 text-rose-400'}`}>
                             {trade.alpha >= 0 ? 'OUTPERFORMED BY ' : 'UNDERPERFORMED BY '} {formatPercent(Math.abs(trade.alpha))}
                           </div>
                         )}
                      </div>
                    </td>
                    <td className="px-8 py-6 text-right">
                      <div className="flex flex-col items-end gap-2">
                        <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl border border-white/5 transition-all duration-300 ${reason.bg} group-hover:border-white/10`}>
                           <ReasonIcon className={`w-3.5 h-3.5 ${reason.color}`} />
                           <span className={`text-[10px] font-black uppercase tracking-wider ${reason.color}`}>{trade.action.replace('_', ' ')}</span>
                        </div>
                        {(trade.remaining_shares ?? 0) > 0 && (
                          <div className="bg-blue-500/10 text-blue-400 border border-blue-500/10 px-2 py-0.5 rounded-lg font-black text-[9px] uppercase tracking-widest">
                            Partial Liquidation
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
