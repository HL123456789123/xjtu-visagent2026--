/**
 * 应用入口
 *
 * - 注册全局错误监控（在其他插件之前注册）
 * - 初始化 Vue 应用
 * - 注册 ElementPlus / Router / Pinia 插件
 * - 引入全局样式
 */
import { createApp } from 'vue'

// 全局样式
import '@/assets/styles/global.scss'

// Element Plus
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

// 路由 / 状态管理
import App from './App.vue'
import router from './router'
import pinia from './stores'

// 全局错误监控
import { setupErrorReporting } from "@/utils/error_reporter";

// 创建应用
const app = createApp(App)

// 注册全局错误监控（在其他插件之前注册）
setupErrorReporting(app)

// 注册插件
app.use(pinia)                        // 状态管理
app.use(router)                       // 路由
app.use(ElementPlus, { locale: zhCn }) // Element Plus 中文

// 挂载到 DOM
app.mount('#app')
