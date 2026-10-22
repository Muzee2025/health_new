import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import axios from 'axios'
import App from './App.vue'
import './styles/tokens.css'
import './styles/business.css'
import * as echarts from 'echarts'
import { installBusinessCharts } from './styles/business-theme'

document.body.classList.add('xy-business')
installBusinessCharts(echarts)
import router from './router'

const rawBaseURL = String(import.meta.env.VITE_API_BASE_URL || '').trim()
const normalizedBaseURL = rawBaseURL.replace(/\/+$/, '')
// Avoid '/api/api/*' when request URLs already include '/api/*'.
axios.defaults.baseURL = normalizedBaseURL.replace(/\/api$/, '')

function getStoredToken() {
  const raw = localStorage.getItem('token') || localStorage.getItem('access_token') || ''
  const t = String(raw).trim()
  if (!t) return ''
  if (t.toLowerCase().startsWith('bearer ')) return t.slice(7).trim()
  return t
}

axios.interceptors.request.use(
  (config) => {
    const token = getStoredToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const reqUrl = String(error.config?.url || '')
    const requestToken = String(error.config?.headers?.Authorization || '').replace(/^bearer\s+/i, '').trim()
    if (status === 401 && !reqUrl.includes('/api/login') && requestToken === getStoredToken()) {
      localStorage.removeItem('token')
      localStorage.removeItem('access_token')
      localStorage.removeItem('role')
      localStorage.removeItem('user')
      const current = router.currentRoute.value
      if (current.path !== '/login') {
        router.replace({
          path: '/login',
          query: { redirect: current.fullPath || '/' },
        })
      }
    }
    const d = error.response?.data?.detail
    let msg = '请求失败'
    if (typeof d === 'string') msg = d
    else if (Array.isArray(d)) msg = d.map((x) => x.msg || JSON.stringify(x)).join('; ')
    else if (d != null) msg = String(d)
    else if (error.message) msg = error.message
    const err = new Error(msg)
    err.status = status
    err.response = error.response
    return Promise.reject(err)
  }
)

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(ElementPlus, { locale: zhCn })
app.use(router)
app.config.globalProperties.$http = axios
app.mount('#app')

// Register Service Worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(err => {
      console.error('ServiceWorker registration failed: ', err);
    });
  });
}
