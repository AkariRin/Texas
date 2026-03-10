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
      redirect: '/personnel/users',
    },
    {
      path: '/personnel/users',
      name: 'personnel-users',
      component: () => import('@/views/personnel/PersonnelUsers.vue'),
    },
    {
      path: '/personnel/groups',
      name: 'personnel-groups',
      component: () => import('@/views/personnel/PersonnelGroups.vue'),
    },
    {
      path: '/personnel/admins',
      name: 'personnel-admins',
      component: () => import('@/views/personnel/PersonnelAdmins.vue'),
    },
    {
      path: '/personnel/sync',
      name: 'personnel-sync',
      component: () => import('@/views/personnel/PersonnelSync.vue'),
    },
    {
      path: '/llm',
      redirect: '/llm/providers',
    },
    {
      path: '/llm/providers',
      name: 'llm-providers',
      component: () => import('@/views/llm/LLMProviders.vue'),
    },
    {
      path: '/llm/models',
      name: 'llm-models',
      component: () => import('@/views/llm/LLMModels.vue'),
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
