<template>
  <div class="auth-page">
    <a-card title="登录旅行助手" class="auth-card" :bordered="false">
      <a-form :model="form" layout="vertical" @finish="handleLogin">
        <a-form-item
          label="邮箱"
          name="email"
          :rules="[
            { required: true, message: '请输入邮箱' },
            { type: 'email', message: '邮箱格式不正确' }
          ]"
        >
          <a-input v-model:value="form.email" size="large" autocomplete="email" />
        </a-form-item>

        <a-form-item
          label="密码"
          name="password"
          :rules="[{ required: true, min: 8, message: '密码至少8个字符' }]"
        >
          <a-input-password
            v-model:value="form.password"
            size="large"
            autocomplete="current-password"
          />
        </a-form-item>

        <a-button type="primary" html-type="submit" size="large" block :loading="submitting">
          登录
        </a-button>
      </a-form>

      <div class="auth-link">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { login } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const submitting = ref(false)
const form = reactive({ email: '', password: '' })

const handleLogin = async () => {
  submitting.value = true
  try {
    await login(form)
    message.success('登录成功')
    const requestedRedirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    const redirect = requestedRedirect.startsWith('/') && !requestedRedirect.startsWith('//')
      ? requestedRedirect
      : '/'
    await router.replace(redirect)
  } catch (error: any) {
    message.error(error.response?.data?.detail?.message || '邮箱或密码错误')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: calc(100vh - 160px);
  display: grid;
  place-items: center;
  padding: 32px 16px;
}
.auth-card {
  width: min(420px, 100%);
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12);
}
.auth-link {
  margin-top: 20px;
  text-align: center;
}
</style>
