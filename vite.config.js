import { defineConfig } from 'vite'

import vue from '@vitejs/plugin-vue'

import { fileURLToPath, URL } from 'node:url'



export default defineConfig({

  plugins: [vue()],

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
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },

  },

})

