import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// 构建产物直接输出到 Python 包里，由 server/app.py 托管，并提交进仓库
// （手机 Termux 上不装 Node 也能用）。改了 frontend/ 就要重新 npm run build 并提交产物。
const outDir = fileURLToPath(new URL('../src/artist_gallery/server/static', import.meta.url))

// 开发时 `npm run dev` 的页面在 5173 端口，接口代理到本机的 `artist-gallery serve`（默认 8765）。
const backend = 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [vue()],
  base: '/',
  build: {
    outDir,
    emptyOutDir: true, // 输出目录在项目外，必须显式允许清空；会连同旧的占位页一起替换
    assetsDir: 'assets', // server/app.py 里 /assets 就是挂这个目录
    target: 'es2020', // 老一点的 Android WebView 也能跑
  },
  server: {
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/thumbs': { target: backend, changeOrigin: true },
      '/images': { target: backend, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.js'],
  },
})
