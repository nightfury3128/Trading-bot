'use client'
import { TrendingDown, TrendingUp, DollarSign, Briefcase } from 'lucide-react'

export default function PortfolioSummary({ 
  totalValue, 
  cash, 
  positionsCount, 
  dailyChange,
  investedAmount,
  unrealizedPnL,
  currency = 'USD'
}: { 
  totalValue: number; 
  cash: number; 
  positionsCount: number; 
  dailyChange: number;
  investedAmount: number;
  unrealizedPnL: number;
  currency?: 'USD' | 'INR';
}) {
  const symbol = currency === 'INR' ? '₹' : '$'
  const locale = currency === 'INR' ? 'en-IN' : 'en-US'
  const format = (v: number) => {
    return `${v < 0 ? '-' : ''}${symbol}${Math.abs(v).toLocaleString(locale, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 w-full">
      <Card title="Total Value" value={format(totalValue)} icon={<DollarSign className="w-5 h-5 text-blue-500" />} />
      <Card title="Cash Balance" value={format(cash)} icon={<DollarSign className="w-5 h-5 text-emerald-500" />} />
      <Card title="Invested" value={format(investedAmount)} icon={<Briefcase className="w-5 h-5 text-indigo-500" />} />
      <Card 
        title="Unrealized P/L" 
        value={format(unrealizedPnL)} 
        icon={unrealizedPnL >= 0 ? <TrendingUp className="w-5 h-5 text-emerald-500" /> : <TrendingDown className="w-5 h-5 text-rose-500" />} 
        valueColor={unrealizedPnL >= 0 ? 'text-emerald-500' : 'text-rose-500'}
      />
      <Card title="Positions" value={positionsCount.toString()} icon={<Briefcase className="w-5 h-5 text-purple-500" />} />
      <Card 
        title="Daily Change" 
        value={format(dailyChange)} 
        icon={dailyChange >= 0 ? <TrendingUp className="w-5 h-5 text-emerald-500" /> : <TrendingDown className="w-5 h-5 text-rose-500" />} 
        valueColor={dailyChange > 0 ? 'text-emerald-500' : dailyChange < 0 ? 'text-rose-500' : 'text-white'}
      />
    </div>
  )
}

function Card({ title, value, icon, valueColor = "text-white" }: { title: string, value: string, icon: React.ReactNode, valueColor?: string }) {
  return (
    <div className="bg-[#171717]/80 backdrop-blur-md border border-gray-800/60 p-6 rounded-2xl shadow-lg flex items-center justify-between hover:bg-[#1a1a1a] transition-all hover:scale-105 hover:shadow-2xl hover:border-blue-500/30 group cursor-default">
      <div>
        <p className="text-gray-400 text-xs font-black uppercase tracking-widest mb-2 group-hover:text-blue-400 transition-colors">{title}</p>
        <h3 className={`text-2xl font-bold tracking-tighter ${valueColor}`}>{value}</h3>
      </div>
      <div className="p-3 bg-gray-900/50 rounded-xl shadow-inner border border-gray-800 group-hover:bg-blue-500/10 group-hover:border-blue-500/20 transition-all">
        {icon}
      </div>
    </div>
  )
}
