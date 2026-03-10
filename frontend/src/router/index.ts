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
      component: () => import('@/views/PersonnelUsersView.vue'),
    },
    {
      path: '/personnel/groups',
      name: 'personnel-groups',
      component: () => import('@/views/PersonnelGroupsView.vue'),
    },
    {
      path: '/personnel/admins',
      name: 'personnel-admins',
      component: () => import('@/views/PersonnelAdminsView.vue'),
    },
    {
      path: '/personnel/sync',
      name: 'personnel-sync',
      component: () => import('@/views/PersonnelSyncView.vue'),
    },
    {
      path: '/llm',
      redirect: '/llm/providers',
    },
    {
      path: '/llm/providers',
      name: 'llm-providers',
      component: () => import('@/views/LLMProvidersView.vue'),
    },
    {
      path: '/llm/models',
      name: 'llm-models',
      component: () => import('@/views/LLMModelsView.vue'),
    },
    {
      path: '/chat',
      redirect: '/chat/overview',
    },
    {
      path: '/chat/overview',
      name: 'chat-overview',
      component: () => import('@/views/ChatOverviewView.vue'),
    },
    {
      path: '/chat/messages',
      name: 'chat-messages',
      component: () => import('@/views/ChatMessagesView.vue'),
    },
    {
      path: '/chat/archive',
      name: 'chat-archive',
      component: () => import('@/views/ChatArchiveView.vue'),
    },
    {
      path: '/queue',
      name: 'queue',
      component: () => import('@/views/QueueView.vue'),
    },
    {
      path: '/logs',
      name: 'logs',
      component: () => import('@/views/LogsView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
    },
  ],
})

export default router
