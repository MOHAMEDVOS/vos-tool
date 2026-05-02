import React from 'react'
import { Sidebar } from './Sidebar'
import { Footer } from './Footer'
import { motion, AnimatePresence } from 'framer-motion'

interface Props {
  children: React.ReactNode
  /** Pass the active tab key so page transitions trigger on tab change */
  pageKey?: string
}

export function AppShell({ children, pageKey }: Props) {
  return (
    <div className="flex h-screen overflow-hidden bg-surface-page text-t-primary transition-colors duration-150">
      <Sidebar />

      <main className="flex-1 overflow-y-auto">
        <div className="flex flex-col min-h-full p-8 pb-2 mx-auto max-w-7xl">
          <div className="flex-1">
            <AnimatePresence mode="wait">
              <motion.div
                key={pageKey ?? 'page'}
                initial={{ opacity: 0, y: 10, filter: 'blur(3px)' }}
                animate={{ opacity: 1, y: 0,  filter: 'blur(0px)' }}
                exit={{    opacity: 0, y: -6,  filter: 'blur(2px)' }}
                transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              >
                {children}
              </motion.div>
            </AnimatePresence>
          </div>
          
          <Footer />
        </div>
      </main>
    </div>
  )
}
