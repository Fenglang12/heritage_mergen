import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  plugins: [
    vue(),
    // 自动按需引入 Element Plus 组件，无需手动 import
    AutoImport({ resolvers: [ElementPlusResolver()] }),
    Components({ resolvers: [ElementPlusResolver()] })
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        withCredentials: true,
        configure(proxy) {
          proxy.on('proxyReq', (proxyReq, req) => {
            const remote = req.socket?.remoteAddress || ''
            if (!proxyReq.getHeader('x-forwarded-for') && remote) {
              proxyReq.setHeader('X-Forwarded-For', remote.replace(/^::ffff:/, ''))
            }
          })
        }
      }
    }
  }
})
