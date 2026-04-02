'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { useRouter } from 'next/navigation'
import PortfolioSummary from '@/components/PortfolioSummary'
import TradeCards from '@/components/TradeCards'
import PortfolioTable from '@/components/PortfolioTable'
import PerformanceGraph from '@/components/PerformanceGraph'
import IndustryPieChart from '@/components/IndustryPieChart'
import FXTracker from '@/components/FXTracker'
import MarketWeightChart from '@/components/MarketWeightChart'
import TopPredictionsChart from '@/components/TopPredictionsChart'
import { LogOut, RefreshCw } from 'lucide-react'

export default function Dashboard() {
  const supabase = createClient()
  const router = useRouter()
  
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [data, setData] = useState<any>(null)
  const [displayCurrency, setDisplayCurrency] = useState<'USD' | 'INR'>('INR')
  const [marketFilter, setMarketFilter] = useState<'ALL' | 'US' | 'INDIA'>('ALL')
  
  const fetchData = async () => {
    setRefreshing(true)
    try {
      const res = await fetch('/api/dashboard', { cache: 'no-store' })
      if (res.status === 401) {
        router.push('/login')
        return
      }
      const json = await res.json()
      setData(json)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 60000)
    return () => clearInterval(interval)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleLogout = async () => {
    await supabase.auth.signOut()
    router.push('/login')
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#0a0a0a] text-white">
        <div className="w-16 h-16 border-4 border-gray-800 border-t-blue-500 rounded-full animate-spin mb-4" />
        <p className="text-gray-400 font-medium">Loading Portfolio Data...</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#0a0a0a] text-white">
        <p className="text-rose-500 font-medium bg-rose-500/10 px-4 py-2 rounded-xl">Error: Unable to load data from API.</p>
      </div>
    )
  }

  const { portfolio: fullPortfolio, trades: fullTrades, performance, account, livePrices, sectors, fxRate } = data
  
  // Filtering
  const filteredPortfolio = fullPortfolio.filter((p: any) => {
    if (marketFilter === 'US') return !p.ticker.endsWith('.NS')
    if (marketFilter === 'INDIA') return p.ticker.endsWith('.NS')
    return true
  })
  
  const filteredTrades = fullTrades.filter((t: any) => {
    if (marketFilter === 'US') return !t.ticker.endsWith('.NS')
    if (marketFilter === 'INDIA') return t.ticker.endsWith('.NS')
    return true
  })

  // Value Calculations
  let investedValueBase = 0 // in native currency logic, but usually stored in db
  let currentPortfolioValueBase = 0
  
  // For global stats, we convert everything to display currency
  let totalInvestedValue = 0
  let totalCurrentValue = 0
  
  filteredPortfolio.forEach((p: any) => {
    const currentPrice = livePrices[p.ticker] || p.buy_price
    const tickerCurrency = p.ticker.endsWith('.NS') ? 'INR' : 'USD'
    
    // Convert to display currency
    let valInvested = Number(p.shares) * p.buy_price
    let valCurrent = Number(p.shares) * currentPrice
    
    if (displayCurrency === 'INR' && tickerCurrency === 'USD') {
      valInvested *= fxRate
      valCurrent *= fxRate
    } else if (displayCurrency === 'USD' && tickerCurrency === 'INR') {
      valInvested /= fxRate
      valCurrent /= fxRate
    }
    
    totalInvestedValue += valInvested
    totalCurrentValue += valCurrent
  })
  
  // Cash balance logic
  let displayCash = 0
  if (marketFilter === 'US') {
     displayCash = displayCurrency === 'INR' ? account.cash_usd * fxRate : account.cash_usd
  } else if (marketFilter === 'INDIA') {
     displayCash = displayCurrency === 'USD' ? account.cash_inr / fxRate : account.cash_inr
  } else {
     // ALL
     const total_usd = account.cash_usd + (account.cash_inr / fxRate)
     displayCash = displayCurrency === 'INR' ? total_usd * fxRate : total_usd
  }

  const totalValue = displayCash + totalCurrentValue
  const unrealizedPnL = totalCurrentValue - totalInvestedValue

  // Realized Profit Calculation
  let totalRealizedPnL = 0
  const allTradesClean = data.allTrades || []
  
  allTradesClean.forEach((t: any) => {
    // Filter by market
    const isIndian = t.ticker.endsWith('.NS')
    if (marketFilter === 'US' && isIndian) return
    if (marketFilter === 'INDIA' && !isIndian) return
    
    // Only count sells/exits for realized profit
    // (Strategies can emit MODEL_SELL as well.)
    const action = String(t.action || '').toUpperCase()
    const isExit = ['SELL', 'STOP_LOSS', 'TAKE_PROFIT', 'MODEL_SELL'].includes(action)
    if (!isExit) return
    
    let pnl = Number(t.realized_pnl)
    if (!Number.isFinite(pnl)) pnl = 0
    const tickerCurrency = isIndian ? 'INR' : 'USD'
    
    // Convert to display currency
    if (displayCurrency === 'INR' && tickerCurrency === 'USD') {
      pnl *= fxRate
    } else if (displayCurrency === 'USD' && tickerCurrency === 'INR') {
      pnl /= fxRate
    }
    
    totalRealizedPnL += pnl
  })

  let dailyChange = 0
  if (performance && performance.length >= 2) {
    const last = performance[performance.length - 1].total_value
    const prev = performance[performance.length - 2].total_value
    dailyChange = last - prev
    if (displayCurrency === 'INR') dailyChange *= fxRate
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-gray-100 p-4 md:p-8 font-sans selection:bg-blue-500/30">
      <header className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between mb-8 pb-6 border-b border-gray-800/60">
        <div className="mb-4 md:mb-0">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/20">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <h1 className="text-3xl font-bold text-white tracking-tight">Global Dashboard</h1>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-6 w-full md:w-auto">
          <FXTracker fxRate={fxRate} fxHistory={data.fxHistory || []} />
          
          <div className="flex items-center gap-3">
            <div className="flex bg-[#171717] p-1 rounded-xl border border-gray-800">
            {['ALL', 'US', 'INDIA'].map((m) => (
              <button
                key={m}
                onClick={() => setMarketFilter(m as any)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${marketFilter === m ? 'bg-blue-500 text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
              >
                {m}
              </button>
            ))}
          </div>

          <div className="flex bg-[#171717] p-1 rounded-xl border border-gray-800">
            {['INR', 'USD'].map((c) => (
              <button
                key={c}
                onClick={() => setDisplayCurrency(c as any)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${displayCurrency === c ? 'bg-emerald-500 text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
              >
                {c}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <button 
                onClick={fetchData} 
                disabled={refreshing}
                className="py-2 px-4 bg-[#171717] border border-gray-800 rounded-xl hover:bg-[#202020] transition-colors flex items-center justify-center disabled:opacity-50 group shadow-sm text-sm font-medium"
            >
                <RefreshCw className={`w-4 h-4 text-gray-400 group-hover:text-white ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <button 
                onClick={handleLogout} 
                className="flex items-center justify-center gap-2 bg-rose-500/10 text-rose-500 border border-rose-500/20 hover:bg-rose-500/20 px-4 py-2 rounded-xl transition-all font-medium text-sm"
            >
                <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
      </header>

      <main className="max-w-7xl mx-auto space-y-8">
        <PortfolioSummary 
          totalValue={totalValue} 
          cash={displayCash} 
          positionsCount={filteredPortfolio.length} 
          dailyChange={dailyChange} 
          investedAmount={totalInvestedValue}
          unrealizedPnL={unrealizedPnL}
          realizedPnL={totalRealizedPnL}
          currency={displayCurrency}
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
            <div className="bg-[#171717] border border-gray-800 rounded-3xl p-6 md:p-8 shadow-sm">
              <PerformanceGraph data={performance} currency={displayCurrency} fxRate={fxRate} />
            </div>

            <div className="bg-[#171717] border border-gray-800 rounded-3xl p-6 md:p-8 shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white tracking-tight">Active Positions</h2>
                <span className="text-sm text-gray-400">{filteredPortfolio.length} Assets</span>
              </div>
              <PortfolioTable 
                portfolio={filteredPortfolio} 
                livePrices={livePrices} 
                totalInvestedValue={totalInvestedValue} 
                currency={displayCurrency}
                fxRate={fxRate}
              />
            </div>
          </div>
          
          <div className="space-y-8">
            {/* NEW: Portfolio Weighting Chart */}
            <div className="bg-[#171717] border border-gray-800 rounded-3xl p-6 shadow-sm">
              <h2 className="text-xl font-bold text-white tracking-tight mb-8">Capital Allocation</h2>
              <MarketWeightChart 
                 portfolio={fullPortfolio} 
                 cash_usd={account.cash_usd} 
                 cash_inr={account.cash_inr} 
                 fxRate={fxRate} 
              />
            </div>

            {/* Asset Allocation Pie Chart */}
            <div className="bg-[#171717] border border-gray-800 rounded-3xl p-6 shadow-sm">
              <h2 className="text-xl font-bold text-white tracking-tight mb-8">Industry Breakdown</h2>
              <IndustryPieChart 
                portfolio={filteredPortfolio} 
                livePrices={livePrices} 
                sectors={sectors || {}} 
                currency={displayCurrency}
                fxRate={fxRate}
              />
            </div>

            {/* NEW: ML Top Prediction Signals */}
            <div className="bg-[#171717] border border-gray-800 rounded-3xl p-6 shadow-sm">
              <h2 className="text-xl font-bold text-white tracking-tight mb-8">Trade Signals</h2>
              <TopPredictionsChart scores={data.ml_scores || {}} />
            </div>

            <div className="bg-[#171717] border border-gray-800 rounded-3xl p-6 shadow-sm flex flex-col max-h-[400px]">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white tracking-tight">Recent Activity</h2>
              </div>
              <div className="overflow-y-auto flex-1 pr-2 custom-scrollbar">
                <TradeCards trades={filteredTrades} currency={displayCurrency} fxRate={fxRate} />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
