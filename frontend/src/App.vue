<template>
  <div id="app">
    <a-layout style="min-height: 100vh">
      <a-layout-header class="app-header">
        <div class="app-title">
          🌍 HelloAgents智能旅行助手
        </div>
        <a-space v-if="authState.user">
          <span class="user-name">{{ authState.user.display_name }}</span>
          <a-button ghost @click="router.push('/trips')">我的行程</a-button>
          <a-button ghost @click="router.push('/')">新建行程</a-button>
          <a-button ghost @click="handleLogout">退出登录</a-button>
        </a-space>
      </a-layout-header>
      <a-layout-content style="padding: 24px">
        <router-view />
      </a-layout-content>
      <a-layout-footer style="text-align: center">
        HelloAgents智能旅行助手 ©2025 基于HelloAgents框架
      </a-layout-footer>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { authState, logout } from '@/stores/auth'

const router = useRouter()

const handleLogout = async () => {
  await logout()
  message.success('已退出登录')
  await router.replace('/login')
}
</script>

<style>
#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans', sans-serif;
}
.app-header {
  background: #001529;
  padding: 0 50px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.app-title {
  color: white;
  font-size: 24px;
  font-weight: bold;
}
.user-name {
  color: white;
}
</style>
