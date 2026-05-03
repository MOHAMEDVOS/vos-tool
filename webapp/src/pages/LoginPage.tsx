// test deploy trigger
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { GoogleLogin } from '@react-oauth/google'
import { AnimatePresence, motion } from 'framer-motion'
import { useGoogleLogin } from '@/hooks/useAuth'
import { useAuthStore } from '@/store/authStore'
import { useUiStore } from '@/store/uiStore'
import { LoginCanvasBackground } from '@/components/ui/LoginCanvasBackground'
import { createTimeline, animate, stagger } from 'animejs'

export function LoginPage() {
  const navigate  = useNavigate()
  const token     = useAuthStore((s) => s.token)
  const setLoginAnimating = useUiStore((s) => s.setLoginAnimating)
  const { mutate: loginWithGoogle, isPending, error } = useGoogleLogin()

  const cardRef        = useRef<HTMLDivElement>(null)
  const logoMarkRef    = useRef<HTMLDivElement>(null)
  const titleRef       = useRef<HTMLHeadingElement>(null)
  const subtitleRef    = useRef<HTMLHeadingElement>(null)
  const taglineRef     = useRef<HTMLParagraphElement>(null)
  const dividerRef     = useRef<HTMLDivElement>(null)
  const authSectionRef = useRef<HTMLDivElement>(null)
  const footerRef      = useRef<HTMLDivElement>(null)
  const glowRingRef    = useRef<HTMLDivElement>(null)
  const accentBarRef   = useRef<HTMLDivElement>(null)
  const dotsRef        = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (token) {
      setLoginAnimating(true)
      navigate('/', { replace: true })
    }
  }, [token, navigate, setLoginAnimating])

  /* ── Master entrance timeline ── */
  useEffect(() => {
    if (!cardRef.current) return

    const ease = 'cubicBezier(0.16, 1, 0.3, 1)'

    const tl = createTimeline({ defaults: { ease } })

    tl.add(cardRef.current, { translateY: [48, 0], opacity: [0, 1], duration: 900 })
      .add(accentBarRef.current!, { scaleX: [0, 1], opacity: [0, 1], duration: 700, ease: 'cubicBezier(0.34, 1.56, 0.64, 1)' }, '-=700')
      .add(logoMarkRef.current!, { scale: [0, 1], opacity: [0, 1], rotate: [-15, 0], duration: 600, ease: 'spring(1, 80, 12, 4)' }, '-=500')
      .add(titleRef.current!, { translateX: [-14, 0], opacity: [0, 1], duration: 500 }, '-=200')
      .add(subtitleRef.current!, { translateX: [-10, 0], opacity: [0, 1], duration: 420 }, '-=360')
      .add(taglineRef.current!, { translateY: [6, 0], opacity: [0, 1], duration: 400 }, '-=300')
      .add(dividerRef.current!, { scaleX: [0, 1], opacity: [0, 1], duration: 450 }, '-=200')
      .add(authSectionRef.current!, { translateY: [12, 0], opacity: [0, 1], duration: 500 }, '-=200')
      .add(footerRef.current!, { translateY: [8, 0], opacity: [0, 1], duration: 400 }, '-=200')

    /* glow ring pulse */
    if (glowRingRef.current) {
      animate(glowRingRef.current, {
        scale:    [0.88, 1.08],
        opacity:  [0.18, 0.42],
        duration: 2800,
        alternate: true,
        loop:     true,
        ease:     'cubicBezier(0.45, 0, 0.55, 1)',
      })
    }

    /* logo shimmer */
    if (logoMarkRef.current) {
      animate(logoMarkRef.current, {
        boxShadow: [
          { to: '0 0 8px 2px rgba(255,255,255,0.15)' },
          { to: '0 0 22px 6px rgba(255,255,255,0.38)' },
          { to: '0 0 8px 2px rgba(255,255,255,0.15)' },
        ],
        duration: 2600,
        loop:     true,
        ease:     'cubicBezier(0.45, 0, 0.55, 1)',
      })
    }
  }, [])

  /* ── Status dots stagger loop ── */
  useEffect(() => {
    if (!dotsRef.current) return
    const dots = Array.from(dotsRef.current.querySelectorAll<HTMLElement>('.status-dot'))
    if (!dots.length) return
    animate(dots, {
      opacity:  [0.18, 0.9, 0.18],
      scale:    [0.7, 1.2, 0.7],
      duration: 1800,
      loop:     true,
      delay:    stagger(320),
      ease:     'cubicBezier(0.45, 0, 0.55, 1)',
    })
  }, [])

  /* ── Magnetic card tilt ── */
  useEffect(() => {
    const card   = cardRef.current
    const parent = card?.parentElement
    if (!card || !parent) return

    const onMove = (e: MouseEvent) => {
      const rect  = card.getBoundingClientRect()
      const dx    = (e.clientX - rect.left - rect.width  / 2) / (rect.width  / 2)
      const dy    = (e.clientY - rect.top  - rect.height / 2) / (rect.height / 2)
      animate(card, { rotateX: -dy * 5, rotateY: dx * 5, duration: 300, ease: 'cubicBezier(0.16, 1, 0.3, 1)' })
    }

    const onLeave = () => {
      animate(card, { rotateX: 0, rotateY: 0, duration: 600, ease: 'spring(1, 80, 10, 0)' })
    }

    parent.addEventListener('mousemove',  onMove)
    parent.addEventListener('mouseleave', onLeave)
    return () => {
      parent.removeEventListener('mousemove',  onMove)
      parent.removeEventListener('mouseleave', onLeave)
    }
  }, [])

  return (
    <div
      className="relative flex flex-col min-h-screen items-center justify-center bg-[#000] selection:bg-white selection:text-black overflow-hidden"
      style={{ perspective: '1000px' }}
    >
      <LoginCanvasBackground />

      {/* Radial vignette */}
      <div
        className="fixed inset-0 z-[1] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse 70% 70% at 50% 50%, transparent 20%, rgba(0,0,0,0.75) 100%)' }}
      />

      {/* Ambient glow ring */}
      <div
        ref={glowRingRef}
        className="fixed z-[2] pointer-events-none"
        style={{
          width: 520, height: 520, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0) 70%)',
          top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
          opacity: 0,
        }}
      />

      <div className="flex-1 flex items-center justify-center w-full relative z-10">
        <div
          ref={cardRef}
          style={{ opacity: 0, transformStyle: 'preserve-3d', width: '100%', maxWidth: 420, padding: '0 24px' }}
        >
          <div
            className="relative bg-[rgba(0,0,0,0.84)] rounded-xl overflow-hidden"
            style={{
              boxShadow: '0px 0px 0px 1px rgba(255,255,255,0.10), 0 32px 96px rgba(0,0,0,0.75)',
              backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
              willChange: 'transform, opacity',
            }}
          >
            {/* Accent bar */}
            <div
              ref={accentBarRef}
              className="accent-bar"
              style={{ transformOrigin: 'left center', transform: 'scaleX(0)', opacity: 0 }}
            />

            <div className="px-10 py-12 md:px-12 md:py-14">

              {/* Logo + header */}
              <div className="mb-14 text-center md:text-left">
                <div className="flex items-center justify-center md:justify-start gap-2 mb-10">
                  <div
                    ref={logoMarkRef}
                    className="w-7 h-7 bg-white rounded-[3px] flex items-center justify-center"
                    style={{ transform: 'scale(0)', opacity: 0, willChange: 'transform, box-shadow' }}
                  >
                    <span className="text-black text-[11px] font-black tracking-tight select-none">V</span>
                  </div>
                </div>

                <h1
                  ref={titleRef}
                  className="text-[48px] font-semibold tracking-[-2.88px] leading-[1.1] text-white mb-2"
                  style={{ fontFeatureSettings: "'liga' 1, 'ss01' 1", opacity: 0 }}
                >
                  VOS
                </h1>

                <h2
                  ref={subtitleRef}
                  className="text-[18px] font-medium tracking-[-0.32px] text-white mb-4"
                  style={{ opacity: 0 }}
                >
                  Voice Observation System
                </h2>

                <p
                  ref={taglineRef}
                  className="text-[14px] leading-relaxed text-[#666] flex items-center gap-[2px]"
                  style={{ opacity: 0 }}
                >
                  AI That Listens, Learns, and Elevates Quality
                  <span className="inline-block w-[1.5px] h-[14px] bg-[#555] ml-1 cursor-blink" />
                </p>
              </div>

              {/* Auth section */}
              <div ref={authSectionRef} className="space-y-8" style={{ opacity: 0 }}>
                <div ref={dividerRef} className="relative py-2" style={{ opacity: 0, transformOrigin: 'center' }}>
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
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
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
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                        className="w-full vercel-btn-wrapper-pitch"
                      >
                        <GoogleLogin
                          onSuccess={(cr) => { if (cr.credential) loginWithGoogle(cr.credential) }}
                          onError={() => console.log('Login Failed')}
                          theme="filled_black" shape="square" width="100%" text="signin_with"
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                    className="p-3 rounded-md border border-red-500/20 text-red-500 text-[12px] text-center font-medium"
                  >
                    {error.message || 'Authentication failed'}
                  </motion.div>
                )}
              </div>

              {/* Footer */}
              <div
                ref={footerRef}
                className="mt-14 pt-8 border-t border-white/5 flex items-center justify-between"
                style={{ opacity: 0 }}
              >
                <div className="flex items-center gap-3">
                  <div ref={dotsRef} className="flex gap-[5px] items-center">
                    {[0, 1, 2].map((i) => (
                      <div
                        key={i}
                        className="status-dot w-[6px] h-[6px] rounded-full bg-[#3a3a3a]"
                        style={{ opacity: 0.18, willChange: 'transform, opacity' }}
                      />
                    ))}
                  </div>
                  <span className="font-mono text-[9px] font-medium text-[#444] uppercase tracking-widest">
                    Systems Ready
                  </span>
                </div>
                <a
                  href="https://t.me/Mohmed_abdo"
                  target="_blank" rel="noopener noreferrer"
                  className="text-[10px] font-medium text-[#444] hover:text-white transition-colors uppercase tracking-widest"
                >
                  Mohamed Abdo
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; -webkit-font-smoothing: antialiased; background-color: #000; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        @keyframes cursor-blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
        .cursor-blink { animation: cursor-blink 1.1s step-end infinite; }
        .vercel-btn-wrapper-pitch iframe { border-radius: 4px !important; border: none !important; box-shadow: 0px 0px 0px 1px rgba(255,255,255,0.10) !important; }
        .vercel-btn-wrapper-pitch:hover iframe { background-color: #080808 !important; }
        *:focus-visible { outline: 1px solid white !important; outline-offset: 4px !important; }
      `}} />
    </div>
  )
}
