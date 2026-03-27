import { createRouter, createWebHistory } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    icon?: string
    subtitle?: string
    group?: string
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/overview/DashboardView.vue'),
      meta: {
        title: '仪表盘',
        icon: 'mdi-view-dashboard',
        subtitle: 'Texas 机器人管理面板概览',
      },
    },
    {
      path: '/personnel',
      redirect: '/personnel/users',
    },
    {
      path: '/personnel/users',
      name: 'personnel-users',
      component: () => import('@/views/personnel/PersonnelUsersView.vue'),
      meta: {
        title: '用户管理',
        icon: 'mdi-account-group',
        subtitle: '管理和查看机器人用户信息',
        group: '用户与群组',
      },
    },
    {
      path: '/personnel/groups',
      name: 'personnel-groups',
      component: () => import('@/views/personnel/PersonnelGroupsView.vue'),
      meta: {
        title: '群聊管理',
        icon: 'mdi-forum',
        subtitle: '管理和查看机器人加入的群聊',
        group: '用户与群组',
      },
    },
    {
      path: '/personnel/admins',
      name: 'personnel-admins',
      component: () => import('@/views/personnel/PersonnelAdminsView.vue'),
      meta: {
        title: '超级管理员',
        icon: 'mdi-shield-crown',
        subtitle: '管理机器人超级管理员权限',
        group: '用户与群组',
      },
    },
    {
      path: '/llm',
      redirect: '/llm/providers',
    },
    {
      path: '/llm/providers',
      name: 'llm-providers',
      component: () => import('@/views/llm/LLMProvidersView.vue'),
      meta: {
        title: '提供商',
        icon: 'mdi-server-network',
        subtitle: '管理 LLM 服务提供商配置',
        group: '大模型',
      },
    },
    {
      path: '/llm/models',
      name: 'llm-models',
      component: () => import('@/views/llm/LLMModelsView.vue'),
      meta: {
        title: '模型管理',
        icon: 'mdi-brain',
        subtitle: '管理和配置 LLM 模型',
        group: '大模型',
      },
    },
    {
      path: '/chat',
      redirect: '/chat/messages',
    },
    {
      path: '/chat/messages',
      name: 'chat-messages',
      component: () => import('@/views/chat/ChatMessagesView.vue'),
      meta: {
        title: '消息记录',
        icon: 'mdi-message-text-outline',
        subtitle: '查看群聊和私聊消息记录',
        group: '聊天记录',
      },
    },
    {
      path: '/chat/archive',
      name: 'chat-archive',
      component: () => import('@/views/chat/ChatArchiveView.vue'),
      meta: {
        title: '归档管理',
        icon: 'mdi-archive-outline',
        subtitle: '查看和管理聊天记录归档',
        group: '聊天记录',
      },
    },
    {
      path: '/queue',
      name: 'queue',
      component: () => import('@/views/system/QueueView.vue'),
      meta: {
        title: '任务队列',
        icon: 'mdi-tray-full',
        subtitle: '查看定时任务调度与消息队列状态',
        group: '系统',
      },
    },
    {
      path: '/logs',
      name: 'logs',
      component: () => import('@/views/system/LogsView.vue'),
      meta: {
        title: '应用日志',
        icon: 'mdi-text-box-outline',
        subtitle: '实时日志流',
        group: '系统',
      },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/system/SettingsView.vue'),
      meta: {
        title: '设置',
        icon: 'mdi-cog',
        subtitle: 'Texas 机器人管理面板设置',
        group: '系统',
      },
    },
    {
      path: '/permissions',
      redirect: '/permissions/groups',
    },
    {
      path: '/permissions/groups',
      name: 'permissions-groups',
      component: () => import('@/views/permission/PermissionGroupsView.vue'),
      meta: {
        title: '群聊权限',
        icon: 'mdi-shield-check',
        subtitle: '管理各群对功能的启用/禁用状态',
        group: '权限管理',
      },
    },
    {
      path: '/permissions/private',
      name: 'permissions-private',
      component: () => import('@/views/permission/PermissionPrivateView.vue'),
      meta: {
        title: '私聊权限',
        icon: 'mdi-account-lock',
        subtitle: '管理私聊功能的黑名单/白名单用户',
        group: '权限管理',
      },
    },
  ],
})

router.afterEach((to) => {
  const pageTitle = to.meta?.title as string | undefined
  document.title = pageTitle ? `${pageTitle} | Texas` : 'Texas'
})

export default router
