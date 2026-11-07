import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 3000,
    allowedHosts: [
      '.trycloudflare.com',
      ...(process.env.CLOUDFLARE_TUNNEL_HOST ? [process.env.CLOUDFLARE_TUNNEL_HOST] : []),
    ],
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
