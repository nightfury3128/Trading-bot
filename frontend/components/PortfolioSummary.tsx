'use client'
import { TrendingDown, TrendingUp, DollarSign, Briefcase } from 'lucide-react'

export default function PortfolioSummary({ 
  totalValue, 
  cash, 
  positionsCount, 
  dailyChange,
  investedAmount,
  unrealizedPnL
}: { 
  totalValue: number; 
  cash: number; 
  positionsCount: number; 
  dailyChange: number;
  investedAmount: number;
  unrealizedPnL: number;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 w-full">
      <Card title="Total Value" value={`$${totalValue.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`} icon={<DollarSign className="w-5 h-5 text-blue-500" />} />
      <Card title="Cash Balance" value={`$${cash.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`} icon={<DollarSign className="w-5 h-5 text-emerald-500" />} />
      <Card title="Invested" value={`$${investedAmount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`} icon={<Briefcase className="w-5 h-5 text-indigo-500" />} />
      <Card 
        title="Unrealized P/L" 
        value={`${unrealizedPnL >= 0 ? '+' : ''}$${unrealizedPnL.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`} 
        icon={unrealizedPnL >= 0 ? <TrendingUp className="w-5 h-5 text-emerald-500" /> : <TrendingDown className="w-5 h-5 text-rose-500" />} 
        valueColor={unrealizedPnL >= 0 ? 'text-emerald-500' : 'text-rose-500'}
      />
      <Card title="Positions" value={positionsCount.toString()} icon={<Briefcase className="w-5 h-5 text-purple-500" />} />
      <Card 
        title="Daily Change" 
        value={`${dailyChange > 0 ? '+' : ''}$${dailyChange.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`} 
        icon={dailyChange >= 0 ? <TrendingUp className="w-5 h-5 text-emerald-500" /> : <TrendingDown className="w-5 h-5 text-rose-500" />} 
        valueColor={dailyChange > 0 ? 'text-emerald-500' : dailyChange < 0 ? 'text-rose-500' : 'text-white'}
      />
    </div>
  )
}

function Card({ title, value, icon, valueColor = "text-white" }: { title: string, value: string, icon: React.ReactNode, valueColor?: string }) {
  return (
    <div className="bg-[#171717]/80 backdrop-blur-md border border-gray-800/60 p-6 rounded-2xl shadow-lg flex items-center justify-between hover:bg-[#1a1a1a] transition-all hover:-translate-y-0.5 hover:shadow-xl group">
      <div>
        <p className="text-gray-400 text-sm font-medium mb-1 group-hover:text-gray-300 transition-colors">{title}</p>
        <h3 className={`text-2xl font-bold tracking-tight ${valueColor}`}>{value}</h3>
      </div>
      <div className="p-3 bg-[#262626]/80 rounded-xl shadow-inner border border-gray-700/50 group-hover:scale-110 transition-transform">
        {icon}
      </div>
    </div>
  )
}
