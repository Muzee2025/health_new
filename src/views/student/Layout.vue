﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿<template>
  <div class="app-layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="logo-area">
        <el-icon class="logo-icon"><Platform /></el-icon>
        <span class="logo-text">心域智链</span>
      </div>

      <nav class="nav-menu">
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
        
        <div class="nav-item" @click="logout">
          <el-icon><SwitchButton /></el-icon> <span class="nav-text">退出登录</span>
        </div>
      </nav>

      <div class="user-profile">
        <el-avatar :size="40" src="https://api.dicebear.com/7.x/avataaars/svg?seed=Felix" />
        <div class="user-info">
          <div class="user-name">{{ user.name || user.username }}</div>
          <div class="user-email">{{ user.username }}@edu.cn</div>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <div class="main-content">
      <header class="top-header">
        <h1 class="page-title">心理健康数据看板</h1>
        
        <div class="search-box">
          <el-icon class="search-icon"><Search /></el-icon>
          <input type="text" placeholder="Search" />
        </div>

        <div class="header-right">
          <el-icon class="icon-btn"><Bell /></el-icon>
          <el-icon class="icon-btn"><Calendar /></el-icon>
          <div class="avatar-group">
            <el-avatar :size="32" src="https://api.dicebear.com/7.x/avataaars/svg?seed=A" class="overlap-avatar" />
            <div class="avatar-count">+24</div>
          </div>
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { 
  Platform, House, DataAnalysis, Calendar, Reading, 
  Document, ChatDotRound, SwitchButton, Search, Bell
} from '@element-plus/icons-vue'

const router = useRouter()
const user = ref({})

onMounted(() => {
  const userInfo = localStorage.getItem('user')
  if (userInfo) {
    user.value = JSON.parse(userInfo)
  }
})

const logout = () => {
  localStorage.clear()
  router.push('/login')
}
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background-color: #FAFAFA;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Sidebar */
.sidebar {
  width: 240px;
  background-color: #FAFAFA;
  display: flex;
  flex-direction: column;
  padding: 30px 0;
  border-right: 1px solid #E5E7EB;
}

.logo-area {
  display: flex;
  align-items: center;
  padding: 0 30px;
  margin-bottom: 40px;
  font-size: 18px;
  font-weight: bold;
  color: #111827;
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
  color: #4B5563;
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
  color: #9CA3AF;
}

.nav-item:hover, .nav-item.active {
  color: #6B9AC4;
  font-weight: 500;
}

.nav-item.active {
  background-color: rgba(107, 154, 196, 0.14);
  color: #6B9AC4;
}

.nav-item.active::before {
  content: "";
  position: absolute;
  left: -10px;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 3px;
  background: #6B9AC4;
}

.nav-item.active .el-icon {
  color: #6B9AC4;
}

.nav-divider {
  height: 1px;
  background-color: rgba(0,0,0,0.05);
  margin: 20px 30px;
}

/* User Profile */
.user-profile {
  display: flex;
  align-items: center;
  padding: 14px 22px 0 22px;
  margin-top: auto;
  border-top: 1px solid #E5E7EB;
}

.user-info {
  margin-left: 12px;
}

.user-name {
  font-size: 14px;
  font-weight: bold;
  color: #111827;
}

.user-email {
  font-size: 12px;
  color: #9CA3AF;
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
  color: #111827;
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.search-box {
  display: flex;
  align-items: center;
  background-color: #FFFFFF;
  padding: 10px 16px;
  border-radius: 12px;
  width: 300px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  margin-left: auto;
}

.search-icon {
  color: #9CA3AF;
  margin-right: 10px;
  font-size: 18px;
}

.search-box input {
  border: none;
  outline: none;
  background: transparent;
  width: 100%;
  font-size: 14px;
  color: #111827;
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
  border: 1px solid #E5E7EB;
  background: #FFFFFF;
  padding: 8px;
  font-size: 18px;
  color: #111827;
  cursor: pointer;
  transition: all .2s ease;
}

.icon-btn:hover {
  color: #6B9AC4;
  border-color: #6B9AC4;
}

.avatar-group {
  display: flex;
  align-items: center;
  background-color: #FFFFFF;
  padding: 4px 12px 4px 4px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.overlap-avatar {
  border: 2px solid #FFFFFF;
}

.avatar-count {
  font-size: 13px;
  font-weight: bold;
  margin-left: 8px;
  color: #111827;
}

.primary-btn {
  background-color: #6B9AC4;
  color: #FFFFFF;
  border: none;
  padding: 10px 20px;
  border-radius: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.primary-btn:hover {
  background-color: #5A89B3;
}

/* Page Wrapper */
.page-wrapper {
  flex: 1;
  padding: 0 40px 40px 40px;
  overflow-y: auto;
}
</style>
