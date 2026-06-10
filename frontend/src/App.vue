<template>
  <!-- 公开页面（登录页）：不加布局 -->
  <router-view v-if="$route.meta.public" />
  <!-- Admin 页面：使用 AdminLayout（已在路由中作为父组件引入） -->
  <router-view v-else-if="isAdminRoute" />
  <!-- 其他需认证页面：使用 AppLayout（含用户侧边栏） -->
  <AppLayout v-else>
    <router-view />
  </AppLayout>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'

const route = useRoute()

const isAdminRoute = computed(() => route.path.startsWith('/admin'))
</script>
