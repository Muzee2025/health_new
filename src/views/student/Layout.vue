﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿<template>
  <div class="app-layout xy-business">
    <!-- Sidebar -->
    <button class="nav-scrim" type="button" aria-hidden="true" tabindex="-1" @click="closeMobileNav" v-if="mobileNavOpen"></button>
    <aside ref="sidebarRef" id="student-navigation-panel" class="sidebar" :class="{ 'mobile-open': mobileNavOpen }" :aria-hidden="isMobile && !mobileNavOpen ? 'true' : 'false'" @keydown.tab="handleNavTab" @click="handleNavClick">
      <div class="sidebar-head">
        <router-link to="/student" class="logo-area" aria-label="心域智链首页"><img :src="brandLogo" class="business-brand" alt="心域智链" width="152" height="52" /></router-link>
        <button class="mobile-nav-close" type="button" aria-label="关闭导航" @click="closeMobileNav"><el-icon><LibraryIcon name="arrow-left" /></el-icon><span>关闭</span></button>
      </div>

      <nav class="nav-menu" aria-label="学生导航" @keydown.esc="closeMobileNav">
        <router-link to="/student/dashboard" class="nav-item" active-class="active" exact-active-class="active">
          <el-icon><LibraryIcon name="home" /></el-icon><span class="nav-text">首页</span>
        </router-link>
        <div class="nav-group" :class="{ 'group-active': activeStudentGroup === 'growth' }">
          <button type="button" class="nav-item nav-group-toggle" :aria-expanded="growthOpen" aria-controls="growth-submenu" @click="growthOpen = !growthOpen">
            <el-icon><LibraryIcon name="assessment" /></el-icon><span class="nav-text">自助成长</span><el-icon class="nav-caret" :class="{ expanded: growthOpen }"><LibraryIcon name="arrow-down" /></el-icon>
          </button>
          <div v-if="growthOpen" id="growth-submenu" class="nav-submenu">
            <router-link to="/student/test" class="nav-item nav-subitem" active-class="active">心理测评</router-link>
            <router-link to="/student/articles" class="nav-item nav-subitem" active-class="active">心理科普</router-link>
          </div>
        </div>
        <router-link to="/student/appointments" class="nav-item" active-class="active">
          <el-icon><LibraryIcon name="appointment" /></el-icon><span class="nav-text">预约咨询</span>
        </router-link>
        <router-link to="/student/advanced-chat" class="nav-item" active-class="active">
          <el-icon><LibraryIcon name="chat" /></el-icon><span class="nav-text">智能助手</span>
        </router-link>
        <router-link to="/student/treehole" class="nav-item" active-class="active">
          <el-icon><LibraryIcon name="treehole" /></el-icon><span class="nav-text">匿名树洞</span>
        </router-link>
        <div class="nav-group" :class="{ 'group-active': activeStudentGroup === 'mine' }">
          <button type="button" class="nav-item nav-group-toggle" :aria-expanded="mineOpen" aria-controls="mine-submenu" @click="mineOpen = !mineOpen">
            <el-icon><LibraryIcon name="user" /></el-icon><span class="nav-text">我的</span><el-icon class="nav-caret" :class="{ expanded: mineOpen }"><LibraryIcon name="arrow-down" /></el-icon>
          </button>
          <div v-if="mineOpen" id="mine-submenu" class="nav-submenu">
            <router-link to="/student/report" class="nav-item nav-subitem" active-class="active">心理报告</router-link>
            <router-link to="/student/questions" class="nav-item nav-subitem" active-class="active">留言与答复</router-link>
          </div>
        </div>

        <div class="nav-divider"></div>

        <button type="button" class="nav-item" @click="logout">
          <el-icon><LibraryIcon name="logout"  /></el-icon> <span class="nav-text">退出登录</span>
        </button>
      </nav>

      <div class="user-profile">
        <el-avatar :size="40" :src="profileAvatar" alt="学生头像" />
        <div class="user-info">
          <div class="user-name">{{ user.name || user.username }}</div>
          <div class="user-email">学生空间</div>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <div class="main-content" :inert="mobileNavOpen">
      <header class="top-header">
        <button ref="mobileNavTrigger" class="mobile-nav-trigger" type="button" aria-controls="student-navigation-panel" :aria-expanded="mobileNavOpen" @click="toggleMobileNav"><el-icon><LibraryIcon name="collection" /></el-icon><span>导航</span></button>
        <h1 class="page-title">{{ pageTitle }}</h1>

        <div class="header-right">

          <button class="primary-btn" @click="$router.push('/student/appointments')">新增预约</button>
        </div>
      </header>

      <div class="page-wrapper">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ElIcon, ElAvatar } from 'element-plus'
import { getVisualAsset } from '../../design/asset-registry'
const brandLogo = getVisualAsset('brandLogo').url
const profileAvatar = getVisualAsset('studentAvatar').url

import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const user = ref({})
const route = useRoute()
const mobileNavOpen = ref(false)
const mobileNavTrigger = ref(null)
const sidebarRef = ref(null)
const isMobile = ref(false)
let mediaQuery
let navFocusRequest = 0
const focusableNavItems = () => [...(sidebarRef.value?.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])') || [])].filter(element => element.getClientRects().length > 0)
const nextFrame = () => new Promise(resolve => window.requestAnimationFrame(resolve))
const openMobileNav = async () => {
  const request = ++navFocusRequest
  mobileNavOpen.value = true
  await nextTick()
  for (let attempt = 0; attempt < 4; attempt += 1) {
    await nextFrame()
    if (request !== navFocusRequest || !mobileNavOpen.value || !isMobile.value || !sidebarRef.value?.isConnected) return
    const target = focusableNavItems().find(element => {
      const style = window.getComputedStyle(element)
      return style.display !== 'none' && style.visibility === 'visible' && !element.hasAttribute('disabled')
    })
    target?.focus?.({ preventScroll: true })
    if (target && sidebarRef.value.contains(document.activeElement)) return
  }
}
const closeMobileNav = async () => {
  if (!mobileNavOpen.value) return
  navFocusRequest += 1
  mobileNavOpen.value = false
  await nextTick()
  mobileNavTrigger.value?.focus?.()
}
const toggleMobileNav = () => { if (mobileNavOpen.value) closeMobileNav(); else openMobileNav() }
const handleNavClick = (event) => { if (event.target.closest?.('a[href]')) closeMobileNav() }
const handleEscape = (event) => { if (event.key === 'Escape') closeMobileNav() }
const handleNavTab = (event) => {
  if (!mobileNavOpen.value || !isMobile.value || event.key !== 'Tab') return
  const items = focusableNavItems()
  if (!items.length) return
  const first = items[0]
  const last = items[items.length - 1]
  if (event.shiftKey && (document.activeElement === first || !sidebarRef.value?.contains(document.activeElement))) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && (document.activeElement === last || !sidebarRef.value?.contains(document.activeElement))) {
    event.preventDefault()
    first.focus()
  }
}
const syncViewport = async (event) => {
  isMobile.value = event.matches
  if (!event.matches && mobileNavOpen.value) {
    navFocusRequest += 1
    mobileNavOpen.value = false
    await nextTick()
    sidebarRef.value?.querySelector('[aria-current="page"], .nav-item')?.focus?.()
  }
}
const pageTitle = computed(() => ({ dashboard: '我的近况', test: '心理测评', appointments: '预约咨询', articles: '心理科普', 'advanced-chat': '智能心理助手', report: '我的心理报告', treehole: '匿名树洞', questions: '留言与答复' }[route.path.split('/').at(-1)] || '学生空间'))
const growthOpen = ref(['/student/test', '/student/articles'].some(path => route.path === path || route.path.startsWith('/article/')))
const mineOpen = ref(['/student/report', '/student/questions'].includes(route.path))
const activeStudentGroup = computed(() => {
  if (['/student/test', '/student/articles'].includes(route.path) || route.path.startsWith('/article/')) return 'growth'
  if (['/student/report', '/student/questions'].includes(route.path)) return 'mine'
  return route.path.split('/')[2] || 'dashboard'
})
watch(() => route.path, (path) => {
  if (mobileNavOpen.value) closeMobileNav()
  if (['/student/test', '/student/articles'].includes(path) || path.startsWith('/article/')) growthOpen.value = true
  if (['/student/report', '/student/questions'].includes(path)) mineOpen.value = true
})

onMounted(() => {
  mediaQuery = window.matchMedia('(max-width: 760px)')
  isMobile.value = mediaQuery.matches
  mediaQuery.addEventListener?.('change', syncViewport)
  window.addEventListener('keydown', handleEscape)
  const userInfo = localStorage.getItem('user')
  if (userInfo) {
    try { user.value = JSON.parse(userInfo) || {} } catch { user.value = {} }
  }
})
onUnmounted(() => { navFocusRequest += 1; mediaQuery?.removeEventListener?.('change', syncViewport); window.removeEventListener('keydown', handleEscape) })

const logout = () => {
  for (const key of ['token', 'access_token', 'role', 'user']) localStorage.removeItem(key)
  router.push('/login')
}
</script>
