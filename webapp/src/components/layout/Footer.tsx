import React from 'react'
import { motion } from 'framer-motion'
import { ExternalLink } from 'lucide-react'

export function Footer() {
  return (
    <footer className="mt-auto py-1 border-t border-[var(--b-divider)] opacity-90 transition-opacity duration-300">
      <div className="flex flex-col md:flex-row items-center justify-between gap-2 text-[7.5px] font-bold uppercase tracking-[0.3em] text-t-muted">
        
        {/* Left: Status */}
        <div className="flex items-center gap-1.5">
          <motion.div
            animate={{ 
              opacity: [0.6, 1, 0.6] 
            }}
            transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
            className="h-1 w-1 rounded-full bg-accent shadow-[0_0_4px_var(--accent)]"
          />
          <span className="text-accent/80">AI-Powered Audit Platform</span>
        </div>

        {/* Center: Copyright */}
        <div className="select-none opacity-80">
          &copy; {new Date().getFullYear()} VOS RAILWAY &bull; Intelligence Audit System
        </div>

        {/* Right: Credits */}
        <div className="flex items-center gap-1.5">
          <span className="opacity-80">Developed by</span>
          <a 
            href="https://t.me/Mohmed_abdo" 
            target="_blank" 
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-t-primary hover:text-accent transition-all duration-300 group"
          >
            MOHAMED ABDO
            <ExternalLink size={7} className="group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform opacity-70" />
          </a>
        </div>

      </div>
    </footer>
  )
}
