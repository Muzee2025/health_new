﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿<template>
  <div class="app-layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <router-link to="/student" class="logo-area" aria-label="心域智链首页"><img :src="brandLogo" class="business-brand" alt="心域智链" width="152" height="52" /></router-link>

      <nav class="nav-menu" aria-label="学生导航">
        <router-link to="/student/dashboard" class="nav-item" active-class="active">
          <el-icon><House /></el-icon> <span class="nav-text">首页</span>
        </router-link>
        <router-link to="/student/test" class="nav-item" active-class="active">
          <el-icon><DataAnalysis /></el-icon> <span class="nav-text">心理测评</span>
        </router-link>
        <router-link to="/student/appointments" class="nav-item" active-class="active">
          <el-icon><Calendar /></el-icon> <span class="nav-text">预约咨询</span>
        </router-link>
        <router-link to="/student/articles" class="nav-item" active-class="active">
          <el-icon><Reading /></el-icon> <span class="nav-text">心理科普</span>
        </router-link>
        <router-link to="/student/advanced-chat" class="nav-item" active-class="active">
          <el-icon><ChatDotRound /></el-icon> <span class="nav-text">智能心理助手</span>
        </router-link>
        <router-link to="/student/report" class="nav-item" active-class="active">
          <el-icon><Document /></el-icon> <span class="nav-text">我的心理报告</span>
        </router-link>
        <router-link to="/student/treehole" class="nav-item" active-class="active">
          <el-icon><ChatDotRound /></el-icon> <span class="nav-text">匿名树洞</span>
        </router-link>

        <div class="nav-divider"></div>

        <button type="button" class="nav-item" @click="logout">
          <el-icon><SwitchButton /></el-icon> <span class="nav-text">退出登录</span>
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
    <div class="main-content">
      <header class="top-header">
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
import brandLogo from '../../assets/brand/brand-logo-horizontal.svg'
import profileAvatar from '../../assets/avatars/students/avatar-student-01-96.webp'
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Platform, House, DataAnalysis, Calendar, Reading,
  Document, ChatDotRound, SwitchButton, Search, Bell
} from '@element-plus/icons-vue'

const router = useRouter()
const user = ref({})
const route = useRoute()
const pageTitle = computed(() => ({ dashboard: '心理健康数据看板', test: '心理测评', appointments: '预约咨询', articles: '心理科普', 'advanced-chat': '智能心理助手', report: '我的心理报告', treehole: '匿名树洞', questions: '心理问答' }[route.path.split('/').at(-1)] || '学生空间'))

onMounted(() => {
  const userInfo = localStorage.getItem('user')
  if (userInfo) {
    try { user.value = JSON.parse(userInfo) || {} } catch { user.value = {} }
  }
})

const logout = () => {
  for (const key of ['token', 'access_token', 'role', 'user']) localStorage.removeItem(key)
  router.push('/login')
}
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background-color: var(--surface-warm);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Sidebar */
.sidebar {
  width: 240px;
  background-color: var(--surface-warm);
  display: flex;
  flex-direction: column;
  padding: 30px 0;
  border-right: 1px solid var(--border);
}

.logo-area {
  display: flex;
  align-items: center;
  padding: 0 30px;
  margin-bottom: 40px;
  font-size: 18px;
  font-weight: bold;
  color: var(--text-primary);
}

.logo-icon {
  font-size: 24px;
  margin-right: 10px;
}

.nav-menu {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 12px 30px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  transition: all 0.2s;
  cursor: pointer;
  position: relative;
  border-radius: 12px;
  margin: 0 10px;
}

.nav-item .el-icon {
  font-size: 18px;
  margin-right: 12px;
  color: var(--text-secondary);
}

.nav-item:hover, .nav-item.active {
  color: var(--brand-600);
  font-weight: 500;
}

.nav-item.active {
  background-color: color-mix(in srgb, var(--brand-500) 14%, transparent);
  color: var(--brand-600);
}

.nav-item.active::before {
  content: "";
  position: absolute;
  left: -10px;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 3px;
  background: var(--brand-600);
}

.nav-item.active .el-icon {
  color: var(--brand-600);
}

.nav-divider {
  height: 1px;
  background-color: color-mix(in srgb, var(--gray-900) 5%, transparent);
  margin: 20px 30px;
}

/* User Profile */
.user-profile {
  display: flex;
  align-items: center;
  padding: 14px 22px 0 22px;
  margin-top: auto;
  border-top: 1px solid var(--border);
}

.user-info {
  margin-left: 12px;
}

.user-name {
  font-size: 14px;
  font-weight: bold;
  color: var(--text-primary);
}

.user-email {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* Main Content */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.top-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 30px 40px;
  gap: 16px;
}

.page-title {
  font-size: 24px;
  font-weight: bold;
  color: var(--text-primary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.search-box {
  display: flex;
  align-items: center;
  background-color: var(--surface);
  padding: 10px 16px;
  border-radius: 12px;
  width: 300px;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--gray-900) 6%, transparent);
  margin-left: auto;
}

.search-icon {
  color: var(--text-secondary);
  margin-right: 10px;
  font-size: 18px;
}

.search-box input {
  border: none;
  outline: none;
  background: transparent;
  width: 100%;
  font-size: 14px;
  color: var(--text-primary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--surface);
  padding: 8px;
  font-size: 18px;
  color: var(--text-primary);
  cursor: pointer;
  transition: all .2s ease;
}

.icon-btn:hover {
  color: var(--brand-600);
  border-color: var(--brand-600);
}

.avatar-group {
  display: flex;
  align-items: center;
  background-color: var(--surface);
  padding: 4px 12px 4px 4px;
  border-radius: 12px;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--gray-900) 6%, transparent);
}

.overlap-avatar {
  border: 2px solid var(--surface);
}

.avatar-count {
  font-size: 13px;
  font-weight: bold;
  margin-left: 8px;
  color: var(--text-primary);
}

.primary-btn {
  background-color: var(--brand-600);
  color: var(--surface);
  border: none;
  padding: 10px 20px;
  border-radius: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--gray-900) 6%, transparent);
}

.primary-btn:hover {
  background-color: var(--brand-600);
}

/* Page Wrapper */
.page-wrapper {
  flex: 1;
  padding: 0 40px 40px 40px;
  overflow-y: auto;
}
</style>
