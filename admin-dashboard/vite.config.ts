import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'


function figmaAssetResolver() {
  return {
    name: 'figma-asset-resolver',
    resolveId(id: string) {
      if (id.startsWith('figma:asset/')) {
        const filename = id.replace('figma:asset/', '')
        return path.resolve(__dirname, 'src/assets', filename)
      }
    },
  }
}

// The admin backend, proxied below. Override with ADMIN_API_TARGET if the relay
// API runs on a different port than the default.
const ADMIN_API_TARGET = process.env.ADMIN_API_TARGET ?? 'http://127.0.0.1:8771'

// Every top-level path the backend owns. These are proxied so the dashboard
// always calls its OWN origin: the session cookie the backend sets is
// SameSite=Lax, so pointing the browser straight at the API on another host
// (e.g. the relay's LAN IP while the page is served from localhost) makes the
// request cross-site, the cookie is silently dropped, /auth/me reports
// unauthenticated and the dashboard route bounces back to the login screen.
// Going through the proxy keeps everything same-origin, from any machine.
const API_PATHS = [
  '/agents',
  '/analytics',
  '/auth',
  '/blacklist',
  '/health',
  '/ledger',
  '/policy',
  '/telemetry',
  '/threats',
]

const apiProxy = Object.fromEntries(
  API_PATHS.map(p => [p, { target: ADMIN_API_TARGET, changeOrigin: false }]),
)

export default defineConfig({
  plugins: [
    figmaAssetResolver(),
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
  ],
  server: {
    host: true,
    port: 5175,
    proxy: apiProxy,
  },
  preview: { port: 5175, proxy: apiProxy },
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },

  // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
  assetsInclude: ['**/*.svg', '**/*.csv'],
})
