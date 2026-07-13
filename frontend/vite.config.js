import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],

  // 路径别名
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },

  // CSS 配置 —— 全局注入 SCSS 变量
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "@/assets/styles/variables.scss" as *;`,
      },
    },
  },

  // 开发服务器配置
  server: {
    port: 3000,
    open: true,
    // HMR WebSocket 使用独立路径，避免与根路径冲突
    hmr: {
      path: '/__vite_hmr',
    },
    // API 代理 —— 将 /api 请求转发到后端
    proxy: {
      '/api': {
        target: 'http://localhost:8888',
        changeOrigin: true,
        // WebSocket 代理也需要开启
        ws: true,
      },
    },
  },
})
