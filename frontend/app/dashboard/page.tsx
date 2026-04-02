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
import TradeAnalysis from '@/components/TradeAnalysis'
import { LogOut, RefreshCw, Award, Globe, ShieldCheck, Zap, Activity } from 'lucide-react'

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
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleLogout = async () => {
    await supabase.auth.signOut()
    router.push('/login')
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#050505] text-white">
        <div className="relative">
          <div className="w-24 h-24 border-b-2 border-blue-500 rounded-full animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-16 h-16 border-t-2 border-emerald-500 rounded-full animate-spin-slow" />
          </div>
        </div>
        <p className="text-gray-500 font-black uppercase tracking-[0.3em] text-[10px] mt-8 animate-pulse">Initializing Alpha Core</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#050505] text-white">
        <p className="text-rose-500 font-black tracking-tighter bg-rose-500/10 px-6 py-3 rounded-2xl border border-rose-500/20 shadow-2xl shadow-rose-500/10 uppercase text-xs">Error: Core Communication Failure</p>
      </div>
    )
  }

  const { portfolio: fullPortfolio, trades: fullTrades, performance, account, livePrices, sectors, fxRate } = data

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

  // Value Calculations converted to display currency
  let totalInvestedValue = 0
  let totalCurrentValue = 0

  filteredPortfolio.forEach((p: any) => {
    const currentPrice = livePrices[p.ticker] || p.buy_price
    const tickerCurrency = p.ticker.endsWith('.NS') ? 'INR' : 'USD'

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

  let displayCash = 0
  if (marketFilter === 'US') {
    displayCash = displayCurrency === 'INR' ? account.cash_usd * fxRate : account.cash_usd
  } else if (marketFilter === 'INDIA') {
    displayCash = displayCurrency === 'USD' ? account.cash_inr / fxRate : account.cash_inr
  } else {
    const total_usd = account.cash_usd + (account.cash_inr / fxRate)
    displayCash = displayCurrency === 'INR' ? total_usd * fxRate : total_usd
  }

  const totalValue = displayCash + totalCurrentValue
  const unrealizedPnL = totalCurrentValue - totalInvestedValue

  let totalRealizedPnL = 0
  const allTradesClean = data.allTrades || []

  allTradesClean.forEach((t: any) => {
    const isIndian = t.ticker.endsWith('.NS')
    if (marketFilter === 'US' && isIndian) return
    if (marketFilter === 'INDIA' && !isIndian) return

    const action = String(t.action || '').toUpperCase()
    const isExit = ['SELL', 'STOP_LOSS', 'TAKE_PROFIT', 'MODEL_SELL', 'NEGATIVE_SIGNAL', 'PROFIT_LOCK', 'RISK_REDUCTION'].includes(action)
    if (!isExit) return

    let pnl = Number(t.realized_pnl)
    if (!Number.isFinite(pnl)) pnl = 0
    const tickerCurrency = isIndian ? 'INR' : 'USD'
    if (displayCurrency === 'INR' && tickerCurrency === 'USD') pnl *= fxRate
    else if (displayCurrency === 'USD' && tickerCurrency === 'INR') pnl /= fxRate
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
    <div className="min-h-screen bg-[#020202] text-gray-100 font-sans selection:bg-blue-500/30 overflow-x-hidden">
      {/* Background Cinematic Glows */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-blue-500/5 blur-[150px] rounded-full" />
      </div>

      <header className="border-b border-white/5 bg-[#080808]/50 backdrop-blur-md sticky top-0 z-[100]">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-white rounded-xl flex items-center justify-center shadow-2xl shadow-white/10 group overflow-hidden relative">
              <div className="absolute inset-0 bg-blue-500 scale-0 group-hover:scale-100 transition-transform duration-500 rounded-xl" />
              <Activity className="w-5 h-5 text-black relative z-10 group-hover:text-white transition-colors" />
            </div>
            <div>
              <h1 className="text-sm font-black text-white tracking-[0.2em] uppercase leading-none">Antigravity</h1>
              <span className="text-[9px] font-black text-gray-500 uppercase tracking-widest mt-1 inline-block">AI QUANT LABS • LIVE</span>
            </div>
          </div>

          <div className="hidden lg:flex items-center gap-8">
            <FXTracker fxRate={fxRate} fxHistory={data.fxHistory || []} />
          </div>

          <div className="flex items-center gap-3">
            <div className="flex bg-black p-1 rounded-xl border border-white/5">
              {['INR', 'USD'].map((c) => (
                <button
                  key={c}
                  onClick={() => setDisplayCurrency(c as any)}
                  className={`px-4 py-1.5 rounded-lg text-[10px] font-black tracking-widest transition-all duration-300 ${displayCurrency === c ? 'bg-white text-black' : 'text-gray-500 hover:text-white'}`}
                >
                  {c}
                </button>
              ))}
            </div>
            <button
              onClick={fetchData}
              className="w-10 h-10 bg-black border border-white/5 rounded-xl flex items-center justify-center hover:bg-white/5 transition-all group"
            >
              <RefreshCw className={`w-4 h-4 text-gray-400 group-hover:text-white ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={handleLogout}
              className="w-10 h-10 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-center justify-center hover:bg-rose-500/20 transition-all text-rose-500"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10 relative z-10 space-y-12">
        {/* Portfolio Summary - Now at top, full width */}
        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-1.5 h-6 bg-blue-500 rounded-full" />
              <h2 className="text-sm font-black text-white tracking-widest uppercase">Operational Summary</h2>
            </div>
            <div className="flex bg-white/5 p-1 rounded-xl border border-white/5">
              {['ALL', 'US', 'INDIA'].map((m) => (
                <button
                  key={m}
                  onClick={() => setMarketFilter(m as any)}
                  className={`px-4 py-1.5 rounded-lg text-[9px] font-black tracking-[0.2em] transition-all duration-300 ${marketFilter === m ? 'bg-white text-black shadow-lg shadow-white/10' : 'text-gray-500 hover:text-white'}`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

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
        </section>

        {/* Global Analytics Section */}
        <section className="space-y-10">
          <div className="flex items-center gap-4">
            <div className="w-1.5 h-12 bg-blue-500 rounded-full" />
            <div>
              <h3 className="text-3xl font-black text-white tracking-tighter">Market Performance</h3>
              <p className="text-gray-500 font-bold uppercase text-[10px] tracking-widest">Portfolio Analytics vs Benchmarks</p>
            </div>
          </div>
          <div className="bg-[#0c0c0c] border border-white/5 rounded-[3rem] p-10 shadow-2xl relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/[0.03] to-transparent pointer-events-none" />
            <PerformanceGraph
              data={performance}
              currency={displayCurrency}
              fxRate={fxRate}
              usBenchmarkData={data.usBenchmarkHistory || []}
              inBenchmarkData={data.inBenchmarkHistory || []}
            />
          </div>
        </section>

        {/* Main Intelligence Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
          <div className="lg:col-span-2 space-y-10">
            <div className="bg-[#0c0c0c] border border-white/5 rounded-[3rem] p-10 shadow-2xl overflow-hidden relative">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                  <ShieldCheck className="w-6 h-6 text-emerald-500" />
                  <div>
                    <h2 className="text-2xl font-black text-white tracking-tighter">Active Portfolio</h2>
                    <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">{filteredPortfolio.length} ASSETS DEPLOYED</span>
                  </div>
                </div>
              </div>
              <PortfolioTable
                portfolio={filteredPortfolio}
                livePrices={livePrices}
                totalInvestedValue={totalInvestedValue}
                currency={displayCurrency}
                fxRate={fxRate}
              />
            </div>

            {/* Trade Intelligence (Analytics) */}
            <div className="space-y-10 pt-10">
              <div className="flex items-center gap-4">
                <div className="w-1.5 h-12 bg-emerald-500 rounded-full" />
                <div>
                  <h3 className="text-3xl font-black text-white tracking-tighter leading-none">Trade Intelligence</h3>
                  <p className="text-gray-500 font-bold uppercase text-[10px] tracking-widest mt-1">Advanced Outcome Breakdown</p>
                </div>
              </div>
              <TradeAnalysis
                trades={data.allTrades || []}
                currency={displayCurrency}
                fxRate={fxRate}
              />
            </div>
          </div>

          <div className="space-y-10">
            {/* Capital Allocation */}
            <div className="bg-[#0c0c0c]/80 backdrop-blur-3xl border border-white/5 rounded-[2.5rem] p-8 shadow-2xl">
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-sm font-black text-white tracking-widest uppercase">Allocation</h2>
              </div>
              <MarketWeightChart
                portfolio={fullPortfolio}
                cash_usd={account.cash_usd}
                cash_inr={account.cash_inr}
                fxRate={fxRate}
              />
            </div>

            {/* Industry Breakdown */}
            <div className="bg-[#0c0c0c]/80 backdrop-blur-3xl border border-white/5 rounded-[2.5rem] p-8 shadow-2xl">
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-sm font-black text-white tracking-widest uppercase">Industry Exposure</h2>
              </div>
              <IndustryPieChart
                portfolio={filteredPortfolio}
                livePrices={livePrices}
                sectors={sectors || {}}
                currency={displayCurrency}
                fxRate={fxRate}
              />
            </div>

            {/* Prediction Signals */}
            <div className="bg-[#0c0c0c]/80 backdrop-blur-3xl border border-white/5 rounded-[2.5rem] p-8 shadow-2xl">
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-sm font-black text-white tracking-widest uppercase">ML Core Signals</h2>
              </div>
              <TopPredictionsChart scores={data.ml_scores || {}} />
            </div>

            {/* Recent Activity Feed */}
            <div className="bg-[#0c0c0c]/80 backdrop-blur-3xl border border-white/5 rounded-[2.5rem] p-8 shadow-2xl flex flex-col max-h-[600px]">
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-sm font-black text-white tracking-widest uppercase">Chronicle</h2>
              </div>
              <div className="overflow-y-auto flex-1 pr-2 custom-scrollbar">
                <TradeCards trades={filteredTrades} currency={displayCurrency} fxRate={fxRate} />
              </div>
            </div>
          </div>
        </div>
      </main>

      <style jsx global>{`
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;700;900&family=JetBrains+Mono:wght@500;800&display=swap');
        
        body {
          font-family: 'Outfit', sans-serif;
        }
        
        .font-mono {
          font-family: 'JetBrains+Mono', monospace;
        }
        
        .animate-spin-slow {
          animation: spin 3s linear infinite;
        }

        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.1);
        }
      `}</style>
    </div>
  )
}
