import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { GoogleLogin } from '@react-oauth/google'
import { motion, AnimatePresence } from 'framer-motion'
import { useGoogleLogin } from '@/hooks/useAuth'
import { useAuthStore } from '@/store/authStore'
import { LoginCanvasBackground } from '@/components/ui/LoginCanvasBackground'
import { Footer } from '@/components/layout/Footer'

/**
 * LoginPage - Vercel/Geist Pitch Black
 *
 * Theme: Achromatic Pitch Black (#000), total darkness.
 * Typography: Negative letter-spacing, structural ligatures.
 * Borders: 1px sharp shadow-as-border only.
 * Background: Neural graph canvas — nodes + signal pulses.
 */

export function LoginPage() {
  const navigate = useNavigate()
  const token = useAuthStore((s) => s.token)
  const { mutate: loginWithGoogle, isPending, error } = useGoogleLogin()

  useEffect(() => {
    if (token) navigate('/', { replace: true })
  }, [token, navigate])

  return (
    <div className="relative flex flex-col min-h-screen items-center justify-center bg-[#000] selection:bg-white selection:text-black overflow-hidden">

      {/* Neural graph — fills the whole screen behind the card */}
      <LoginCanvasBackground />

      {/* Very subtle radial vignette so card stays legible */}
      <div
        className="fixed inset-0 z-[1] pointer-events-none"
        style={{
          background:
            'radial-gradient(ellipse 70% 70% at 50% 50%, transparent 20%, rgba(0,0,0,0.72) 100%)',
        }}
      />

      <div className="flex-1 flex items-center justify-center w-full relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="w-full max-w-[420px] px-6"
        >
          {/* Pitch Black Card */}
          <div
            className="relative bg-[rgba(0,0,0,0.82)] rounded-xl overflow-hidden"
            style={{
              boxShadow:
                '0px 0px 0px 1px rgba(255,255,255,0.10), 0 24px 80px rgba(0,0,0,0.7)',
              backdropFilter: 'blur(18px)',
              WebkitBackdropFilter: 'blur(18px)',
            }}
          >
            {/* Top shimmer bar */}
            <div className="accent-bar" />

            <div className="px-10 py-12 md:px-12 md:py-14">

              {/* Logo mark + header */}
              <div className="mb-14 text-center md:text-left">
                <div className="flex items-center justify-center md:justify-start gap-2 mb-10">
                  {/* Logo mark — pulses in on load */}
                  <motion.div
                    initial={{ scale: 0.6, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ duration: 0.45, ease: [0.34, 1.56, 0.64, 1] }}
                    className="w-7 h-7 bg-white rounded-[3px] flex items-center justify-center"
                    style={{ boxShadow: '0 0 14px rgba(255,255,255,0.25)' }}
                  >
                    <span className="text-black text-[11px] font-black tracking-tight select-none">V</span>
                  </motion.div>
                </div>

                <motion.h1
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.1, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                  className="text-[48px] font-semibold tracking-[-2.88px] leading-[1.1] text-white mb-2"
                  style={{ fontFeatureSettings: "'liga' 1, 'ss01' 1" }}
                >
                  VOS
                </motion.h1>

                <motion.h2
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.16, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                  className="text-[18px] font-medium tracking-[-0.32px] text-white mb-4"
                >
                  Voice Observation System
                </motion.h2>

                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.28, duration: 0.5 }}
                  className="text-[14px] leading-relaxed text-[#666] flex items-center gap-[2px]"
                >
                  AI That Listens, Learns, and Elevates Quality
                  {/* Blinking cursor */}
                  <span className="inline-block w-[1.5px] h-[14px] bg-[#555] ml-1 cursor-blink" />
                </motion.p>
              </div>

              {/* Authentication section */}
              <div className="space-y-8">
                <div className="relative py-2">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-white/5" />
                  </div>
                  <div className="relative flex justify-center">
                    <span className="bg-transparent px-3 text-[10px] font-medium text-[#444] uppercase tracking-[0.2em]">
                      Authentication
                    </span>
                  </div>
                </div>

                <div className="flex justify-center">
                  <AnimatePresence mode="wait">
                    {isPending ? (
                      <motion.div
                        key="loading"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="flex items-center gap-3 py-3"
                      >
                        <div className="w-4 h-4 rounded-full border-[1.5px] border-white/10 border-t-white animate-spin" />
                        <span className="font-mono text-[11px] font-medium text-[#444] uppercase tracking-widest">
                          Authorizing
                        </span>
                      </motion.div>
                    ) : (
                      <motion.div
                        key="auth"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="w-full vercel-btn-wrapper-pitch"
                      >
                        <GoogleLogin
                          onSuccess={(cr) => { if (cr.credential) loginWithGoogle(cr.credential) }}
                          onError={() => console.log('Login Failed')}
                          theme="filled_black"
                          shape="square"
                          width="100%"
                          text="signin_with"
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {error && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="p-3 rounded-md border border-red-500/20 text-red-500 text-[12px] text-center font-medium"
                  >
                    {error.message || 'Authentication failed'}
                  </motion.div>
                )}
              </div>

              {/* Footer — animated status dots */}
              <div className="mt-14 pt-8 border-t border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex gap-[5px] items-center">
                    {[0, 1, 2].map((i) => (
                      <motion.div
                        key={i}
                        className="w-[6px] h-[6px] rounded-full bg-[#2a2a2a]"
                        animate={{ backgroundColor: ['#2a2a2a', '#4a4a4a', '#2a2a2a'] }}
                        transition={{
                          duration: 1.8,
                          repeat: Infinity,
                          delay: i * 0.35,
                          ease: 'easeInOut',
                        }}
                        style={{ boxShadow: '0 0 0 2px rgba(0,0,0,0.8)' }}
                      />
                    ))}
                  </div>
                  <span className="font-mono text-[9px] font-medium text-[#444] uppercase tracking-widest">
                    Systems Ready
                  </span>
                </div>
                <a href="#" className="text-[10px] font-medium text-[#444] hover:text-white transition-colors uppercase tracking-widest">
                  Support
                </a>
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      <div className="w-full max-w-7xl px-8 pb-4 relative z-10">
        <Footer />
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;900&family=JetBrains+Mono:wght@400;500&display=swap');

        body {
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          -webkit-font-smoothing: antialiased;
          background-color: #000;
        }

        .font-mono { font-family: 'JetBrains Mono', monospace; }

        /* Blinking cursor after tagline */
        @keyframes cursor-blink {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0; }
        }
        .cursor-blink { animation: cursor-blink 1.1s step-end infinite; }

        /* Google button styling */
        .vercel-btn-wrapper-pitch iframe {
          border-radius: 4px !important;
          border: none !important;
          box-shadow: 0px 0px 0px 1px rgba(255,255,255,0.10) !important;
          transition: background 0.1s ease !important;
        }
        .vercel-btn-wrapper-pitch:hover iframe {
          background-color: #080808 !important;
        }

        /* Focus rings */
        *:focus-visible {
          outline: 1px solid white !important;
          outline-offset: 4px !important;
        }
      `}} />
    </div>
  )
}
