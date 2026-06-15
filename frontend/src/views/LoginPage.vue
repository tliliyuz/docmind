<template>
  <div class="login-page">
    <div class="login-card">
      <!-- Logo -->
      <div class="welcome-logo">
        <i class="fas fa-brain"></i>
      </div>
      <h1 class="app-title">DocMind</h1>
      <p class="app-subtitle">企业知识库智能问答平台</p>

      <!-- 切换 Tab -->
      <div class="tab-switch">
        <button
          :class="['tab-btn', { active: mode === 'login' }]"
          @click="switchMode('login')"
        >
          登录
        </button>
        <button
          :class="['tab-btn', { active: mode === 'register' }]"
          @click="switchMode('register')"
        >
          注册
        </button>
      </div>

      <!-- 表单 -->
      <form class="login-form" @submit.prevent="handleSubmit">
        <div class="input-group">
          <i class="fas fa-user prefix-icon"></i>
          <input
            v-model="username"
            class="form-input input-with-icon"
            :placeholder="mode === 'login' ? '请输入用户名' : '请设置用户名（至少 2 个字符）'"
            autocomplete="username"
          />
        </div>

        <div class="input-group">
          <i class="fas fa-lock prefix-icon"></i>
          <input
            v-model="password"
            class="form-input input-with-icon"
            type="password"
            :placeholder="mode === 'login' ? '请输入密码' : '请设置密码（至少 6 个字符）'"
            autocomplete="current-password"
          />
        </div>

        <!-- 错误提示 -->
        <div v-if="errorMsg" class="error-msg">
          <i class="fas fa-exclamation-circle"></i>
          {{ errorMsg }}
        </div>

        <!-- 提交按钮 -->
        <button type="submit" class="submit-btn" :disabled="loading">
          <i v-if="loading" class="fas fa-spinner fa-spin"></i>
          {{ mode === 'login' ? '登 录' : '注 册' }}
        </button>
      </form>

      <!-- 底部提示 -->
      <p class="toggle-tip">
        {{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
        <a href="#" @click.prevent="switchMode(mode === 'login' ? 'register' : 'login')">
          {{ mode === 'login' ? '立即注册' : '去登录' }}
        </a>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const mode = ref('login')
const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')

function switchMode(m) {
  mode.value = m
  username.value = ''
  password.value = ''
  errorMsg.value = ''
}

async function handleSubmit() {
  errorMsg.value = ''

  // 前端基础校验
  const name = username.value.trim()
  if (!name) {
    errorMsg.value = '请输入用户名'
    return
  }
  if (name.length < 2) {
    errorMsg.value = '用户名至少 2 个字符'
    return
  }
  if (/^\d+$/.test(name)) {
    errorMsg.value = '用户名不能为纯数字，请包含文字或字母'
    return
  }
  if (password.value.length < 6) {
    errorMsg.value = '密码至少 6 个字符'
    return
  }

  loading.value = true
  try {
    if (mode.value === 'login') {
      await authStore.login(username.value.trim(), password.value)
      ElMessage.success('登录成功')
      router.push('/chat')
    } else {
      await authStore.register(username.value.trim(), password.value)
      // 注册成功后切换到登录模式，清空密码
      mode.value = 'login'
      password.value = ''
      errorMsg.value = ''
      ElMessage.success('注册成功，请登录')
    }
  } catch (err) {
    const data = err.response?.data
    errorMsg.value = data?.message || '网络异常，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  width: 100%;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--dm-bg-page);
}

.login-card {
  width: 420px;
  padding: var(--dm-space-10) var(--dm-space-8);
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-xl);
  box-shadow: var(--dm-shadow-lg);
  text-align: center;
}

/* Logo */
.welcome-logo {
  width: var(--dm-welcome-logo-size);
  height: var(--dm-welcome-logo-size);
  background: var(--dm-primary);
  border-radius: var(--dm-radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: var(--dm-text-2xl);
  margin: 0 auto;
}

.app-title {
  font-size: var(--dm-text-xl);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
  margin-top: var(--dm-space-4);
}

.app-subtitle {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-tertiary);
  margin-top: var(--dm-space-1);
  margin-bottom: var(--dm-space-6);
}

/* 切换 Tab */
.tab-switch {
  display: flex;
  background: var(--dm-border-light);
  border-radius: var(--dm-radius-sm);
  padding: 4px;
  margin-bottom: var(--dm-space-5);
}

.tab-btn {
  flex: 1;
  height: 34px;
  border: none;
  background: transparent;
  font-size: var(--dm-text-body);
  color: var(--dm-text-secondary);
  cursor: pointer;
  border-radius: 6px;
  transition: all var(--dm-transition-fast);
}

.tab-btn.active {
  background: var(--dm-bg-card);
  color: var(--dm-text-primary);
  font-weight: var(--dm-weight-semibold);
  box-shadow: var(--dm-shadow-sm);
}

/* 表单 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--dm-space-4);
}

/* 提交按钮 */
.submit-btn {
  width: 100%;
  height: 46px;
  background: var(--dm-text-primary);
  color: white;
  border: none;
  border-radius: var(--dm-radius-sm);
  font-size: var(--dm-text-sm);
  font-weight: var(--dm-weight-semibold);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--dm-space-2);
  transition: all var(--dm-transition-normal);
  margin-top: var(--dm-space-2);
}

.submit-btn:hover:not(:disabled) {
  background: var(--dm-primary-hover);
  box-shadow: var(--dm-shadow-md);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 错误提示 */
.error-msg {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  background: var(--dm-danger-light);
  color: var(--dm-danger);
  font-size: var(--dm-text-xs);
  border-radius: var(--dm-radius-sm);
  text-align: left;
}

/* 底部切换提示 */
.toggle-tip {
  margin-top: var(--dm-space-5);
  font-size: var(--dm-text-xs);
  color: var(--dm-text-tertiary);
}

.toggle-tip a {
  color: var(--dm-text-primary);
  text-decoration: none;
  font-weight: var(--dm-weight-semibold);
}

.toggle-tip a:hover {
  text-decoration: underline;
}
</style>
