import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/features/auth/auth'

const routes = [
  { path: '/login', component: () => import('@/features/auth/views/LoginView.vue'), meta: { guest: true } },
  {
    path: '/',
    component: () => import('@/core/views/LayoutView.vue'),
    meta: { auth: true },
    redirect: () => {
      const role = parseInt(localStorage.getItem('role') || '0')
      return role === 1 ? '/admin/users' : '/map'
    },
    children: [
      { path: 'map',       component: () => import('@/features/map/views/MapView.vue'),       meta: { auth: true } },
      { path: 'source',    component: () => import('@/features/source/views/SourceView.vue'),    meta: { auth: true } },
      { path: 'revive',    component: () => import('@/features/revive/views/ReviveView.vue'),    meta: { auth: true } },
      { path: 'chat',      component: () => import('@/features/chat/views/ChatView.vue'),      meta: { auth: true } },
      { path: 'graph',     component: () => import('@/features/graph/views/GraphView.vue'),     meta: { auth: true } },
      { path: 'quiz',      component: () => import('@/features/quiz/views/QuizView.vue'),      meta: { auth: true } },
      { path: 'report',    component: () => import('@/features/report/views/ReportView.vue'),    meta: { auth: true } },
      { path: 'community', component: () => import('@/features/community/views/CommunityView.vue'), meta: { auth: true } },
      { path: 'feedback',  component: () => import('@/features/feedback/views/FeedbackView.vue'),  meta: { auth: true } },
      { path: 'admin/checkins',  component: () => import('@/features/admin/views/AdminCheckins.vue'),  meta: { auth: true, admin: true } },
      { path: 'admin/feedbacks', component: () => import('@/features/admin/views/AdminFeedbacks.vue'), meta: { auth: true, admin: true } },
      { path: 'admin/users',     component: () => import('@/features/admin/views/AdminUsers.vue'),     meta: { auth: true, admin: true } },
      { path: 'admin/heatmap',   component: () => import('@/features/admin/views/AdminHeatmap.vue'),   meta: { auth: true, admin: true } },
      { path: 'admin', redirect: '/admin/users', meta: { auth: true, admin: true } },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.auth  && !auth.isLoggedIn) return '/login'
  if (to.meta.guest && auth.isLoggedIn)  return auth.isAdmin ? '/admin/users' : '/'
  if (to.meta.admin && !auth.isAdmin)    return '/map'
})

export default router
