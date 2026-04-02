'use client'

import { createClient } from '@/lib/supabase/client'
import { useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'

function LoginForm() {
  const supabase = createClient()
  const router = useRouter()
  
  const [loading, setLoading] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState('')
  
  const searchParams = useSearchParams()
  const errorMsg = searchParams.get('error')

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError('')
    setLoading(true)

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })

    if (error) {
      setAuthError(error.message)
      setLoading(false)
    } else {
      router.push('/dashboard')
    }
  }

  const handleGitHubLogin = async () => {
    setLoading(true)
    await supabase.auth.signInWithOAuth({
      provider: 'github',
      options: {
        redirectTo: `${window.location.origin}/api/auth/callback`,
      },
    })
  }

  return (
    <div className="w-full max-w-md p-8 rounded-2xl bg-[#171717] shadow-2xl border border-gray-800 text-center relative overflow-hidden">
      {/* Subtle background glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-48 h-48 bg-blue-500/20 blur-[80px] rounded-full pointer-events-none" />
      
      <h1 className="text-3xl font-bold text-white mb-2 relative z-10">Trading Dashboard</h1>
      <p className="text-gray-400 mb-6 relative z-10">Sign in to access your portfolio</p>

      {errorMsg === 'unauthorized' && (
        <div className="mb-6 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-500 text-sm relative z-10">
          Access Denied. You are not on the permitted users list.
        </div>
      )}

      {authError && (
        <div className="mb-6 p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-500 text-sm relative z-10">
          {authError}
        </div>
      )}

      {/* Email / Password Form */}
      <form onSubmit={handleEmailLogin} className="flex flex-col gap-4 relative z-10 mb-6 text-left">
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-1">Email</label>
          <input 
            type="email" 
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-3 rounded-xl bg-[#262626] border border-gray-700 text-white focus:outline-none focus:border-blue-500 transition-colors"
            placeholder="you@example.com"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-1">Password</label>
          <input 
            type="password" 
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-4 py-3 rounded-xl bg-[#262626] border border-gray-700 text-white focus:outline-none focus:border-blue-500 transition-colors"
            placeholder="••••••••"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full mt-2 bg-blue-600 text-white py-3 px-4 rounded-xl font-bold hover:bg-blue-500 transition-all disabled:opacity-50 hover:scale-[1.02] shadow-[0_0_20px_rgba(59,130,246,0.15)]"
        >
          {loading ? 'Authenticating...' : 'Sign In'}
        </button>
      </form>

      <div className="relative flex items-center py-2 mb-6 z-10">
        <div className="flex-grow border-t border-gray-800"></div>
        <span className="flex-shrink-0 mx-4 text-gray-500 text-sm">Or continue with</span>
        <div className="flex-grow border-t border-gray-800"></div>
      </div>
      
      {/* GitHub Fallback */}
      <button
        type="button"
        onClick={handleGitHubLogin}
        disabled={loading}
        className="w-full relative z-10 flex items-center justify-center gap-3 bg-white text-black py-3 px-4 rounded-xl font-medium hover:bg-gray-200 transition-all disabled:opacity-50 shadow-[0_0_20px_rgba(255,255,255,0.1)]"
      >
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.6.113.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
        </svg>
        GitHub
      </button>
    </div>
  )
}

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0a0a0a]">
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </div>
  )
}
