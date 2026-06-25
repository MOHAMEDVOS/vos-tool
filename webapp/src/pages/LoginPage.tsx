// test deploy trigger
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useGoogleLogin as useGoogleAuth } from '@react-oauth/google'
import { AnimatePresence, motion } from 'framer-motion'
import { useGoogleLogin } from '@/hooks/useAuth'
import { useAuthStore } from '@/store/authStore'
import { createTimeline, animate, stagger } from 'animejs'

const LOGIN_BACKGROUND_VIDEO_URL = 'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260418_115655_b4d9cd77-feed-43cd-a198-af78ebdf1f7a.mp4'

/**
 * A component that handles a seamless loop for videos that don't perfectly loop
 * by cross-fading between two video elements.
 */
function SeamlessVideo({ src }: { src: string }) {
  const [activeIdx, setActiveIdx] = useState(0)
  const [soundOn, setSoundOn] = useState(false)
  const v1Ref = useRef<HTMLVideoElement>(null)
  const v2Ref = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const v1 = v1Ref.current
    const v2 = v2Ref.current
    if (!v1 || !v2) return

    // Initial play
    if (activeIdx === 0) {
      v1.play().catch(() => {})
    } else {
      v2.play().catch(() => {})
    }

    const interval = setInterval(() => {
      const active = activeIdx === 0 ? v1 : v2
      const next = activeIdx === 0 ? v2 : v1

      // Trigger 1.5 seconds before end for a more generous overlap
      if (active.duration && active.currentTime > active.duration - 1.5) {
        if (next.paused) {
          next.currentTime = 0
          next.play().then(() => {
            setActiveIdx(activeIdx === 0 ? 1 : 0)
          }).catch(() => {})
        }
      }
    }, 50)

    return () => clearInterval(interval)
  }, [activeIdx])

  /* Browsers block unmuted autoplay until the user interacts with the page.
     Start muted so the background always plays, then enable sound on the
     user's first interaction (they have to click to sign in anyway). Audio
     stops automatically on login when this component unmounts. */
  useEffect(() => {
    const enable = () => {
      if (v1Ref.current) v1Ref.current.volume = 0.7
      if (v2Ref.current) v2Ref.current.volume = 0.7
      setSoundOn(true)
    }
    window.addEventListener('pointerdown', enable, { once: true })
    window.addEventListener('keydown',     enable, { once: true })
    window.addEventListener('touchstart',  enable, { once: true })
    return () => {
      window.removeEventListener('pointerdown', enable)
      window.removeEventListener('keydown',     enable)
      window.removeEventListener('touchstart',  enable)
    }
  }, [])

  const videoStyle = (isActive: boolean): React.CSSProperties => ({
    position: 'absolute',
    inset: 0,
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    opacity: isActive ? 1 : 0,
    transition: 'opacity 2000ms cubic-bezier(0.45, 0, 0.55, 1)', // Softer ease-in-out
    pointerEvents: 'none',
    transform: 'scale(1.02)', // Tiny scale to hide potential edge flicker
  })

  return (
    <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
      <video
        ref={v1Ref}
        src={src}
        style={videoStyle(activeIdx === 0)}
        muted={!soundOn || activeIdx !== 0}
        playsInline
        preload="auto"
      />
      <video
        ref={v2Ref}
        src={src}
        style={videoStyle(activeIdx === 1)}
        muted={!soundOn || activeIdx !== 1}
        playsInline
        preload="auto"
      />
    </div>
  )
}

export function LoginPage() {
  const navigate  = useNavigate()
  const token     = useAuthStore((s) => s.token)

  const { mutate: loginWithGoogle, isPending, error } = useGoogleLogin()
  
  const googleLoginHandler = useGoogleAuth({
    onSuccess: (tokenResponse) => {
      loginWithGoogle({ access_token: tokenResponse.access_token })
    },
    onError: () => console.log('Login Failed'),
  })

  const cardRef        = useRef<HTMLDivElement>(null)
  const logoMarkRef    = useRef<HTMLDivElement>(null)
  const loginWaterRef  = useRef<HTMLDivElement>(null)
  const titleRef       = useRef<HTMLHeadingElement>(null)
  const subtitleRef    = useRef<HTMLHeadingElement>(null)
  const taglineRef     = useRef<HTMLParagraphElement>(null)
  const typewriterRef  = useRef<HTMLSpanElement>(null)
  const dividerRef     = useRef<HTMLDivElement>(null)
  const authSectionRef = useRef<HTMLDivElement>(null)
  const footerRef      = useRef<HTMLDivElement>(null)
  const glowRingRef    = useRef<HTMLDivElement>(null)
  const accentBarRef   = useRef<HTMLDivElement>(null)
  const dotsRef        = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (token) navigate('/', { replace: true })
  }, [token, navigate])

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
      .add(taglineRef.current!, { opacity: [0, 1], duration: 1 }, '-=300')
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
  }, [])

  /* ── Water fill loop on login V logo ── */
  useEffect(() => {
    const water = loginWaterRef.current
    if (!water) return

    let stopped = false
    let holdTimer: ReturnType<typeof setTimeout>
    let cycleTimer: ReturnType<typeof setTimeout>

    const runCycle = () => {
      if (stopped) return
      water.style.transform = 'translateY(100%)'
      animate(water, {
        translateY: ['100%', '0%'],
        duration: 2000,
        ease: 'cubicBezier(0.2, 0.8, 0.4, 1)',
        onComplete: () => {
          holdTimer = setTimeout(() => {
            if (stopped) return
            animate(water, {
              translateY: ['0%', '100%'],
              duration: 600,
              ease: 'cubicBezier(0.4, 0, 0.8, 1)',
              onComplete: () => {
                cycleTimer = setTimeout(() => { if (!stopped) runCycle() }, 400)
              },
            })
          }, 5 * 60 * 1000)
        },
      })
    }

    // Wait for entrance animation to finish (~1.8s) before starting fill
    const startTimer = setTimeout(runCycle, 1800)
    return () => {
      stopped = true
      clearTimeout(startTimer)
      clearTimeout(holdTimer)
      clearTimeout(cycleTimer)
    }
  }, [])

  /* ── Typewriter on tagline ── */
  useEffect(() => {
    const el = typewriterRef.current
    if (!el) return
    const full = 'AI That Listens, Learns, and Elevates Quality'
    el.textContent = ''
    let i = 0
    // Start after entrance animation reaches the tagline (~1.4s)
    const start = setTimeout(() => {
      const interval = setInterval(() => {
        el.textContent = full.slice(0, ++i)
        if (i >= full.length) clearInterval(interval)
      }, 38)
      return () => clearInterval(interval)
    }, 1400)
    return () => clearTimeout(start)
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


  return (
    <div
      className="relative flex flex-col min-h-screen items-center justify-center bg-[#000] selection:bg-white selection:text-black overflow-hidden"
    >
      <SeamlessVideo src={LOGIN_BACKGROUND_VIDEO_URL} />

      {/* Readability wash over the video */}
      <div
        className="fixed inset-0 z-[1] pointer-events-none bg-black/45"
      />

      {/* Radial vignette */}
      <div
        className="fixed inset-0 z-[2] pointer-events-none"
        style={{ background: 'radial-gradient(ellipse 70% 70% at 50% 50%, transparent 20%, rgba(0,0,0,0.75) 100%)' }}
      />

      {/* Ambient glow ring */}
      <div
        ref={glowRingRef}
        className="fixed z-[3] pointer-events-none"
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
            className="relative bg-[rgba(10,10,10,0.58)] rounded-xl overflow-hidden"
            style={{
              boxShadow: '0px 0px 0px 1px rgba(255,255,255,0.08), 0 32px 96px rgba(0,0,0,0.8)',
              backdropFilter: 'blur(24px) saturate(160%)', WebkitBackdropFilter: 'blur(24px) saturate(160%)',
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
                    className="w-7 h-7 bg-white rounded-[3px] flex items-center justify-center relative overflow-hidden"
                    style={{ transform: 'scale(0)', opacity: 0, willChange: 'transform, box-shadow' }}
                  >
                    <div
                      ref={loginWaterRef}
                      className="absolute inset-0 z-0 pointer-events-none"
                      style={{
                        background: 'linear-gradient(to top, #ededed 0%, #ffffff 100%)',
                        transform: 'translateY(100%)',
                        willChange: 'transform',
                      }}
                    />
                    <span
                      className="text-[11px] font-black tracking-tight select-none relative z-10"
                      style={{ color: '#ffffff', mixBlendMode: 'difference' }}
                    >V</span>
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
                  className="text-[14px] leading-relaxed text-white"
                  style={{ opacity: 0 }}
                >
                  <span ref={typewriterRef} />
                  <span className="inline-block w-[1.5px] h-[13px] bg-white ml-[2px] align-middle cursor-blink" />
                </p>
              </div>

              {/* Auth section */}
              <div ref={authSectionRef} className="space-y-8" style={{ opacity: 0 }}>
                <div ref={dividerRef} className="relative py-2" style={{ opacity: 0, transformOrigin: 'center' }}>
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-white/10" />
                  </div>
                  <div className="relative flex justify-center">
                    <span className="bg-transparent px-3 text-[10px] font-medium text-[#888] uppercase tracking-[0.2em]">
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
                        <span className="font-mono text-[11px] font-medium text-[#888] uppercase tracking-widest">
                          Authorizing
                        </span>
                      </motion.div>
                    ) : (
                      <motion.div
                        key="auth"
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                        className="w-full relative"
                      >
                        <div className="w-full flex items-center justify-center">
                          <button 
                            className="gsi-material-button" 
                            onClick={() => googleLoginHandler()}
                            style={{ width: '100%', minWidth: '240px' }}
                          >
                            <div className="gsi-material-button-state"></div>
                            <div className="gsi-material-button-content-wrapper">
                              <div className="gsi-material-button-icon">
                                <svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" style={{ display: 'block' }}>
                                  <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"></path>
                                  <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"></path>
                                  <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"></path>
                                  <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"></path>
                                  <path fill="none" d="M0 0h48v48H0z"></path>
                                </svg>
                              </div>
                              <span className="gsi-material-button-contents">Sign in with Google</span>
                              <span style={{ display: 'none' }}>Sign in with Google</span>
                            </div>
                          </button>
                        </div>
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
                  <span className="font-mono text-[9px] font-medium text-[#888] uppercase tracking-widest">
                    Systems Ready
                  </span>
                </div>
                <a
                  href="https://t.me/Mohmed_abdo"
                  target="_blank" rel="noopener noreferrer"
                  className="text-[10px] font-medium text-[#888] hover:text-white transition-colors uppercase tracking-widest"
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
        *:focus-visible { outline: 1px solid white !important; outline-offset: 4px !important; }

        /* Custom Google Button Styles */
        .gsi-material-button {
          -moz-user-select: none;
          -webkit-user-select: none;
          -ms-user-select: none;
          -webkit-appearance: none;
          background-color: #131314;
          background-image: none;
          border: 1px solid #8e918f;
          -webkit-border-radius: 4px;
          border-radius: 4px;
          -webkit-box-sizing: border-box;
          box-sizing: border-box;
          color: #e3e3e3;
          cursor: pointer;
          font-family: 'Roboto', arial, sans-serif;
          font-size: 14px;
          font-weight: 500;
          height: 44px;
          letter-spacing: 0.25px;
          outline: none;
          overflow: hidden;
          padding: 0 12px;
          position: relative;
          text-align: center;
          -webkit-transition: background-color .218s, border-color .218s, box-shadow .218s;
          transition: background-color .218s, border-color .218s, box-shadow .218s;
          vertical-align: middle;
          white-space: nowrap;
          width: 100%;
          max-width: 400px;
          min-width: min-content;
        }

        .gsi-material-button .gsi-material-button-icon {
          height: 20px;
          margin-right: 12px;
          min-width: 20px;
          width: 20px;
        }

        .gsi-material-button .gsi-material-button-content-wrapper {
          -webkit-align-items: center;
          align-items: center;
          display: flex;
          -webkit-flex-direction: row;
          flex-direction: row;
          -webkit-flex-wrap: nowrap;
          flex-wrap: nowrap;
          height: 100%;
          justify-content: center;
          position: relative;
          width: 100%;
        }

        .gsi-material-button .gsi-material-button-contents {
          -webkit-flex-grow: 1;
          flex-grow: 1;
          font-family: 'Roboto', arial, sans-serif;
          font-weight: 500;
          overflow: hidden;
          text-overflow: ellipsis;
          vertical-align: top;
        }

        .gsi-material-button .gsi-material-button-state {
          -webkit-transition: opacity .218s;
          transition: opacity .218s;
          bottom: 0;
          left: 0;
          opacity: 0;
          position: absolute;
          right: 0;
          top: 0;
        }

        .gsi-material-button:disabled {
          cursor: default;
          background-color: #13131461;
          border-color: #8e918f1f;
        }

        .gsi-material-button:disabled .gsi-material-button-contents {
          color: #e3e3e31f;
        }

        .gsi-material-button:disabled .gsi-material-button-icon {
          opacity: 32%;
        }

        .gsi-material-button:not(:disabled):active .gsi-material-button-state, 
        .gsi-material-button:not(:disabled):focus .gsi-material-button-state {
          background-color: #e3e3e3;
          opacity: 12%;
        }

        .gsi-material-button:not(:disabled):hover {
          -webkit-box-shadow: 0 1px 2px 0 rgba(0, 0, 0, .30), 0 1px 3px 1px rgba(0, 0, 0, .15);
          box-shadow: 0 1px 2px 0 rgba(0, 0, 0, .30), 0 1px 3px 1px rgba(0, 0, 0, .15);
          background-color: #1e1e1f;
        }

        .gsi-material-button:not(:disabled):hover .gsi-material-button-state {
          background-color: #e3e3e3;
          opacity: 8%;
        }
      `}} />
    </div>
  )
}
