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
  ],
})

export default router
