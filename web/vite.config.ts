import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// `base` controls the URL prefix at runtime. Defaults to '/' for the
// FastAPI-served path (StaticFiles mount at root). CI override to the
// repo subpath when deploying to GitHub Pages (served at /<repo>/),
// via VITE_BASE_PATH in .github/workflows/deploy-pages.yml.
export default defineConfig({
  base: process.env.VITE_BASE_PATH ?? '/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
