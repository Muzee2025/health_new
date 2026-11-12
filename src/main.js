import { createApp, defineAsyncComponent } from 'vue'
import { provideGlobalConfig } from 'element-plus'
import 'element-plus/dist/index.css'
import LibraryIcon from './design/LibraryIcon.vue'
import { getVisualAsset } from './design/asset-registry'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import axios from 'axios'
import App from './App.vue'
import './styles/tokens.css'
import './styles/business.css'
import { installBusinessPalette } from './design/chart-registry'

document.body.classList.add('xy-business')
installBusinessPalette()
const favicon = document.querySelector('#app-favicon')
if (favicon) favicon.href = getVisualAsset('favicon').url
const themeColor = document.querySelector('#app-theme-color')
if (themeColor)
  themeColor.content = getComputedStyle(document.documentElement)
    .getPropertyValue('--brand-600')
    .trim()
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
  (error) => Promise.reject(error),
)

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const reqUrl = String(error.config?.url || '')
    const requestToken = String(error.config?.headers?.Authorization || '')
      .replace(/^bearer\s+/i, '')
      .trim()
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
    // Only what a caller needs to react to. The whole response carried the
    // request config, so anything that logged this error — a console.error in a
    // view, a crash reporter — printed the Authorization header and body.
    err.response = error.response
      ? { status: error.response.status, data: error.response.data }
      : undefined
    return Promise.reject(err)
  },
)

const app = createApp(App)

app.component('LibraryIcon', LibraryIcon)
app.component(
  'LibraryEmpty',
  defineAsyncComponent(() => import('./design/LibraryEmpty.vue')),
)

provideGlobalConfig({ locale: zhCn }, app, true)
app.use(router)
app.config.globalProperties.$http = axios
app.mount('#app')

// Register Service Worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.error('ServiceWorker registration failed: ', err)
    })
  })
}
