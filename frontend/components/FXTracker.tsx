'use client'
import { LineChart, Line, ResponsiveContainer, Tooltip, YAxis } from 'recharts'
import { ArrowUpRight, ArrowDownRight, Globe } from 'lucide-react'

export default function FXTracker({ 
  fxRate, 
  fxHistory 
}: { 
  fxRate: number; 
  fxHistory: any[];
}) {
  if (!fxHistory || fxHistory.length < 2) return null;

  const first = fxHistory[0].value;
  const last = fxRate;
  const change = last - first;
  const changePct = (change / first) * 100;
  const isUp = change >= 0;

  return (
    <div className="flex items-center gap-6 bg-[#171717] border border-gray-800 rounded-2xl px-5 py-3 shadow-lg hover:bg-[#1a1a1a] transition-all group cursor-pointer">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-xl ${isUp ? 'bg-emerald-500/10 text-emerald-500' : 'bg-rose-500/10 text-rose-500'} group-hover:scale-110 transition-transform`}>
          <Globe className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest">USD / INR</span>
            {isUp ? <ArrowUpRight className="w-3 h-3 text-emerald-500" /> : <ArrowDownRight className="w-3 h-3 text-rose-500" />}
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-bold text-white tracking-tighter">₹{fxRate.toFixed(2)}</span>
            <span className={`text-[11px] font-bold ${isUp ? 'text-emerald-500' : 'text-rose-500'}`}>
              {isUp ? '+' : ''}{changePct.toFixed(2)}%
            </span>
          </div>
        </div>
      </div>

      <div className="w-32 h-10 hidden sm:block">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={fxHistory}>
            <YAxis hide domain={['auto', 'auto']} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#111', borderColor: '#333', fontSize: '10px', borderRadius: '8px' }}
              labelStyle={{ display: 'none' }}
              formatter={(val: any) => [`₹${val.toFixed(2)}`, 'FX']}
            />
            <Line 
              type="monotone" 
              dataKey="value" 
              stroke={isUp ? '#10b981' : '#f43f5e'} 
              strokeWidth={2} 
              dot={false}
              animationDuration={2000}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
