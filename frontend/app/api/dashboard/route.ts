import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import YahooFinance from 'yahoo-finance2'

export const dynamic = 'force-dynamic'
export const revalidate = 0

const yahooFinance = new (YahooFinance as any)()

export async function GET() {
  const supabase = await createClient()

  // Verify auth securely on the server
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  // Fetch Supabase data
  const [portfolioRes, tradesRes, perfRes, accountRes] = await Promise.all([
    supabase.from('portfolio').select('*'),
    supabase.from('trades').select('*').order('date', { ascending: false }).limit(20),
    supabase.from('performance').select('*').order('date', { ascending: true }),
    supabase.from('account').select('*').eq('id', 1).single()
  ])

  const portfolio = portfolioRes.data || []
  const trades = tradesRes.data || []
  const performance = perfRes.data || []
  const account = accountRes.data || { cash: 0 }

  // Fetch live prices via Yahoo Finance
  const tickers = portfolio.map((p: any) => p.ticker)
  const livePrices: Record<string, number> = {}
  const sectors: Record<string, string> = {}
  
  if (tickers.length > 0) {
    try {
      const quotes: any = await yahooFinance.quote(tickers)
      const quotesArray = Array.isArray(quotes) ? quotes : [quotes]
      quotesArray.forEach((q: any) => {
        if (q && q.symbol && q.regularMarketPrice) {
          livePrices[q.symbol] = q.regularMarketPrice
        }
      })
      
      // Async sector resolution 
      const profiles = await Promise.all(
        tickers.map((t: string) => yahooFinance.quoteSummary(t, { modules: ['assetProfile'] })
          .then((res: any) => ({ ticker: t, sector: res?.assetProfile?.sector || 'Unknown' }))
          .catch(() => ({ ticker: t, sector: 'Unknown' }))
        )
      )
      
      profiles.forEach(p => {
        sectors[p.ticker] = p.sector
      })
      
    } catch (e) {
      console.error('Yahoo Finance Error:', e)
      // gracefully fail and return without live prices, dashboard uses fallback
    }
  }

  return NextResponse.json({
    portfolio,
    trades,
    performance,
    account,
    livePrices,
    sectors
  })
}
