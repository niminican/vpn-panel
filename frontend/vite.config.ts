import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/vpn/',
  server: {
    port: 3000,
    proxy: {
      '/vpn/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/vpn/, ''),
      },
    },
  },
})
