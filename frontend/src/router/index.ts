import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
    },
    {
      path: '/personnel',
      name: 'personnel',
      component: () => import('@/views/personnel/PersonnelIndex.vue'),
    },
    {
      path: '/queue',
      name: 'queue',
      component: () => import('@/views/queue/QueueIndex.vue'),
    },
    {
      path: '/logs',
      name: 'logs',
      component: () => import('@/views/LogsView.vue'),
    },
  ],
})

export default router
