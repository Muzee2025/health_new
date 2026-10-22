import { defineConfig } from 'vite'

import vue from '@vitejs/plugin-vue'

import { fileURLToPath, URL } from 'node:url'



const configuredBackend = new URL(process.env.HEALTH_BACKEND_TARGET || 'http://127.0.0.1:18080')
if (configuredBackend.protocol !== 'http:' || configuredBackend.hostname !== '127.0.0.1'
    || !['18080', '18081'].includes(configuredBackend.port) || configuredBackend.username || configuredBackend.password
    || configuredBackend.pathname !== '/' || configuredBackend.search || configuredBackend.hash) {
  throw new Error('HEALTH_BACKEND_TARGET must be this project loopback service on port 18080, or isolated QA on 18081')
}
const backendTarget = configuredBackend.origin

export default defineConfig({

  plugins: [vue()],

  build: { manifest: true },

  test: {
    include: ['src/**/*.test.{js,ts}'],
  },

  resolve: {

    alias: {

      '@': fileURLToPath(new URL('./src', import.meta.url)),

    },

  },

  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        ws: true,
      },
      '/static': {
        target: backendTarget,
        changeOrigin: true,
      },
    },

  },

})

