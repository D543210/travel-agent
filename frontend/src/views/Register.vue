<template>
  <div class="auth-page">
    <a-card title="创建账号" class="auth-card" :bordered="false">
      <a-form :model="form" layout="vertical" @finish="handleRegister">
        <a-form-item label="显示名称" name="display_name" :rules="[{ required: true, message: '请输入显示名称' }]">
          <a-input v-model:value="form.display_name" size="large" autocomplete="name" />
        </a-form-item>
        <a-form-item label="邮箱" name="email" :rules="[{ required: true, type: 'email', message: '请输入有效邮箱' }]">
          <a-input v-model:value="form.email" size="large" autocomplete="email" />
        </a-form-item>
        <a-form-item label="密码" name="password" :rules="[{ required: true, min: 8, message: '密码至少8个字符' }]">
          <a-input-password v-model:value="form.password" size="large" autocomplete="new-password" />
        </a-form-item>
        <a-form-item label="确认密码" name="confirmPassword" :rules="[{ required: true, validator: validateConfirmation }]">
          <a-input-password v-model:value="form.confirmPassword" size="large" autocomplete="new-password" />
        </a-form-item>
        <a-button type="primary" html-type="submit" size="large" block :loading="submitting">
          注册
        </a-button>
      </a-form>
      <div class="auth-link">
        已有账号？<router-link to="/login">返回登录</router-link>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { register } from '@/stores/auth'

const router = useRouter()
const submitting = ref(false)
const form = reactive({ email: '', password: '', confirmPassword: '', display_name: '' })

const validateConfirmation = async (_rule: unknown, value: string) => {
  if (!value) throw new Error('请再次输入密码')
  if (value !== form.password) throw new Error('两次输入的密码不一致')
}

const handleRegister = async () => {
  submitting.value = true
  try {
    await register({
      email: form.email,
      password: form.password,
      display_name: form.display_name
    })
    message.success('注册成功，请登录')
    await router.replace('/login')
  } catch (error: any) {
    message.error(error.response?.data?.detail?.message || '注册失败')
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
