'use client'

const RISK_COLORS: Record<string, string> = {
  LOW: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  MEDIUM: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  HIGH: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
}

const DEFAULT_RISK_LEVEL = 'MEDIUM'

export default function PortfolioTable({ 
  portfolio, 
  livePrices, 
  totalInvestedValue,
  currency = 'USD',
  fxRate = 83.5
}: { 
  portfolio: any[], 
  livePrices: Record<string, number>, 
  totalInvestedValue: number,
  currency?: 'USD' | 'INR',
  fxRate?: number
}) {
  const symbol = currency === 'INR' ? '₹' : '$'
  const locale = currency === 'INR' ? 'en-IN' : 'en-US'
  
  const format = (v: number) => {
    return `${v < 0 ? '-' : ''}${symbol}${Math.abs(v).toLocaleString(locale, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
  }

  const convert = (val: number, ticker: string) => {
    const tickerCurrency = ticker.endsWith('.NS') ? 'INR' : 'USD'
    if (currency === tickerCurrency) return val
    if (currency === 'INR' && tickerCurrency === 'USD') return val * fxRate
    if (currency === 'USD' && tickerCurrency === 'INR') return val / fxRate
    return val
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-800/50 bg-[#171717]/50">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="border-b border-gray-800 bg-[#111111]">
            <th className="py-4 px-5 font-semibold text-gray-400 text-sm tracking-wide">Ticker</th>
            <th className="py-4 px-5 font-semibold text-gray-400 text-sm tracking-wide">Shares</th>
            <th className="py-4 px-5 font-semibold text-gray-400 text-sm tracking-wide">Avg Cost</th>
            <th className="py-4 px-5 font-semibold text-gray-400 text-sm tracking-wide">Current Price</th>
            <th className="py-4 px-5 font-semibold text-gray-400 text-sm tracking-wide">Value</th>
            <th className="py-4 px-5 font-semibold text-gray-400 text-sm tracking-wide w-[20%]">Allocation</th>
            <th className="py-4 px-5 font-semibold text-gray-400 text-sm tracking-wide">Stop Loss</th>
            <th className="py-4 px-5 font-semibold text-gray-400 text-sm tracking-wide text-right">P/L</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {portfolio.map((pos, i) => {
            const currentPriceNative = livePrices[pos.ticker] || pos.buy_price
            const buyPriceNative = Number(pos.buy_price)
            
            const price = convert(currentPriceNative, pos.ticker)
            const buyPrice = convert(buyPriceNative, pos.ticker)
            
            const shares = Number(pos.shares)
            const value = shares * price
            const pnlTotal = value - (shares * buyPrice)
            const pnl = ((price - buyPrice) / buyPrice) * 100
            const allocation = totalInvestedValue > 0 ? (value / totalInvestedValue) * 100 : 0
            
            return (
              <tr key={i} className="hover:bg-[#1f1f1f] transition-colors group">
                <td className="py-4 px-5 font-bold text-gray-100 flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center text-xs text-gray-400 group-hover:bg-blue-500 group-hover:text-white transition-colors">
                    {pos.ticker[0]}
                  </div>
                  {pos.ticker}
                </td>
                <td className="py-4 px-5 text-gray-300 font-mono text-sm">{shares.toFixed(4)}</td>
                <td className="py-4 px-5 text-gray-300 font-mono text-sm">{format(buyPrice)}</td>
                <td className="py-4 px-5 text-gray-100 font-mono text-sm">{format(price)}</td>
                <td className="py-4 px-5 font-medium text-white tracking-tight">{format(value)}</td>
                <td className="py-4 px-5">
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-2 bg-gray-800/80 rounded-full overflow-hidden border border-gray-700/30">
                      <div className="h-full bg-gradient-to-r from-blue-600 to-blue-400 rounded-full" style={{ width: `${Math.min(100, allocation)}%` }} />
                    </div>
                    <span className="text-xs font-mono text-gray-400 w-10">{allocation.toFixed(1)}%</span>
                  </div>
                </td>
                <td className="py-4 px-5 font-mono text-sm">
                  {pos.ticker.endsWith('.NS') && pos.stop_loss != null ? (() => {
                    const stopPrice = convert(buyPriceNative * Number(pos.stop_loss), pos.ticker)
                    const riskLevel: string = pos.risk_level || DEFAULT_RISK_LEVEL
                    const colorClass = RISK_COLORS[riskLevel] || RISK_COLORS[DEFAULT_RISK_LEVEL]
                    return (
                      <div className="flex flex-col gap-1">
                        <span className="text-gray-200">{format(stopPrice)}</span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide border ${colorClass} w-fit`}>
                          {riskLevel}
                        </span>
                      </div>
                    )
                  })() : (
                    <span className="text-gray-600">—</span>
                  )}
                </td>
                <td className="py-4 px-5 text-right font-medium">
                  <div className="flex flex-col items-end gap-1">
                    <span className={`text-sm ${pnlTotal >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {format(pnlTotal)}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide ${pnl > 0 ? 'bg-emerald-500/10 text-emerald-400' : pnl < 0 ? 'bg-rose-500/10 text-rose-400' : 'bg-gray-800 text-gray-400'}`}>
                      {pnl > 0 ? '+' : ''}{pnl.toFixed(2)}%
                    </span>
                  </div>
                </td>
              </tr>
            )
          })}
          {portfolio.length === 0 && (
            <tr>
              <td colSpan={8} className="py-12 text-center text-gray-500 font-medium">No active positions.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
