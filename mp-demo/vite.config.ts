import { defineConfig, loadEnv } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig(({ mode }) => {
  // 与 mp-demo/.env.<mode> 共用一套变量：代理目标跟 VITE_API_BASE 保持一致
  const env = loadEnv(mode, __dirname, '')
  const proxyTarget = String(env.VITE_API_BASE || 'http://127.0.0.1:8090').replace(/\/+$/, '')

  return {
    plugins: [uni()],
    server: {
      host: '127.0.0.1',
      port: 5174,
      // H5 开发时把 /api 代理到当前环境的后端，避免跨域
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
