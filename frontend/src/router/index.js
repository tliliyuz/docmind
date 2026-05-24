import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginPage.vue'),
    meta: { public: true }
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/ChatPage.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/admin/documents',
    name: 'AdminDocuments',
    component: () => import('@/views/admin/DocumentList.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/admin/conversations',
    name: 'AdminConversations',
    component: () => import('@/views/admin/ConversationList.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/knowledge-bases',
    name: 'KnowledgeList',
    component: () => import('@/views/KnowledgeList.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/knowledge-bases/public',
    name: 'PublicKnowledgeList',
    component: () => import('@/views/PublicKnowledgeList.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/knowledge-bases/:id',
    name: 'KnowledgeDetail',
    component: () => import('@/views/KnowledgeDetail.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/admin/knowledge',
    name: 'AdminKnowledge',
    component: () => import('@/views/admin/KnowledgeList.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/admin/stats',
    name: 'AdminStats',
    component: () => import('@/views/admin/StatsPage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/',
    redirect: '/chat'
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/chat'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫 — 认证与权限检查
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  // 已登录用户访问公开页面（如登录页）→ 重定向到聊天页
  if (to.meta.public && authStore.isLoggedIn) {
    next('/chat')
    return
  }

  // 需要认证的页面 → 未登录则跳转登录页
  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    next('/login')
    return
  }

  // 需要管理员权限 → 非 admin 用户重定向
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next('/chat')
    return
  }

  next()
})

export default router
