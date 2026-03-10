import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/overview/DashboardView.vue'),
      meta: { title: '仪表盘' },
    },
    {
      path: '/personnel',
      redirect: '/personnel/users',
    },
    {
      path: '/personnel/users',
      name: 'personnel-users',
      component: () => import('@/views/personnel/PersonnelUsersView.vue'),
      meta: { title: '用户管理' },
    },
    {
      path: '/personnel/groups',
      name: 'personnel-groups',
      component: () => import('@/views/personnel/PersonnelGroupsView.vue'),
      meta: { title: '群聊管理' },
    },
    {
      path: '/personnel/admins',
      name: 'personnel-admins',
      component: () => import('@/views/personnel/PersonnelAdminsView.vue'),
      meta: { title: '管理员' },
    },
    {
      path: '/llm',
      redirect: '/llm/providers',
    },
    {
      path: '/llm/providers',
      name: 'llm-providers',
      component: () => import('@/views/llm/LLMProvidersView.vue'),
      meta: { title: '提供商' },
    },
    {
      path: '/llm/models',
      name: 'llm-models',
      component: () => import('@/views/llm/LLMModelsView.vue'),
      meta: { title: '模型管理' },
    },
    {
      path: '/chat',
      name: 'chat-overview',
      component: () => import('@/views/chat/ChatOverviewView.vue'),
      meta: { title: '消息概览' },
    },
    {
      path: '/chat/messages',
      name: 'chat-messages',
      component: () => import('@/views/chat/ChatMessagesView.vue'),
      meta: { title: '消息浏览' },
    },
    {
      path: '/chat/archive',
      name: 'chat-archive',
      component: () => import('@/views/chat/ChatArchiveView.vue'),
      meta: { title: '归档管理' },
    },
    {
      path: '/queue',
      name: 'queue',
      component: () => import('@/views/system/QueueView.vue'),
      meta: { title: '任务队列' },
    },
    {
      path: '/logs',
      name: 'logs',
      component: () => import('@/views/system/LogsView.vue'),
      meta: { title: '应用日志' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/system/SettingsView.vue'),
      meta: { title: '设置' },
    },
  ],
})

router.afterEach((to) => {
  const pageTitle = to.meta?.title as string | undefined
  document.title = pageTitle ? `${pageTitle} | Texas` : 'Texas'
})

export default router
