'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { useRouter } from 'next/navigation'
import PortfolioSummary from '@/components/PortfolioSummary'
import TradeCards from '@/components/TradeCards'
import PortfolioTable from '@/components/PortfolioTable'
import PerformanceGraph from '@/components/PerformanceGraph'
import IndustryPieChart from '@/components/IndustryPieChart'
import { LogOut, RefreshCw } from 'lucide-react'

export default function Dashboard() {
  const supabase = createClient()
  const router = useRouter()
  
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [data, setData] = useState<any>(null)
  
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
    // Auto refresh every 60 seconds
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

  const { portfolio, trades, performance, account, livePrices, sectors } = data
  let investedValue = 0
  let currentPortfolioValue = 0
  
  portfolio.forEach((p: any) => {
    const currentPrice = livePrices[p.ticker] || p.buy_price
    investedValue += Number(p.shares) * p.buy_price
    currentPortfolioValue += Number(p.shares) * currentPrice
  })
  
  const totalValue = account.cash + currentPortfolioValue
  const unrealizedPnL = currentPortfolioValue - investedValue

  let dailyChange = 0
  if (performance && performance.length >= 2) {
    const last = performance[performance.length - 1].total_value
    const prev = performance[performance.length - 2].total_value
    dailyChange = last - prev
  } else if (performance && performance.length === 1) {
    dailyChange = totalValue - performance[0].total_value
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
            <h1 className="text-3xl font-bold text-white tracking-tight">Trading Dashboard</h1>
          </div>
          <p className="text-gray-400 ml-11">Live Portfolio Overview &amp; ML Models</p>
        </div>
        <div className="flex items-center gap-3 w-full md:w-auto">
          <button 
            onClick={fetchData} 
            disabled={refreshing}
            className="flex-1 md:flex-none py-2 px-4 bg-[#171717] border border-gray-800 rounded-xl hover:bg-[#202020] transition-colors flex items-center justify-center disabled:opacity-50 group shadow-sm text-sm font-medium"
            title="Refresh Data"
          >
            <RefreshCw className={`w-4 h-4 text-gray-400 group-hover:text-white mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Syncing...' : 'Sync Data'}
          </button>
          <button 
            onClick={handleLogout} 
            className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-rose-500/10 text-rose-500 border border-rose-500/20 hover:bg-rose-500/20 px-4 py-2 rounded-xl transition-all font-medium text-sm"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto space-y-8">
        <PortfolioSummary 
          totalValue={totalValue} 
          cash={account.cash} 
          positionsCount={portfolio.length} 
          dailyChange={dailyChange} 
          investedAmount={investedValue}
          unrealizedPnL={unrealizedPnL}
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
            {/* Performance Line Chart */}
            <div className="bg-[#171717] border border-gray-800 rounded-3xl p-6 md:p-8 shadow-sm">
              <PerformanceGraph data={performance} />
            </div>

            {/* Positions Table */}
            <div className="bg-[#171717] border border-gray-800 rounded-3xl p-6 md:p-8 shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white tracking-tight">Active Positions</h2>
                <span className="text-sm text-gray-400">{portfolio.length} Assets</span>
              </div>
              <PortfolioTable portfolio={portfolio} livePrices={livePrices} totalInvestedValue={investedValue} />
            </div>
          </div>
          
          <div className="space-y-8">
            {/* Sector Pie Chart */}
            <div className="bg-[#171717] border border-gray-800 rounded-3xl p-6 md:p-8 shadow-sm">
              <h2 className="text-xl font-bold text-white tracking-tight mb-8">Sector Allocation</h2>
              <IndustryPieChart portfolio={portfolio} livePrices={livePrices} sectors={sectors || {}} />
            </div>

            {/* Recent Trades List */}
            <div className="bg-[#171717] border border-gray-800 rounded-3xl p-6 md:p-8 shadow-sm flex flex-col max-h-[600px]">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white tracking-tight">Recent Trades</h2>
              </div>
              <div className="overflow-y-auto flex-1 pr-2 custom-scrollbar">
                <TradeCards trades={trades} />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
