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
  const [portfolioRes, tradesRes, allTradesRes, perfRes, accountRes] = await Promise.all([
    supabase.from('portfolio').select('*'),
    supabase.from('trades').select('*').order('date', { ascending: false }).limit(20),
    supabase.from('trades').select('*').order('date', { ascending: false }),
    supabase.from('performance').select('*').order('date', { ascending: true }),
    supabase.from('account').select('*').eq('id', 1).single()
  ])

  const portfolio = portfolioRes.data || []
  const trades = tradesRes.data || []
  const allTrades = allTradesRes.data || []
  const performance = perfRes.data || []
  const account = accountRes.data || { cash_usd: 0, cash_inr: 0 }

  // Fetch live prices and FX rate via Yahoo Finance
  const tickers = portfolio.map((p: any) => p.ticker)
  const livePrices: Record<string, number> = {}
  const sectors: Record<string, string> = {}
  let fxRate = 83.5 // Fallback
  let fxHistory: any[] = []
  let benchmarkData: any[] = []
  
  try {
    const fxQuote: any = await yahooFinance.quote('USDINR=X')
    if (fxQuote && fxQuote.regularMarketPrice) {
      fxRate = fxQuote.regularMarketPrice
    }

    // Fetch FX History for trend graph (Last 7 days)
    const sevenDaysAgo = new Date()
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
    const fxChart = await yahooFinance.chart('USDINR=X', {
      period1: sevenDaysAgo,
      interval: '1h'
    })
    if (fxChart && fxChart.quotes) {
      fxHistory = fxChart.quotes.map((q: any) => ({
        date: q.date,
        value: q.close
      })).filter((q: any) => q.value != null)
    }

    // Fetch US Benchmark (^GSPC - S&P 500)
    const yearAgo = new Date()
    yearAgo.setFullYear(yearAgo.getFullYear() - 1)
    
    const [spResults, niftyResults] = await Promise.all([
      yahooFinance.chart('^GSPC', { period1: yearAgo, interval: '1d' }),
      yahooFinance.chart('^NSEI', { period1: yearAgo, interval: '1d' })
    ])

    const usBenchmarkHistory = (spResults.quotes || [])
      .map((q: any) => ({ date: q.date.toISOString().split('T')[0], value: q.close }))
      .filter((q: any) => q.value != null)
      
    const inBenchmarkHistory = (niftyResults.quotes || [])
      .map((q: any) => ({ date: q.date.toISOString().split('T')[0], value: q.close }))
      .filter((q: any) => q.value != null)

    // Enrich allTrades with Buy/Sell matching logic for UI
    const enrichedTrades: any[] = []
    const lastBuys: Record<string, any> = {}
    
    // Process trades in CHRONOLOGICAL order to match buys with sells
    const chronTrades = [...allTrades].reverse()
    
    chronTrades.forEach((t: any) => {
      const ticker = t.ticker
      const action = String(t.action).toUpperCase()
      const isExit = ['SELL', 'STOP_LOSS', 'TAKE_PROFIT', 'MODEL_SELL'].includes(action)
      
      if (action === 'BUY') {
        lastBuys[ticker] = t
        enrichedTrades.push(t)
      } else if (isExit) {
        const tradeData = { ...t }
        
        // Priority: 1. Stored data in DB (new trades), 2. Matched chronological data (old trades)
        let buy = lastBuys[ticker]
        let entryDateStr = tradeData.entry_date || (buy ? buy.date : null)
        let buyPriceValue = tradeData.entry_price || (buy ? buy.price : null)

        if (entryDateStr) {
          tradeData.buy_price = buyPriceValue
          tradeData.buy_date = entryDateStr
          
          const entryDate = String(entryDateStr).split(' ')[0]
          const exitDate = t.date.split(' ')[0]
          
          // Calculate holding days
          const d1 = new Date(entryDate)
          const d2 = new Date(exitDate)
          tradeData.holding_days = Math.max(0, Math.floor((d2.getTime() - d1.getTime()) / (1000 * 3600 * 24)))
          
          // Benchmark Performance
          const history = ticker.endsWith('.NS') ? inBenchmarkHistory : usBenchmarkHistory
          
          // Find the nearest benchmark price on or BEFORE the trade dates
          const startBench = [...history].reverse().find((h: any) => h.date <= entryDate)
          const endBench = [...history].reverse().find((h: any) => h.date <= exitDate)
          
          if (startBench && endBench) {
            const marketReturn = (endBench.value - startBench.value) / startBench.value
            tradeData.market_return = marketReturn * 100
            
            // Recalculate alpha based on the matched holding period
            tradeData.alpha = (t.pnl_pct || 0) - tradeData.market_return
          }
          
          // Include remaining_shares for the frontend (from DB or current run)
          tradeData.remaining_shares = tradeData.remaining_shares || 0
          
          if (!tradeData.entry_date) delete lastBuys[ticker]
        }
        enrichedTrades.push(tradeData)
      } else {
        enrichedTrades.push(t)
      }
    })

    // Back to descending for the API return
    const processedTrades = enrichedTrades.reverse()

    if (tickers.length > 0) {
      const quotes: any = await yahooFinance.quote(tickers)
      const quotesArray = Array.isArray(quotes) ? quotes : [quotes]
      quotesArray.forEach((q: any) => {
        if (q && q.symbol && q.regularMarketPrice) {
          livePrices[q.symbol] = q.regularMarketPrice
        }
      })
      
      const profiles = await Promise.all(
        tickers.map((t: string) => yahooFinance.quoteSummary(t, { modules: ['assetProfile'] })
          .then((res: any) => ({ ticker: t, sector: res?.assetProfile?.sector || 'Unknown' }))
          .catch(() => ({ ticker: t, sector: 'Unknown' }))
        )
      )
      
      profiles.forEach(p => {
        sectors[p.ticker] = p.sector
      })
    }

    return NextResponse.json({
      portfolio,
      trades: processedTrades.slice(0, 20),
      allTrades: processedTrades,
      performance,
      account,
      livePrices,
      sectors,
      fxRate,
      fxHistory,
      usBenchmarkHistory,
      inBenchmarkHistory
    })
  } catch (e) {
    console.error('Yahoo Finance Error:', e)
    return NextResponse.json({
      portfolio,
      trades,
      allTrades,
      performance,
      account,
      livePrices,
      sectors,
      fxRate
    })
  }
}
